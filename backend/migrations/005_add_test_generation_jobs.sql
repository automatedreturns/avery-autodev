-- Add test_generation_jobs table for tracking code generation progress
CREATE TABLE IF NOT EXISTS test_generation_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    test_suite_id INTEGER NOT NULL,
    created_by INTEGER NOT NULL,

    -- Job status: pending, running, completed, failed
    status VARCHAR(50) NOT NULL DEFAULT 'pending',

    -- Progress tracking
    total_tests INTEGER NOT NULL DEFAULT 0,
    completed_tests INTEGER NOT NULL DEFAULT 0,
    current_test_name VARCHAR(255),

    -- Current stage: pending, cloning, generating, committing, pushing, completed
    current_stage VARCHAR(50) NOT NULL DEFAULT 'pending',

    -- Results
    branch_name VARCHAR(255),
    base_branch VARCHAR(255),
    generated_files TEXT, -- JSON array of file paths
    pr_url VARCHAR(500),

    -- Error tracking
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- Foreign keys
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (test_suite_id) REFERENCES test_suites(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_test_generation_jobs_workspace ON test_generation_jobs(workspace_id);
CREATE INDEX IF NOT EXISTS idx_test_generation_jobs_suite ON test_generation_jobs(test_suite_id);
CREATE INDEX IF NOT EXISTS idx_test_generation_jobs_status ON test_generation_jobs(status);
