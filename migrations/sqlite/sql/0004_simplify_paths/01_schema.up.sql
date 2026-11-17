ALTER TABLE rooms ADD COLUMN raw_project_path TEXT NOT NULL DEFAULT '';
UPDATE rooms SET raw_project_path = project_path;
DROP INDEX channels_active_path;
ALTER TABLE channels DROP COLUMN working_path_key;
ALTER TABLE channels ADD COLUMN worktree_path TEXT;
UPDATE channels SET worktree_path = working_path WHERE workspace_kind = 'worktree';
ALTER TABLE channels DROP COLUMN working_path;
ALTER TABLE sessions DROP COLUMN project_path;
