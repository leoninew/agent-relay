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
    PRIMARY KEY(room_id, id),
    UNIQUE(room_id, name)
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
    session_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY(room_id, id),
    UNIQUE(room_id, name),
    UNIQUE(room_id, session_id),
    FOREIGN KEY(room_id, session_id) REFERENCES sessions(room_id, id)
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
    PRIMARY KEY(room_id, id),
    UNIQUE(room_id, seq)
);

CREATE TABLE deliveries (
    room_id TEXT NOT NULL,
    id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    target_member_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY(room_id, id),
    UNIQUE(room_id, message_id, target_member_id),
    FOREIGN KEY(room_id, message_id) REFERENCES messages(room_id, id),
    FOREIGN KEY(room_id, target_member_id) REFERENCES members(room_id, id)
);
