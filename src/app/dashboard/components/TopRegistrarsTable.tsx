'use client';

import { TopRegistrarsResponse } from '@/types/stats';
import { Building2 } from 'lucide-react';

interface TopRegistrarsTableProps {
  data: TopRegistrarsResponse | null;
  isLoading: boolean;
}

export function TopRegistrarsTable({ data, isLoading }: TopRegistrarsTableProps) {
  const formatHours = (hours: number | null): string => {
    if (hours === null) return 'N/A';
    if (hours < 1) return `${Math.round(hours * 60)}m`;
    if (hours < 24) return `${hours.toFixed(1)}h`;
    return `${(hours / 24).toFixed(1)}d`;
  };

  if (isLoading) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Building2 className="h-5 w-5 text-teal-500" />
          Top Registrars
        </h3>
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-10 bg-slate-100 dark:bg-slate-800 rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!data || data.registrars.length === 0) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Building2 className="h-5 w-5 text-teal-500" />
          Top Registrars
        </h3>
        <div className="text-center py-8 text-muted-foreground">
          No registrar data available
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
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <Building2 className="h-5 w-5 text-teal-500" />
        Top Registrars
        <span className="text-sm font-normal text-muted-foreground ml-auto">
          {data.total} total
        </span>
      </h3>

      {/* Mobile Card View */}
      <div className="sm:hidden space-y-2">
        {data.registrars.map((registrar, index) => (
          <div
            key={registrar.registrar}
            className="bg-muted/30 rounded-lg p-3 border border-slate-100 dark:border-slate-800"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium text-xs truncate flex-1" title={registrar.registrar}>
                {registrar.registrar}
              </span>
              <span className={`text-xs font-bold ${getResolutionColor(registrar.resolution_rate)}`}>
                {registrar.resolution_rate.toFixed(0)}%
              </span>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="text-muted-foreground">
                <span className="font-medium text-foreground">{registrar.case_count}</span> cases
              </span>
              <span className="text-green-600">
                {registrar.resolved_count} resolved
              </span>
              <span className="text-muted-foreground">
                Avg: {formatHours(registrar.avg_resolution_hours)}
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
              <th className="text-left py-2 px-2 font-medium text-muted-foreground">Registrar</th>
              <th className="text-center py-2 px-2 font-medium text-muted-foreground">Cases</th>
              <th className="text-center py-2 px-2 font-medium text-muted-foreground">Resolved</th>
              <th className="text-center py-2 px-2 font-medium text-muted-foreground">Rate</th>
              <th className="text-right py-2 px-2 font-medium text-muted-foreground">Avg Time</th>
            </tr>
          </thead>
          <tbody>
            {data.registrars.map((registrar, index) => (
              <tr
                key={registrar.registrar}
                className={`border-b border-slate-100 dark:border-slate-800 ${
                  index % 2 === 0 ? 'bg-slate-50/50 dark:bg-slate-800/20' : ''
                }`}
              >
                <td className="py-2 px-2 truncate max-w-[180px]" title={registrar.registrar}>
                  {registrar.registrar}
                </td>
                <td className="py-2 px-2 text-center font-medium">{registrar.case_count}</td>
                <td className="py-2 px-2 text-center text-green-600">{registrar.resolved_count}</td>
                <td className={`py-2 px-2 text-center font-medium ${getResolutionColor(registrar.resolution_rate)}`}>
                  {registrar.resolution_rate.toFixed(0)}%
                </td>
                <td className="py-2 px-2 text-right text-muted-foreground">
                  {formatHours(registrar.avg_resolution_hours)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
