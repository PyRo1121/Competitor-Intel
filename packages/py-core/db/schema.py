"""
Competitor Intelligence SQLite Schema
Local-first database for competitive monitoring.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import logging

from utils.monorepo_paths import db_path

logger = logging.getLogger(__name__)

DB_PATH = db_path()

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

-- Structured funding rounds (detailed history)
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
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
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
CREATE INDEX IF NOT EXISTS idx_competitor_rel ON competitor_relationships(company_id, competitor_id);
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

def init_database():
    """Initialize the database with full schema and optimizations."""
    Path(DB_PATH.parent).mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -64000")
    conn.execute("PRAGMA temp_store = MEMORY")

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='website_snapshots'")
    if cursor.fetchone():
        cursor.execute("PRAGMA table_info(website_snapshots)")
        cols = [c[1] for c in cursor.fetchall()]
        if 'captured_at' not in cols:
            cursor.execute("DROP TABLE website_snapshots")
            conn.commit()

    conn.executescript(SCHEMA)
    conn.commit()

    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_raw_signals_dedup'"
    )
    if not cursor.fetchone():
        try:
            conn.execute(
                "CREATE UNIQUE INDEX idx_raw_signals_dedup ON raw_signals(source, signal_type)"
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            logger.warning(
                "Skipped idx_raw_signals_dedup: duplicate (source, signal_type) rows in DB"
            )

    # Seed initial companies if empty
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM companies")
    if cursor.fetchone()[0] == 0:
        seed_companies(conn)
    
    conn.close()
    logger.info("Database initialized at %s", DB_PATH)
    return DB_PATH

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
        conn.execute("""
            INSERT OR IGNORE INTO companies 
            (name, slug, website, x_handle, github_org) 
            VALUES (?, ?, ?, ?, ?)
        """, (name, slug, website, x_handle, github_org))
    
    conn.commit()
    logger.info("Seeded %d initial companies", len(companies))

if __name__ == "__main__":
    init_database()