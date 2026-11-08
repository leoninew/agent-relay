CREATE TABLE member_context_queries (
    id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    request TEXT NOT NULL,
    messages TEXT NOT NULL,
    provided_at TEXT NOT NULL,
    FOREIGN KEY (room_id, member_id) REFERENCES members(room_id, id)
);
CREATE INDEX member_context_queries_member ON member_context_queries(room_id, member_id);

CREATE TABLE member_topic_positions (
    room_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    seq INTEGER NOT NULL CHECK (seq >= 0),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (room_id, member_id, topic_id),
    FOREIGN KEY (room_id, member_id) REFERENCES members(room_id, id),
    FOREIGN KEY (room_id, topic_id) REFERENCES topics(room_id, id)
);

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
