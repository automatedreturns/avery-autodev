/**
 * Phase 2: Test Policy Type Definitions
 *
 * Types for test policy configuration and enforcement.
 */

export interface TestFrameworksConfig {
  backend: string;
  frontend: string;
}

export interface TestPolicyConfig {
  require_tests_for_features: boolean;
  require_tests_for_bug_fixes: boolean;
  minimum_coverage_percent: number;
  allow_coverage_decrease: boolean;
  max_coverage_decrease_percent: number;
  require_edge_case_tests: boolean;
  require_integration_tests: boolean;
  test_quality_threshold: number;
  auto_generate_tests: boolean;
  test_frameworks: TestFrameworksConfig;
}

export interface TestPolicyResponse {
  workspace_id: number;
  test_policy_enabled: boolean;
  test_policy_config: TestPolicyConfig;
}

export interface TestPolicyUpdate {
  require_tests_for_features?: boolean;
  require_tests_for_bug_fixes?: boolean;
  minimum_coverage_percent?: number;
  allow_coverage_decrease?: boolean;
  max_coverage_decrease_percent?: number;
  require_edge_case_tests?: boolean;
  require_integration_tests?: boolean;
  test_quality_threshold?: number;
  auto_generate_tests?: boolean;
  test_frameworks?: TestFrameworksConfig;
}

export interface PolicyViolation {
  rule: string;
  severity: 'error' | 'warning' | 'info';
  message: string;
  current_value: any;
  expected_value: any;
  fix_suggestion: string;
  affected_files: string[];
}

export interface PolicyDecision {
  passed: boolean;
  violations: PolicyViolation[];
  warnings: PolicyViolation[];
  info: PolicyViolation[];
  summary: string;
  coverage_percent?: number;
  test_quality_score?: number;
  tests_generated?: number;
}

export interface PolicyRecommendation {
  priority: number;
  type: string;
  title: string;
  description: string;
  action: string;
  file?: string;
  lines?: number[];
}

export interface PolicyRecommendationsResponse {
  workspace_id: number;
  snapshot_id: number;
  recommendations: PolicyRecommendation[];
  total_recommendations: number;
}
