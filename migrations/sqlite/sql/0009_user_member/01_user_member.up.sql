CREATE TABLE members_next (
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

CREATE TABLE member_topics_next (
    room_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY(room_id, member_id, topic_id),
    FOREIGN KEY(room_id, member_id) REFERENCES members_next(room_id, id),
    FOREIGN KEY(room_id, topic_id) REFERENCES topics(room_id, id)
);

CREATE TABLE deliveries_next (
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
    FOREIGN KEY(room_id, target_member_id) REFERENCES members_next(room_id, id)
);

CREATE TABLE member_context_queries_next (
    id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    request TEXT NOT NULL,
    messages TEXT NOT NULL,
    provided_at TEXT NOT NULL,
    FOREIGN KEY(room_id, member_id) REFERENCES members_next(room_id, id)
);

CREATE TABLE member_topic_positions_next (
    room_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    seq INTEGER NOT NULL CHECK(seq >= 0),
    updated_at TEXT NOT NULL,
    PRIMARY KEY(room_id, member_id, topic_id),
    FOREIGN KEY(room_id, member_id) REFERENCES members_next(room_id, id),
    FOREIGN KEY(room_id, topic_id) REFERENCES topics(room_id, id)
);

INSERT INTO members_next (room_id, id, name, session_id, payload, deleted_at)
SELECT room_id, id, name, session_id, json_set(payload, '$.kind', 'agent'), deleted_at
FROM members ORDER BY rowid;

INSERT INTO member_topics_next SELECT * FROM member_topics ORDER BY rowid;
INSERT INTO deliveries_next SELECT * FROM deliveries ORDER BY rowid;
INSERT INTO member_context_queries_next SELECT * FROM member_context_queries ORDER BY rowid;
INSERT INTO member_topic_positions_next SELECT * FROM member_topic_positions ORDER BY rowid;

DROP TABLE member_topics;
DROP TABLE deliveries;
DROP TABLE member_context_queries;
DROP TABLE member_topic_positions;
DROP TABLE members;

ALTER TABLE members_next RENAME TO members;
ALTER TABLE member_topics_next RENAME TO member_topics;
ALTER TABLE deliveries_next RENAME TO deliveries;
ALTER TABLE member_context_queries_next RENAME TO member_context_queries;
ALTER TABLE member_topic_positions_next RENAME TO member_topic_positions;

CREATE UNIQUE INDEX members_active_name ON members(room_id, name) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX members_active_session ON members(room_id, session_id) WHERE deleted_at IS NULL;
CREATE INDEX deliveries_dispatch ON deliveries(status, target_session_id);
CREATE INDEX member_context_queries_member ON member_context_queries(room_id, member_id);

CREATE TRIGGER members_event_insert AFTER INSERT ON members
BEGIN
    INSERT INTO room_events(room_id, kind, entity_id, message_id)
    VALUES (NEW.room_id, 'member', NEW.id, NULL);
END;

CREATE TRIGGER members_event_update AFTER UPDATE ON members
BEGIN
    INSERT INTO room_events(room_id, kind, entity_id, message_id)
    VALUES (NEW.room_id, 'member', NEW.id, NULL);
END;

CREATE TRIGGER member_topics_event_insert AFTER INSERT ON member_topics
BEGIN
    INSERT INTO room_events(room_id, kind, entity_id, message_id)
    VALUES (NEW.room_id, 'member', NEW.member_id, NULL);
END;

CREATE TRIGGER member_topics_event_delete AFTER DELETE ON member_topics
BEGIN
    INSERT INTO room_events(room_id, kind, entity_id, message_id)
    VALUES (OLD.room_id, 'member', OLD.member_id, NULL);
END;

CREATE TRIGGER deliveries_event_insert AFTER INSERT ON deliveries
BEGIN
    INSERT INTO room_events(room_id, kind, entity_id, message_id)
    VALUES (NEW.room_id, 'delivery', NEW.id, NEW.message_id);
END;

CREATE TRIGGER deliveries_event_update AFTER UPDATE ON deliveries
BEGIN
    INSERT INTO room_events(room_id, kind, entity_id, message_id)
    VALUES (NEW.room_id, 'delivery', NEW.id, NEW.message_id);
END;

CREATE TRIGGER member_topic_positions_event_insert AFTER INSERT ON member_topic_positions
BEGIN
    INSERT INTO room_events(room_id, kind, entity_id, message_id)
    VALUES (NEW.room_id, 'position', NEW.member_id, NULL);
END;

CREATE TRIGGER member_topic_positions_event_update AFTER UPDATE ON member_topic_positions
BEGIN
    INSERT INTO room_events(room_id, kind, entity_id, message_id)
    VALUES (NEW.room_id, 'position', NEW.member_id, NULL);
END;

INSERT INTO members (room_id, id, name, session_id, payload)
SELECT id, 'user', '你', NULL, json_object(
    'id', 'user', 'kind', 'human', 'session_id', NULL, 'name', '你', 'initials', '你',
    'presence', 'available', 'activity', '', 'activity_source', 'user',
    'observed_at', NULL, 'topic_ids', json('[]'), 'deleted_at', NULL
) FROM rooms ORDER BY rowid;

UPDATE messages SET publisher_id = 'user',
    payload = json_set(payload, '$.sender_id', 'user', '$.sender_name', '你')
WHERE publisher_id = '';

UPDATE messages SET payload = json_set(
    payload,
    '$.mentioned_member_ids', json_insert(json_extract(payload, '$.mentioned_member_ids'), '$[#]', 'user'),
    '$.recipient_ids', json_insert(json_extract(payload, '$.recipient_ids'), '$[#]', 'user')
) WHERE json_extract(payload, '$.console_recipient') = 1;

UPDATE messages SET payload = json_remove(payload, '$.console_recipient')
WHERE json_type(payload, '$.console_recipient') IS NOT NULL;
