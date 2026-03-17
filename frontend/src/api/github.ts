import axios, { AxiosError } from 'axios';
import type { GitHubTokenData, GitHubTokenResponse, GitHubRepoValidation, GitHubBranchList, GitProvider } from '../types/github';
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

// Git provider API functions
export const storeGitHubToken = async (data: GitHubTokenData): Promise<GitHubTokenResponse> => {
  try {
    const response = await api.post<GitHubTokenResponse>('/api/v1/github/token', data);
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const validateRepository = async (
  repository: string,
  provider: GitProvider = 'github',
  gitlabUrl?: string,
): Promise<GitHubRepoValidation> => {
  try {
    const response = await api.get<GitHubRepoValidation>('/api/v1/github/validate-repo', {
      params: { repo: repository, provider, gitlab_url: gitlabUrl },
    });
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const listBranches = async (
  repository: string,
  refresh: boolean = false,
  provider: GitProvider = 'github',
  gitlabUrl?: string,
): Promise<GitHubBranchList> => {
  try {
    const response = await api.get<GitHubBranchList>('/api/v1/github/branches', {
      params: { repo: repository, refresh, provider, gitlab_url: gitlabUrl },
    });
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const removeGitHubToken = async (provider: GitProvider = 'github'): Promise<void> => {
  try {
    await api.delete('/api/v1/github/token', {
      params: { provider },
    });
  } catch (error) {
    return handleApiError(error);
  }
};
