/**
 * Phase 2: Test Generation API Client
 *
 * API functions for AI-powered test generation and validation.
 */

import type {
  AgentTestGeneration,
  TestGenerationRequest,
  TestGenerationStats,
  TestQualityValidation,
  BatchTestGenerationRequest,
  BatchTestGenerationResponse,
  TestGenerationListResponse,
  TestGenerationStatus,
  TriggerType,
} from '../types/test_generation';
import { api, handleApiError } from './client';

/**
 * Create a new test generation job.
 */
export const createTestGenerationJob = async (
  data: TestGenerationRequest
): Promise<AgentTestGeneration> => {
  try {
    const response = await api.post<AgentTestGeneration>('/api/v1/test-generation', data);
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

/**
 * Get a specific test generation job.
 */
export const getTestGenerationJob = async (jobId: number): Promise<AgentTestGeneration> => {
  try {
    const response = await api.get<AgentTestGeneration>(`/api/v1/test-generation/${jobId}`);
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

/**
 * List test generation jobs for a workspace.
 */
export const listTestGenerationJobs = async (
  workspaceId: number,
  status?: TestGenerationStatus,
  triggerType?: TriggerType,
  limit = 50
): Promise<TestGenerationListResponse> => {
  try {
    const params: Record<string, any> = { limit };
    if (status) {
      params.status = status;
    }
    if (triggerType) {
      params.trigger_type = triggerType;
    }

    const response = await api.get<TestGenerationListResponse>(
      `/api/v1/test-generation/workspaces/${workspaceId}/jobs`,
      { params }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

/**
 * Update a test generation job (for agent workflows).
 */
export const updateTestGenerationJob = async (
  jobId: number,
  data: Partial<AgentTestGeneration>
): Promise<AgentTestGeneration> => {
  try {
    const response = await api.patch<AgentTestGeneration>(
      `/api/v1/test-generation/${jobId}`,
      data
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

/**
 * Retry a failed test generation job.
 */
export const retryTestGeneration = async (
  jobId: number,
  context?: string
): Promise<AgentTestGeneration> => {
  try {
    const response = await api.post<AgentTestGeneration>(
      `/api/v1/test-generation/${jobId}/retry`,
      { context }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

/**
 * Create multiple test generation jobs in a batch.
 */
export const createBatchTestGeneration = async (
  data: BatchTestGenerationRequest
): Promise<BatchTestGenerationResponse> => {
  try {
    const response = await api.post<BatchTestGenerationResponse>(
      '/api/v1/test-generation/batch',
      data
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

/**
 * Get test generation statistics for a workspace.
 */
export const getTestGenerationStats = async (
  workspaceId: number,
  days?: number
): Promise<TestGenerationStats> => {
  try {
    const data: Record<string, any> = { workspace_id: workspaceId };
    if (days) {
      data.days = days;
    }

    const response = await api.post<TestGenerationStats>('/api/v1/test-generation/stats', data);
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

/**
 * Validate the quality of generated tests.
 */
export const validateTestQuality = async (jobId: number): Promise<TestQualityValidation> => {
  try {
    const response = await api.post<TestQualityValidation>(
      `/api/v1/test-generation/${jobId}/validate`
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};
