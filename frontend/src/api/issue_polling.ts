import axios from 'axios';
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

export interface PollResult {
  success: boolean;
  issues_found: number;
  issues_linked: number;
  issues_skipped: number;
  prs_checked: number;
  prs_with_conflicts: number;
  pr_tasks_created: number;
  error: string | null;
}

export interface PollingStatus {
  id: number;
  workspace_id: number;
  last_poll_time: string | null;
  total_issues_imported: number;
  last_poll_issues_found: number;
  last_poll_issues_linked: number;
  last_poll_issues_skipped: number;
  last_poll_prs_checked: number;
  last_poll_prs_with_conflicts: number;
  total_pr_tasks_created: number;
  last_poll_status: string; // "success", "error", "never"
  last_poll_error: string | null;
  updated_at: string;
}

export const pollWorkspaceIssues = async (workspaceId: number): Promise<PollResult> => {
  const response = await api.post<PollResult>(
    `/api/v1/workspaces/${workspaceId}/poll-issues`
  );
  return response.data;
};

export const getPollingStatus = async (
  workspaceId: number
): Promise<PollingStatus> => {
  const response = await api.get<PollingStatus>(
    `/api/v1/workspaces/${workspaceId}/polling-status`
  );
  return response.data;
};
