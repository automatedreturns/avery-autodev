-- Migration: Add polling_enabled column to workspaces
-- Date: 2025-12-15
-- Description: Adds a flag to enable/disable automatic issue polling per workspace

-- Add polling_enabled column (default to disabled for safety)
ALTER TABLE workspaces ADD COLUMN polling_enabled BOOLEAN NOT NULL DEFAULT 0;
