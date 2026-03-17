/**
 * Test Suite API client
 */

import { api, handleApiError } from './client';
import type {
  TestSuite,
  TestSuiteCreate,
  TestSuiteUpdate,
  TestSuiteListResponse,
  TestCase,
  TestCaseCreate,
  TestCaseListResponse,
  TestRun,
  TestRunCreate,
  TestRunListResponse,
  TestResultListResponse,
  TestAnalysisRequest,
  TestAnalysisResponse,
  CoverageHistoryResponse,
  TestGenerationJob,
} from '../types/test_suite';

// Test Suite Management
export const createTestSuite = async (
  workspaceId: number,
  data: TestSuiteCreate
): Promise<TestSuite> => {
  try {
    const response = await api.post<TestSuite>(
      `/api/v1/workspaces/${workspaceId}/test-suites/`,
      data
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const listTestSuites = async (
  workspaceId: number,
  skip = 0,
  limit = 100
): Promise<TestSuiteListResponse> => {
  try {
    const response = await api.get<TestSuiteListResponse>(
      `/api/v1/workspaces/${workspaceId}/test-suites/`,
      { params: { skip, limit } }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const getTestSuite = async (
  workspaceId: number,
  suiteId: number
): Promise<TestSuite> => {
  try {
    const response = await api.get<TestSuite>(
      `/api/v1/workspaces/${workspaceId}/test-suites/${suiteId}`
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const updateTestSuite = async (
  workspaceId: number,
  suiteId: number,
  data: TestSuiteUpdate
): Promise<TestSuite> => {
  try {
    const response = await api.put<TestSuite>(
      `/api/v1/workspaces/${workspaceId}/test-suites/${suiteId}`,
      data
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const deleteTestSuite = async (
  workspaceId: number,
  suiteId: number
): Promise<void> => {
  try {
    await api.delete(`/api/v1/workspaces/${workspaceId}/test-suites/${suiteId}`);
  } catch (error) {
    return handleApiError(error);
  }
};

// Test Case Management
export const createTestCase = async (
  workspaceId: number,
  suiteId: number,
  data: TestCaseCreate
): Promise<TestCase> => {
  try {
    const response = await api.post<TestCase>(
      `/api/v1/workspaces/${workspaceId}/test-suites/${suiteId}/test-cases`,
      data
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const listTestCases = async (
  workspaceId: number,
  suiteId: number,
  skip = 0,
  limit = 100
): Promise<TestCaseListResponse> => {
  try {
    const response = await api.get<TestCaseListResponse>(
      `/api/v1/workspaces/${workspaceId}/test-suites/${suiteId}/test-cases`,
      { params: { skip, limit } }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

// Test Analysis
export const analyzeTests = async (
  workspaceId: number,
  suiteId: number,
  data: TestAnalysisRequest
): Promise<TestAnalysisResponse> => {
  try {
    const response = await api.post<TestAnalysisResponse>(
      `/api/v1/workspaces/${workspaceId}/test-suites/${suiteId}/analyze`,
      data
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const applySuggestions = async (
  workspaceId: number,
  suiteId: number,
  suggestedTests: any[]
): Promise<TestCaseListResponse> => {
  try {
    const response = await api.post<TestCaseListResponse>(
      `/api/v1/workspaces/${workspaceId}/test-suites/${suiteId}/apply-suggestions`,
      suggestedTests
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

// Test Execution
export const runTestSuite = async (
  workspaceId: number,
  suiteId: number,
  data: TestRunCreate
): Promise<TestRun> => {
  try {
    const response = await api.post<TestRun>(
      `/api/v1/workspaces/${workspaceId}/test-suites/${suiteId}/run`,
      data
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const listTestRuns = async (
  workspaceId: number,
  suiteId?: number,
  skip = 0,
  limit = 100
): Promise<TestRunListResponse> => {
  try {
    const params: any = { skip, limit };
    if (suiteId) params.suite_id = suiteId;

    const response = await api.get<TestRunListResponse>(
      `/api/v1/workspaces/${workspaceId}/test-runs`,
      { params }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const getTestRun = async (
  workspaceId: number,
  runId: number
): Promise<TestRun> => {
  try {
    const response = await api.get<TestRun>(
      `/api/v1/workspaces/${workspaceId}/test-runs/${runId}`
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const getTestRunStatus = async (
  workspaceId: number,
  runId: number
): Promise<TestRun> => {
  try {
    const response = await api.get<TestRun>(
      `/api/v1/workspaces/${workspaceId}/test-runs/${runId}/status`
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const getTestResults = async (
  workspaceId: number,
  runId: number,
  skip = 0,
  limit = 100
): Promise<TestResultListResponse> => {
  try {
    const response = await api.get<TestResultListResponse>(
      `/api/v1/workspaces/${workspaceId}/test-runs/${runId}/results`,
      { params: { skip, limit } }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

// Test Discovery
export const discoverTests = async (
  workspaceId: number,
  suiteId: number
): Promise<{ discovered_count: number; imported_count: number; skipped_count: number; tests: any[] }> => {
  try {
    const response = await api.post(
      `/api/v1/workspaces/${workspaceId}/test-suites/${suiteId}/discover-tests`
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

// Test Code Generation
export const generateTestCode = async (
  workspaceId: number,
  suiteId: number,
  testCaseIds?: number[]
): Promise<TestGenerationJob> => {
  try {
    const response = await api.post<TestGenerationJob>(
      `/api/v1/workspaces/${workspaceId}/test-suites/${suiteId}/generate-code`,
      testCaseIds ? { test_case_ids: testCaseIds } : {}
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const getTestGenerationJobStatus = async (
  workspaceId: number,
  jobId: number
): Promise<TestGenerationJob> => {
  try {
    const response = await api.get<TestGenerationJob>(
      `/api/v1/workspaces/${workspaceId}/test-generation-jobs/${jobId}`
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

// Coverage
export const getCoverageHistory = async (
  workspaceId: number,
  suiteId: number,
  limit = 10
): Promise<CoverageHistoryResponse> => {
  try {
    const response = await api.get<CoverageHistoryResponse>(
      `/api/v1/workspaces/${workspaceId}/test-suites/${suiteId}/coverage-history`,
      { params: { limit } }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};
