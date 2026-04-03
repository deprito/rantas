'use client';

import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { RoleLabels, Permission } from '@/types/auth';
import { User, LogOut, Shield, Settings, ChevronDown, BarChart3, Inbox } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { usePendingCount } from '@/hooks/usePendingCount';
import { ThemeToggle } from '@/components/theme-toggle';

export function UserMenu() {
  const { user, logout, hasPermission } = useAuth();
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const { pendingCount } = usePendingCount();

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = () => {
    setIsOpen(false);
    logout();
  };

  const navigateToAdmin = () => {
    setIsOpen(false);
    router.push('/admin');
  };

  const navigateToDashboard = () => {
    setIsOpen(false);
    router.push('/dashboard');
  };

  if (!user) {
    return <Skeleton className="h-10 w-32" />;
  }

  const isAdmin = user.role.name === 'ADMIN';
  const canViewConfig = hasPermission(Permission.CONFIG_VIEW);
  const canViewUsers = hasPermission(Permission.USER_VIEW_ANY);
  const canViewStats = hasPermission(Permission.STATS_VIEW);
  const canViewSubmissions = hasPermission(Permission.SUBMISSION_VIEW);

  return (
    <div className="relative" ref={menuRef}>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setIsOpen(!isOpen)}
        className="gap-2"
      >
        <User className="h-4 w-4" />
        <span className="hidden sm:inline">{user.username}</span>
        <span className="hidden md:inline text-muted-foreground">
          ({RoleLabels[user.role.name as keyof typeof RoleLabels]})
        </span>
        <ChevronDown className="h-4 w-4" />
      </Button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-slate-900 rounded-lg shadow-lg border z-50">
          {/* Theme Toggle */}
          <div className="p-2">
            <ThemeToggle />
          </div>

          <div className="border-t my-1" />

          {/* User Info */}
          <div className="px-4 py-3 border-b">
            <p className="font-medium">{user.username}</p>
            <p className="text-sm text-muted-foreground">{user.email}</p>
            <div className="flex items-center gap-1 mt-1">
              <Shield className="h-3 w-3 text-primary" />
              <span className="text-xs text-muted-foreground">
                {RoleLabels[user.role.name as keyof typeof RoleLabels]}
              </span>
            </div>
          </div>

          {/* Menu Items */}
          <div className="py-1">
            {canViewStats && (
              <button
                onClick={navigateToDashboard}
                className="w-full px-4 py-2 text-left text-sm hover:bg-muted flex items-center gap-2"
              >
                <BarChart3 className="h-4 w-4" />
                Statistics Dashboard
              </button>
            )}

            {canViewSubmissions && (
              <Link
                href="/admin?tab=submissions"
                className="w-full px-4 py-2 text-left text-sm hover:bg-muted flex items-center justify-between"
                onClick={() => setIsOpen(false)}
              >
                <span className="flex items-center gap-2">
                  <Inbox className="h-4 w-4" />
                  Public Submissions
                </span>
                {pendingCount > 0 && (
                  <Badge variant="destructive" className="h-5 w-5 p-0 flex items-center justify-center text-xs">
                    {pendingCount > 99 ? '99+' : pendingCount}
                  </Badge>
                )}
              </Link>
            )}

            {(isAdmin || canViewUsers || canViewConfig) && (
              <>
                <button
                  onClick={navigateToAdmin}
                  className="w-full px-4 py-2 text-left text-sm hover:bg-muted flex items-center gap-2"
                >
                  <Settings className="h-4 w-4" />
                  Administration
                </button>
              </>
            )}

            {(canViewStats || canViewSubmissions || isAdmin || canViewUsers || canViewConfig) && (
              <div className="border-t my-1" />
            )}

            <button
              onClick={handleLogout}
              className="w-full px-4 py-2 text-left text-sm hover:bg-muted text-destructive flex items-center gap-2"
            >
              <LogOut className="h-4 w-4" />
              Sign Out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
