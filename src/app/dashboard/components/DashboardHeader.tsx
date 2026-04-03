'use client';

import { RefreshCw, BarChart3, Inbox } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { UserMenu } from '@/components/user-menu';
import { DateRangeFilter } from './DateRangeFilter';
import { ExportControls } from './ExportControls';
import { DateRangeFilter as DateRangeFilterType } from '@/types/stats';
import { usePendingCount } from '@/hooks/usePendingCount';
import Link from 'next/link';

interface DashboardHeaderProps {
  dateRange: DateRangeFilterType;
  onDateRangeChange: (range: DateRangeFilterType) => void;
  onRefresh: () => void;
  isLoading: boolean;
  hasExportPermission: boolean;
}

export function DashboardHeader({
  dateRange,
  onDateRangeChange,
  onRefresh,
  isLoading,
  hasExportPermission,
}: DashboardHeaderProps) {
  const { pendingCount } = usePendingCount();

  return (
    <header className="border-b bg-white/50 dark:bg-slate-950/50 backdrop-blur-sm sticky top-0 z-10">
      <div className="container mx-auto px-4 py-4">
        {/* Desktop: Single row layout */}
        <div className="hidden md:block">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <Link href="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
                <div className="bg-primary/10 p-2 rounded-lg">
                  <BarChart3 className="h-6 w-6 text-primary" />
                </div>
                <div>
                  <h1 className="text-xl font-bold">Statistics Dashboard</h1>
                  <p className="text-xs text-muted-foreground">
                    PhishTrack Case Analytics
                  </p>
                </div>
              </Link>
            </div>

            <div className="flex items-center gap-2">
              {pendingCount > 0 && (
                <Link href="/admin?tab=submissions">
                  <Button variant="outline" size="sm" className="gap-2">
                    <Inbox className="h-4 w-4" />
                    Pending Submissions
                    <Badge variant="destructive" className="h-5 w-5 p-0 flex items-center justify-center text-xs">
                      {pendingCount > 99 ? '99+' : pendingCount}
                    </Badge>
                  </Button>
                </Link>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={onRefresh}
                disabled={isLoading}
              >
                <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              </Button>
              <UserMenu />
            </div>
          </div>

          <div className="flex items-center justify-between gap-4">
            <DateRangeFilter
              dateRange={dateRange}
              onDateRangeChange={onDateRangeChange}
            />
            <ExportControls
              dateRange={dateRange}
              hasExportPermission={hasExportPermission}
            />
          </div>
        </div>

        {/* Mobile: Compact layout */}
        <div className="md:hidden">
          {/* Top row - Title and actions */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Link href="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
                <div className="bg-primary/10 p-1.5 rounded-lg">
                  <BarChart3 className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h1 className="text-base font-bold">Statistics Dashboard</h1>
                </div>
              </Link>
            </div>

            <div className="flex items-center gap-1">
              {pendingCount > 0 && (
                <Link href="/admin?tab=submissions">
                  <Button variant="outline" size="sm" className="gap-1 text-xs">
                    <Inbox className="h-4 w-4" />
                    <Badge variant="destructive" className="h-5 w-5 p-0 flex items-center justify-center text-xs">
                      {pendingCount > 99 ? '99+' : pendingCount}
                    </Badge>
                  </Button>
                </Link>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={onRefresh}
                disabled={isLoading}
                className="px-2"
              >
                <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              </Button>
              <UserMenu />
            </div>
          </div>

          {/* Filters row - scrollable on mobile */}
          <div className="flex flex-col gap-2 overflow-x-auto scrollbar-hide -mx-4 px-4">
            <DateRangeFilter
              dateRange={dateRange}
              onDateRangeChange={onDateRangeChange}
            />
            <ExportControls
              dateRange={dateRange}
              hasExportPermission={hasExportPermission}
            />
          </div>
        </div>
      </div>
    </header>
  );
}
