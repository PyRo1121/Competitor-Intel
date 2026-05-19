CREATE TABLE IF NOT EXISTS alerts_sent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    channel TEXT NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES intelligence_events(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_alerts_event ON alerts_sent(event_id);
CREATE INDEX IF NOT EXISTS idx_alerts_sent ON alerts_sent(sent_at);
