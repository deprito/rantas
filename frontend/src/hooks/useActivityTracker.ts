import { useEffect, useState, useCallback, useRef } from 'react';

const ACTIVITY_EVENTS = [
  'mousedown',
  'mousemove',
  'keydown',
  'scroll',
  'touchstart',
  'click',
  'visibilitychange',
] as const;

const LAST_ACTIVITY_KEY = 'lastActivity';

interface UseActivityTrackerOptions {
  /** Timeout in minutes before considering user inactive */
  timeoutMinutes: number;
  /** Whether to enable tracking (default: true) */
  enabled?: boolean;
}

interface UseActivityTrackerResult {
  /** Whether user is currently inactive */
  isInactive: boolean;
  /** Timestamp of last activity (ms since epoch) */
  lastActivity: number;
  /** Remaining time until inactivity timeout (ms) */
  timeRemaining: number;
  /** Manually reset the activity timer */
  resetActivity: () => void;
}

/**
 * Hook to track user activity and detect inactivity
 * Stores last activity timestamp in localStorage for cross-tab synchronization
 */
export function useActivityTracker({
  timeoutMinutes,
  enabled = true,
}: UseActivityTrackerOptions): UseActivityTrackerResult {
  const timeoutMs = timeoutMinutes * 60 * 1000;

  // Use refs to track state without causing re-renders or stale closures
  const lastActivityRef = useRef<number>(Date.now());
  const isInactiveRef = useRef(false);
  const [isInactive, setIsInactive] = useState(false);
  const [lastActivity, setLastActivity] = useState(() => {
    if (typeof window === 'undefined') return Date.now();
    const stored = localStorage.getItem(LAST_ACTIVITY_KEY);
    const initial = stored ? parseInt(stored, 10) : Date.now();
    lastActivityRef.current = initial;
    return initial;
  });
  const [timeRemaining, setTimeRemaining] = useState(timeoutMs);

  // Reset activity timer
  const resetActivity = useCallback(() => {
    const now = Date.now();
    lastActivityRef.current = now;
    setLastActivity(now);
    localStorage.setItem(LAST_ACTIVITY_KEY, now.toString());
    setIsInactive(false);
    isInactiveRef.current = false;
  }, []);

  // Handle storage changes from other tabs
  useEffect(() => {
    if (!enabled || typeof window === 'undefined') return;

    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === LAST_ACTIVITY_KEY && e.newValue) {
        const newActivity = parseInt(e.newValue, 10);
        if (!isNaN(newActivity)) {
          lastActivityRef.current = newActivity;
          setLastActivity(newActivity);
          setIsInactive(false);
          isInactiveRef.current = false;
        }
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [enabled]);

  // Set up activity event listeners and inactivity check
  useEffect(() => {
    if (!enabled || typeof window === 'undefined') return;

    // Throttled activity handler to avoid excessive updates
    let activityTimeout: NodeJS.Timeout | null = null;
    const handleActivity = () => {
      if (activityTimeout) return;
      activityTimeout = setTimeout(() => {
        resetActivity();
        activityTimeout = null;
      }, 1000); // Update at most once per second
    };

    // Set up event listeners
    ACTIVITY_EVENTS.forEach((event) => {
      // For visibilitychange, only reset if becoming visible
      if (event === 'visibilitychange') {
        document.addEventListener(event, () => {
          if (!document.hidden) {
            handleActivity();
          }
        });
      } else {
        document.addEventListener(event, handleActivity, { passive: true });
      }
    });

    // Check for inactivity every second
    const checkInterval = setInterval(() => {
      const now = Date.now();
      const inactiveTime = now - lastActivityRef.current;
      const remaining = Math.max(0, timeoutMs - inactiveTime);
      setTimeRemaining(remaining);

      // Use ref to get current state value
      const wasInactive = isInactiveRef.current;
      const nowInactive = inactiveTime >= timeoutMs;

      if (nowInactive && !wasInactive) {
        setIsInactive(true);
        isInactiveRef.current = true;
      } else if (!nowInactive && wasInactive) {
        setIsInactive(false);
        isInactiveRef.current = false;
      }
    }, 1000);

    return () => {
      ACTIVITY_EVENTS.forEach((event) => {
        if (event === 'visibilitychange') {
          document.removeEventListener(event, () => {});
        } else {
          document.removeEventListener(event, handleActivity);
        }
      });
      clearInterval(checkInterval);
      if (activityTimeout) {
        clearTimeout(activityTimeout);
      }
    };
  }, [enabled, timeoutMs, resetActivity]);

  return {
    isInactive,
    lastActivity,
    timeRemaining,
    resetActivity,
  };
}
