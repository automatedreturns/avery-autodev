-- Migration: Add last_issue_poll column to workspaces table
-- Date: 2025-12-15
-- Description: Adds tracking for when issues were last polled from GitHub

-- Add last_issue_poll column if it doesn't exist
ALTER TABLE workspaces ADD COLUMN last_issue_poll DATETIME DEFAULT NULL;
