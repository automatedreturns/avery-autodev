import React, { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import type { User, AuthContextType, AuthFeatures } from '../types/auth';
import * as authApi from '../api/auth';
import { getToken, saveToken, removeToken } from '../utils/storage';

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authFeatures, setAuthFeatures] = useState<AuthFeatures | null>(null);

  // Check authentication and load features on mount
  useEffect(() => {
    checkAuth();
    loadAuthFeatures();
  }, []);

  const loadAuthFeatures = async () => {
    const features = await authApi.getAuthFeatures();
    setAuthFeatures(features);
  };

  const checkAuth = async () => {
    try {
      const storedToken = getToken();
      if (storedToken) {
        setToken(storedToken);
        const userData = await authApi.getCurrentUser();
        setUser(userData);
        setIsAuthenticated(true);
      }
    } catch (error) {
      // Token invalid or expired
      removeToken();
      setToken(null);
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    const response = await authApi.login(email, password);
    saveToken(response.access_token);
    setToken(response.access_token);
    const userData = await authApi.getCurrentUser();
    setUser(userData);
    setIsAuthenticated(true);
  };

  const loginWithGoogle = () => {
    const googleLoginUrl = authApi.getGoogleLoginUrl();
    window.location.href = googleLoginUrl;
  };

  const logout = () => {
    removeToken();
    setToken(null);
    setUser(null);
    setIsAuthenticated(false);
  };

  const value: AuthContextType = {
    user,
    token,
    loading,
    isAuthenticated,
    authFeatures,
    login,
    loginWithGoogle,
    logout,
    checkAuth,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
