export interface User {
  id: number;
  email: string;
  username: string;
  is_active: boolean;
  created_at: string;
  github_username?: string;
  gitlab_username?: string;
  gitlab_url?: string;
  google_id?: string;
  google_email?: string;
  google_picture?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export interface AuthFeatures {
  password: boolean;
  magic_link: boolean;
  google: boolean;
}

export interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  isAuthenticated: boolean;
  authFeatures: AuthFeatures | null;
  login: (email: string, password: string) => Promise<void>;
  loginWithGoogle: () => void;
  logout: () => void;
  checkAuth: () => Promise<void>;
}
