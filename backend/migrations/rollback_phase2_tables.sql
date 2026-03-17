-- Phase 2: Test-Aware Agent - Rollback Migration
-- Remove test policy configuration and coverage tracking tables

-- 1. Drop trigger
DROP TRIGGER IF EXISTS update_agent_test_gen_timestamp;

-- 2. Drop indexes for coverage_snapshots
DROP INDEX IF EXISTS idx_coverage_snapshot_workspace_id;
DROP INDEX IF EXISTS idx_coverage_snapshot_created_at;
DROP INDEX IF EXISTS idx_coverage_snapshot_workspace_created;
DROP INDEX IF EXISTS idx_coverage_snapshot_ci_run_id;

-- 3. Drop indexes for agent_test_generations
DROP INDEX IF EXISTS idx_agent_test_gen_workspace_id;
DROP INDEX IF EXISTS idx_agent_test_gen_agent_job_id;
DROP INDEX IF EXISTS idx_agent_test_gen_status;
DROP INDEX IF EXISTS idx_agent_test_gen_created_at;
DROP INDEX IF EXISTS idx_agent_test_gen_workspace_created;

-- 4. Drop coverage_snapshots table
DROP TABLE IF EXISTS coverage_snapshots;

-- 5. Drop agent_test_generations table
DROP TABLE IF EXISTS agent_test_generations;

-- 6. Remove test policy columns from workspaces
-- Note: SQLite doesn't support DROP COLUMN, so you would need to:
-- a) Create a new table without these columns
-- b) Copy data from old table
-- c) Drop old table
-- d) Rename new table

-- For SQLite, a complete rollback requires manual intervention:
-- CREATE TABLE workspaces_new (...);  -- Without test_policy_enabled and test_policy_config
-- INSERT INTO workspaces_new SELECT id, name, description, ... FROM workspaces;
-- DROP TABLE workspaces;
-- ALTER TABLE workspaces_new RENAME TO workspaces;

-- WARNING: The above workspace column removal is not included in this script
-- to avoid accidental data loss. If you need to remove the columns,
-- please run the commands manually with caution.

-- Rollback Complete
-- Phase 2 tables have been removed
