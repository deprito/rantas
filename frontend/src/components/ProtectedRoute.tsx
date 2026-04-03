'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { RefreshCw } from 'lucide-react';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requirePermission?: string;
  fallback?: React.ReactNode;
}

// Show minimal loading indicator after a short delay to avoid flicker
const LOADING_INDICATOR_DELAY = 300;

export function ProtectedRoute({ children, requirePermission, fallback }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, hasPermission } = useAuth();
  const router = useRouter();
  const [showLoading, setShowLoading] = useState(false);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  // Delay showing loading indicator to avoid flicker on fast auth checks
  useEffect(() => {
    if (isLoading) {
      const timer = setTimeout(() => {
        setShowLoading(true);
      }, LOADING_INDICATOR_DELAY);
      return () => clearTimeout(timer);
    } else {
      setShowLoading(false);
    }
  }, [isLoading]);

  // Show loading state (only after delay)
  if (isLoading && showLoading) {
    return (
      <div className="fixed top-4 right-4 z-50">
        <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg px-4 py-2 flex items-center gap-2 fade-in">
          <RefreshCw className="h-4 w-4 animate-spin text-primary" />
          <span className="text-sm text-muted-foreground">Verifying...</span>
        </div>
      </div>
    );
  }

  // Not authenticated
  if (!isAuthenticated) {
    return fallback ?? null;
  }

  // Check specific permission if required
  if (requirePermission && !hasPermission(requirePermission)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
        <div className="text-center max-w-md mx-auto p-8">
          <div className="bg-destructive/10 border border-destructive/20 text-destructive p-6 rounded-lg mb-6">
            <h1 className="text-xl font-bold mb-2">Access Denied</h1>
            <p className="text-sm">You don't have permission to access this page.</p>
          </div>
          <button
            onClick={() => router.back()}
            className="text-primary hover:underline"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

// HOC for easier usage
export function withProtection<P extends object>(
  Component: React.ComponentType<P>,
  requirePermission?: string
) {
  return function ProtectedComponent(props: P) {
    return (
      <ProtectedRoute requirePermission={requirePermission}>
        <Component {...props} />
      </ProtectedRoute>
    );
  };
}
