'use client';

import { TopDomainsResponse } from '@/types/stats';
import { Globe } from 'lucide-react';

interface TopDomainsTableProps {
  data: TopDomainsResponse | null;
  isLoading: boolean;
}

export function TopDomainsTable({ data, isLoading }: TopDomainsTableProps) {
  if (isLoading) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Globe className="h-5 w-5 text-blue-500" />
          Top Reported Domains
        </h3>
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-10 bg-slate-100 dark:bg-slate-800 rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!data || data.domains.length === 0) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Globe className="h-5 w-5 text-blue-500" />
          Top Reported Domains
        </h3>
        <div className="text-center py-8 text-muted-foreground">
          No domain data available
        </div>
      </div>
    );
  }

  const getResolutionColor = (rate: number): string => {
    if (rate >= 80) return 'text-green-600';
    if (rate >= 50) return 'text-amber-600';
    return 'text-red-600';
  };

  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4 fade-in">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <Globe className="h-5 w-5 text-blue-500" />
        Top Reported Domains
        <span className="text-sm font-normal text-muted-foreground ml-auto">
          {data.total} total
        </span>
      </h3>

      {/* Mobile Card View */}
      <div className="sm:hidden space-y-2">
        {data.domains.map((domain, index) => (
          <div
            key={domain.domain}
            className="bg-muted/30 rounded-lg p-3 border border-slate-100 dark:border-slate-800"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-mono text-xs truncate flex-1" title={domain.domain}>
                {domain.domain}
              </span>
              <span className={`text-xs font-bold ${getResolutionColor(domain.resolution_rate)}`}>
                {domain.resolution_rate.toFixed(0)}%
              </span>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="text-muted-foreground">
                <span className="font-medium text-foreground">{domain.case_count}</span> cases
              </span>
              <span className="text-green-600">
                {domain.resolved_count} resolved
              </span>
              <span className="text-red-600">
                {domain.failed_count} failed
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Desktop Table View */}
      <div className="hidden sm:block overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 dark:border-slate-700">
              <th className="text-left py-2 px-2 font-medium text-muted-foreground">Domain</th>
              <th className="text-center py-2 px-2 font-medium text-muted-foreground">Cases</th>
              <th className="text-center py-2 px-2 font-medium text-muted-foreground">Resolved</th>
              <th className="text-center py-2 px-2 font-medium text-muted-foreground">Failed</th>
              <th className="text-right py-2 px-2 font-medium text-muted-foreground">Rate</th>
            </tr>
          </thead>
          <tbody>
            {data.domains.map((domain, index) => (
              <tr
                key={domain.domain}
                className={`border-b border-slate-100 dark:border-slate-800 ${
                  index % 2 === 0 ? 'bg-slate-50/50 dark:bg-slate-800/20' : ''
                }`}
              >
                <td className="py-2 px-2 font-mono text-xs truncate max-w-[200px]" title={domain.domain}>
                  {domain.domain}
                </td>
                <td className="py-2 px-2 text-center font-medium">{domain.case_count}</td>
                <td className="py-2 px-2 text-center text-green-600">{domain.resolved_count}</td>
                <td className="py-2 px-2 text-center text-red-600">{domain.failed_count}</td>
                <td className={`py-2 px-2 text-right font-medium ${getResolutionColor(domain.resolution_rate)}`}>
                  {domain.resolution_rate.toFixed(0)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
