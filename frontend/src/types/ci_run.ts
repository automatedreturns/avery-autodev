/**
 * TypeScript types for CI run management
 */

export interface CIRun {
  id: number;
  workspace_id: number;
  agent_job_id: number | null;
  repository: string;
  pr_number: number;
  branch_name: string;
  commit_sha: string;
  run_id: string;
  job_name: string;
  workflow_name: string;
  status: CIRunStatus;
  conclusion: CIRunConclusion | null;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  logs_url: string | null;
  check_results: Record<string, string> | null;
  error_summary: string | null;
  coverage_before: number | null;
  coverage_after: number | null;
  coverage_delta: number | null;
  retry_count: number;
  max_retries: number;
  self_fix_attempted: boolean;
  self_fix_successful: boolean | null;
  tests_total: number | null;
  tests_passed: number | null;
  tests_failed: number | null;
  tests_skipped: number | null;
  lint_errors_count: number | null;
  type_errors_count: number | null;
  created_at: string;
  updated_at: string;
}

export interface CIRunSummary {
  id: number;
  pr_number: number;
  job_name: string;
  status: CIRunStatus;
  conclusion: CIRunConclusion | null;
  duration_seconds: number | null;
  tests_passed: number | null;
  tests_failed: number | null;
  coverage_delta: number | null;
  self_fix_attempted: boolean;
  created_at: string;
}

export interface QualityGateResult {
  passed: boolean;
  pr_number: number;
  checks: Record<string, boolean>;
  violations: string[];
  coverage_delta: number | null;
  recommendation: QualityGateRecommendation;
}

export interface SelfFixRequest {
  ci_run_id: number;
  force?: boolean;
}

export interface SelfFixResponse {
  success: boolean;
  ci_run_id: number;
  retry_count: number;
  message: string;
  new_commit_sha?: string;
  fixes_applied?: Array<{
    file: string;
    changes: string;
  }>;
  issue_url?: string;
  issue_number?: number;
}

export interface IssuePreview {
  title: string;
  body: string;
  labels: string[];
  ci_run_id: number;
}

export interface CreateIssueRequest {
  title: string;
  body: string;
  labels?: string[];
}

export type CIRunStatus = "queued" | "in_progress" | "completed";
export type CIRunConclusion = "success" | "failure" | "cancelled" | "skipped";
export type QualityGateRecommendation = "approve" | "needs_review" | "request_changes";

export interface CIRunListParams {
  pr_number?: number;
  status?: CIRunStatus;
  limit?: number;
}

export interface CIRunMetrics {
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  self_fix_attempts: number;
  self_fix_successes: number;
  self_fix_rate: number;
  average_duration: number;
}
