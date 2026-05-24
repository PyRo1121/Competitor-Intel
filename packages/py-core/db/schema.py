"""
Competitor Intelligence SQLite Schema
Local-first database for competitive monitoring.
"""

import logging
import os
import sqlite3
from pathlib import Path

from db.connection import active_db_path
from db.migrations import apply_runtime_migrations

logger = logging.getLogger(__name__)

SCHEMA = """
-- Core companies table
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    website TEXT,
    x_handle TEXT,
    github_org TEXT,
    industry TEXT DEFAULT 'AI/Productivity',
    status TEXT DEFAULT 'active',  -- active, acquired, dead, pivoted
    first_tracked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- Funding events (Crunchbase + SEC + announcements)
CREATE TABLE IF NOT EXISTS funding_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    round_type TEXT,           -- Seed, Series A, Series B, etc.
    amount_usd INTEGER,
    valuation_usd INTEGER,
    announced_date DATE,
    investors TEXT,            -- JSON array as text for simplicity
    source TEXT,               -- x, rss, website, crunchbase_free, sec
    source_url TEXT,
    confidence REAL DEFAULT 0.8,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- Product / feature updates
CREATE TABLE IF NOT EXISTS product_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    update_type TEXT,          -- feature, pricing, launch, acquisition, etc.
    announced_date DATE,
    source TEXT,
    source_url TEXT,
    semantic_hash TEXT,        -- for deduping
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- X/Twitter activity (via Grok native access)
CREATE TABLE IF NOT EXISTS x_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    post_id TEXT UNIQUE,
    text TEXT NOT NULL,
    posted_at TIMESTAMP,
    likes INTEGER DEFAULT 0,
    retweets INTEGER DEFAULT 0,
    replies INTEGER DEFAULT 0,
    url TEXT,
    is_founder_post BOOLEAN DEFAULT 0,
    sentiment REAL,            -- -1 to 1
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- GitHub activity
CREATE TABLE IF NOT EXISTS github_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    repo TEXT,
    event_type TEXT,           -- commit, release, star_milestone, pr
    event_date TIMESTAMP,
    details TEXT,              -- JSON
    stars_delta INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- RSS / Blog items
CREATE TABLE IF NOT EXISTS rss_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER,
    feed_url TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    published_at TIMESTAMP,
    url TEXT UNIQUE,
    source_name TEXT,
    semantic_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL
);

-- Flexible raw signals (any source, any format)
CREATE TABLE IF NOT EXISTS raw_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER,
    source TEXT NOT NULL,      -- x, rss, github, website, sec, crunchbase_free
    signal_type TEXT NOT NULL,
    data_json TEXT NOT NULL,   -- full payload
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT 0,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL
);

-- Daily/periodic reports
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date DATE DEFAULT (date('now')),
    summary TEXT,
    companies_changed INTEGER DEFAULT 0,
    high_signal_count INTEGER DEFAULT 0,
    discord_message_id TEXT,
    obsidian_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Extended company profiles (deep enrichment)
CREATE TABLE IF NOT EXISTS company_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL UNIQUE,
    founded_year INTEGER,
    headquarters TEXT,
    team_size INTEGER,
    team_size_source TEXT,
    business_model TEXT,        -- SaaS, API, Open Source, etc.
    tech_stack TEXT,            -- JSON array of technologies
    description_long TEXT,      -- Full company description
    traction TEXT,              -- Key metrics (users, revenue tier)
    moat TEXT,                  -- Competitive moat analysis
    last_enriched_at TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- Canonical funding rounds (aggregated from funding_round_claims)
CREATE TABLE IF NOT EXISTS funding_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    round_type TEXT NOT NULL,   -- Seed, Series A, Series B, etc.
    amount_usd INTEGER,
    valuation_usd INTEGER,
    announced_date DATE,
    lead_investor TEXT,
    co_investors TEXT,          -- JSON array
    source TEXT,
    source_url TEXT,
    confidence REAL DEFAULT 0.8,
    cluster_key TEXT,
    report_count INTEGER DEFAULT 1,
    official_report_count INTEGER DEFAULT 0,
    corroboration_score REAL DEFAULT 0.5,
    source_tier_best TEXT,
    fields_provenance TEXT,     -- JSON per-field sources and tiers
    currency TEXT DEFAULT 'USD',
    pre_money_valuation_usd INTEGER,
    post_money_valuation_usd INTEGER,
    instrument_type TEXT,       -- equity, safe, convertible_note, debt
    total_investor_count INTEGER DEFAULT 0,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- Per-source funding observations (source of truth before aggregation)
CREATE TABLE IF NOT EXISTS funding_round_claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    funding_round_id INTEGER,
    intelligence_event_id INTEGER,
    raw_signal_id INTEGER,
    round_type TEXT NOT NULL,
    amount_usd INTEGER,
    valuation_usd INTEGER,
    lead_investor TEXT,
    co_investors TEXT,
    announced_date TEXT,
    source TEXT NOT NULL,
    source_url TEXT UNIQUE,
    source_tier TEXT NOT NULL,
    source_weight REAL NOT NULL,
    is_official INTEGER DEFAULT 0,
    is_rumor INTEGER DEFAULT 0,
    extraction_confidence REAL,
    headline TEXT,
    snippet TEXT,
    currency TEXT DEFAULT 'USD',
    pre_money_valuation_usd INTEGER,
    post_money_valuation_usd INTEGER,
    instrument_type TEXT,
    deal_terms_text TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (funding_round_id) REFERENCES funding_rounds(id) ON DELETE SET NULL
);

-- Global investor firms (VCs, strategics) — not tied to a single portfolio company
CREATE TABLE IF NOT EXISTS investor_firms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    name_normalized TEXT UNIQUE,
    investor_type TEXT DEFAULT 'VC',
    tier INTEGER DEFAULT 3,
    website TEXT,
    twitter TEXT,
    linkedin TEXT,
    location TEXT,
    description TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Per-outlet investor mentions on a single claim
CREATE TABLE IF NOT EXISTS funding_claim_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    funding_round_claim_id INTEGER NOT NULL,
    investor_id INTEGER,
    investor_name_raw TEXT NOT NULL,
    role TEXT NOT NULL,
    is_lead INTEGER DEFAULT 0,
    amount_usd INTEGER,
    excerpt TEXT,
    FOREIGN KEY (funding_round_claim_id) REFERENCES funding_round_claims(id) ON DELETE CASCADE,
    FOREIGN KEY (investor_id) REFERENCES investor_firms(id) ON DELETE SET NULL
);

-- Aggregated investors on a canonical funding round
CREATE TABLE IF NOT EXISTS round_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    funding_round_id INTEGER NOT NULL,
    investor_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    is_lead INTEGER DEFAULT 0,
    amount_invested_usd INTEGER,
    report_count INTEGER DEFAULT 1,
    source_domain_count INTEGER DEFAULT 1,
    corroboration_score REAL DEFAULT 0.5,
    has_official_source INTEGER DEFAULT 0,
    updated_at TEXT,
    FOREIGN KEY (funding_round_id) REFERENCES funding_rounds(id) ON DELETE CASCADE,
    FOREIGN KEY (investor_id) REFERENCES investor_firms(id) ON DELETE CASCADE,
    UNIQUE(funding_round_id, investor_id)
);

-- Which claim(s) reported each round participant
CREATE TABLE IF NOT EXISTS participant_source_attributions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_participant_id INTEGER NOT NULL,
    funding_round_claim_id INTEGER NOT NULL,
    investor_id INTEGER,
    role TEXT,
    amount_usd INTEGER,
    excerpt TEXT,
    source_url TEXT,
    source_tier TEXT,
    is_official INTEGER DEFAULT 0,
    FOREIGN KEY (round_participant_id) REFERENCES round_participants(id) ON DELETE CASCADE,
    FOREIGN KEY (funding_round_claim_id) REFERENCES funding_round_claims(id) ON DELETE CASCADE,
    UNIQUE(round_participant_id, funding_round_claim_id)
);

-- Team members (key hires, departures)
CREATE TABLE IF NOT EXISTS team_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    role TEXT,
    is_founder BOOLEAN DEFAULT 0,
    joined_date DATE,
    left_date DATE,
    source TEXT,
    linkedin_url TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- Products and features
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,              -- API, SaaS, Mobile, etc.
    pricing_json TEXT,          -- Pricing tiers as JSON
    launch_date DATE,
    status TEXT DEFAULT 'active', -- active, deprecated, beta
    source TEXT,
    url TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- Deep GitHub metrics
CREATE TABLE IF NOT EXISTS github_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    repo_name TEXT,
    total_commits INTEGER,
    commits_last_30d INTEGER,
    contributor_count INTEGER,
    active_contributors_30d INTEGER,
    primary_language TEXT,
    languages_json TEXT,        -- Language breakdown as JSON
    release_count INTEGER,
    last_release_date DATE,
    issue_resolution_days REAL, -- Avg time to close issues
    star_growth_30d INTEGER,
    fork_growth_30d INTEGER,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- X/Twitter activity analytics
CREATE TABLE IF NOT EXISTS x_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    period_start DATE,
    period_end DATE,
    post_count INTEGER,
    avg_likes INTEGER,
    avg_retweets INTEGER,
    avg_replies INTEGER,
    sentiment_positive REAL,    -- 0.0-1.0
    sentiment_neutral REAL,
    sentiment_negative REAL,
    top_topics TEXT,            -- JSON array of trending topics
    engagement_velocity REAL,   -- Avg engagement per day
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- Competitive positioning
CREATE TABLE IF NOT EXISTS competitive_positioning (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    dimension TEXT NOT NULL,    -- pricing, features, market_share, etc.
    score REAL,                 -- 0.0-1.0 normalized score
    comparison_json TEXT,       -- JSON with competitor comparisons
    analysis TEXT,              -- Textual analysis
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- Job postings (hiring velocity = growth signal)
CREATE TABLE IF NOT EXISTS job_postings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    department TEXT,
    location TEXT,
    salary_range TEXT,
    job_type TEXT,              -- full-time, contract, internship
    source TEXT,                -- linkedin, indeed, company_site, lever, greenhouse
    source_url TEXT,
    posted_at DATE,
    removed_at DATE,
    is_active BOOLEAN DEFAULT 1,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- Competitor relationships (who competes with whom)
CREATE TABLE IF NOT EXISTS competitor_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    competitor_id INTEGER NOT NULL,
    relationship_type TEXT DEFAULT 'direct',  -- direct, adjacent, potential
    overlap_areas TEXT,         -- JSON array of competing product areas
    market_share_estimate TEXT,
    source TEXT,
    confidence REAL DEFAULT 0.7,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (competitor_id) REFERENCES companies(id) ON DELETE CASCADE,
    UNIQUE(company_id, competitor_id)
);

-- Technology stack detections
CREATE TABLE IF NOT EXISTS technology_stack (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    category TEXT NOT NULL,     -- frontend, backend, database, infra, ml, security
    technology TEXT NOT NULL,
    detection_source TEXT,      -- github, job_posting, website, wappalyzer
    confidence REAL DEFAULT 0.8,
    first_detected TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_confirmed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- Website snapshots (track homepage changes)
CREATE TABLE IF NOT EXISTS website_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    meta_description TEXT,
    hash TEXT NOT NULL,
    screenshot_path TEXT,
    changed_elements TEXT,      -- JSON of what changed since last snapshot
    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- Customer signals (wins, case studies, testimonials)
CREATE TABLE IF NOT EXISTS customer_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    signal_type TEXT NOT NULL,  -- case_study, testimonial, logo_won, churn
    customer_name TEXT,
    customer_size TEXT,         -- enterprise, mid-market, smb
    description TEXT,
    source TEXT,
    source_url TEXT,
    signal_date DATE,
    confidence REAL DEFAULT 0.8,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- Patents and trademarks (IP intelligence)
CREATE TABLE IF NOT EXISTS ip_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    asset_type TEXT NOT NULL,   -- patent, trademark, copyright
    title TEXT,
    description TEXT,
    filing_number TEXT,
    filing_date DATE,
    status TEXT,                -- pending, granted, rejected
    jurisdiction TEXT,
    source TEXT,
    source_url TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- Alerts tracking
CREATE TABLE IF NOT EXISTS alerts_sent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    channel TEXT NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES intelligence_events(id) ON DELETE CASCADE
);

-- Indexes for performance (critical for SQLite scale)
CREATE INDEX IF NOT EXISTS idx_companies_slug ON companies(slug);
CREATE INDEX IF NOT EXISTS idx_funding_company_date ON funding_events(company_id, announced_date);
CREATE INDEX IF NOT EXISTS idx_product_company_date ON product_updates(company_id, announced_date);
CREATE INDEX IF NOT EXISTS idx_x_company_date ON x_posts(company_id, posted_at);
CREATE INDEX IF NOT EXISTS idx_github_company_date ON github_activity(company_id, event_date);
CREATE INDEX IF NOT EXISTS idx_rss_url ON rss_items(url);
CREATE INDEX IF NOT EXISTS idx_raw_source_type ON raw_signals(source, signal_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_signals_dedup ON raw_signals(source, signal_type);
CREATE INDEX IF NOT EXISTS idx_raw_processed ON raw_signals(processed);
CREATE INDEX IF NOT EXISTS idx_funding_rounds_company ON funding_rounds(company_id, announced_date);
CREATE INDEX IF NOT EXISTS idx_team_company ON team_members(company_id, joined_date);
CREATE INDEX IF NOT EXISTS idx_products_company ON products(company_id, status);
CREATE INDEX IF NOT EXISTS idx_github_company ON github_metrics(company_id, extracted_at);
CREATE INDEX IF NOT EXISTS idx_x_activity_company ON x_activity(company_id, period_end);
CREATE INDEX IF NOT EXISTS idx_company_details ON company_details(company_id);
CREATE INDEX IF NOT EXISTS idx_competitive ON competitive_positioning(company_id, dimension);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON job_postings(company_id, posted_at);
CREATE INDEX IF NOT EXISTS idx_jobs_active ON job_postings(company_id, is_active);
CREATE INDEX IF NOT EXISTS idx_competitor_rel
    ON competitor_relationships(company_id, competitor_id);
CREATE INDEX IF NOT EXISTS idx_tech_stack ON technology_stack(company_id, category);
CREATE INDEX IF NOT EXISTS idx_website_snap ON website_snapshots(company_id, captured_at);
CREATE INDEX IF NOT EXISTS idx_customer_signals ON customer_signals(company_id, signal_date);
CREATE INDEX IF NOT EXISTS idx_ip_assets ON ip_assets(company_id, asset_type);
CREATE INDEX IF NOT EXISTS idx_alerts_event ON alerts_sent(event_id);
CREATE INDEX IF NOT EXISTS idx_alerts_sent ON alerts_sent(sent_at);

-- Views for common queries
CREATE VIEW IF NOT EXISTS v_recent_signals AS
SELECT
    c.name,
    rs.source,
    rs.signal_type,
    rs.detected_at,
    rs.data_json
FROM raw_signals rs
JOIN companies c ON rs.company_id = c.id
WHERE rs.detected_at >= datetime('now', '-7 days')
ORDER BY rs.detected_at DESC;
"""


def ensure_raw_signals_dedup_index(conn: sqlite3.Connection) -> None:
    """Ensure UNIQUE(source, signal_type) on raw_signals; fail loud in prod modes."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_raw_signals_dedup'"
    )
    if cursor.fetchone():
        return
    try:
        conn.execute(
            "CREATE UNIQUE INDEX idx_raw_signals_dedup ON raw_signals(source, signal_type)"
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        msg = (
            "Cannot create idx_raw_signals_dedup: duplicate (source, signal_type) rows. "
            "Run: make migrate-dedup"
        )
        strict = os.environ.get("CI_STRICT_PIPELINE", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        require = os.environ.get("CI_REQUIRE_DEDUP_INDEX", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        if strict or require:
            raise RuntimeError(msg) from exc
        logger.warning("Skipped idx_raw_signals_dedup: %s", exc)


def init_database():
    """Initialize the database with full schema and optimizations."""
    path = active_db_path()
    Path(path.parent).mkdir(parents=True, exist_ok=True)

    from db.connection import configure_connection

    conn = sqlite3.connect(str(path), timeout=60.0)
    configure_connection(conn, profile="maintenance")

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='website_snapshots'")
    if cursor.fetchone():
        cursor.execute("PRAGMA table_info(website_snapshots)")
        cols = [c[1] for c in cursor.fetchall()]
        if "captured_at" not in cols:
            cursor.execute("DROP TABLE website_snapshots")
            conn.commit()

    conn.executescript(SCHEMA)
    conn.commit()

    ensure_raw_signals_dedup_index(conn)

    apply_runtime_migrations(conn)

    # maintenance uses EXCLUSIVE locking_mode — reset before close so collectors/API can connect
    conn.execute("PRAGMA locking_mode = NORMAL")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.commit()

    # Seed initial companies if empty
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM companies")
    if cursor.fetchone()[0] == 0:
        seed_companies(conn)

    conn.close()
    logger.info("Database initialized at %s", path)
    return path


def seed_companies(conn):
    """Seed with the 16 core AI competitors."""
    companies = [
        ("Cursor", "cursor", "https://cursor.com", "cursor_ai", "cursor"),
        ("Perplexity", "perplexity", "https://perplexity.ai", "perplexity_ai", None),
        ("Cognition (Devin)", "cognition-devin", "https://cognition.ai", "cognition_labs", None),
        ("Harvey AI", "harvey-ai", "https://harvey.ai", "harvey_ai", None),
        ("ElevenLabs", "elevenlabs", "https://elevenlabs.io", "elevenlabsio", None),
        ("Runway", "runway", "https://runwayml.com", "runwayml", None),
        ("Linear", "linear", "https://linear.app", "linear", "linear"),
        ("Notion", "notion", "https://notion.so", "notionhq", "notion"),
        ("Arc Browser", "arc", "https://arc.net", "thebrowsercompany", "thebrowsercompany"),
        ("Coda", "coda", "https://coda.io", "coda_hq", None),
        ("Height", "height", "https://height.app", "heightapp", None),
        ("Mem", "mem", "https://mem.ai", "memdotai", None),
        ("Limitless", "limitless", "https://limitless.ai", "getlimitless", None),
        ("Rewind", "rewind", "https://rewind.ai", "rewindai", None),
        ("Adept", "adept", "https://adept.ai", "adeptailabs", None),
        ("Anthropic", "anthropic", "https://anthropic.com", "anthropicai", None),
    ]

    for name, slug, website, x_handle, github_org in companies:
        conn.execute(
            """
            INSERT OR IGNORE INTO companies
            (name, slug, website, x_handle, github_org)
            VALUES (?, ?, ?, ?, ?)
        """,
            (name, slug, website, x_handle, github_org),
        )

    conn.commit()
    logger.info("Seeded %d initial companies", len(companies))


if __name__ == "__main__":
    init_database()
