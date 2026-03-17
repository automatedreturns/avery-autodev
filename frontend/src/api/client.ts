import axios, { AxiosError } from 'axios';
import { getToken, removeToken } from '../utils/storage';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Create axios instance
export const api = axios.create({
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

// Add response interceptor to handle auth errors globally
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error: AxiosError) => {
    // Handle authentication errors
    if (error.response?.status === 401) {
      // Clear invalid token
      removeToken();

      // Redirect to signin page
      window.location.href = '/signin';

      return Promise.reject(new Error('Session expired. Please sign in again.'));
    }

    // Handle forbidden errors (could also be auth-related)
    if (error.response?.status === 403) {
      const errorData = error.response.data as { detail?: string };

      // Check if it's an auth issue
      if (errorData.detail?.toLowerCase().includes('token') ||
          errorData.detail?.toLowerCase().includes('authentication')) {
        removeToken();
        window.location.href = '/signin';
        return Promise.reject(new Error('Session expired. Please sign in again.'));
      }
    }

    return Promise.reject(error);
  }
);

// Error handling helper
export const handleApiError = (error: unknown): never => {
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
