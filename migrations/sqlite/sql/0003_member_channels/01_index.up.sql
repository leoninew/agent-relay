DROP INDEX members_active_session;
CREATE UNIQUE INDEX members_active_session ON members(room_id, channel_id, session_id)
    WHERE deleted_at IS NULL;
