'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { AuthContextType, UserWithPermissions, Permission } from '@/types/auth';
import { api } from '@/lib/api';
import { getJwtExpiry, getJwtTimeRemaining } from '@/lib/jwt';
import { useActivityTracker } from '@/hooks/useActivityTracker';
import { SessionWarningDialog } from '@/components/SessionWarningDialog';

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const TOKEN_KEY = 'phishtrack_token';
const USER_KEY = 'phishtrack_user';
const LAST_ACTIVITY_KEY = 'lastActivity';

// Configuration
const ACTIVITY_TIMEOUT_MINUTES = 30; // Log out after 30 minutes of inactivity
const WARNING_SECONDS = 120; // Show warning 2 minutes before logout
const TOKEN_REFRESH_BUFFER_MS = 5 * 60 * 1000; // Refresh token 5 minutes before expiry
const CHECK_INTERVAL_MS = 60 * 1000; // Check every minute

// Feature flags - can be controlled via environment variables
const ENABLE_TAB_SYNC = process.env.NEXT_PUBLIC_ENABLE_TAB_SYNC !== 'false';
const ENABLE_ACTIVITY_TIMEOUT = process.env.NEXT_PUBLIC_ENABLE_ACTIVITY_TIMEOUT !== 'false';
const ENABLE_TOKEN_REFRESH = process.env.NEXT_PUBLIC_ENABLE_TOKEN_REFRESH !== 'false';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<UserWithPermissions | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showWarning, setShowWarning] = useState(false);
  const [warningTimeRemaining, setWarningTimeRemaining] = useState(WARNING_SECONDS);

  const tokenRefreshIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const resetActivityRef = useRef<(() => void) | null>(null);

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

        // Initialize last activity time on mount
        const existingActivity = localStorage.getItem(LAST_ACTIVITY_KEY);
        if (!existingActivity) {
          localStorage.setItem(LAST_ACTIVITY_KEY, Date.now().toString());
        }
      } catch (e) {
        // Invalid stored data, clear it
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
      }
    }

    setIsLoading(false);
  }, []);

  // Internal logout function - defined early for use in other effects
  const performLogout = useCallback(() => {
    setToken(null);
    setUser(null);
    setShowWarning(false);

    // Clear localStorage
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(LAST_ACTIVITY_KEY);

    // Clear token in API client
    api.setToken(null);

    // Redirect to login
    router.push('/login');
  }, [router]);

  // Register unauthorized handler with API client
  useEffect(() => {
    // Set up the handler that will be called when a 401 is detected
    api.setOnUnauthorized(() => {
      // Clear auth state
      setToken(null);
      setUser(null);
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      localStorage.removeItem(LAST_ACTIVITY_KEY);
      api.setToken(null);
      // Redirect to login
      router.push('/login');
    });
  }, [router]);

  // Tab synchronization - log out in other tabs when token is removed
  useEffect(() => {
    if (!ENABLE_TAB_SYNC) return;

    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === TOKEN_KEY && e.newValue === null) {
        // Token was removed in another tab
        performLogout();
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [performLogout]);

  // Activity timeout tracking
  const { isInactive, resetActivity, timeRemaining } = useActivityTracker({
    timeoutMinutes: ACTIVITY_TIMEOUT_MINUTES,
    enabled: ENABLE_ACTIVITY_TIMEOUT && !!token,
  });

  // Keep ref updated with latest resetActivity function
  useEffect(() => {
    resetActivityRef.current = resetActivity;
  }, [resetActivity]);

  // Handle inactivity - show warning then logout
  useEffect(() => {
    if (!ENABLE_ACTIVITY_TIMEOUT || !token) return;

    const warningThreshold = WARNING_SECONDS * 1000; // Convert to milliseconds

    if (timeRemaining <= warningThreshold && timeRemaining > 0) {
      // Show warning dialog
      setWarningTimeRemaining(Math.ceil(timeRemaining / 1000));
      setShowWarning(true);
    } else if (timeRemaining === 0 && isInactive) {
      // Time's up - log out
      setShowWarning(false);
      performLogout();
    } else {
      // Hide warning if user became active again
      setShowWarning(false);
    }
  }, [timeRemaining, isInactive, token, performLogout]);

  // Token refresh - periodically check and refresh before expiry
  useEffect(() => {
    if (!ENABLE_TOKEN_REFRESH || !token) {
      if (tokenRefreshIntervalRef.current) {
        clearInterval(tokenRefreshIntervalRef.current);
        tokenRefreshIntervalRef.current = null;
      }
      return;
    }

    const checkAndRefreshToken = async () => {
      const timeRemaining = getJwtTimeRemaining(token);

      // If token is expired or will expire soon, refresh it
      if (timeRemaining !== null && timeRemaining <= TOKEN_REFRESH_BUFFER_MS) {
        try {
          const userData = await api.getCurrentUser();
          setUser(userData);
          localStorage.setItem(USER_KEY, JSON.stringify(userData));
        } catch {
          // Refresh failed - token might be invalid
          performLogout();
        }
      }
    };

    // Check immediately
    checkAndRefreshToken();

    // Set up interval to check periodically
    tokenRefreshIntervalRef.current = setInterval(checkAndRefreshToken, CHECK_INTERVAL_MS);

    return () => {
      if (tokenRefreshIntervalRef.current) {
        clearInterval(tokenRefreshIntervalRef.current);
        tokenRefreshIntervalRef.current = null;
      }
    };
  }, [token, performLogout]);

  const login = useCallback(async (username: string, password: string) => {
    const response = await api.login(username, password);

    setToken(response.access_token);
    setUser(response.user);

    // Store in localStorage
    localStorage.setItem(TOKEN_KEY, response.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(response.user));
    localStorage.setItem(LAST_ACTIVITY_KEY, Date.now().toString());

    // Set token in API client
    api.setToken(response.access_token);

    // Reset activity tracking
    resetActivityRef.current?.();

    // Redirect to dashboard
    router.push('/');
  }, [router]);

  const logout = useCallback(() => {
    performLogout();
  }, [performLogout]);

  const refreshToken = useCallback(async () => {
    if (!token) return;

    try {
      const userData = await api.getCurrentUser();
      setUser(userData);
      localStorage.setItem(USER_KEY, JSON.stringify(userData));
    } catch (error) {
      // Token might be expired, logout
      performLogout();
    }
  }, [token, performLogout]);

  const hasPermission = useCallback((permission: string): boolean => {
    if (!user) return false;
    return user.permissions.includes('*') || user.permissions.includes(permission);
  }, [user]);

  const hasAnyPermission = useCallback((permissions: string[]): boolean => {
    if (!user) return false;
    if (user.permissions.includes('*')) return true;
    return permissions.some(p => user.permissions.includes(p));
  }, [user]);

  const handleExtendSession = useCallback(() => {
    resetActivityRef.current?.();
    setShowWarning(false);
  }, []);

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
      {ENABLE_ACTIVITY_TIMEOUT && (
        <SessionWarningDialog
          open={showWarning}
          onExtend={handleExtendSession}
          onLogout={logout}
          remainingSeconds={warningTimeRemaining}
        />
      )}
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
