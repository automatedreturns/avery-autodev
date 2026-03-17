import axios, { AxiosError } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

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

// Types
export interface ContactRequest {
  name: string;
  email: string;
  company: string;
  message: string;
}

export interface ContactResponse {
  message: string;
  success: boolean;
}

// API functions
export const contactSales = async (data: ContactRequest): Promise<ContactResponse> => {
  try {
    const response = await api.post<ContactResponse>('/api/v1/contact/sales', data);
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};
