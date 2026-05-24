"""
Idempotent SQLite schema migrations for Competitor Intel.

Production databases evolved ahead of schema.py; fresh installs must reach the
same shape without destructive ALTERs. Safe to call on every init_database().
"""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)


def _columns(cursor: sqlite3.Cursor, table: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _add_column(
    cursor: sqlite3.Cursor,
    table: str,
    name: str,
    definition: str,
    existing: set[str],
) -> bool:
    if name in existing:
        return False
    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
    logger.info("Added column %s.%s", table, name)
    return True


def _ensure_table(cursor: sqlite3.Cursor, ddl: str) -> None:
    cursor.execute(ddl)


def apply_runtime_migrations(conn: sqlite3.Connection) -> None:
    """Bring an existing or new database up to the operational column surface."""
    cursor = conn.cursor()

    if _columns(cursor, "companies"):
        cols = _columns(cursor, "companies")
        company_extras = [
            ("github_stars", "INTEGER DEFAULT 0"),
            ("github_forks", "INTEGER DEFAULT 0"),
            ("github_repos", "INTEGER DEFAULT 0"),
            ("last_github_update", "TEXT"),
            ("github_data", "TEXT"),
            ("description", "TEXT"),
            ("score", "REAL"),
            ("first_seen", "TEXT"),
            ("last_updated", "TEXT"),
            ("star_velocity_7d", "INTEGER DEFAULT 0"),
            ("star_velocity_30d", "INTEGER DEFAULT 0"),
            ("last_scored_at", "TEXT"),
            ("embedding", "BLOB"),
        ]
        for name, definition in company_extras:
            if _add_column(cursor, "companies", name, definition, cols):
                cols.add(name)

    if _columns(cursor, "company_details"):
        cols = _columns(cursor, "company_details")
        _add_column(cursor, "company_details", "embedding", "TEXT", cols)
        for name, definition in [
            ("traction", "TEXT"),
            ("moat", "TEXT"),
        ]:
            if _add_column(cursor, "company_details", name, definition, cols):
                cols.add(name)

    if _columns(cursor, "funding_rounds"):
        cols = _columns(cursor, "funding_rounds")
        _add_column(cursor, "funding_rounds", "embedding", "TEXT", cols)
        fr_extras = [
            ("cluster_key", "TEXT"),
            ("report_count", "INTEGER DEFAULT 1"),
            ("official_report_count", "INTEGER DEFAULT 0"),
            ("corroboration_score", "REAL DEFAULT 0.5"),
            ("source_tier_best", "TEXT"),
            ("fields_provenance", "TEXT"),
            ("updated_at", "TEXT"),
        ]
        for name, definition in fr_extras:
            if _add_column(cursor, "funding_rounds", name, definition, cols):
                cols.add(name)
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_funding_rounds_cluster "
            "ON funding_rounds(cluster_key) WHERE cluster_key IS NOT NULL"
        )

    _ensure_table(
        cursor,
        """
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
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
            FOREIGN KEY (funding_round_id) REFERENCES funding_rounds(id) ON DELETE SET NULL
        )
        """,
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_funding_claims_company "
        "ON funding_round_claims(company_id, announced_date)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_funding_claims_round "
        "ON funding_round_claims(funding_round_id)"
    )

    if _columns(cursor, "funding_round_claims"):
        frc_cols = _columns(cursor, "funding_round_claims")
        claim_extras = [
            ("currency", "TEXT DEFAULT 'USD'"),
            ("pre_money_valuation_usd", "INTEGER"),
            ("post_money_valuation_usd", "INTEGER"),
            ("instrument_type", "TEXT"),
            ("deal_terms_text", "TEXT"),
        ]
        for name, definition in claim_extras:
            if _add_column(cursor, "funding_round_claims", name, definition, frc_cols):
                frc_cols.add(name)

    if _columns(cursor, "funding_rounds"):
        cols = _columns(cursor, "funding_rounds")
        round_extras = [
            ("currency", "TEXT DEFAULT 'USD'"),
            ("pre_money_valuation_usd", "INTEGER"),
            ("post_money_valuation_usd", "INTEGER"),
            ("instrument_type", "TEXT"),
            ("total_investor_count", "INTEGER DEFAULT 0"),
        ]
        for name, definition in round_extras:
            if _add_column(cursor, "funding_rounds", name, definition, cols):
                cols.add(name)

    if _columns(cursor, "funding_events"):
        fe_cols = _columns(cursor, "funding_events")
        for name, definition in [
            ("event_type", "TEXT"),
            ("is_rumor", "TEXT"),
            ("counterparty", "TEXT"),
        ]:
            if _add_column(cursor, "funding_events", name, definition, fe_cols):
                fe_cols.add(name)

    if _columns(cursor, "alerts_sent"):
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_alerts_sent_event_channel "
            "ON alerts_sent(event_id, channel)"
        )

    if _columns(cursor, "investors"):
        inv_cols = _columns(cursor, "investors")
        for name, definition in [
            ("name_normalized", "TEXT"),
            ("investor_type", "TEXT"),
            ("type", "TEXT"),
            ("stage_focus", "TEXT"),
            ("sector_focus", "TEXT"),
            ("website", "TEXT"),
            ("twitter", "TEXT"),
            ("linkedin", "TEXT"),
            ("email", "TEXT"),
            ("location", "TEXT"),
            ("description", "TEXT"),
            ("tier", "INTEGER DEFAULT 3"),
            ("company_id", "INTEGER"),
            ("investment_amount", "INTEGER"),
            ("round", "TEXT"),
            ("lead_investor", "INTEGER DEFAULT 0"),
            ("first_seen", "TEXT"),
            ("last_updated", "TEXT"),
        ]:
            if _add_column(cursor, "investors", name, definition, inv_cols):
                inv_cols.add(name)
        cursor.execute(
            """
            UPDATE investors SET name_normalized = lower(replace(trim(name), ' ', '-'))
            WHERE name_normalized IS NULL AND name IS NOT NULL
            """
        )
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_investors_name_normalized "
            "ON investors(name_normalized) WHERE name_normalized IS NOT NULL"
        )

    _ensure_table(
        cursor,
        """
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
            first_seen TEXT,
            last_updated TEXT
        )
        """,
    )

    # Rebuild participant tables if they still point at legacy investors(company_id).
    if _columns(cursor, "round_participants"):
        cursor.execute("SELECT COUNT(*) FROM round_participants")
        if cursor.fetchone()[0] == 0:
            cursor.execute("DROP TABLE IF EXISTS participant_source_attributions")
            cursor.execute("DROP TABLE IF EXISTS funding_claim_participants")
            cursor.execute("DROP TABLE IF EXISTS round_participants")

    _ensure_table(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS funding_claim_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            funding_round_claim_id INTEGER NOT NULL,
            investor_id INTEGER,
            investor_name_raw TEXT NOT NULL,
            role TEXT NOT NULL,
            is_lead INTEGER DEFAULT 0,
            amount_usd INTEGER,
            excerpt TEXT,
            FOREIGN KEY (funding_round_claim_id) REFERENCES funding_round_claims(id)
                ON DELETE CASCADE,
            FOREIGN KEY (investor_id) REFERENCES investor_firms(id) ON DELETE SET NULL
        )
        """,
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_claim_participants_claim "
        "ON funding_claim_participants(funding_round_claim_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_claim_participants_investor "
        "ON funding_claim_participants(investor_id)"
    )

    _ensure_table(
        cursor,
        """
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
        )
        """,
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_round_participants_round "
        "ON round_participants(funding_round_id)"
    )

    _ensure_table(
        cursor,
        """
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
            FOREIGN KEY (round_participant_id) REFERENCES round_participants(id)
                ON DELETE CASCADE,
            FOREIGN KEY (funding_round_claim_id) REFERENCES funding_round_claims(id)
                ON DELETE CASCADE,
            UNIQUE(round_participant_id, funding_round_claim_id)
        )
        """,
    )

    _ensure_table(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS intelligence_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            event_type TEXT NOT NULL,
            round_type TEXT,
            amount_usd INTEGER,
            valuation_usd INTEGER,
            lead_investor TEXT,
            counterparty TEXT,
            is_rumor INTEGER DEFAULT 0,
            confidence REAL DEFAULT 0.7,
            announced_date TEXT,
            source TEXT,
            source_url TEXT UNIQUE,
            raw_signal_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            embedding TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
        """,
    )
    ie_cols = _columns(cursor, "intelligence_events")
    _add_column(cursor, "intelligence_events", "embedding", "TEXT", ie_cols)
    _add_column(cursor, "intelligence_events", "raw_signal_id", "INTEGER", ie_cols)
    _add_column(cursor, "intelligence_events", "updated_at", "TEXT", ie_cols)
    _add_column(cursor, "intelligence_events", "description", "TEXT", ie_cols)

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_intel_company ON intelligence_events(company_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_intel_event_type ON intelligence_events(event_type)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_intel_date ON intelligence_events(announced_date)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_intel_raw_signal ON intelligence_events(raw_signal_id)"
    )
    if _columns(cursor, "raw_signals"):
        rs_cols = _columns(cursor, "raw_signals")
        _add_column(cursor, "raw_signals", "process_attempts", "INTEGER DEFAULT 0", rs_cols)
        _add_column(cursor, "raw_signals", "last_process_error", "TEXT", rs_cols)

    _ensure_table(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS company_identifiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            id_type TEXT NOT NULL,
            id_value TEXT NOT NULL,
            UNIQUE(id_type, id_value),
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
        """,
    )

    if _columns(cursor, "companies"):
        ccols = _columns(cursor, "companies")
        _add_column(cursor, "companies", "normalized_domain", "TEXT", ccols)

    _ensure_table(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS company_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            website TEXT,
            x_handle TEXT,
            github_org TEXT,
            industry TEXT,
            description TEXT,
            discovery_source TEXT,
            signals TEXT,
            score REAL DEFAULT 0.0,
            score_breakdown TEXT,
            status TEXT DEFAULT 'pending',
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
    )

    _ensure_table(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS investors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            investor_type TEXT,
            type TEXT,
            stage_focus TEXT,
            sector_focus TEXT,
            website TEXT,
            twitter TEXT,
            linkedin TEXT,
            email TEXT,
            location TEXT,
            description TEXT,
            tier INTEGER DEFAULT 3,
            company_id INTEGER,
            investment_amount INTEGER,
            round TEXT,
            lead_investor INTEGER DEFAULT 0,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
        """,
    )

    _ensure_table(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS funding_events_investors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            funding_event_id INTEGER NOT NULL,
            investor_id INTEGER NOT NULL,
            role TEXT,
            amount_invested_usd INTEGER,
            FOREIGN KEY (funding_event_id) REFERENCES funding_events(id) ON DELETE CASCADE,
            FOREIGN KEY (investor_id) REFERENCES investors(id) ON DELETE CASCADE,
            UNIQUE(funding_event_id, investor_id)
        )
        """,
    )

    _ensure_table(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS job_posting_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            job_posting_id INTEGER,
            intelligence_event_id INTEGER,
            raw_signal_id INTEGER,
            external_id TEXT,
            title TEXT NOT NULL,
            department TEXT,
            team TEXT,
            location TEXT,
            location_type TEXT,
            remote_policy TEXT,
            seniority_band TEXT,
            employment_type TEXT,
            job_type TEXT,
            salary_min_usd INTEGER,
            salary_max_usd INTEGER,
            salary_range TEXT,
            salary_currency TEXT DEFAULT 'USD',
            description_snippet TEXT,
            description_text TEXT,
            tech_stack_json TEXT,
            source TEXT NOT NULL,
            source_url TEXT UNIQUE,
            source_tier TEXT NOT NULL,
            source_weight REAL NOT NULL,
            is_official INTEGER DEFAULT 0,
            ats_platform TEXT,
            posted_at TEXT,
            closes_at TEXT,
            is_active INTEGER DEFAULT 1,
            extraction_confidence REAL,
            raw_payload_json TEXT,
            extracted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
            FOREIGN KEY (job_posting_id) REFERENCES job_postings(id) ON DELETE SET NULL
        )
        """,
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_job_claims_company "
        "ON job_posting_claims(company_id, is_active)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_job_claims_posting ON job_posting_claims(job_posting_id)"
    )

    _ensure_table(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS job_posting_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_posting_claim_id INTEGER,
            job_posting_id INTEGER,
            skill TEXT NOT NULL,
            category TEXT,
            confidence REAL DEFAULT 0.8,
            FOREIGN KEY (job_posting_claim_id) REFERENCES job_posting_claims(id) ON DELETE CASCADE,
            FOREIGN KEY (job_posting_id) REFERENCES job_postings(id) ON DELETE CASCADE
        )
        """,
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_job_skills_posting ON job_posting_skills(job_posting_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_job_skills_claim "
        "ON job_posting_skills(job_posting_claim_id)"
    )

    _ensure_table(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS company_job_boards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            ats_platform TEXT NOT NULL,
            board_slug TEXT NOT NULL,
            board_url TEXT,
            is_verified INTEGER DEFAULT 0,
            last_fetched_at TEXT,
            last_job_count INTEGER DEFAULT 0,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
            UNIQUE(company_id, ats_platform)
        )
        """,
    )

    _ensure_table(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS job_velocity_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            snapshot_date TEXT NOT NULL,
            active_openings INTEGER DEFAULT 0,
            new_postings_30d INTEGER DEFAULT 0,
            departments_hiring INTEGER DEFAULT 0,
            locations_hiring INTEGER DEFAULT 0,
            seniority_levels INTEGER DEFAULT 0,
            extracted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
            UNIQUE(company_id, snapshot_date)
        )
        """,
    )

    if _columns(cursor, "job_postings"):
        jp_cols = _columns(cursor, "job_postings")
        job_posting_extras = [
            ("cluster_key", "TEXT"),
            ("team", "TEXT"),
            ("location_type", "TEXT"),
            ("remote_policy", "TEXT"),
            ("seniority_band", "TEXT"),
            ("employment_type", "TEXT"),
            ("salary_min_usd", "INTEGER"),
            ("salary_max_usd", "INTEGER"),
            ("ats_platform", "TEXT"),
            ("external_id", "TEXT"),
            ("description_snippet", "TEXT"),
            ("description_text", "TEXT"),
            ("tech_stack_json", "TEXT"),
            ("corroboration_score", "REAL DEFAULT 0.5"),
            ("report_count", "INTEGER DEFAULT 1"),
            ("official_report_count", "INTEGER DEFAULT 0"),
            ("source_tier_best", "TEXT"),
            ("fields_provenance", "TEXT"),
            ("updated_at", "TEXT"),
        ]
        for name, definition in job_posting_extras:
            _add_column(cursor, "job_postings", name, definition, jp_cols)
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_job_postings_cluster "
            "ON job_postings(cluster_key)"
        )

    _ensure_table(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS company_profile_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            field_key TEXT NOT NULL,
            field_value TEXT NOT NULL,
            source TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_tier TEXT NOT NULL,
            source_weight REAL NOT NULL,
            is_official INTEGER DEFAULT 0,
            extraction_confidence REAL,
            headline TEXT,
            snippet TEXT,
            intelligence_event_id INTEGER,
            raw_signal_id INTEGER,
            extracted_at TEXT NOT NULL,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
            UNIQUE(source_url, field_key)
        )
        """,
    )
    _ensure_table(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS team_member_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            name_normalized TEXT NOT NULL,
            role TEXT,
            is_founder INTEGER DEFAULT 0,
            joined_date TEXT,
            linkedin_url TEXT,
            source TEXT NOT NULL,
            source_url TEXT NOT NULL UNIQUE,
            source_tier TEXT NOT NULL,
            source_weight REAL NOT NULL,
            is_official INTEGER DEFAULT 0,
            extraction_confidence REAL,
            headline TEXT,
            snippet TEXT,
            intelligence_event_id INTEGER,
            raw_signal_id INTEGER,
            extracted_at TEXT NOT NULL,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
        """,
    )
    _ensure_table(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS product_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            name_normalized TEXT NOT NULL,
            description TEXT,
            category TEXT,
            status TEXT DEFAULT 'active',
            product_url TEXT,
            launch_date TEXT,
            pricing_json TEXT,
            source TEXT NOT NULL,
            source_url TEXT NOT NULL UNIQUE,
            source_tier TEXT NOT NULL,
            source_weight REAL NOT NULL,
            is_official INTEGER DEFAULT 0,
            extraction_confidence REAL,
            headline TEXT,
            snippet TEXT,
            intelligence_event_id INTEGER,
            raw_signal_id INTEGER,
            extracted_at TEXT NOT NULL,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
        """,
    )
    _ensure_table(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS license_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            jurisdiction TEXT NOT NULL,
            license_type TEXT NOT NULL,
            status TEXT NOT NULL,
            regulator TEXT,
            license_number TEXT,
            effective_date TEXT,
            source TEXT NOT NULL,
            source_url TEXT NOT NULL UNIQUE,
            source_tier TEXT NOT NULL,
            source_weight REAL NOT NULL,
            is_official INTEGER DEFAULT 0,
            extraction_confidence REAL,
            headline TEXT,
            snippet TEXT,
            intelligence_event_id INTEGER,
            extracted_at TEXT NOT NULL,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
        """,
    )
    _ensure_table(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS regulatory_licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            jurisdiction TEXT NOT NULL,
            license_type TEXT NOT NULL,
            status TEXT NOT NULL,
            regulator TEXT,
            license_number TEXT,
            effective_date TEXT,
            corroboration_score REAL DEFAULT 0.5,
            report_count INTEGER DEFAULT 1,
            fields_provenance TEXT,
            updated_at TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
            UNIQUE(company_id, jurisdiction, license_type)
        )
        """,
    )

    if _columns(cursor, "company_details"):
        cd_cols = _columns(cursor, "company_details")
        _add_column(cursor, "company_details", "fields_provenance", "TEXT", cd_cols)

    if _columns(cursor, "team_members"):
        tm_cols = _columns(cursor, "team_members")
        for name, definition in [
            ("name_normalized", "TEXT"),
            ("source_url", "TEXT"),
            ("corroboration_score", "REAL DEFAULT 0.5"),
            ("report_count", "INTEGER DEFAULT 1"),
            ("fields_provenance", "TEXT"),
        ]:
            _add_column(cursor, "team_members", name, definition, tm_cols)
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_team_members_norm "
            "ON team_members(company_id, name_normalized)"
        )

    if _columns(cursor, "products"):
        pr_cols = _columns(cursor, "products")
        for name, definition in [
            ("name_normalized", "TEXT"),
            ("corroboration_score", "REAL DEFAULT 0.5"),
            ("report_count", "INTEGER DEFAULT 1"),
            ("fields_provenance", "TEXT"),
        ]:
            _add_column(cursor, "products", name, definition, pr_cols)
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_products_norm "
            "ON products(company_id, name_normalized)"
        )

    _ensure_table(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS company_valuations (
            company_id INTEGER PRIMARY KEY,
            valuation_usd INTEGER NOT NULL,
            valuation_kind TEXT NOT NULL,
            method TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.3,
            as_of_date TEXT,
            source_funding_round_id INTEGER,
            source_notes TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
            FOREIGN KEY (source_funding_round_id) REFERENCES funding_rounds(id) ON DELETE SET NULL
        )
        """,
    )

    _ensure_table(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS company_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            alias_display TEXT NOT NULL,
            alias_normalized TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL,
            confidence REAL DEFAULT 0.9,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
        """,
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_company_aliases_company ON company_aliases(company_id)"
    )

    _ensure_table(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS cap_table_holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            holder_name TEXT NOT NULL,
            holder_normalized TEXT NOT NULL,
            ownership_pct REAL,
            share_class TEXT,
            as_of_date TEXT,
            source TEXT NOT NULL,
            source_url TEXT NOT NULL,
            confidence REAL DEFAULT 0.5,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
            UNIQUE(company_id, holder_normalized, source_url)
        )
        """,
    )

    _ensure_table(
        cursor,
        """
        CREATE TABLE IF NOT EXISTS alert_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            company_id INTEGER,
            event_types TEXT NOT NULL,
            min_confidence REAL DEFAULT 0.5,
            channel TEXT DEFAULT 'discord',
            enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
        """,
    )

    conn.commit()
    logger.debug("Runtime migrations applied")
