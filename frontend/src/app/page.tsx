'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { UrlSubmitForm } from '@/components/url-submit-form';
import { CaseCard, CaseCardSkeleton } from '@/components/case-card';
import { UserMenu } from '@/components/user-menu';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { Case, CaseStatus } from '@/types/case';
import { useAuth } from '@/contexts/AuthContext';
import { Permission } from '@/types/auth';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Shield, AlertTriangle, RefreshCw, ChevronLeft, ChevronRight, Inbox, BarChart3, Radar } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import { usePendingCount } from '@/hooks/usePendingCount';

const PAGE_SIZE = 10;

function DashboardContent() {
  const router = useRouter();
  const { user, hasPermission } = useAuth();
  const { pendingCount } = usePendingCount();
  const [cases, setCases] = useState<Case[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [apiConnected, setApiConnected] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  // Permission checks
  const canViewSubmissions = hasPermission(Permission.SUBMISSION_VIEW);
  const canUpdateCase = hasPermission(Permission.CASE_UPDATE);
  const canViewHunting = hasPermission(Permission.HUNTING_VIEW);

  const loadCases = useCallback(async (silent = false) => {
    try {
      if (!silent) setIsLoading(true);
      setError(null);

      const response = await api.listCases({ page: currentPage, page_size: PAGE_SIZE });
      setCases(response.cases);
      setTotalPages(response.pages ?? 1);
      setApiConnected(true);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        // Empty case list is OK
        setCases([]);
        setTotalPages(1);
        setApiConnected(true);
      } else {
        console.error('Failed to load cases:', err);
        if (!silent) {
          setError(err instanceof Error ? err.message : 'Failed to load cases');
          setApiConnected(false);
        }
      }
    } finally {
      if (!silent) {
        setIsLoading(false);
      }
    }
  }, [currentPage]);

  // Load cases on mount and when page changes
  useEffect(() => {
    loadCases();
  }, [currentPage]);

  const handleSubmit = useCallback(async (url: string) => {
    setIsSubmitting(true);
    setError(null);

    try {
      await api.createCase(url);
      // Reload cases to show the new case
      loadCases(true);
      // Navigate to page 1 to see the new case
      setCurrentPage(1);
    } catch (err) {
      console.error('Failed to create case:', err);
      setError(err instanceof Error ? err.message : 'Failed to create case');
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  const handleRefresh = useCallback(() => {
    loadCases();
  }, [loadCases]);

  const goToPreviousPage = useCallback(() => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1);
    }
  }, [currentPage]);

  const goToNextPage = useCallback(() => {
    if (currentPage < totalPages) {
      setCurrentPage(currentPage + 1);
    }
  }, [currentPage, totalPages]);

  // Check if user can create cases
  const canCreateCase = hasPermission(Permission.CASE_CREATE);
  const canSendReport = hasPermission(Permission.CASE_SEND_REPORT);
  const canDeleteCase = hasPermission(Permission.CASE_DELETE);
  const canViewStats = hasPermission(Permission.STATS_VIEW);

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
      {/* Header */}
      <header className="border-b bg-white/50 dark:bg-slate-950/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="container mx-auto px-3 sm:px-4 py-3 sm:py-4">
          {/* Desktop: Single row layout */}
          <div className="hidden sm:flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="bg-primary/10 p-2 rounded-lg">
                <Shield className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h1 className="text-xl font-bold">RANTAS</h1>
                <p className="text-xs text-muted-foreground flex items-center gap-1">
                  Automated Takedown System
                  {!apiConnected && (
                    <span className="text-destructive">(API Disconnected)</span>
                  )}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={handleRefresh} disabled={isLoading}>
                <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              </Button>
              {canViewStats && (
                <Link href="/dashboard">
                  <Button variant="outline" size="sm" className="gap-2" title="Statistics Dashboard">
                    <BarChart3 className="h-4 w-4" />
                    <span className="hidden sm:inline">Statistics</span>
                  </Button>
                </Link>
              )}
              {canViewHunting && (
                <Link href="/hunting">
                  <Button variant="outline" size="sm" className="gap-2" title="Hunting - Typosquat Detection">
                    <Radar className="h-4 w-4" />
                    <span className="hidden sm:inline">Hunting</span>
                  </Button>
                </Link>
              )}
              {canViewSubmissions && pendingCount > 0 && (
                <Link href="/admin?tab=submissions">
                  <Button variant="outline" size="sm" className="relative gap-2" title="Pending submissions">
                    <Inbox className="h-4 w-4" />
                    <Badge variant="destructive" className="h-5 min-w-5 px-1 flex items-center justify-center text-xs">
                      {pendingCount > 99 ? '99+' : pendingCount}
                    </Badge>
                  </Button>
                </Link>
              )}
              <UserMenu />
            </div>
          </div>

          {/* Mobile: Two-row layout with scrollable actions */}
          <div className="sm:hidden">
            {/* Top row - Logo and User Menu */}
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className="bg-primary/10 p-1.5 rounded-lg">
                  <Shield className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h1 className="text-lg font-bold">RANTAS</h1>
                  <p className="text-[10px] text-muted-foreground">
                    {!apiConnected ? (
                      <span className="text-destructive">(API Disconnected)</span>
                    ) : (
                      'Automated Takedown System'
                    )}
                  </p>
                </div>
              </div>
              <UserMenu />
            </div>

            {/* Second row - Actions - scrollable on mobile */}
            <div className="flex items-center gap-1 overflow-x-auto pb-1 -mx-3 px-3 scrollbar-hide">
              <Button variant="ghost" size="sm" onClick={handleRefresh} disabled={isLoading} className="shrink-0 px-2">
                <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              </Button>
              {canViewStats && (
                <Link href="/dashboard">
                  <Button variant="outline" size="sm" className="gap-1 shrink-0 text-xs" title="Statistics Dashboard">
                    <BarChart3 className="h-4 w-4" />
                    <span className="hidden xs:inline">Statistics</span>
                  </Button>
                </Link>
              )}
              {canViewHunting && (
                <Link href="/hunting">
                  <Button variant="outline" size="sm" className="gap-1 shrink-0 text-xs" title="Hunting - Typosquat Detection">
                    <Radar className="h-4 w-4" />
                    <span className="hidden xs:inline">Hunting</span>
                  </Button>
                </Link>
              )}
              {canViewSubmissions && pendingCount > 0 && (
                <Link href="/admin?tab=submissions">
                  <Button variant="outline" size="sm" className="relative gap-1 shrink-0 text-xs" title="Pending submissions">
                    <Inbox className="h-4 w-4" />
                    <Badge variant="destructive" className="h-5 min-w-5 px-1 flex items-center justify-center text-xs">
                      {pendingCount > 99 ? '99+' : pendingCount}
                    </Badge>
                  </Button>
                </Link>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {/* Error Display */}
        {error && (
          <div className="mb-6 bg-destructive/10 border border-destructive/20 text-destructive p-4 rounded-lg">
            <p className="font-medium flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              Error
            </p>
            <p className="text-sm mt-1">{error}</p>
          </div>
        )}

        {/* Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - URL Form (Sticky) */}
          <div className="lg:col-span-1">
            <div className="lg:sticky lg:top-24">
              {canCreateCase ? (
                <UrlSubmitForm onSubmit={handleSubmit} isSubmitting={isSubmitting} />
              ) : (
                <div className="bg-muted/50 border border-border p-4 rounded-lg text-center">
                  <p className="text-muted-foreground text-sm">
                    Your account ({user?.role.name}) does not have permission to create new cases.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Right Column - Cases List with Pagination */}
          <div className="lg:col-span-2">
            {/* Cases List */}
            {isLoading && cases.length === 0 ? (
              <div className="text-center py-16">
                <div className="inline-flex items-center justify-center w-16 h-16 bg-muted rounded-full mb-4">
                  <RefreshCw className="h-8 w-8 text-muted-foreground animate-spin" />
                </div>
                <h2 className="text-xl font-semibold mb-2">Loading Cases...</h2>
              </div>
            ) : cases.length === 0 ? (
              <div className="text-center py-16">
                <div className="inline-flex items-center justify-center w-16 h-16 bg-muted rounded-full mb-4">
                  <AlertTriangle className="h-8 w-8 text-muted-foreground" />
                </div>
                <h2 className="text-xl font-semibold mb-2">No Active Cases</h2>
                <p className="text-muted-foreground max-w-md mx-auto">
                  {canCreateCase
                    ? 'Submit a suspicious URL to start the automated investigation and takedown process.'
                    : 'Contact an administrator to create cases.'}
                </p>
              </div>
            ) : (
              <>
                <div className="space-y-6">
                  {isSubmitting && <CaseCardSkeleton />}
                  {cases.map((caze) => (
                    <CaseCard
                      key={caze.id}
                      case={caze}
                      onUpdated={loadCases}
                      onDeleted={loadCases}
                      canSendReport={canSendReport}
                      canDeleteCase={canDeleteCase}
                    />
                  ))}
                </div>

                {/* Pagination Controls */}
                {totalPages > 1 && (
                  <div className="mt-8 flex items-center justify-between gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={goToPreviousPage}
                      disabled={currentPage === 1}
                    >
                      <ChevronLeft className="h-4 w-4 mr-1" />
                      Previous
                    </Button>

                    <span className="text-sm text-muted-foreground">
                      Page {currentPage} of {totalPages}
                    </span>

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={goToNextPage}
                      disabled={currentPage === totalPages}
                    >
                      Next
                      <ChevronRight className="h-4 w-4 ml-1" />
                    </Button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t bg-white/50 dark:bg-slate-950/50 backdrop-blur-sm mt-16">
        <div className="container mx-auto px-4 py-6 text-center text-sm text-muted-foreground">
          <p>
            RANTAS Automated Takedown System • For authorized security researchers only
          </p>
          <p className="mt-1 text-xs">
            All URLs are masked for security. Requests are isolated through dedicated proxies.
          </p>
        </div>
      </footer>
    </div>
  );
}

// Wrap with ProtectedRoute
export default function Home() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}
