import { api } from './client';

export interface User {
  id: number;
  username: string;
  email: string;
}

export const searchUsers = async (query: string): Promise<User[]> => {
  const response = await api.get<User[]>('/api/v1/users/search/query', {
    params: { q: query }
  });
  return response.data;
};
