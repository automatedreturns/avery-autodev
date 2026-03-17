import type {
  Workspace,
  WorkspaceDetail,
  WorkspaceCreateData,
  WorkspaceUpdateData,
  WorkspaceListResponse,
  AddMemberData,
} from '../types/workspace';
import { api, handleApiError } from './client';

// Workspace API functions
export const createWorkspace = async (data: WorkspaceCreateData): Promise<Workspace> => {
  try {
    const response = await api.post<Workspace>('/api/v1/workspaces/', data);
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const listWorkspaces = async (skip = 0, limit = 100): Promise<WorkspaceListResponse> => {
  try {
    const response = await api.get<WorkspaceListResponse>('/api/v1/workspaces/', {
      params: { skip, limit },
    });
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const getWorkspace = async (id: number): Promise<WorkspaceDetail> => {
  try {
    const response = await api.get<WorkspaceDetail>(`/api/v1/workspaces/${id}`);
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const updateWorkspace = async (id: number, data: WorkspaceUpdateData): Promise<WorkspaceDetail> => {
  try {
    const response = await api.put<WorkspaceDetail>(`/api/v1/workspaces/${id}`, data);
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const deleteWorkspace = async (id: number): Promise<void> => {
  try {
    await api.delete(`/api/v1/workspaces/${id}`);
  } catch (error) {
    return handleApiError(error);
  }
};

export const addMember = async (workspaceId: number, data: AddMemberData): Promise<void> => {
  try {
    await api.post(`/api/v1/workspaces/${workspaceId}/members`, data);
  } catch (error) {
    return handleApiError(error);
  }
};

export const removeMember = async (workspaceId: number, userId: number): Promise<void> => {
  try {
    await api.delete(`/api/v1/workspaces/${workspaceId}/members/${userId}`);
  } catch (error) {
    return handleApiError(error);
  }
};

export const setDefaultWorkspace = async (workspaceId: number): Promise<{ workspace_id: number; is_default: boolean }> => {
  try {
    const response = await api.post<{ workspace_id: number; is_default: boolean }>(
      `/api/v1/workspaces/${workspaceId}/set-default`
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const togglePollingEnabled = async (workspaceId: number, enabled: boolean): Promise<{ workspace_id: number; polling_enabled: boolean }> => {
  try {
    const response = await api.patch<{ workspace_id: number; polling_enabled: boolean }>(
      `/api/v1/workspaces/${workspaceId}/polling-enabled`,
      null,
      { params: { enabled } }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const addWorkspaceMember = async (workspaceId: number, data: AddMemberData): Promise<void> => {
  try {
    await api.post(`/api/v1/workspaces/${workspaceId}/members`, data);
  } catch (error) {
    return handleApiError(error);
  }
};

export interface WorkflowSetupResult {
  status: 'created' | 'updated' | 'exists' | 'error';
  message: string;
  path: string;
  commit?: string;
}

export interface WorkflowSetupInstructions {
  workflow_path: string;
  secrets_to_add: Array<{
    name: string;
    value: string;
    description: string;
  }>;
  instructions: string[];
  webhook_url: string;
}

export interface WorkflowSetupResponse {
  workflow: WorkflowSetupResult;
  instructions: WorkflowSetupInstructions;
}

export const setupWorkflow = async (
  workspaceId: number,
  forceUpdate = false
): Promise<WorkflowSetupResponse> => {
  try {
    const response = await api.post<WorkflowSetupResponse>(
      `/api/v1/workspaces/${workspaceId}/setup-workflow`,
      null,
      { params: { force_update: forceUpdate } }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};
