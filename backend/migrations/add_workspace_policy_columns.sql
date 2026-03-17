-- Phase 2: Add test policy columns to workspaces table
-- This migration only adds the missing workspace columns
-- The agent_test_generations and coverage_snapshots tables already exist via SQLAlchemy

-- 1. Add test_policy_enabled column
ALTER TABLE workspaces ADD COLUMN test_policy_enabled BOOLEAN DEFAULT TRUE NOT NULL;

-- 2. Add test_policy_config column with default policy
ALTER TABLE workspaces ADD COLUMN test_policy_config JSON DEFAULT '{"require_tests_for_features":true,"require_tests_for_bug_fixes":true,"minimum_coverage_percent":80.0,"allow_coverage_decrease":false,"max_coverage_decrease_percent":0.0,"require_edge_case_tests":true,"require_integration_tests":false,"test_quality_threshold":70.0,"auto_generate_tests":true,"test_frameworks":{"backend":"pytest","frontend":"jest"}}';

-- Verify columns were added
-- Run: PRAGMA table_info(workspaces);
