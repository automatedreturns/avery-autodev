/**
 * Test Suite types and interfaces
 */

export interface TestSuite {
  id: number;
  workspace_id: number;
  name: string;
  description: string | null;
  test_framework: string;
  test_directory: string;
  coverage_threshold: number;
  is_active: boolean;
  created_by: number;
  created_at: string;
  updated_at: string;
  test_case_count: number;
  last_run: string | null;
}

export interface TestSuiteCreate {
  name: string;
  description?: string;
  test_framework: string;
  test_directory: string;
  coverage_threshold?: number;
  is_active?: boolean;
}

export interface TestSuiteUpdate {
  name?: string;
  description?: string;
  test_framework?: string;
  test_directory?: string;
  coverage_threshold?: number;
  is_active?: boolean;
}

export interface TestCase {
  id: number;
  test_suite_id: number;
  file_path: string;
  test_name: string;
  test_type: string;
  description: string | null;
  mock_data: Record<string, any> | null;
  assertions: Record<string, any> | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface TestCaseCreate {
  file_path: string;
  test_name: string;
  test_type: string;
  description?: string;
  mock_data?: Record<string, any>;
  assertions?: Record<string, any>;
  status?: string;
}

export interface TestRun {
  id: number;
  test_suite_id: number;
  workspace_task_id: number | null;
  branch_name: string;
  trigger_type: string;
  status: string;
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  skipped_tests: number;
  duration_seconds: number | null;
  coverage_percentage: number | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  triggered_by: number;
  created_at: string;
}

export interface TestRunCreate {
  branch_name?: string;
  trigger_type?: string;
  workspace_task_id?: number;
}

export interface TestResult {
  id: number;
  test_run_id: number;
  test_case_id: number | null;
  test_name: string;
  file_path: string;
  status: string;
  duration_seconds: number | null;
  error_message: string | null;
  stack_trace: string | null;
  output: string | null;
  created_at: string;
}

export interface TestAnalysisRequest {
  file_paths?: string[];
  focus_areas?: string[];
}

export interface GeneratedTestCase {
  file_path: string;
  test_name: string;
  test_type: string;
  description: string;
  mock_data: Record<string, any> | null;
  assertions: Record<string, any> | null;
  reasoning: string;
}

export interface TestAnalysisResponse {
  analysis_summary: string;
  suggested_tests: GeneratedTestCase[];
  coverage_gaps: string[];
  recommendations: string[];
}

export interface CoverageHistory {
  test_run_id: number;
  coverage_percentage: number;
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  branch_name: string;
  created_at: string;
}

export interface TestSuiteListResponse {
  test_suites: TestSuite[];
  total: number;
}

export interface TestCaseListResponse {
  test_cases: TestCase[];
  total: number;
}

export interface TestRunListResponse {
  test_runs: TestRun[];
  total: number;
}

export interface TestResultListResponse {
  test_results: TestResult[];
  total: number;
}

export interface CoverageHistoryResponse {
  history: CoverageHistory[];
  total: number;
}

export interface TestGenerationJob {
  id: number;
  workspace_id: number;
  test_suite_id: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  total_tests: number;
  completed_tests: number;
  current_test_name: string | null;
  current_stage: 'pending' | 'cloning' | 'generating' | 'committing' | 'pushing' | 'completed';
  branch_name: string | null;
  base_branch: string | null;
  generated_files: string[] | null;
  pr_url: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}
