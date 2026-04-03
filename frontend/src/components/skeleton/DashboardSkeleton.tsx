'use client';

import { Card } from '@/components/ui/card';
import { SkeletonShimmer } from './SkeletonCard';

/**
 * Skeleton for Dashboard Stats Cards
 */
export function DashboardStatsSkeleton() {
  return (
    <div className="space-y-4 fade-in">
      {/* Main Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="rounded-lg border p-4 bg-accent/5 border-accent/20">
            <div className="flex items-center justify-between">
              <div>
                <SkeletonShimmer height="h-3" width="w-20" className="mb-2 opacity-60" />
                <SkeletonShimmer height="h-8" width="w-16" />
              </div>
              <div className="p-3 rounded-full bg-accent/10">
                <SkeletonShimmer height="h-5" width="w-5" />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Source Breakdown Row */}
      <Card className="p-4">
        <SkeletonShimmer height="h-4" width="w-48" className="mb-3" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="rounded-lg border p-4 bg-accent/5 border-accent/20">
              <div className="flex items-center justify-between">
                <div>
                  <SkeletonShimmer height="h-3" width="w-28" className="mb-2 opacity-60" />
                  <SkeletonShimmer height="h-8" width="w-16" />
                  <SkeletonShimmer height="h-3" width="w-32" className="mt-2 opacity-60" />
                </div>
                <div className="p-3 rounded-full bg-accent/10">
                  <SkeletonShimmer height="h-5" width="w-5" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

/**
 * Skeleton for Dashboard Chart (Status Distribution, Trends, etc.)
 */
export function DashboardChartSkeleton({ title = 'Chart' }: { title?: string }) {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4 h-[350px] fade-in">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">{title}</h3>
        {title === 'Case Trends' && (
          <SkeletonShimmer height="h-8" width="w-32" />
        )}
      </div>
      <div className="h-[280px] bg-accent/10 rounded animate-pulse flex items-center justify-center">
        <div className="w-48 h-48 rounded-full bg-accent/20 animate-pulse" />
      </div>
    </div>
  );
}

/**
 * Skeleton for Dashboard Metrics Card (Email Metrics, Resolution Metrics, etc.)
 */
export function DashboardMetricsCardSkeleton({ title }: { title: string }) {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4 fade-in">
      <h3 className="text-lg font-semibold mb-4">{title}</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="text-center">
            <SkeletonShimmer height="h-8" width="w-16" className="mx-auto mb-1" />
            <SkeletonShimmer height="h-3" width="w-24" className="mx-auto opacity-60" />
          </div>
        ))}
      </div>
      <div className="mt-4 space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex items-center justify-between">
            <SkeletonShimmer height="h-4" width="w-32" />
            <SkeletonShimmer height="h-4" width="w-16" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Skeleton for Dashboard Table (Top Domains, Top Registrars, etc.)
 */
export function DashboardTableSkeleton({ title, icon }: { title: string; icon?: React.ReactNode }) {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4 fade-in">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        {icon || (
          <div className="h-5 w-5 bg-accent/20 rounded animate-pulse" />
        )}
        {title}
      </h3>
      <div className="space-y-3">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-10 bg-accent/10 rounded animate-pulse" />
        ))}
      </div>
    </div>
  );
}

/**
 * Skeleton for Brand Impacted Chart
 */
export function BrandImpactedSkeleton() {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4 fade-in">
      <h3 className="text-lg font-semibold mb-4">Brand Impacted Statistics</h3>
      <div className="h-[200px] bg-accent/10 rounded animate-pulse flex items-center justify-center">
        <div className="w-32 h-32 rounded-full bg-accent/20 animate-pulse" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="text-center">
            <SkeletonShimmer height="h-6" width="w-12" className="mx-auto mb-1" />
            <SkeletonShimmer height="h-3" width="w-24" className="mx-auto opacity-60" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Skeleton for User Leaderboard
 */
export function UserLeaderboardSkeleton() {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4 fade-in">
      <h3 className="text-lg font-semibold mb-4">User Leaderboard</h3>
      <div className="space-y-3">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="flex items-center gap-4">
            <SkeletonShimmer height="h-8" width="w-8" className="rounded-full shrink-0" />
            <SkeletonShimmer height="h-4" width="w-32" className="flex-1" />
            <SkeletonShimmer height="h-6" width="w-16" />
          </div>
        ))}
      </div>
    </div>
  );
}
