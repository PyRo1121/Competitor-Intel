-- Investor Intelligence Tables
-- Adds structured investor tracking and funding round participation

CREATE TABLE IF NOT EXISTS investors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    investor_type TEXT,           -- VC, Angel, Accelerator, Family Office, Corporate VC
    stage_focus TEXT,             -- Pre-Seed, Seed, Series A, etc.
    sector_focus TEXT,
    website TEXT,
    twitter TEXT,
    linkedin TEXT,
    email TEXT,
    location TEXT,
    description TEXT,
    tier INTEGER DEFAULT 3,       -- 1 = Top-tier (a16z, Sequoia, etc.), 2 = Strong, 3 = Standard
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_investors_name ON investors(name);
CREATE INDEX IF NOT EXISTS idx_investors_tier ON investors(tier);

CREATE TABLE IF NOT EXISTS funding_events_investors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    funding_event_id INTEGER NOT NULL,
    investor_id INTEGER NOT NULL,
    role TEXT,                    -- Lead, Co-Lead, Participant
    amount_invested_usd INTEGER,
    FOREIGN KEY (funding_event_id) REFERENCES funding_events(id) ON DELETE CASCADE,
    FOREIGN KEY (investor_id) REFERENCES investors(id) ON DELETE CASCADE,
    UNIQUE(funding_event_id, investor_id)
);

CREATE INDEX IF NOT EXISTS idx_funding_investors_event ON funding_events_investors(funding_event_id);
CREATE INDEX IF NOT EXISTS idx_funding_investors_investor ON funding_events_investors(investor_id);