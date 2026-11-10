import sqlite3

from agent_relay.domain.rooms.models import TopicPosition


def read_topic_positions(
    connection: sqlite3.Connection, room_id: str, member_id: str | None = None
) -> list[TopicPosition]:
    member_clause = " AND mt.member_id = ?" if member_id is not None else ""
    args = (room_id, member_id) if member_id is not None else (room_id,)
    rows = connection.execute(
        "SELECT mt.member_id, mt.topic_id, COALESCE(p.seq, 0) AS seq, p.updated_at, "
        "(SELECT COUNT(*) FROM messages message WHERE message.room_id = mt.room_id "
        "AND message.seq > COALESCE(p.seq, 0) AND EXISTS "
        "(SELECT 1 FROM message_topics message_topic WHERE message_topic.room_id = message.room_id "
        "AND message_topic.message_id = message.id AND message_topic.topic_id = mt.topic_id)) "
        "AS later_count FROM member_topics mt "
        "JOIN members member ON member.room_id = mt.room_id AND member.id = mt.member_id "
        "AND member.deleted_at IS NULL "
        "JOIN topics topic ON topic.room_id = mt.room_id AND topic.id = mt.topic_id "
        "AND topic.deleted_at IS NULL "
        "LEFT JOIN member_topic_positions p ON p.room_id = mt.room_id "
        "AND p.member_id = mt.member_id AND p.topic_id = mt.topic_id "
        f"WHERE mt.room_id = ?{member_clause} ORDER BY member.rowid, mt.position",
        args,
    ).fetchall()
    return [TopicPosition.model_validate(dict(row)) for row in rows]
