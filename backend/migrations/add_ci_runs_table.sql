-- Migration: Add CI Runs table for GitHub Actions integration
-- Date: 2026-01-06
-- Description: Adds ci_runs table to track GitHub Actions CI/CD executions and enable agent self-fix

CREATE TABLE IF NOT EXISTS ci_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Related entities
    workspace_id INTEGER NOT NULL,
    agent_job_id INTEGER,

    -- GitHub information
    repository VARCHAR(500) NOT NULL,
    pr_number INTEGER NOT NULL,
    branch_name VARCHAR(255) NOT NULL,
    commit_sha VARCHAR(40) NOT NULL,

    -- GitHub Actions run information
    run_id VARCHAR(100) NOT NULL,
    job_name VARCHAR(200) NOT NULL,
    workflow_name VARCHAR(200) NOT NULL DEFAULT 'Agent PR Validation',

    -- Status tracking
    status VARCHAR(50) NOT NULL,
    conclusion VARCHAR(50),

    -- Timestamps
    started_at DATETIME,
    completed_at DATETIME,
    duration_seconds REAL,

    -- Results and logs
    logs_url TEXT,
    check_results JSON,
    error_summary TEXT,
    raw_logs TEXT,

    -- Test coverage
    coverage_before REAL,
    coverage_after REAL,
    coverage_delta REAL,
    coverage_report_url TEXT,

    -- Self-fix tracking
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    self_fix_attempted BOOLEAN NOT NULL DEFAULT 0,
    self_fix_successful BOOLEAN,

    -- Quality metrics
    tests_total INTEGER,
    tests_passed INTEGER,
    tests_failed INTEGER,
    tests_skipped INTEGER,
    lint_errors_count INTEGER,
    type_errors_count INTEGER,

    -- Audit
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Foreign keys
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_job_id) REFERENCES agent_jobs(id) ON DELETE CASCADE
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_ci_runs_workspace_id ON ci_runs(workspace_id);
CREATE INDEX IF NOT EXISTS idx_ci_runs_agent_job_id ON ci_runs(agent_job_id);
CREATE INDEX IF NOT EXISTS idx_ci_runs_pr_number ON ci_runs(pr_number);
CREATE INDEX IF NOT EXISTS idx_ci_runs_run_id ON ci_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_ci_runs_status ON ci_runs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_ci_runs_conclusion ON ci_runs(conclusion, created_at);
CREATE INDEX IF NOT EXISTS idx_ci_runs_workspace_pr ON ci_runs(workspace_id, pr_number);
CREATE INDEX IF NOT EXISTS idx_ci_runs_created_at ON ci_runs(created_at DESC);

-- Create trigger to update updated_at timestamp
CREATE TRIGGER IF NOT EXISTS update_ci_runs_timestamp
    AFTER UPDATE ON ci_runs
    BEGIN
        UPDATE ci_runs SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;
