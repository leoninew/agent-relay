ALTER TABLE deliveries ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE deliveries ADD COLUMN next_attempt_at TEXT;
