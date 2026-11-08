CREATE TABLE room_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id TEXT NOT NULL REFERENCES rooms(id),
    kind TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    message_id TEXT
);
CREATE INDEX room_events_cursor ON room_events(room_id, event_id);
CREATE INDEX messages_sender_page ON messages(room_id, publisher_id, seq);
INSERT INTO room_events(room_id, kind, entity_id)
SELECT id, 'room', id FROM rooms ORDER BY rowid;

CREATE TRIGGER rooms_event_insert AFTER INSERT ON rooms
BEGIN
    INSERT INTO room_events(room_id, kind, entity_id, message_id)
    VALUES (NEW.id, 'room', NEW.id, NULL);
END;

CREATE TRIGGER rooms_event_update AFTER UPDATE ON rooms
BEGIN
    INSERT INTO room_events(room_id, kind, entity_id, message_id)
    VALUES (NEW.id, 'room', NEW.id, NULL);
END;

CREATE TRIGGER topics_event_insert AFTER INSERT ON topics
BEGIN
    INSERT INTO room_events(room_id, kind, entity_id, message_id)
    VALUES (NEW.room_id, 'topic', NEW.id, NULL);
END;

CREATE TRIGGER topics_event_update AFTER UPDATE ON topics
BEGIN
    INSERT INTO room_events(room_id, kind, entity_id, message_id)
    VALUES (NEW.room_id, 'topic', NEW.id, NULL);
END;

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

CREATE TRIGGER sessions_event_insert AFTER INSERT ON sessions
BEGIN
    INSERT INTO room_events(room_id, kind, entity_id, message_id)
    VALUES (NEW.room_id, 'session', NEW.id, NULL);
END;

CREATE TRIGGER sessions_event_update AFTER UPDATE ON sessions
BEGIN
    INSERT INTO room_events(room_id, kind, entity_id, message_id)
    VALUES (NEW.room_id, 'session', NEW.id, NULL);
END;

CREATE TRIGGER messages_event_insert AFTER INSERT ON messages
BEGIN
    INSERT INTO room_events(room_id, kind, entity_id, message_id)
    VALUES (NEW.room_id, 'message', NEW.id, NEW.id);
END;

CREATE TRIGGER messages_event_update AFTER UPDATE ON messages
BEGIN
    INSERT INTO room_events(room_id, kind, entity_id, message_id)
    VALUES (NEW.room_id, 'message', NEW.id, NEW.id);
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
