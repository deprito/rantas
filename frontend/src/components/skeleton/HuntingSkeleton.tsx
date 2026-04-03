'use client';

import { Card } from '@/components/ui/card';
import { SkeletonShimmer } from './SkeletonCard';

/**
 * Skeleton for Hunting Status Card
 */
export function HuntingStatusSkeleton() {
  return (
    <Card className="p-4 border-l-4 border-l-gray-400 bg-gray-50/50 dark:bg-gray-950/20 fade-in">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <SkeletonShimmer height="h-4" width="w-4" className="rounded-full" />
            <SkeletonShimmer height="h-4" width="w-48" />
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex items-center gap-1">
                <SkeletonShimmer height="h-3" width="w-3" />
                <SkeletonShimmer height="h-3" width="w-24" />
              </div>
            ))}
          </div>
        </div>
        <SkeletonShimmer height="h-8" width="w-16" className="shrink-0 rounded" />
      </div>
    </Card>
  );
}

/**
 * Skeleton for Hunting Stats Cards
 */
export function HuntingStatsSkeleton() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 fade-in">
      {[1, 2, 3, 4, 5].map((i) => (
        <Card key={i} className="p-4">
          <SkeletonShimmer height="h-8" width="w-20" className="mb-2" />
          <SkeletonShimmer height="h-3" width="w-28" />
        </Card>
      ))}
    </div>
  );
}

/**
 * Skeleton for Hunting Domain List Item
 */
export function HuntingDomainSkeleton() {
  return (
    <Card className="p-4 fade-in">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <SkeletonShimmer height="h-6" width="w-48" />
            <SkeletonShimmer height="h-6" width="w-20" />
            <SkeletonShimmer height="h-6" width="w-24" />
            <SkeletonShimmer height="h-6" width="w-28" />
          </div>
          <div className="text-sm space-y-1">
            <SkeletonShimmer height="h-4" width="w-64" />
            <div className="flex items-center gap-2">
              <SkeletonShimmer height="h-4" width="w-32" />
              <SkeletonShimmer height="h-3" width="w-24" />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <SkeletonShimmer height="h-8" width="w-16" className="rounded" />
          <SkeletonShimmer height="h-8" width="w-20" className="rounded" />
          <SkeletonShimmer height="h-8" width="w-20" className="rounded" />
        </div>
      </div>
    </Card>
  );
}

/**
 * Skeleton for Hunting Filter Bar
 */
export function HuntingFiltersSkeleton() {
  return (
    <Card className="p-4 fade-in">
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <SkeletonShimmer height="h-4" width="w-4" />
          <SkeletonShimmer height="h-4" width="w-16" />
        </div>
        {[1, 2, 3, 4].map((i) => (
          <SkeletonShimmer key={i} height="h-9" width="w-32" className="rounded" />
        ))}
      </div>
    </Card>
  );
}

/**
 * Skeleton for CertPatrol Raw Stream
 */
export function CertPatrolStreamSkeleton() {
  return (
    <Card className="p-0 overflow-hidden fade-in">
      <div className="p-4 border-b">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <SkeletonShimmer height="h-4" width="w-4" />
            <SkeletonShimmer height="h-4" width="w-40" />
          </div>
          <div className="flex items-center gap-1">
            <SkeletonShimmer height="h-2" width="w-2" className="rounded-full" />
            <SkeletonShimmer height="h-3" width="w-16" />
          </div>
        </div>
      </div>
      <div className="bg-slate-950 p-3 font-mono text-xs h-[calc(100vh-350px)] overflow-y-auto">
        <div className="flex flex-col items-center justify-center h-full text-slate-500">
          {[1, 2, 3].map((i) => (
            <div key={i} className="w-full max-w-md mb-4 border-b border-slate-800 pb-2">
              <div className="flex items-center gap-2 text-slate-400 mb-1">
                <SkeletonShimmer height="h-3" width="w-12" className="bg-slate-700" />
                <SkeletonShimmer height="h-3" width="w-16" className="bg-slate-700" />
                <SkeletonShimmer height="h-3" width="w-20" className="bg-slate-700 ml-auto" />
              </div>
              <SkeletonShimmer height="h-4" width="w-full" className="bg-slate-800" />
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
