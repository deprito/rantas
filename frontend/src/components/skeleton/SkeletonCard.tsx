'use client';

import { Card } from '@/components/ui/card';

interface SkeletonCardProps {
  className?: string;
  children: React.ReactNode;
}

/**
 * A reusable skeleton card container with fade-in animation
 */
export function SkeletonCard({ className, children }: SkeletonCardProps) {
  return (
    <Card className={`${className} fade-in`}>
      {children}
    </Card>
  );
}

interface SkeletonShimmerProps {
  className?: string;
  height?: string;
  width?: string;
}

/**
 * A shimmer effect skeleton element with animation
 */
export function SkeletonShimmer({ className = '', height = 'h-4', width = 'w-full' }: SkeletonShimmerProps) {
  return (
    <div
      className={`${height} ${width} bg-accent/50 animate-pulse rounded ${className}`}
      role="presentation"
      aria-label="Loading content"
    />
  );
}

interface SkeletonCardProps {
  title?: boolean;
  subtitle?: boolean;
  lines?: number;
  icon?: boolean;
}

/**
 * Skeleton for a stats card with optional title, subtitle, lines, and icon
 */
export function SkeletonStatCard({ title = true, subtitle = false, lines = 0, icon = true }: SkeletonCardProps) {
  return (
    <div className="rounded-lg border p-4 bg-accent/5 border-accent/20">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          {title && (
            <SkeletonShimmer height="h-3" width="w-24" className="mb-2 opacity-60" />
          )}
          <SkeletonShimmer height="h-8" width="w-16" />
          {subtitle && (
            <SkeletonShimmer height="h-3" width="w-32" className="mt-2 opacity-60" />
          )}
          {lines > 0 && (
            <>
              {Array.from({ length: lines }).map((_, i) => (
                <SkeletonShimmer key={i} height="h-3" width="w-20" className="mt-1 opacity-40" />
              ))}
            </>
          )}
        </div>
        {icon && (
          <div className="p-3 rounded-full bg-accent/10">
            <SkeletonShimmer height="h-5" width="w-5" />
          </div>
        )}
      </div>
    </div>
  );
}

interface SkeletonTableProps {
  rows?: number;
  columns?: number;
  showHeader?: boolean;
}

/**
 * Skeleton for a table with specified rows and columns
 */
export function SkeletonTable({ rows = 5, columns = 4, showHeader = true }: SkeletonTableProps) {
  return (
    <div className="space-y-3">
      {showHeader && (
        <div className="flex gap-4 py-2 border-b">
          {Array.from({ length: columns }).map((_, i) => (
            <SkeletonShimmer key={`header-${i}`} height="h-4" width="w-20" className="opacity-60" />
          ))}
        </div>
      )}
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={`row-${rowIndex}`} className="h-10 bg-accent/10 rounded animate-pulse" />
      ))}
    </div>
  );
}

interface SkeletonChartProps {
  title?: string;
  height?: string;
  showLegend?: boolean;
}

/**
 * Skeleton for a chart component
 */
export function SkeletonChart({ title, height = 'h-[280px]', showLegend = true }: SkeletonChartProps) {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4">
      {title && (
        <h3 className="text-lg font-semibold mb-4">{title}</h3>
      )}
      <div className="flex items-center justify-center">
        <div className={`${height} w-full bg-accent/10 rounded animate-pulse flex items-center justify-center`}>
          <div className="w-32 h-32 rounded-full bg-accent/20 animate-pulse" />
        </div>
      </div>
      {showLegend && (
        <div className="flex justify-center gap-4 mt-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex items-center gap-2">
              <SkeletonShimmer height="h-3" width="w-3" className="rounded-full" />
              <SkeletonShimmer height="h-3" width="w-16" />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
