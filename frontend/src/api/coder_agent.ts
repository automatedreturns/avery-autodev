import axios, { AxiosError } from 'axios';
import type {
  CoderAgentExecuteRequest,
  CoderAgentExecuteResponse,
  CoderAgentStatusResponse,
} from '../types/coder_agent';
import { getToken } from '../utils/storage';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to include auth token
api.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Error handling helper
const handleApiError = (error: unknown): never => {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ detail: string }>;
    if (axiosError.response) {
      throw new Error(axiosError.response.data?.detail || 'An error occurred');
    } else if (axiosError.request) {
      throw new Error('Unable to connect to server');
    }
  }
  throw new Error('An unexpected error occurred');
};

// Coder Agent API functions
export const executeCoderAgent = async (
  workspaceId: number,
  taskId: number,
  data: CoderAgentExecuteRequest
): Promise<CoderAgentExecuteResponse> => {
  try {
    const response = await api.post<CoderAgentExecuteResponse>(
      `/api/v1/workspaces/${workspaceId}/tasks/${taskId}/execute-agent`,
      data
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const getCoderAgentStatus = async (
  workspaceId: number,
  taskId: number
): Promise<CoderAgentStatusResponse> => {
  try {
    const response = await api.get<CoderAgentStatusResponse>(
      `/api/v1/workspaces/${workspaceId}/tasks/${taskId}/agent-status`
    );
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};
