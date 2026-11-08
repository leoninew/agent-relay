ALTER TABLE messages ADD COLUMN publisher_id TEXT NOT NULL DEFAULT '';
ALTER TABLE messages ADD COLUMN publication_id TEXT;
UPDATE messages SET publisher_id = COALESCE(json_extract(payload, '$.sender_id'), '');
CREATE UNIQUE INDEX messages_publication ON messages(room_id, publisher_id, publication_id);

ALTER TABLE deliveries ADD COLUMN target_session_id TEXT NOT NULL DEFAULT '';
ALTER TABLE deliveries ADD COLUMN status TEXT NOT NULL DEFAULT 'pending';
UPDATE deliveries SET target_session_id = (
    SELECT session_id FROM members
    WHERE members.room_id = deliveries.room_id AND members.id = deliveries.target_member_id
);
UPDATE deliveries SET status = CASE
    WHEN json_extract(payload, '$.status') = 'pending' THEN 'pending' ELSE 'unknown' END;
UPDATE deliveries SET payload = json_set(
    payload, '$.target_session_id', target_session_id,
    '$.client_message_id', lower(hex(randomblob(16))), '$.status', status,
    '$.error', CASE WHEN status = 'unknown' THEN '历史记录没有可核验的入队凭证' ELSE NULL END
);
CREATE INDEX deliveries_dispatch ON deliveries(status, target_session_id);
