INSERT INTO rooms(id,project_path,name,description) SELECT id,project_path,name,description FROM legacy_rooms ORDER BY rowid;
INSERT INTO channels(room_id,id,name,working_path,working_path_key,is_default,workspace_kind,status)
    SELECT id,'channel-default','默认',project_path,project_path,1,'existing','ready' FROM rooms ORDER BY rowid;
INSERT INTO sessions(room_id,id,name,provider,project_path,presence,observed_at)
    SELECT room_id,id,name,provider,project_path,presence,observed_at FROM legacy_sessions ORDER BY rowid;
INSERT INTO topics(room_id,id,name,description,created_at,deleted_at)
    SELECT room_id,id,name,description,created_at,deleted_at FROM legacy_topics ORDER BY rowid;
INSERT INTO members(room_id,id,name,session_id,kind,initials,presence,activity,activity_source,observed_at,deleted_at)
    SELECT room_id,id,name,session_id,kind,initials,presence,activity,activity_source,observed_at,deleted_at FROM legacy_members ORDER BY rowid;
INSERT INTO member_topics(room_id,member_id,topic_id,position)
    SELECT room_id,member_id,topic_id,position FROM legacy_member_topics ORDER BY rowid;
INSERT INTO messages(room_id,id,seq,publisher_id,publication_id,content,capabilities,reply_to_message_id,created_at,deleted_at)
    SELECT room_id,id,seq,publisher_id,publication_id,content,capabilities,reply_to_message_id,created_at,deleted_at FROM legacy_messages ORDER BY rowid;
INSERT INTO message_topics(room_id,message_id,topic_id,position)
    SELECT room_id,message_id,topic_id,position FROM legacy_message_topics ORDER BY rowid;
INSERT INTO message_mentions(room_id,message_id,member_id,position)
    SELECT room_id,message_id,member_id,position FROM legacy_message_mentions ORDER BY rowid;
INSERT INTO message_recipients(room_id,message_id,member_id,position)
    SELECT room_id,message_id,member_id,position FROM legacy_message_recipients ORDER BY rowid;
INSERT INTO deliveries(room_id,id,message_id,target_member_id,target_session_id,client_message_id,status,updated_at,queued_at,received_at,received_item_id,received_turn_id,activation_attempted_at,note,queued_submission_id,receipt_metadata,submission_method,steered_turn_id,error,deleted_at)
    SELECT room_id,id,message_id,target_member_id,target_session_id,client_message_id,status,updated_at,queued_at,received_at,received_item_id,received_turn_id,activation_attempted_at,note,queued_submission_id,receipt_metadata,submission_method,steered_turn_id,error,deleted_at FROM legacy_deliveries ORDER BY rowid;
INSERT INTO room_events(event_id,room_id,kind,entity_id,message_id)
    SELECT event_id,room_id,kind,entity_id,message_id FROM legacy_room_events ORDER BY rowid;
INSERT INTO member_context_queries(id,room_id,member_id,message_id,topic_id,keyword,before_seq,after_seq,page_limit,provided_at)
    SELECT id,room_id,member_id,message_id,topic_id,keyword,before_seq,after_seq,page_limit,provided_at FROM legacy_member_context_queries ORDER BY rowid;
INSERT INTO member_context_messages(room_id,query_id,message_id,position)
    SELECT room_id,query_id,message_id,position FROM legacy_member_context_messages ORDER BY rowid;
INSERT INTO member_topic_positions(room_id,member_id,topic_id,seq,updated_at)
    SELECT room_id,member_id,topic_id,seq,updated_at FROM legacy_member_topic_positions ORDER BY rowid;
DROP TABLE legacy_member_topic_positions;
DROP TABLE legacy_member_context_messages;
DROP TABLE legacy_member_context_queries;
DROP TABLE legacy_room_events;
DROP TABLE legacy_deliveries;
DROP TABLE legacy_message_recipients;
DROP TABLE legacy_message_mentions;
DROP TABLE legacy_message_topics;
DROP TABLE legacy_messages;
DROP TABLE legacy_member_topics;
DROP TABLE legacy_members;
DROP TABLE legacy_topics;
DROP TABLE legacy_sessions;
DROP TABLE legacy_rooms;
DELETE FROM sqlite_sequence WHERE name = 'room_events';
INSERT INTO sqlite_sequence(name,seq) SELECT 'room_events',seq FROM channel_event_watermark;
DROP TABLE channel_event_watermark;
