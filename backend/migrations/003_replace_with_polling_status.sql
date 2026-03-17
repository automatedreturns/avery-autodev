-- Migration: Replace polling_history with polling_status
-- Date: 2025-12-15
-- Description: Simplifies polling tracking to show last poll time and cumulative stats per workspace

-- Drop the old polling_history table
DROP TABLE IF EXISTS polling_history;

-- Create polling_status table (one row per workspace)
CREATE TABLE IF NOT EXISTS polling_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL UNIQUE,
    last_poll_time DATETIME,
    total_issues_imported INTEGER NOT NULL DEFAULT 0,
    last_poll_issues_found INTEGER NOT NULL DEFAULT 0,
    last_poll_issues_linked INTEGER NOT NULL DEFAULT 0,
    last_poll_issues_skipped INTEGER NOT NULL DEFAULT 0,
    last_poll_status VARCHAR NOT NULL DEFAULT 'never',  -- 'success', 'error', 'never'
    last_poll_error TEXT,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_polling_status_workspace
ON polling_status(workspace_id);
