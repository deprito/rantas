import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Permission } from '@/types/auth';
import { api } from '@/lib/api';

const POLL_INTERVAL = 30000; // 30 seconds

/**
 * Hook to fetch and track pending submissions count
 * Automatically polls every 30 seconds to keep count updated
 */
export function usePendingCount() {
  const { hasPermission } = useAuth();
  const [pendingCount, setPendingCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  const canViewSubmissions = hasPermission(Permission.SUBMISSION_VIEW);

  const fetchPendingCount = useCallback(async () => {
    if (!canViewSubmissions) {
      setPendingCount(0);
      return;
    }

    setIsLoading(true);
    try {
      const count = await api.getPendingSubmissionsCount();
      setPendingCount(count);
    } catch {
      // Silently fail - count will remain as is
    } finally {
      setIsLoading(false);
    }
  }, [canViewSubmissions]);

  useEffect(() => {
    fetchPendingCount();

    // Set up polling interval
    const interval = setInterval(fetchPendingCount, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchPendingCount]);

  return { pendingCount, isLoading, refetch: fetchPendingCount };
}
