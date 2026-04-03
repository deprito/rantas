'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { AuthContextType, UserWithPermissions, Permission } from '@/types/auth';
import { api } from '@/lib/api';

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const TOKEN_KEY = 'phishtrack_token';
const USER_KEY = 'phishtrack_user';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<UserWithPermissions | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load token and user from localStorage on mount
  useEffect(() => {
    const storedToken = localStorage.getItem(TOKEN_KEY);
    const storedUser = localStorage.getItem(USER_KEY);

    if (storedToken && storedUser) {
      try {
        setToken(storedToken);
        setUser(JSON.parse(storedUser));
        // Set token in API client
        api.setToken(storedToken);
      } catch (e) {
        // Invalid stored data, clear it
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
      }
    }

    setIsLoading(false);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const response = await api.login(username, password);

    setToken(response.access_token);
    setUser(response.user);

    // Store in localStorage
    localStorage.setItem(TOKEN_KEY, response.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(response.user));

    // Set token in API client
    api.setToken(response.access_token);

    // Redirect to dashboard
    router.push('/');
  }, [router]);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);

    // Clear localStorage
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);

    // Clear token in API client
    api.setToken(null);

    // Redirect to login
    router.push('/login');
  }, [router]);

  const refreshToken = useCallback(async () => {
    if (!token) return;

    try {
      // For now, we'll use the /me endpoint to refresh user data
      const userData = await api.getCurrentUser();
      setUser(userData);
      localStorage.setItem(USER_KEY, JSON.stringify(userData));
    } catch (error) {
      // Token might be expired, logout
      logout();
    }
  }, [token, logout]);

  const hasPermission = useCallback((permission: string): boolean => {
    if (!user) return false;
    return user.permissions.includes('*') || user.permissions.includes(permission);
  }, [user]);

  const hasAnyPermission = useCallback((permissions: string[]): boolean => {
    if (!user) return false;
    if (user.permissions.includes('*')) return true;
    return permissions.some(p => user.permissions.includes(p));
  }, [user]);

  const value: AuthContextType = {
    user,
    token,
    login,
    logout,
    refreshToken,
    hasPermission,
    hasAnyPermission,
    isAuthenticated: !!user,
    isLoading,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
