import axios, { AxiosError } from 'axios';
import type { User, AuthResponse } from '../types/auth';
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
      // Server responded with error
      throw new Error(axiosError.response.data?.detail || 'An error occurred');
    } else if (axiosError.request) {
      // Request made but no response
      throw new Error('Unable to connect to server');
    }
  }
  throw new Error('An unexpected error occurred');
};

// API functions
export const requestMagicLink = async (email: string): Promise<{ message: string; email: string }> => {
  try {
    const response = await api.post<{ message: string; email: string }>('/api/v1/auth/magic-link/request', { email });
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const verifyMagicLink = async (token: string): Promise<AuthResponse> => {
  try {
    const response = await api.post<AuthResponse>('/api/v1/auth/magic-link/verify', { token });
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const getCurrentUser = async (): Promise<User> => {
  try {
    const response = await api.get<User>('/api/v1/auth/me');
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const getGoogleLoginUrl = (): string => {
  return `${API_BASE_URL}/api/v1/auth/google/login`;
};

export const handleGoogleCallback = async (code: string): Promise<AuthResponse> => {
  try {
    const response = await api.get<AuthResponse>(`/api/v1/auth/google/callback?code=${code}`);
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};
