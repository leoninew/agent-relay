UPDATE members
SET payload = json_remove(payload, '$.role');
