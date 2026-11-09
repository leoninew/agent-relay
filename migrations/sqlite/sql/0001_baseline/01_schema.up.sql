CREATE TABLE rooms (
    id TEXT PRIMARY KEY,
    project_path TEXT NOT NULL UNIQUE,
    payload TEXT NOT NULL
);

CREATE TABLE topics (
    room_id TEXT NOT NULL REFERENCES rooms(id),
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    payload TEXT NOT NULL,
    deleted_at TEXT,
    PRIMARY KEY(room_id, id)
);

CREATE TABLE sessions (
    room_id TEXT NOT NULL REFERENCES rooms(id),
    id TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY(room_id, id)
);

CREATE TABLE members (
    room_id TEXT NOT NULL REFERENCES rooms(id),
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    session_id TEXT,
    payload TEXT NOT NULL,
    deleted_at TEXT,
    PRIMARY KEY(room_id, id),
    FOREIGN KEY(room_id, session_id) REFERENCES sessions(room_id, id),
    CHECK (
        (json_extract(payload, '$.kind') = 'human'
            AND session_id IS NULL AND id = 'user' AND name = '你' AND deleted_at IS NULL)
        OR (json_extract(payload, '$.kind') = 'agent'
            AND session_id IS NOT NULL AND id <> 'user')
    )
);

CREATE TABLE member_topics (
    room_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY(room_id, member_id, topic_id),
    FOREIGN KEY(room_id, member_id) REFERENCES members(room_id, id),
    FOREIGN KEY(room_id, topic_id) REFERENCES topics(room_id, id)
);

CREATE TABLE messages (
    room_id TEXT NOT NULL REFERENCES rooms(id),
    id TEXT NOT NULL,
    seq INTEGER NOT NULL CHECK(seq > 0),
    payload TEXT NOT NULL,
    publisher_id TEXT NOT NULL DEFAULT '',
    publication_id TEXT,
    PRIMARY KEY(room_id, id),
    UNIQUE(room_id, seq)
);

CREATE TABLE deliveries (
    room_id TEXT NOT NULL,
    id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    target_member_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    target_session_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    PRIMARY KEY(room_id, id),
    UNIQUE(room_id, message_id, target_member_id),
    FOREIGN KEY(room_id, message_id) REFERENCES messages(room_id, id),
    FOREIGN KEY(room_id, target_member_id) REFERENCES members(room_id, id)
);

CREATE TABLE room_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id TEXT NOT NULL REFERENCES rooms(id),
    kind TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    message_id TEXT
);

CREATE TABLE member_context_queries (
    id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    request TEXT NOT NULL,
    messages TEXT NOT NULL,
    provided_at TEXT NOT NULL,
    FOREIGN KEY(room_id, member_id) REFERENCES members(room_id, id)
);

CREATE TABLE member_topic_positions (
    room_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    seq INTEGER NOT NULL CHECK(seq >= 0),
    updated_at TEXT NOT NULL,
    PRIMARY KEY(room_id, member_id, topic_id),
    FOREIGN KEY(room_id, member_id) REFERENCES members(room_id, id),
    FOREIGN KEY(room_id, topic_id) REFERENCES topics(room_id, id)
);

CREATE UNIQUE INDEX topics_active_name ON topics(room_id, name) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX members_active_name ON members(room_id, name) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX members_active_session ON members(room_id, session_id) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX messages_publication ON messages(room_id, publisher_id, publication_id);
CREATE INDEX messages_sender_page ON messages(room_id, publisher_id, seq);
CREATE INDEX deliveries_dispatch ON deliveries(status, target_session_id);
CREATE INDEX room_events_cursor ON room_events(room_id, event_id);
CREATE INDEX member_context_queries_member ON member_context_queries(room_id, member_id);
