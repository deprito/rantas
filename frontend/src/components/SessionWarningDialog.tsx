'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { AlertCircle } from 'lucide-react';

interface SessionWarningDialogProps {
  /** Whether the dialog is open */
  open: boolean;
  /** Callback when user clicks "Stay Logged In" */
  onExtend: () => void;
  /** Callback when session expires */
  onLogout: () => void;
  /** Remaining time in seconds before logout */
  remainingSeconds: number;
}

/**
 * Dialog shown to user when their session is about to expire due to inactivity
 * Shows a countdown timer and allows extending the session
 */
export function SessionWarningDialog({
  open,
  onExtend,
  onLogout,
  remainingSeconds,
}: SessionWarningDialogProps) {
  const [countdown, setCountdown] = useState(remainingSeconds);

  // Update countdown when remainingSeconds changes externally
  useEffect(() => {
    setCountdown(remainingSeconds);
  }, [remainingSeconds]);

  // Count down every second
  useEffect(() => {
    if (!open || countdown <= 0) return;

    const interval = setInterval(() => {
      setCountdown((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => clearInterval(interval);
  }, [open, countdown]);

  // Auto-logout when countdown reaches zero
  useEffect(() => {
    if (countdown === 0 && open) {
      onLogout();
    }
  }, [countdown, open, onLogout]);

  // Format time as MM:SS
  const formattedTime = useMemo(() => {
    const minutes = Math.floor(countdown / 60);
    const seconds = countdown % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }, [countdown]);

  const handleExtend = useCallback(() => {
    onExtend();
  }, [onExtend]);

  return (
    <Dialog open={open} onOpenChange={() => {}}>
      <DialogContent
        className="sm:max-w-md"
        onPointerDownOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="rounded-full bg-amber-100 dark:bg-amber-900/30 p-2">
              <AlertCircle className="h-6 w-6 text-amber-600 dark:text-amber-500" />
            </div>
            <DialogTitle>Session Expiring Soon</DialogTitle>
          </div>
          <DialogDescription className="pt-2">
            You will be logged out due to inactivity in{' '}
            <span className="font-semibold text-amber-600 dark:text-amber-500">
              {formattedTime}
            </span>
            .
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          <div className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 p-4">
            <p className="text-sm text-muted-foreground">
              To stay logged in, click the button below. This will reset your
              inactivity timer.
            </p>
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={onLogout}>
            Logout Now
          </Button>
          <Button onClick={handleExtend}>Stay Logged In</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
