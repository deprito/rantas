'use client';

import { ResolutionMetrics } from '@/types/stats';
import { Clock, TrendingUp, TrendingDown, Timer } from 'lucide-react';

interface ResolutionMetricsCardProps {
  data: ResolutionMetrics | null;
  isLoading: boolean;
}

export function ResolutionMetricsCard({ data, isLoading }: ResolutionMetricsCardProps) {
  const formatHours = (hours: number | null): string => {
    if (hours === null) return 'N/A';
    if (hours < 1) return `${Math.round(hours * 60)} min`;
    if (hours < 24) return `${hours.toFixed(1)} hrs`;
    const days = hours / 24;
    if (days < 7) return `${days.toFixed(1)} days`;
    return `${(days / 7).toFixed(1)} weeks`;
  };

  if (isLoading) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Clock className="h-5 w-5 text-purple-500" />
          Resolution Metrics
        </h3>
        <div className="space-y-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-12 bg-slate-100 dark:bg-slate-800 rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!data || data.resolved_count === 0) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Clock className="h-5 w-5 text-purple-500" />
          Resolution Metrics
        </h3>
        <div className="text-center py-8 text-muted-foreground">
          No resolution data available
        </div>
      </div>
    );
  }

  const metrics = [
    {
      label: 'Average Time',
      value: formatHours(data.average_hours),
      icon: <Timer className="h-4 w-4 text-purple-500" />,
      highlight: true,
    },
    {
      label: 'Median Time',
      value: formatHours(data.median_hours),
      icon: <Clock className="h-4 w-4 text-blue-500" />,
    },
    {
      label: 'Fastest Resolution',
      value: formatHours(data.min_hours),
      icon: <TrendingDown className="h-4 w-4 text-green-500" />,
    },
    {
      label: 'Slowest Resolution',
      value: formatHours(data.max_hours),
      icon: <TrendingUp className="h-4 w-4 text-red-500" />,
    },
  ];

  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <Clock className="h-5 w-5 text-purple-500" />
        Resolution Metrics
        <span className="text-sm font-normal text-muted-foreground ml-auto">
          {data.resolved_count} resolved
        </span>
      </h3>
      <div className="space-y-3">
        {metrics.map((metric) => (
          <div
            key={metric.label}
            className={`flex items-center justify-between py-2 border-b border-slate-100 dark:border-slate-800 last:border-0 ${
              metric.highlight ? 'bg-purple-50 dark:bg-purple-900/20 -mx-2 px-2 rounded' : ''
            }`}
          >
            <div className="flex items-center gap-2">
              {metric.icon}
              <span className="text-sm text-muted-foreground">{metric.label}</span>
            </div>
            <span className={`font-semibold ${metric.highlight ? 'text-purple-600' : ''}`}>
              {metric.value}
            </span>
          </div>
        ))}
      </div>
      {data.average_hours && data.median_hours && (
        <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700">
          <p className="text-xs text-muted-foreground">
            {data.average_hours > data.median_hours
              ? 'Average is higher than median, indicating some cases take significantly longer to resolve.'
              : 'Consistent resolution times across cases.'}
          </p>
        </div>
      )}
    </div>
  );
}
