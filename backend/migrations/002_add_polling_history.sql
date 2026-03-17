-- Migration: Add polling_history table
-- Date: 2025-12-15
-- Description: Creates table to track automatic issue polling and linking events

-- Create polling_history table
CREATE TABLE IF NOT EXISTS polling_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    issues_found INTEGER NOT NULL DEFAULT 0,
    issues_linked INTEGER NOT NULL DEFAULT 0,
    issues_skipped INTEGER NOT NULL DEFAULT 0,
    success VARCHAR NOT NULL,
    error_message TEXT,
    linked_issue_numbers TEXT,
    triggered_by VARCHAR NOT NULL,
    polled_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_polling_history_workspace
ON polling_history(workspace_id, polled_at DESC);
