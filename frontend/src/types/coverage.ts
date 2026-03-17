/**
 * Phase 2: Coverage Analysis Type Definitions
 *
 * Types for coverage tracking, analysis, and visualization.
 */

export interface FileCoverageDetail {
  lines: number;
  lines_covered?: number;
  lines_total?: number;
  branches?: number;
}

export interface CoverageSnapshot {
  id: number;
  workspace_id: number;
  lines_covered: number;
  lines_total: number;
  coverage_percent: number;
  branches_covered?: number;
  branches_total?: number;
  branch_coverage_percent?: number;
  file_coverage: Record<string, Record<string, any>>;
  uncovered_lines: Record<string, number[]>;
  uncovered_functions: string[];
  commit_sha: string;
  branch_name: string;
  pr_number?: number;
  report_format?: string;
  report_path?: string;
  ci_run_id?: number;
  agent_test_generation_id?: number;
  created_at: string;
  coverage_grade: string;
}

export interface CoverageSnapshotCreate {
  workspace_id: number;
  coverage_percent: number;
  lines_covered: number;
  lines_total: number;
  branches_covered?: number;
  branches_total?: number;
  branch_coverage_percent?: number;
  file_coverage: Record<string, Record<string, any>>;
  uncovered_lines: Record<string, number[]>;
  uncovered_functions: string[];
  commit_sha: string;
  branch_name: string;
  pr_number?: number;
  report_format?: string;
  report_path?: string;
  ci_run_id?: number;
  agent_test_generation_id?: number;
}

export interface FileCoverageChange {
  path: string;
  delta: number;
  current: number;
  previous: number;
  status: 'improved' | 'regressed';
}

export interface CoverageDelta {
  delta_percent: number;
  delta_lines: number;
  previous_coverage: number;
  current_coverage: number;
  improved: boolean;
  improved_files: FileCoverageChange[];
  regressed_files: FileCoverageChange[];
}

export interface CoverageTrend {
  workspace_id: number;
  trend_direction: 'improving' | 'declining' | 'stable';
  average_coverage: number;
  min_coverage: number;
  max_coverage: number;
  total_change: number;
  days_tracked: number;
  snapshots_count: number;
  snapshots: CoverageSnapshot[];
}

export interface UncoveredFileDetail {
  path: string;
  uncovered_count: number;
  uncovered_lines: number[];
  coverage: number;
  priority_score: number;
}

export interface UncoveredCodeResponse {
  snapshot_id: number;
  total_uncovered_lines: number;
  files_with_gaps: number;
  priority_files: UncoveredFileDetail[];
  coverage_percent: number;
  coverage_grade: string;
}

export interface SnapshotComparison {
  snapshot1: Record<string, any>;
  snapshot2: Record<string, any>;
  overall_delta: number;
  lines_delta: number;
  status: 'improved' | 'regressed' | 'unchanged';
  file_changes: FileCoverageChange[];
  total_files_changed: number;
}
