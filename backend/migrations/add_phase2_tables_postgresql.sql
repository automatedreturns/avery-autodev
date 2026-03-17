-- Phase 2: Test-Aware Agent - PostgreSQL Migration
-- Add test policy configuration and coverage tracking tables
-- Compatible with PostgreSQL production database

-- 1. Add test policy configuration to workspaces table
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS test_policy_enabled BOOLEAN DEFAULT TRUE NOT NULL;
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS test_policy_config JSONB DEFAULT '{"require_tests_for_features":true,"require_tests_for_bug_fixes":true,"minimum_coverage_percent":80.0,"allow_coverage_decrease":false,"max_coverage_decrease_percent":0.0,"require_edge_case_tests":true,"require_integration_tests":false,"test_quality_threshold":70.0,"auto_generate_tests":true,"test_frameworks":{"backend":"pytest","frontend":"jest"}}'::jsonb;

-- 2. Create agent_test_generations table
CREATE TABLE IF NOT EXISTS agent_test_generations (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL,
    agent_job_id INTEGER,
    ci_run_id INTEGER,

    -- Generation Context
    trigger_type VARCHAR(50) NOT NULL,
    source_files JSONB DEFAULT '[]'::jsonb,
    generated_test_files JSONB DEFAULT '[]'::jsonb,

    -- Status
    status VARCHAR(50) DEFAULT 'pending' NOT NULL,
    generation_method VARCHAR(50),

    -- Quality Metrics
    tests_generated_count INTEGER DEFAULT 0,
    tests_passed_count INTEGER DEFAULT 0,
    tests_failed_count INTEGER DEFAULT 0,
    test_quality_score NUMERIC(5,2),

    -- Coverage Impact
    coverage_before NUMERIC(5,2),
    coverage_after NUMERIC(5,2),
    coverage_delta NUMERIC(5,2),

    -- Validation
    validation_passed BOOLEAN DEFAULT FALSE,
    validation_errors JSONB DEFAULT '[]'::jsonb,

    -- Resource Usage
    prompt_tokens_used INTEGER DEFAULT 0,
    completion_tokens_used INTEGER DEFAULT 0,
    duration_seconds NUMERIC(10,2),

    -- Error Handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 2,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,

    -- Foreign Keys
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_job_id) REFERENCES agent_jobs(id) ON DELETE SET NULL,
    FOREIGN KEY (ci_run_id) REFERENCES ci_runs(id) ON DELETE SET NULL
);

-- 3. Create coverage_snapshots table
CREATE TABLE IF NOT EXISTS coverage_snapshots (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL,
    ci_run_id INTEGER,
    agent_test_generation_id INTEGER,

    -- Line Coverage
    lines_covered INTEGER NOT NULL,
    lines_total INTEGER NOT NULL,
    coverage_percent NUMERIC(5,2) NOT NULL,

    -- Branch Coverage
    branches_covered INTEGER,
    branches_total INTEGER,
    branch_coverage_percent NUMERIC(5,2),

    -- File-level Coverage
    file_coverage JSONB DEFAULT '{}'::jsonb,

    -- Uncovered Code
    uncovered_lines JSONB DEFAULT '{}'::jsonb,
    uncovered_functions JSONB DEFAULT '[]'::jsonb,

    -- Context
    commit_sha VARCHAR(40) NOT NULL,
    branch_name VARCHAR(255) NOT NULL,
    pr_number INTEGER,

    -- Report Details
    report_format VARCHAR(50),
    report_path VARCHAR(500),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

    -- Foreign Keys
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (ci_run_id) REFERENCES ci_runs(id) ON DELETE SET NULL,
    FOREIGN KEY (agent_test_generation_id) REFERENCES agent_test_generations(id) ON DELETE SET NULL
);

-- 4. Create indexes for agent_test_generations
CREATE INDEX IF NOT EXISTS idx_agent_test_gen_workspace_id ON agent_test_generations(workspace_id);
CREATE INDEX IF NOT EXISTS idx_agent_test_gen_agent_job_id ON agent_test_generations(agent_job_id);
CREATE INDEX IF NOT EXISTS idx_agent_test_gen_status ON agent_test_generations(status);
CREATE INDEX IF NOT EXISTS idx_agent_test_gen_created_at ON agent_test_generations(created_at);
CREATE INDEX IF NOT EXISTS idx_agent_test_gen_workspace_created ON agent_test_generations(workspace_id, created_at);

-- 5. Create indexes for coverage_snapshots
CREATE INDEX IF NOT EXISTS idx_coverage_snapshot_workspace_id ON coverage_snapshots(workspace_id);
CREATE INDEX IF NOT EXISTS idx_coverage_snapshot_created_at ON coverage_snapshots(created_at);
CREATE INDEX IF NOT EXISTS idx_coverage_snapshot_workspace_created ON coverage_snapshots(workspace_id, created_at);
CREATE INDEX IF NOT EXISTS idx_coverage_snapshot_ci_run_id ON coverage_snapshots(ci_run_id);
CREATE INDEX IF NOT EXISTS idx_coverage_snapshot_pr_number ON coverage_snapshots(pr_number);
CREATE INDEX IF NOT EXISTS idx_coverage_snapshot_branch ON coverage_snapshots(branch_name);

-- 6. Create function and trigger for agent_test_generations updated_at
CREATE OR REPLACE FUNCTION update_agent_test_gen_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_agent_test_gen_timestamp ON agent_test_generations;
CREATE TRIGGER update_agent_test_gen_timestamp
BEFORE UPDATE ON agent_test_generations
FOR EACH ROW
EXECUTE FUNCTION update_agent_test_gen_timestamp();

-- 7. Add coverage_grade computed column
-- Note: PostgreSQL doesn't support GENERATED ALWAYS with CASE directly in ALTER TABLE
-- So we'll add a regular column and use a trigger
ALTER TABLE coverage_snapshots ADD COLUMN IF NOT EXISTS coverage_grade VARCHAR(2);

CREATE OR REPLACE FUNCTION calculate_coverage_grade()
RETURNS TRIGGER AS $$
BEGIN
    NEW.coverage_grade := CASE
        WHEN NEW.coverage_percent >= 90 THEN 'A'
        WHEN NEW.coverage_percent >= 80 THEN 'B'
        WHEN NEW.coverage_percent >= 70 THEN 'C'
        WHEN NEW.coverage_percent >= 60 THEN 'D'
        ELSE 'F'
    END;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS calculate_coverage_grade_trigger ON coverage_snapshots;
CREATE TRIGGER calculate_coverage_grade_trigger
BEFORE INSERT OR UPDATE OF coverage_percent ON coverage_snapshots
FOR EACH ROW
EXECUTE FUNCTION calculate_coverage_grade();

-- 8. Add helpful comments to tables
COMMENT ON TABLE agent_test_generations IS 'Tracks AI-generated test generation jobs and their outcomes';
COMMENT ON TABLE coverage_snapshots IS 'Stores test coverage snapshots from CI runs and test generation';
COMMENT ON COLUMN workspaces.test_policy_enabled IS 'Whether test policy enforcement is enabled for this workspace';
COMMENT ON COLUMN workspaces.test_policy_config IS 'JSON configuration for test policy requirements and thresholds';

-- Migration Complete
-- Phase 2: Test-Aware Agent PostgreSQL schema is now ready
-- Next: Run alembic migration for policy integration fields (b8f3d9e5c2a1)
