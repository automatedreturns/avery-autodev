-- Phase 2: Test-Aware Agent - Database Migration
-- Add test policy configuration and coverage tracking tables

-- 1. Add test policy configuration to workspaces table
ALTER TABLE workspaces ADD COLUMN test_policy_enabled BOOLEAN DEFAULT TRUE NOT NULL;
ALTER TABLE workspaces ADD COLUMN test_policy_config JSON DEFAULT '{"require_tests_for_features":true,"require_tests_for_bug_fixes":true,"minimum_coverage_percent":80.0,"allow_coverage_decrease":false,"max_coverage_decrease_percent":0.0,"require_edge_case_tests":true,"require_integration_tests":false,"test_quality_threshold":70.0,"auto_generate_tests":true,"test_frameworks":{"backend":"pytest","frontend":"jest"}}';

-- 2. Create agent_test_generations table
CREATE TABLE agent_test_generations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    agent_job_id INTEGER,
    ci_run_id INTEGER,

    -- Generation Context
    trigger_type VARCHAR(50) NOT NULL,
    source_files JSON DEFAULT '[]',
    generated_test_files JSON DEFAULT '[]',

    -- Status
    status VARCHAR(50) DEFAULT 'pending' NOT NULL,
    generation_method VARCHAR(50),

    -- Quality Metrics
    tests_generated_count INTEGER DEFAULT 0,
    tests_passed_count INTEGER DEFAULT 0,
    tests_failed_count INTEGER DEFAULT 0,
    test_quality_score REAL,

    -- Coverage Impact
    coverage_before REAL,
    coverage_after REAL,
    coverage_delta REAL,

    -- Validation
    validation_passed BOOLEAN DEFAULT FALSE,
    validation_errors JSON DEFAULT '[]',

    -- Resource Usage
    prompt_tokens_used INTEGER DEFAULT 0,
    completion_tokens_used INTEGER DEFAULT 0,
    duration_seconds REAL,

    -- Error Handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 2,

    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    completed_at DATETIME,

    -- Foreign Keys
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_job_id) REFERENCES agent_jobs(id) ON DELETE SET NULL,
    FOREIGN KEY (ci_run_id) REFERENCES ci_runs(id) ON DELETE SET NULL
);

-- 3. Create coverage_snapshots table
CREATE TABLE coverage_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    ci_run_id INTEGER,
    agent_test_generation_id INTEGER,

    -- Line Coverage
    lines_covered INTEGER NOT NULL,
    lines_total INTEGER NOT NULL,
    coverage_percent REAL NOT NULL,

    -- Branch Coverage
    branches_covered INTEGER,
    branches_total INTEGER,
    branch_coverage_percent REAL,

    -- File-level Coverage
    file_coverage JSON DEFAULT '{}',

    -- Uncovered Code
    uncovered_lines JSON DEFAULT '{}',
    uncovered_functions JSON DEFAULT '[]',

    -- Context
    commit_sha VARCHAR(40) NOT NULL,
    branch_name VARCHAR(255) NOT NULL,
    pr_number INTEGER,

    -- Report Details
    report_format VARCHAR(50),
    report_path VARCHAR(500),

    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,

    -- Foreign Keys
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (ci_run_id) REFERENCES ci_runs(id) ON DELETE SET NULL,
    FOREIGN KEY (agent_test_generation_id) REFERENCES agent_test_generations(id) ON DELETE SET NULL
);

-- 4. Create indexes for agent_test_generations
CREATE INDEX idx_agent_test_gen_workspace_id ON agent_test_generations(workspace_id);
CREATE INDEX idx_agent_test_gen_agent_job_id ON agent_test_generations(agent_job_id);
CREATE INDEX idx_agent_test_gen_status ON agent_test_generations(status);
CREATE INDEX idx_agent_test_gen_created_at ON agent_test_generations(created_at);
CREATE INDEX idx_agent_test_gen_workspace_created ON agent_test_generations(workspace_id, created_at);

-- 5. Create indexes for coverage_snapshots
CREATE INDEX idx_coverage_snapshot_workspace_id ON coverage_snapshots(workspace_id);
CREATE INDEX idx_coverage_snapshot_created_at ON coverage_snapshots(created_at);
CREATE INDEX idx_coverage_snapshot_workspace_created ON coverage_snapshots(workspace_id, created_at);
CREATE INDEX idx_coverage_snapshot_ci_run_id ON coverage_snapshots(ci_run_id);

-- 6. Create trigger for agent_test_generations updated_at
CREATE TRIGGER update_agent_test_gen_timestamp
AFTER UPDATE ON agent_test_generations
FOR EACH ROW
BEGIN
    UPDATE agent_test_generations SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

-- Migration Complete
-- Phase 2: Test-Aware Agent database schema is now ready
