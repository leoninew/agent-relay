CREATE TABLE topics_next (
    room_id TEXT NOT NULL REFERENCES rooms(id),
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    payload TEXT NOT NULL,
    deleted_at TEXT,
    PRIMARY KEY(room_id, id)
);

CREATE TABLE members_next (
    room_id TEXT NOT NULL REFERENCES rooms(id),
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    session_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    deleted_at TEXT,
    PRIMARY KEY(room_id, id),
    FOREIGN KEY(room_id, session_id) REFERENCES sessions(room_id, id)
);

CREATE TABLE member_topics_next (
    room_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY(room_id, member_id, topic_id),
    FOREIGN KEY(room_id, member_id) REFERENCES members_next(room_id, id),
    FOREIGN KEY(room_id, topic_id) REFERENCES topics_next(room_id, id)
);

CREATE TABLE deliveries_next (
    room_id TEXT NOT NULL,
    id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    target_member_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY(room_id, id),
    UNIQUE(room_id, message_id, target_member_id),
    FOREIGN KEY(room_id, message_id) REFERENCES messages(room_id, id),
    FOREIGN KEY(room_id, target_member_id) REFERENCES members_next(room_id, id)
);

INSERT INTO topics_next (room_id, id, name, payload)
SELECT room_id, id, name, payload FROM topics ORDER BY rowid;

INSERT INTO members_next (room_id, id, name, session_id, payload)
SELECT room_id, id, name, session_id, payload FROM members ORDER BY rowid;

INSERT INTO member_topics_next
SELECT room_id, member_id, topic_id, position FROM member_topics ORDER BY rowid;

INSERT INTO deliveries_next
SELECT room_id, id, message_id, target_member_id, payload FROM deliveries ORDER BY rowid;

DROP TABLE deliveries;
DROP TABLE member_topics;
DROP TABLE members;
DROP TABLE topics;

ALTER TABLE topics_next RENAME TO topics;
ALTER TABLE members_next RENAME TO members;
ALTER TABLE member_topics_next RENAME TO member_topics;
ALTER TABLE deliveries_next RENAME TO deliveries;

CREATE UNIQUE INDEX topics_active_name ON topics(room_id, name) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX members_active_name ON members(room_id, name) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX members_active_session ON members(room_id, session_id) WHERE deleted_at IS NULL;
