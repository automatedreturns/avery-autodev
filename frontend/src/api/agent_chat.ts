import type {
  AgentMessage,
  AgentMessageCreate,
  AgentMessageListResponse,
} from '../types/agent_message';
import { api, handleApiError } from './client';

// Agent Chat API functions
export const listChatMessages = async (
  workspaceId: number,
  taskId: number,
  skip = 0,
  limit = 1000  // Increased to handle tasks with many progress messages
): Promise<AgentMessageListResponse> => {
  try {
    const response = await api.get<AgentMessageListResponse>(
      `/api/v1/workspaces/${workspaceId}/tasks/${taskId}/chat/messages`,
      { params: { skip, limit } }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const sendChatMessage = async (
  workspaceId: number,
  taskId: number,
  data: AgentMessageCreate,
  files?: File[]
): Promise<AgentMessage> => {
  try {
    // Always send as multipart/form-data (backend expects Form data)
    const formData = new FormData();
    formData.append('content', data.content);

    // Append files if provided
    if (files && files.length > 0) {
      files.forEach((file) => {
        formData.append('files', file);
      });
    }

    // Must explicitly delete Content-Type to override the default 'application/json'
    // from api client. Axios will then auto-set multipart/form-data with boundary.
    const response = await api.post<AgentMessage>(
      `/api/v1/workspaces/${workspaceId}/tasks/${taskId}/chat/messages`,
      formData,
      {
        headers: {
          'Content-Type': undefined,
        },
      }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const clearChatHistory = async (
  workspaceId: number,
  taskId: number
): Promise<void> => {
  try {
    await api.delete(
      `/api/v1/workspaces/${workspaceId}/tasks/${taskId}/chat/messages`
    );
  } catch (error) {
    return handleApiError(error);
  }
};

export const cancelAgentExecution = async (
  workspaceId: number,
  taskId: number
): Promise<{ message: string }> => {
  try {
    const response = await api.post<{ message: string }>(
      `/api/v1/workspaces/${workspaceId}/tasks/${taskId}/chat/cancel`
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export interface CompactSessionResponse {
  message: string;
  previous_session_id: string | null;
  summary_length: number;
  summary_preview: string;
}

export const compactChatSession = async (
  workspaceId: number,
  taskId: number
): Promise<CompactSessionResponse> => {
  try {
    const response = await api.post<CompactSessionResponse>(
      `/api/v1/workspaces/${workspaceId}/tasks/${taskId}/chat/compact`
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export interface DiffFile {
  status: string;
  path: string;
}

export interface DiffData {
  files: DiffFile[];
  diff: string;
}

export const getTaskDiff = async (
  workspaceId: number,
  taskId: number
): Promise<DiffData> => {
  try {
    const response = await api.get<DiffData>(
      `/api/v1/workspaces/${workspaceId}/tasks/${taskId}/diff`
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

// File Browser Types
export interface FileTreeNode {
  name: string;
  path: string;
  type: 'file' | 'dir';
  size?: number;
  children?: FileTreeNode[];
}

export interface FileTreeResponse {
  tree: FileTreeNode[];
  repo_path: string;
}

export interface FileContentResponse {
  path: string;
  content: string;
  size: number;
  is_binary: boolean;
  truncated: boolean;
}

// File Browser API functions
export const getFileTree = async (
  workspaceId: number,
  taskId: number
): Promise<FileTreeResponse> => {
  try {
    const response = await api.get<FileTreeResponse>(
      `/api/v1/workspaces/${workspaceId}/tasks/${taskId}/file-tree`
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const getFileContent = async (
  workspaceId: number,
  taskId: number,
  filePath: string
): Promise<FileContentResponse> => {
  try {
    const response = await api.get<FileContentResponse>(
      `/api/v1/workspaces/${workspaceId}/tasks/${taskId}/files`,
      { params: { path: filePath } }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};
