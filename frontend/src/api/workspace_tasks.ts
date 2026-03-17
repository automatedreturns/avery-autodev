import type {
  WorkspaceTask,
  WorkspaceTaskListResponse,
  WorkspaceTaskCreate,
  AvailableIssuesResponse,
  FeatureRequestCreate,
  FeatureRequestResponse,
  SimilarIssuesSearch,
  SimilarIssuesResponse,
} from '../types/workspace_task';
import { api, handleApiError } from './client';

// Workspace Task API functions
export const listWorkspaceTasks = async (
  workspaceId: number,
  skip = 0,
  limit = 100
): Promise<WorkspaceTaskListResponse> => {
  try {
    const response = await api.get<WorkspaceTaskListResponse>(
      `/api/v1/workspaces/${workspaceId}/tasks`,
      { params: { skip, limit } }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const addWorkspaceTask = async (
  workspaceId: number,
  data: WorkspaceTaskCreate
): Promise<WorkspaceTask> => {
  try {
    const response = await api.post<WorkspaceTask>(
      `/api/v1/workspaces/${workspaceId}/tasks`,
      data
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const getWorkspaceTask = async (
  workspaceId: number,
  taskId: number
): Promise<WorkspaceTask> => {
  try {
    const response = await api.get<WorkspaceTask>(
      `/api/v1/workspaces/${workspaceId}/tasks/${taskId}`
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const removeWorkspaceTask = async (
  workspaceId: number,
  taskId: number
): Promise<void> => {
  try {
    await api.delete(`/api/v1/workspaces/${workspaceId}/tasks/${taskId}`);
  } catch (error) {
    return handleApiError(error);
  }
};

export const listAvailableIssues = async (
  workspaceId: number,
  state: 'open' | 'closed' | 'all' = 'open',
  page = 1,
  perPage = 50
): Promise<AvailableIssuesResponse> => {
  try {
    const response = await api.get<AvailableIssuesResponse>(
      `/api/v1/workspaces/${workspaceId}/available-issues`,
      { params: { state, page, per_page: perPage } }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export interface CreatePRResult {
  success: boolean;
  pr_number: number | null;
  pr_url: string | null;
  message: string;
}

export const createPullRequestFromTask = async (
  workspaceId: number,
  taskId: number,
  assigneeUsername?: string,
  draft: boolean = true
): Promise<CreatePRResult> => {
  try {
    const response = await api.post<CreatePRResult>(
      `/api/v1/workspaces/${workspaceId}/tasks/${taskId}/create-pr`,
      null,
      { params: { assignee_username: assigneeUsername, draft } }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const createFeatureRequest = async (
  workspaceId: number,
  data: FeatureRequestCreate
): Promise<FeatureRequestResponse> => {
  try {
    const response = await api.post<FeatureRequestResponse>(
      `/api/v1/workspaces/${workspaceId}/feature-requests`,
      data
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const searchSimilarIssues = async (
  workspaceId: number,
  search: SimilarIssuesSearch
): Promise<SimilarIssuesResponse> => {
  try {
    const response = await api.post<SimilarIssuesResponse>(
      `/api/v1/workspaces/${workspaceId}/search-similar-issues`,
      search
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export interface PullRequest {
  number: number;
  title: string;
  state: string;
  html_url: string;
  head_branch: string;
  base_branch: string;
  created_at: string;
  updated_at: string;
  labels: string[];
  draft: boolean;
  mergeable_state: string;
}

export interface PullRequestListResponse {
  repository: string;
  pull_requests: PullRequest[];
  total_count: number;
  has_next: boolean;
  error: string | null;
}

export const listPullRequests = async (
  workspaceId: number,
  state: 'open' | 'closed' | 'all' = 'open',
  page = 1,
  perPage = 50
): Promise<PullRequestListResponse> => {
  try {
    const response = await api.get<PullRequestListResponse>(
      `/api/v1/workspaces/${workspaceId}/pull-requests`,
      { params: { state, page, per_page: perPage } }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const linkPullRequestToWorkspace = async (
  workspaceId: number,
  prNumber: number
): Promise<WorkspaceTask> => {
  try {
    const response = await api.post<WorkspaceTask>(
      `/api/v1/workspaces/${workspaceId}/link-pr`,
      null,
      { params: { pr_number: prNumber } }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};
