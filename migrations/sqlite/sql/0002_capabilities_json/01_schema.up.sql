ALTER TABLE messages
    ADD COLUMN capabilities TEXT NOT NULL DEFAULT '[]'
    CHECK (json_valid(capabilities) AND json_type(capabilities) = 'array');
