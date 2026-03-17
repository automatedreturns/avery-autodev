/**
 * Phase 2: Test Generation Type Definitions
 *
 * Types for AI-powered test generation and validation.
 */

export type TestGenerationStatus = 'pending' | 'generating' | 'validating' | 'completed' | 'failed';

export type TriggerType = 'feature' | 'bug_fix' | 'manual' | 'regression' | 'refactor';

export type GenerationType = 'unit' | 'integration' | 'regression';

export interface AgentTestGeneration {
  id: number;
  workspace_id: number;
  agent_job_id?: number;
  ci_run_id?: number;
  trigger_type: TriggerType;
  source_files: string[];
  generated_test_files: string[];
  status: TestGenerationStatus;
  generation_method?: string;
  tests_generated_count: number;
  tests_passed_count: number;
  tests_failed_count: number;
  test_quality_score?: number;
  coverage_before?: number;
  coverage_after?: number;
  coverage_delta?: number;
  validation_passed: boolean;
  validation_errors: string[];
  prompt_tokens_used: number;
  completion_tokens_used: number;
  duration_seconds?: number;
  error_message?: string;
  retry_count: number;
  max_retries: number;
  agent_run_metadata: Record<string, any>;
  created_at: string;
  updated_at?: string;
  completed_at?: string;
}

export interface TestGenerationRequest {
  workspace_id: number;
  files: string[];
  generation_type: GenerationType;
  trigger_type: TriggerType;
  context?: string;
}

export interface TestGenerationStats {
  workspace_id: number;
  total_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  pending_jobs: number;
  in_progress_jobs: number;
  total_tests_generated: number;
  avg_quality_score: number;
  avg_coverage_delta: number;
}

export interface TestQualityMetrics {
  has_assertions: boolean;
  assertion_count: number;
  has_edge_cases: boolean;
  edge_case_count: number;
  has_mocking: boolean;
  mock_count: number;
  has_error_handling: boolean;
  error_case_count: number;
  line_count: number;
}

export interface TestQualityValidation {
  quality_score: number;
  metrics: TestQualityMetrics;
  passed: boolean;
  threshold: number;
  suggestions: string[];
}

export interface BatchTestGenerationRequest {
  workspace_id: number;
  requests: TestGenerationRequest[];
}

export interface BatchTestGenerationResponse {
  workspace_id: number;
  job_ids: number[];
  total_jobs: number;
}

export interface TestGenerationListResponse {
  items: AgentTestGeneration[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}
