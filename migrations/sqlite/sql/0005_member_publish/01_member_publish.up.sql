CREATE TABLE member_publish_tokens (
    token TEXT PRIMARY KEY,
    room_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    UNIQUE (room_id, member_id),
    FOREIGN KEY (room_id, member_id) REFERENCES members(room_id, id)
);
