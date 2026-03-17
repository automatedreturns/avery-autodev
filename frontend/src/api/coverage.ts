/**
 * Phase 2: Coverage Analysis API Client
 *
 * API functions for coverage tracking, analysis, and visualization.
 */

import type {
  CoverageSnapshot,
  CoverageSnapshotCreate,
  CoverageDelta,
  CoverageTrend,
  UncoveredCodeResponse,
  SnapshotComparison,
} from '../types/coverage';
import type {
  PolicyDecision,
  PolicyRecommendationsResponse,
} from '../types/test_policy';
import { api, handleApiError } from './client';

/**
 * Create a new coverage snapshot.
 */
export const createCoverageSnapshot = async (
  data: CoverageSnapshotCreate
): Promise<CoverageSnapshot> => {
  try {
    const response = await api.post<CoverageSnapshot>('/api/v1/coverage/snapshots', data);
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

/**
 * Get a specific coverage snapshot.
 */
export const getCoverageSnapshot = async (snapshotId: number): Promise<CoverageSnapshot> => {
  try {
    const response = await api.get<CoverageSnapshot>(`/api/v1/coverage/snapshots/${snapshotId}`);
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

/**
 * List coverage snapshots for a workspace.
 */
export const listCoverageSnapshots = async (
  workspaceId: number,
  branchName?: string,
  limit = 50
): Promise<CoverageSnapshot[]> => {
  try {
    const params: Record<string, any> = { limit };
    if (branchName) {
      params.branch_name = branchName;
    }

    const response = await api.get<CoverageSnapshot[]>(
      `/api/v1/coverage/workspaces/${workspaceId}/snapshots`,
      { params }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

/**
 * Calculate coverage delta between two snapshots.
 */
export const calculateCoverageDelta = async (
  currentSnapshotId: number,
  previousSnapshotId?: number
): Promise<CoverageDelta> => {
  try {
    const response = await api.post<CoverageDelta>('/api/v1/coverage/delta', {
      current_snapshot_id: currentSnapshotId,
      previous_snapshot_id: previousSnapshotId,
    });
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

/**
 * Compare two coverage snapshots in detail.
 */
export const compareSnapshots = async (
  snapshotId1: number,
  snapshotId2: number
): Promise<SnapshotComparison> => {
  try {
    const response = await api.post<SnapshotComparison>('/api/v1/coverage/compare', {
      snapshot_id_1: snapshotId1,
      snapshot_id_2: snapshotId2,
    });
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

/**
 * Analyze coverage trend over time.
 */
export const analyzeCoverageTrend = async (
  workspaceId: number,
  days = 30,
  branchName?: string
): Promise<CoverageTrend> => {
  try {
    const data: Record<string, any> = { workspace_id: workspaceId, days };
    if (branchName) {
      data.branch_name = branchName;
    }

    const response = await api.post<CoverageTrend>('/api/v1/coverage/trend', data);
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

/**
 * Identify uncovered code in a snapshot.
 */
export const identifyUncoveredCode = async (
  snapshotId: number,
  maxFiles = 10,
  maxLinesPerFile = 20
): Promise<UncoveredCodeResponse> => {
  try {
    const response = await api.post<UncoveredCodeResponse>('/api/v1/coverage/uncovered', {
      snapshot_id: snapshotId,
      max_files: maxFiles,
      max_lines_per_file: maxLinesPerFile,
    });
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

/**
 * Get uncovered files for a workspace (uses latest coverage snapshot).
 */
export const getWorkspaceUncoveredFiles = async (
  workspaceId: number,
  maxFiles = 20,
  maxLinesPerFile = 50
): Promise<UncoveredCodeResponse> => {
  try {
    const response = await api.get<UncoveredCodeResponse>(
      `/api/v1/coverage/workspaces/${workspaceId}/uncovered-files`,
      {
        params: {
          max_files: maxFiles,
          max_lines_per_file: maxLinesPerFile,
        },
      }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

/**
 * Check test policies for a coverage snapshot.
 */
export const checkPolicies = async (
  workspaceId: number,
  currentSnapshotId: number,
  testGenerationId?: number,
  changeType?: string
): Promise<PolicyDecision> => {
  try {
    const data: Record<string, any> = {
      workspace_id: workspaceId,
      current_snapshot_id: currentSnapshotId,
    };

    if (testGenerationId) {
      data.test_generation_id = testGenerationId;
    }
    if (changeType) {
      data.change_type = changeType;
    }

    const response = await api.post<PolicyDecision>('/api/v1/coverage/check-policies', data);
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

/**
 * Get policy recommendations for a coverage snapshot.
 */
export const getPolicyRecommendations = async (
  snapshotId: number
): Promise<PolicyRecommendationsResponse> => {
  try {
    const response = await api.get<PolicyRecommendationsResponse>(
      `/api/v1/coverage/snapshots/${snapshotId}/recommendations`
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};
