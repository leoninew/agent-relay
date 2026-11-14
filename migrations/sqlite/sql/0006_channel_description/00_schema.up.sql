PRAGMA defer_foreign_keys=ON;
CREATE TABLE channels_updated (
    room_id TEXT NOT NULL REFERENCES rooms(id), id TEXT NOT NULL, name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    working_path TEXT NOT NULL, working_path_key TEXT, is_default BOOLEAN NOT NULL,
    workspace_kind TEXT NOT NULL CHECK(workspace_kind IN ('existing', 'worktree')),
    branch TEXT, base_commit TEXT, created_at TEXT, archived_at TEXT,
    PRIMARY KEY(room_id, id),
    CHECK((is_default = 1 AND id = 'channel-default') OR (is_default = 0 AND id <> 'channel-default'))
);
INSERT INTO channels_updated (
    room_id, id, name, description, working_path, working_path_key, is_default,
    workspace_kind, branch, base_commit, created_at, archived_at
)
SELECT room_id, id, name, '', working_path, working_path_key, is_default,
    workspace_kind, branch, base_commit, created_at, archived_at
FROM channels;
DROP TABLE channels;
ALTER TABLE channels_updated RENAME TO channels;
CREATE UNIQUE INDEX channels_active_name ON channels(room_id, name) WHERE archived_at IS NULL;
CREATE UNIQUE INDEX channels_default ON channels(room_id) WHERE is_default = 1;
CREATE UNIQUE INDEX channels_active_path ON channels(working_path_key) WHERE archived_at IS NULL AND workspace_kind = 'worktree';
