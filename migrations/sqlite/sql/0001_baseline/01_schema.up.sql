CREATE TABLE rooms (
    id TEXT PRIMARY KEY,
    project_path TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE topics (
    room_id TEXT NOT NULL REFERENCES rooms(id),
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT,
    deleted_at TEXT,
    PRIMARY KEY(room_id, id)
);

CREATE TABLE sessions (
    room_id TEXT NOT NULL REFERENCES rooms(id),
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    project_path TEXT NOT NULL,
    presence TEXT NOT NULL CHECK(presence IN ('available', 'busy', 'offline', 'unknown')),
    observed_at TEXT,
    PRIMARY KEY(room_id, id)
);

CREATE TABLE members (
    room_id TEXT NOT NULL REFERENCES rooms(id),
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    session_id TEXT,
    kind TEXT NOT NULL CHECK(kind IN ('human', 'agent')),
    initials TEXT NOT NULL,
    presence TEXT NOT NULL CHECK(presence IN ('available', 'busy', 'offline', 'unknown')),
    activity TEXT NOT NULL,
    activity_source TEXT NOT NULL,
    observed_at TEXT,
    deleted_at TEXT,
    PRIMARY KEY(room_id, id),
    FOREIGN KEY(room_id, session_id) REFERENCES sessions(room_id, id),
    CHECK (
        (kind = 'human'
            AND session_id IS NULL AND id = 'user' AND name = '你' AND deleted_at IS NULL)
        OR (kind = 'agent'
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
    publisher_id TEXT NOT NULL,
    publication_id TEXT,
    content TEXT NOT NULL,
    reply_to_message_id TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY(room_id, id),
    UNIQUE(room_id, seq),
    FOREIGN KEY(room_id, publisher_id) REFERENCES members(room_id, id),
    FOREIGN KEY(room_id, reply_to_message_id) REFERENCES messages(room_id, id)
);

CREATE TABLE message_topics (
    room_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK(position >= 0),
    PRIMARY KEY(room_id, message_id, topic_id),
    FOREIGN KEY(room_id, message_id) REFERENCES messages(room_id, id),
    FOREIGN KEY(room_id, topic_id) REFERENCES topics(room_id, id)
);

CREATE TABLE message_mentions (
    room_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK(position >= 0),
    PRIMARY KEY(room_id, message_id, member_id),
    FOREIGN KEY(room_id, message_id) REFERENCES messages(room_id, id),
    FOREIGN KEY(room_id, member_id) REFERENCES members(room_id, id)
);

CREATE TABLE message_recipients (
    room_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK(position >= 0),
    PRIMARY KEY(room_id, message_id, member_id),
    FOREIGN KEY(room_id, message_id) REFERENCES messages(room_id, id),
    FOREIGN KEY(room_id, member_id) REFERENCES members(room_id, id)
);

CREATE TABLE deliveries (
    room_id TEXT NOT NULL,
    id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    target_member_id TEXT NOT NULL,
    target_session_id TEXT NOT NULL,
    client_message_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN (
        'pending', 'submitting', 'queued', 'received', 'rejected', 'unknown'
    )),
    updated_at TEXT NOT NULL,
    queued_at TEXT,
    received_at TEXT,
    received_item_id TEXT,
    received_turn_id TEXT,
    activation_attempted_at TEXT,
    note TEXT,
    queued_submission_id TEXT,
    receipt_metadata TEXT CHECK(receipt_metadata IS NULL OR (
        queued_submission_id IS NOT NULL
        AND json_valid(receipt_metadata)
        AND json_type(receipt_metadata) = 'object'
        AND json_type(receipt_metadata, '$.id') IS NULL
        AND json_type(receipt_metadata, '$.clientUserMessageId') IS NULL
    )),
    error TEXT,
    PRIMARY KEY(room_id, id),
    UNIQUE(room_id, message_id, target_member_id),
    FOREIGN KEY(room_id, message_id) REFERENCES messages(room_id, id),
    FOREIGN KEY(room_id, target_member_id) REFERENCES members(room_id, id),
    FOREIGN KEY(room_id, target_session_id) REFERENCES sessions(room_id, id)
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
    message_id TEXT,
    topic_id TEXT,
    keyword TEXT,
    before_seq INTEGER CHECK(before_seq >= 1),
    after_seq INTEGER CHECK(after_seq >= 0),
    page_limit INTEGER NOT NULL CHECK(page_limit BETWEEN 1 AND 200),
    provided_at TEXT NOT NULL,
    UNIQUE(room_id, id),
    FOREIGN KEY(room_id, member_id) REFERENCES members(room_id, id),
    FOREIGN KEY(room_id, message_id) REFERENCES messages(room_id, id),
    FOREIGN KEY(room_id, topic_id) REFERENCES topics(room_id, id)
);

CREATE TABLE member_context_messages (
    room_id TEXT NOT NULL,
    query_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK(position >= 0),
    PRIMARY KEY(room_id, query_id, message_id),
    FOREIGN KEY(room_id, query_id) REFERENCES member_context_queries(room_id, id),
    FOREIGN KEY(room_id, message_id) REFERENCES messages(room_id, id)
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
CREATE INDEX message_topics_topic ON message_topics(room_id, topic_id, message_id);
CREATE INDEX message_mentions_member ON message_mentions(room_id, member_id, message_id);
CREATE INDEX message_recipients_member ON message_recipients(room_id, member_id, message_id);
CREATE INDEX deliveries_dispatch ON deliveries(status, target_session_id);
CREATE UNIQUE INDEX deliveries_client ON deliveries(target_session_id, client_message_id);
CREATE INDEX room_events_cursor ON room_events(room_id, event_id);
CREATE INDEX member_context_queries_member ON member_context_queries(room_id, member_id);
