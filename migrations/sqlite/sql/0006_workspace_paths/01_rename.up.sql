ALTER TABLE rooms RENAME COLUMN project_path TO workspace_path;
ALTER TABLE rooms RENAME COLUMN raw_project_path TO raw_workspace_path;
DROP INDEX rooms_active_path;
CREATE UNIQUE INDEX rooms_active_workspace
    ON rooms(workspace_path)
    WHERE archived_at IS NULL;
