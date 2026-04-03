'use client';

import { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';
import { Permission } from '@/types/auth';
import { Users, Settings, Shield, Mail, Inbox, Ban, Database } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ConfigManagementContent } from './config/page';
import { UserManagementContent } from './users/page';
import { EmailTemplatesContent } from './email-templates/page';
import { SubmissionsManagementContent } from './submissions/page';
import { BlacklistManagementContent } from './blacklist/page';
import { MigrationsManagementContent } from './migrations/page';
import { usePendingCount } from '@/hooks/usePendingCount';

function AdminLayout() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tab = searchParams.get('tab') || 'users';
  const { hasPermission } = useAuth();
  const { pendingCount } = usePendingCount();

  const canViewUsers = hasPermission(Permission.USER_VIEW_ANY);
  const canViewConfig = hasPermission(Permission.CONFIG_VIEW);
  const canViewEmailTemplates = hasPermission(Permission.EMAIL_TEMPLATE_VIEW);
  const canViewSubmissions = hasPermission(Permission.SUBMISSION_VIEW);
  const canViewBlacklist = hasPermission(Permission.BLACKLIST_VIEW);
  const isAdmin = hasPermission('*');

  // If user can't access anything, show access denied
  if (!canViewUsers && !canViewConfig && !canViewEmailTemplates && !canViewSubmissions && !canViewBlacklist) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900 flex items-center justify-center">
        <div className="text-center max-w-md mx-auto p-8">
          <div className="bg-destructive/10 border border-destructive/20 text-destructive p-6 rounded-lg mb-6">
            <Shield className="h-12 w-12 mx-auto mb-4" />
            <h1 className="text-xl font-bold mb-2">Access Denied</h1>
            <p className="text-sm">You don't have permission to access the administration panel.</p>
          </div>
          <Button onClick={() => router.push('/')}>Back to Dashboard</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
      {/* Header */}
      <header className="border-b bg-white/50 dark:bg-slate-950/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="container mx-auto px-4 py-4">
          {/* Desktop: Original layout */}
          <div className="hidden md:block">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="bg-primary/10 p-2 rounded-lg">
                  <Shield className="h-6 w-6 text-primary" />
                </div>
                <div>
                  <h1 className="text-xl font-bold">Administration</h1>
                  <p className="text-xs text-muted-foreground">
                    System management and configuration
                  </p>
                </div>
              </div>
              <Button variant="outline" onClick={() => router.push('/')}>
                Back to Dashboard
              </Button>
            </div>

            {/* Tabs */}
            <div className="flex gap-2 mt-4 flex-wrap">
              {canViewUsers && (
                <Link href="/admin?tab=users">
                  <Button
                    variant={tab === 'users' ? 'default' : 'ghost'}
                    size="sm"
                    className="gap-2"
                  >
                    <Users className="h-4 w-4" />
                    Users
                  </Button>
                </Link>
              )}
              {canViewSubmissions && (
                <Link href="/admin?tab=submissions">
                  <Button
                    variant={tab === 'submissions' ? 'default' : 'ghost'}
                    size="sm"
                    className={`gap-2 ${pendingCount > 5 && tab !== 'submissions' ? 'ring-2 ring-amber-500/50' : ''}`}
                  >
                    <Inbox className="h-4 w-4" />
                    Public Submissions
                    {pendingCount > 0 && (
                      <Badge
                        variant="destructive"
                        className={`ml-1 h-5 min-w-5 px-1 flex items-center justify-center text-xs ${pendingCount > 5 ? 'animate-pulse' : ''}`}
                      >
                        {pendingCount > 99 ? '99+' : pendingCount}
                      </Badge>
                    )}
                  </Button>
                </Link>
              )}
              {canViewBlacklist && (
                <Link href="/admin?tab=blacklist">
                  <Button
                    variant={tab === 'blacklist' ? 'default' : 'ghost'}
                    size="sm"
                    className="gap-2"
                  >
                    <Ban className="h-4 w-4" />
                    Blacklist
                  </Button>
                </Link>
              )}
              {canViewConfig && (
                <Link href="/admin?tab=config">
                  <Button
                    variant={tab === 'config' ? 'default' : 'ghost'}
                    size="sm"
                    className="gap-2"
                  >
                    <Settings className="h-4 w-4" />
                    Configuration
                  </Button>
                </Link>
              )}
              {canViewEmailTemplates && (
                <Link href="/admin?tab=email-templates">
                  <Button
                    variant={tab === 'email-templates' ? 'default' : 'ghost'}
                    size="sm"
                    className="gap-2"
                  >
                    <Mail className="h-4 w-4" />
                    Email Templates
                  </Button>
                </Link>
              )}
              {isAdmin && (
                <Link href="/admin?tab=migrations">
                  <Button
                    variant={tab === 'migrations' ? 'default' : 'ghost'}
                    size="sm"
                    className="gap-2"
                  >
                    <Database className="h-4 w-4" />
                    Migrations
                  </Button>
                </Link>
              )}
            </div>
          </div>

          {/* Mobile: Compact layout */}
          <div className="md:hidden">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="bg-primary/10 p-1.5 rounded-lg">
                  <Shield className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h1 className="text-base font-bold">Administration</h1>
                </div>
              </div>
              <Button variant="outline" size="sm" onClick={() => router.push('/')}>
                Back
              </Button>
            </div>

            {/* Tabs - Horizontal scroll on mobile */}
            <div className="flex gap-1 overflow-x-auto pb-1 -mx-4 px-4 scrollbar-hide">
              {canViewUsers && (
                <Link href="/admin?tab=users">
                  <Button
                    variant={tab === 'users' ? 'default' : 'ghost'}
                    size="sm"
                    className="gap-1 shrink-0 text-xs"
                  >
                    <Users className="h-4 w-4" />
                    <span className="hidden xs:inline">Users</span>
                  </Button>
                </Link>
              )}
              {canViewSubmissions && (
                <Link href="/admin?tab=submissions">
                  <Button
                    variant={tab === 'submissions' ? 'default' : 'ghost'}
                    size="sm"
                    className={`gap-1 shrink-0 text-xs ${pendingCount > 5 && tab !== 'submissions' ? 'ring-2 ring-amber-500/50' : ''}`}
                  >
                    <Inbox className="h-4 w-4" />
                    <span className="hidden xs:inline">Submissions</span>
                    {pendingCount > 0 && (
                      <Badge
                        variant="destructive"
                        className={`ml-0 h-5 min-w-5 px-1 flex items-center justify-center text-xs ${pendingCount > 5 ? 'animate-pulse' : ''}`}
                      >
                        {pendingCount > 99 ? '99+' : pendingCount}
                      </Badge>
                    )}
                  </Button>
                </Link>
              )}
              {canViewBlacklist && (
                <Link href="/admin?tab=blacklist">
                  <Button
                    variant={tab === 'blacklist' ? 'default' : 'ghost'}
                    size="sm"
                    className="gap-1 shrink-0 text-xs"
                  >
                    <Ban className="h-4 w-4" />
                    <span className="hidden xs:inline">Blacklist</span>
                  </Button>
                </Link>
              )}
              {canViewConfig && (
                <Link href="/admin?tab=config">
                  <Button
                    variant={tab === 'config' ? 'default' : 'ghost'}
                    size="sm"
                    className="gap-1 shrink-0 text-xs"
                  >
                    <Settings className="h-4 w-4" />
                    <span className="hidden xs:inline">Config</span>
                  </Button>
                </Link>
              )}
              {canViewEmailTemplates && (
                <Link href="/admin?tab=email-templates">
                  <Button
                    variant={tab === 'email-templates' ? 'default' : 'ghost'}
                    size="sm"
                    className="gap-1 shrink-0 text-xs"
                  >
                    <Mail className="h-4 w-4" />
                    <span className="hidden xs:inline">Email</span>
                  </Button>
                </Link>
              )}
              {isAdmin && (
                <Link href="/admin?tab=migrations">
                  <Button
                    variant={tab === 'migrations' ? 'default' : 'ghost'}
                    size="sm"
                    className="gap-1 shrink-0 text-xs"
                  >
                    <Database className="h-4 w-4" />
                    <span className="hidden xs:inline">Migrations</span>
                  </Button>
                </Link>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Content based on tab */}
      <main className="container mx-auto px-4 py-8">
        {tab === 'users' && canViewUsers && <UserManagementContent />}
        {tab === 'config' && canViewConfig && <ConfigManagementContent />}
        {tab === 'email-templates' && canViewEmailTemplates && <EmailTemplatesContent />}
        {tab === 'submissions' && canViewSubmissions && <SubmissionsManagementContent />}
        {tab === 'blacklist' && canViewBlacklist && <BlacklistManagementContent />}
        {tab === 'migrations' && isAdmin && <MigrationsManagementContent />}
      </main>
    </div>
  );
}

export default function AdminPage() {
  return (
    <ProtectedRoute>
      <AdminLayout />
    </ProtectedRoute>
  );
}
