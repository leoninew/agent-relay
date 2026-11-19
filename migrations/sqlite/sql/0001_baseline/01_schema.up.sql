CREATE TABLE rooms (
    id TEXT PRIMARY KEY NOT NULL,
    workspace_path TEXT NOT NULL, raw_workspace_path TEXT NOT NULL, name TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now') || '000+00:00'), updated_at TEXT,
    is_deleted BOOLEAN NOT NULL DEFAULT 0 CHECK(is_deleted IN (0, 1)), deleted_at TEXT
);
CREATE UNIQUE INDEX rooms_active_workspace ON rooms(workspace_path) WHERE is_deleted = 0;
CREATE TABLE channels (
    id TEXT NOT NULL,
    room_id TEXT NOT NULL REFERENCES rooms(id),
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    worktree_path TEXT, is_default BOOLEAN NOT NULL CHECK(is_default IN (0, 1)),
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'archived')),
    workspace_kind TEXT NOT NULL CHECK(workspace_kind IN ('existing', 'worktree')),
    branch TEXT, base_commit TEXT, archived_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now') || '000+00:00'), updated_at TEXT,
    is_deleted BOOLEAN NOT NULL DEFAULT 0 CHECK(is_deleted IN (0, 1)), deleted_at TEXT,
    PRIMARY KEY(room_id, id)
);
CREATE UNIQUE INDEX channels_active_name ON channels(room_id, name) WHERE is_deleted = 0 AND status = 'active';
CREATE UNIQUE INDEX channels_default ON channels(room_id) WHERE is_default = 1;
CREATE TABLE sessions (
    id TEXT NOT NULL, room_id TEXT NOT NULL REFERENCES rooms(id), name TEXT NOT NULL,
    provider TEXT NOT NULL,
    presence TEXT NOT NULL CHECK(presence IN ('available', 'busy', 'offline', 'unknown')),
    observed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now') || '000+00:00'), updated_at TEXT,
    PRIMARY KEY(room_id, id)
);
CREATE TABLE topics (
    id TEXT NOT NULL,
    room_id TEXT NOT NULL REFERENCES rooms(id), channel_id TEXT NOT NULL,
    name TEXT NOT NULL, description TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now') || '000+00:00'), updated_at TEXT,
    is_deleted BOOLEAN NOT NULL DEFAULT 0 CHECK(is_deleted IN (0, 1)), deleted_at TEXT,
    PRIMARY KEY(room_id, id, channel_id),
    FOREIGN KEY(room_id, channel_id) REFERENCES channels(room_id, id)
);
CREATE UNIQUE INDEX topics_active_name ON topics(room_id, channel_id, name) WHERE is_deleted = 0;
CREATE TABLE members (
    id TEXT NOT NULL,
    room_id TEXT NOT NULL REFERENCES rooms(id), channel_id TEXT NOT NULL, session_id TEXT,
    name TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('human', 'agent')), initials TEXT NOT NULL,
    presence TEXT NOT NULL CHECK(presence IN ('available', 'busy', 'offline', 'unknown')),
    activity TEXT NOT NULL, activity_source TEXT NOT NULL, observed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now') || '000+00:00'), updated_at TEXT,
    is_deleted BOOLEAN NOT NULL DEFAULT 0 CHECK(is_deleted IN (0, 1)), deleted_at TEXT,
    PRIMARY KEY(room_id, id, channel_id),
    FOREIGN KEY(room_id, channel_id) REFERENCES channels(room_id, id),
    FOREIGN KEY(room_id, session_id) REFERENCES sessions(room_id, id)
);
CREATE UNIQUE INDEX members_active_name ON members(room_id, channel_id, name) WHERE is_deleted = 0;
CREATE UNIQUE INDEX members_active_session ON members(room_id, channel_id, session_id) WHERE is_deleted = 0;
CREATE UNIQUE INDEX members_human ON members(room_id, channel_id) WHERE kind = 'human';
CREATE TABLE member_topics (
    room_id TEXT NOT NULL, member_id TEXT NOT NULL, topic_id TEXT NOT NULL, position INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now') || '000+00:00'), updated_at TEXT,
    channel_id TEXT NOT NULL, PRIMARY KEY(room_id, member_id, topic_id, channel_id),
    FOREIGN KEY(room_id, channel_id, member_id) REFERENCES members(room_id, channel_id, id),
    FOREIGN KEY(room_id, channel_id, topic_id) REFERENCES topics(room_id, channel_id, id)
);
CREATE TABLE messages (
    id TEXT NOT NULL,
    room_id TEXT NOT NULL REFERENCES rooms(id), channel_id TEXT NOT NULL,
    publisher_id TEXT NOT NULL, reply_to_message_id TEXT,
    seq INTEGER NOT NULL CHECK(seq > 0),
    publication_id TEXT, content TEXT NOT NULL,
    capabilities TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now') || '000+00:00'), updated_at TEXT,
    is_deleted BOOLEAN NOT NULL DEFAULT 0 CHECK(is_deleted IN (0, 1)), deleted_at TEXT,
    PRIMARY KEY(room_id, id, channel_id), UNIQUE(room_id, seq),
    FOREIGN KEY(room_id, channel_id, publisher_id) REFERENCES members(room_id, channel_id, id),
    FOREIGN KEY(room_id, channel_id, reply_to_message_id) REFERENCES messages(room_id, channel_id, id)
);
CREATE UNIQUE INDEX messages_publication ON messages(room_id, channel_id, publisher_id, publication_id);
CREATE INDEX messages_sender_page ON messages(room_id, channel_id, publisher_id, seq);
CREATE TABLE message_topics (
    room_id TEXT NOT NULL, message_id TEXT NOT NULL, topic_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK(position >= 0), channel_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now') || '000+00:00'), updated_at TEXT,
    PRIMARY KEY(room_id, message_id, topic_id, channel_id),
    FOREIGN KEY(room_id, channel_id, message_id) REFERENCES messages(room_id, channel_id, id),
    FOREIGN KEY(room_id, channel_id, topic_id) REFERENCES topics(room_id, channel_id, id)
);
CREATE INDEX message_topics_topic ON message_topics(room_id, topic_id, message_id);
CREATE TABLE message_mentions (
    room_id TEXT NOT NULL, message_id TEXT NOT NULL, member_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK(position >= 0), channel_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now') || '000+00:00'), updated_at TEXT,
    PRIMARY KEY(room_id, message_id, member_id, channel_id),
    FOREIGN KEY(room_id, channel_id, message_id) REFERENCES messages(room_id, channel_id, id),
    FOREIGN KEY(room_id, channel_id, member_id) REFERENCES members(room_id, channel_id, id)
);
CREATE INDEX message_mentions_member ON message_mentions(room_id, member_id, message_id);
CREATE TABLE message_recipients (
    room_id TEXT NOT NULL, message_id TEXT NOT NULL, member_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK(position >= 0), channel_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now') || '000+00:00'), updated_at TEXT,
    PRIMARY KEY(room_id, message_id, member_id, channel_id),
    FOREIGN KEY(room_id, channel_id, message_id) REFERENCES messages(room_id, channel_id, id),
    FOREIGN KEY(room_id, channel_id, member_id) REFERENCES members(room_id, channel_id, id)
);
CREATE INDEX message_recipients_member ON message_recipients(room_id, member_id, message_id);
CREATE TABLE deliveries (
    id TEXT NOT NULL,
    room_id TEXT NOT NULL, channel_id TEXT NOT NULL,
    message_id TEXT NOT NULL, target_member_id TEXT NOT NULL,
    target_session_id TEXT NOT NULL, client_message_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending', 'submitting', 'queued', 'received', 'rejected', 'unknown')),
    queued_at TEXT, received_at TEXT, received_item_id TEXT, received_turn_id TEXT,
    activation_attempted_at TEXT, note TEXT, queued_submission_id TEXT, receipt_metadata TEXT,
    submission_method TEXT CHECK(submission_method IN ('queue', 'steer')), steered_turn_id TEXT, error TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0, next_attempt_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now') || '000+00:00'), updated_at TEXT,
    is_deleted BOOLEAN NOT NULL DEFAULT 0 CHECK(is_deleted IN (0, 1)), deleted_at TEXT,
    PRIMARY KEY(room_id, id, channel_id),
    UNIQUE(room_id, channel_id, message_id, target_member_id),
    FOREIGN KEY(room_id, channel_id, message_id) REFERENCES messages(room_id, channel_id, id),
    FOREIGN KEY(room_id, channel_id, target_member_id) REFERENCES members(room_id, channel_id, id),
    FOREIGN KEY(room_id, target_session_id) REFERENCES sessions(room_id, id)
);
CREATE UNIQUE INDEX deliveries_client ON deliveries(target_session_id, client_message_id);
CREATE INDEX deliveries_dispatch ON deliveries(status, target_session_id);
CREATE TABLE room_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, room_id TEXT NOT NULL REFERENCES rooms(id),
    channel_id TEXT NOT NULL, kind TEXT NOT NULL, entity_id TEXT NOT NULL, message_id TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now') || '000+00:00'), updated_at TEXT,
    FOREIGN KEY(room_id, channel_id) REFERENCES channels(room_id, id)
);
CREATE INDEX room_events_cursor ON room_events(room_id, channel_id, event_id);
CREATE TABLE member_context_queries (
    id TEXT PRIMARY KEY NOT NULL,
    room_id TEXT NOT NULL, channel_id TEXT NOT NULL,
    member_id TEXT NOT NULL, message_id TEXT, topic_id TEXT, keyword TEXT,
    before_seq INTEGER CHECK(before_seq >= 1), after_seq INTEGER CHECK(after_seq >= 0),
    page_limit INTEGER NOT NULL CHECK(page_limit BETWEEN 1 AND 200), provided_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now') || '000+00:00'), updated_at TEXT,
    UNIQUE(room_id, channel_id, id),
    FOREIGN KEY(room_id, channel_id, member_id) REFERENCES members(room_id, channel_id, id),
    FOREIGN KEY(room_id, channel_id, message_id) REFERENCES messages(room_id, channel_id, id),
    FOREIGN KEY(room_id, channel_id, topic_id) REFERENCES topics(room_id, channel_id, id)
);
CREATE INDEX member_context_queries_member ON member_context_queries(room_id, member_id);
CREATE TABLE member_context_messages (
    room_id TEXT NOT NULL, query_id TEXT NOT NULL, message_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK(position >= 0), channel_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now') || '000+00:00'), updated_at TEXT,
    PRIMARY KEY(room_id, query_id, message_id, channel_id),
    FOREIGN KEY(room_id, channel_id, query_id) REFERENCES member_context_queries(room_id, channel_id, id),
    FOREIGN KEY(room_id, channel_id, message_id) REFERENCES messages(room_id, channel_id, id)
);
CREATE TABLE member_topic_positions (
    room_id TEXT NOT NULL, member_id TEXT NOT NULL, topic_id TEXT NOT NULL,
    seq INTEGER NOT NULL CHECK(seq >= 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now') || '000+00:00'), updated_at TEXT,
    channel_id TEXT NOT NULL, PRIMARY KEY(room_id, member_id, topic_id, channel_id),
    FOREIGN KEY(room_id, channel_id, member_id) REFERENCES members(room_id, channel_id, id),
    FOREIGN KEY(room_id, channel_id, topic_id) REFERENCES topics(room_id, channel_id, id)
);
CREATE TABLE member_roles (
    id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL UNIQUE, prompt TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now') || '000+00:00'), updated_at TEXT
);
