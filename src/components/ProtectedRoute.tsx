'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { RefreshCw } from 'lucide-react';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requirePermission?: string;
  fallback?: React.ReactNode;
}

export function ProtectedRoute({ children, requirePermission, fallback }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, hasPermission } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  // Show loading state
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
        <div className="text-center">
          <RefreshCw className="h-8 w-8 animate-spin text-primary mx-auto mb-4" />
          <p className="text-muted-foreground">Loading...</p>
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
