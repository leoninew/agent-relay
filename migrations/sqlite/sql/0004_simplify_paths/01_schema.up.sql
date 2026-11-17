DROP INDEX channels_active_path;
ALTER TABLE channels DROP COLUMN working_path_key;
ALTER TABLE channels ADD COLUMN worktree_path TEXT;
UPDATE channels SET worktree_path = working_path WHERE workspace_kind = 'worktree';
ALTER TABLE channels DROP COLUMN working_path;
ALTER TABLE sessions DROP COLUMN project_path;
