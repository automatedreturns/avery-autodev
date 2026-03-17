/**
 * API client for CI run management
 */

import { api } from './client';
import type {
  CIRun,
  CIRunSummary,
  CIRunListParams,
  QualityGateResult,
  SelfFixRequest,
  SelfFixResponse,
  IssuePreview,
  CreateIssueRequest,
} from '../types/ci_run';

const CI_BASE_PATH = '/api/v1/ci';

/**
 * Get CI run details
 */
export const getCIRun = async (ciRunId: number): Promise<CIRun> => {
  const response = await api.get(`${CI_BASE_PATH}/runs/${ciRunId}`);
  return response.data;
};

/**
 * List CI runs for a workspace
 */
export const listCIRuns = async (
  workspaceId: number,
  params?: CIRunListParams
): Promise<CIRunSummary[]> => {
  const response = await api.get(`${CI_BASE_PATH}/workspaces/${workspaceId}/runs`, {
    params,
  });
  return response.data;
};

/**
 * Get quality gate evaluation for a CI run
 */
export const getQualityGate = async (ciRunId: number): Promise<QualityGateResult> => {
  const response = await api.get(`${CI_BASE_PATH}/runs/${ciRunId}/quality-gate`);
  return response.data;
};

/**
 * Get preview of GitHub issue that would be created
 */
export const getIssuePreview = async (
  ciRunId: number
): Promise<IssuePreview> => {
  const response = await api.get(`${CI_BASE_PATH}/runs/${ciRunId}/issue-preview`);
  return response.data;
};

/**
 * Create a GitHub issue for a failed CI run
 */
export const createGitHubIssue = async (
  ciRunId: number,
  request: CreateIssueRequest
): Promise<SelfFixResponse> => {
  const response = await api.post(`${CI_BASE_PATH}/runs/${ciRunId}/create-issue`, request);
  return response.data;
};

/**
 * Get CI run by PR number
 */
export const getCIRunsByPR = async (
  workspaceId: number,
  prNumber: number
): Promise<CIRunSummary[]> => {
  return listCIRuns(workspaceId, { pr_number: prNumber });
};

/**
 * Get recent CI runs
 */
export const getRecentCIRuns = async (
  workspaceId: number,
  limit: number = 10
): Promise<CIRunSummary[]> => {
  return listCIRuns(workspaceId, { limit });
};

/**
 * Trigger self-fix for a failed CI run
 */
export const triggerSelfFix = async (
  ciRunId: number,
  request: SelfFixRequest
): Promise<SelfFixResponse> => {
  const response = await api.post(`${CI_BASE_PATH}/runs/${ciRunId}/self-fix`, request);
  return response.data;
};
