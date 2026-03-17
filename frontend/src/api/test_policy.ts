/**
 * Phase 2: Test Policy API Client
 *
 * API functions for test policy configuration and management.
 */

import type {
  TestPolicyResponse,
  TestPolicyUpdate,
} from '../types/test_policy';
import { api, handleApiError } from './client';

/**
 * Get test policy configuration for a workspace.
 */
export const getTestPolicy = async (workspaceId: number): Promise<TestPolicyResponse> => {
  try {
    const response = await api.get<TestPolicyResponse>(
      `/api/v1/workspaces/${workspaceId}/test-policy`
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

/**
 * Update test policy configuration for a workspace.
 */
export const updateTestPolicy = async (
  workspaceId: number,
  data: TestPolicyUpdate
): Promise<TestPolicyResponse> => {
  try {
    const response = await api.put<TestPolicyResponse>(
      `/api/v1/workspaces/${workspaceId}/test-policy`,
      data
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

/**
 * Toggle test policy enforcement for a workspace.
 */
export const toggleTestPolicyEnabled = async (
  workspaceId: number,
  enabled: boolean
): Promise<TestPolicyResponse> => {
  try {
    const response = await api.patch<TestPolicyResponse>(
      `/api/v1/workspaces/${workspaceId}/test-policy/enabled`,
      null,
      { params: { enabled } }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};
