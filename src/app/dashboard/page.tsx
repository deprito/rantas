'use client';

import { useState, useEffect, useCallback } from 'react';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';
import { Permission } from '@/types/auth';
import { api } from '@/lib/api';
import {
  StatsOverview,
  StatusDistribution,
  TrendsResponse,
  TopDomainsResponse,
  TopRegistrarsResponse,
  EmailEffectiveness,
  ResolutionMetrics,
  BrandImpactedStats,
  DateRangeFilter,
  PeriodType,
} from '@/types/stats';

import { DashboardHeader } from './components/DashboardHeader';
import { StatsCards } from './components/StatsCards';
import { StatusChart } from './components/StatusChart';
import { TrendsChart } from './components/TrendsChart';
import { TopDomainsTable } from './components/TopDomainsTable';
import { TopRegistrarsTable } from './components/TopRegistrarsTable';
import { EmailMetricsCard } from './components/EmailMetricsCard';
import { ResolutionMetricsCard } from './components/ResolutionMetricsCard';
import { BrandImpactedChart } from './components/BrandImpactedChart';
import { AlertTriangle } from 'lucide-react';

function DashboardContent() {
  const { hasPermission } = useAuth();

  // State for filters
  const [dateRange, setDateRange] = useState<DateRangeFilter>({
    startDate: null,
    endDate: null,
  });
  const [trendsPeriod, setTrendsPeriod] = useState<PeriodType>('week');

  // State for data
  const [overview, setOverview] = useState<StatsOverview | null>(null);
  const [statusDistribution, setStatusDistribution] = useState<StatusDistribution | null>(null);
  const [trends, setTrends] = useState<TrendsResponse | null>(null);
  const [topDomains, setTopDomains] = useState<TopDomainsResponse | null>(null);
  const [topRegistrars, setTopRegistrars] = useState<TopRegistrarsResponse | null>(null);
  const [emailEffectiveness, setEmailEffectiveness] = useState<EmailEffectiveness | null>(null);
  const [resolutionMetrics, setResolutionMetrics] = useState<ResolutionMetrics | null>(null);
  const [brandImpactedStats, setBrandImpactedStats] = useState<BrandImpactedStats | null>(null);

  // Loading states
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Permission checks
  const canViewStats = hasPermission(Permission.STATS_VIEW);
  const canExportStats = hasPermission(Permission.STATS_EXPORT);

  // Fetch all data
  const fetchData = useCallback(async () => {
    if (!canViewStats) return;

    setIsLoading(true);
    setError(null);

    const params = {
      start_date: dateRange.startDate || undefined,
      end_date: dateRange.endDate || undefined,
    };

    try {
      // Fetch all data in parallel using allSettled for resilience
      const results = await Promise.allSettled([
        api.getStatsOverview(params),
        api.getStatusDistribution(params),
        api.getTrends({ period: trendsPeriod, days: 30 }),
        api.getTopDomains({ limit: 10, ...params }),
        api.getTopRegistrars({ limit: 10, ...params }),
        api.getEmailEffectiveness(params),
        api.getResolutionMetrics(params),
        api.getBrandImpactedStats(params),
      ]);

      // Extract results, keeping null for failed requests
      const [
        overviewResult,
        distributionResult,
        trendsResult,
        domainsResult,
        registrarsResult,
        emailResult,
        resolutionResult,
        brandImpactedResult,
      ] = results;

      // Check if all requests failed (likely server is down)
      const allFailed = results.every(r => r.status === 'rejected');
      if (allFailed) {
        const firstError = results[0].status === 'rejected' ? results[0].reason : null;
        throw firstError || new Error('All requests failed');
      }

      // Set data from successful requests
      if (overviewResult.status === 'fulfilled') setOverview(overviewResult.value);
      if (distributionResult.status === 'fulfilled') setStatusDistribution(distributionResult.value);
      if (trendsResult.status === 'fulfilled') setTrends(trendsResult.value);
      if (domainsResult.status === 'fulfilled') setTopDomains(domainsResult.value);
      if (registrarsResult.status === 'fulfilled') setTopRegistrars(registrarsResult.value);
      if (emailResult.status === 'fulfilled') setEmailEffectiveness(emailResult.value);
      if (resolutionResult.status === 'fulfilled') setResolutionMetrics(resolutionResult.value);
      if (brandImpactedResult.status === 'fulfilled') setBrandImpactedStats(brandImpactedResult.value);

      // Show warning if some requests failed
      const failedCount = results.filter(r => r.status === 'rejected').length;
      if (failedCount > 0) {
        console.warn(`${failedCount} of ${results.length} dashboard requests failed`);
      }
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err);
      setError(err instanceof Error ? err.message : 'Failed to load dashboard data');
    } finally {
      setIsLoading(false);
    }
  }, [canViewStats, dateRange, trendsPeriod]);

  // Initial load and refresh on filter changes
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Handle trends period change separately (only refetch trends)
  const handlePeriodChange = async (period: PeriodType) => {
    setTrendsPeriod(period);
    try {
      const trendsData = await api.getTrends({ period, days: 30 });
      setTrends(trendsData);
    } catch (err) {
      console.error('Failed to fetch trends:', err);
    }
  };

  if (!canViewStats) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900 flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="h-12 w-12 text-amber-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold mb-2">Access Denied</h2>
          <p className="text-muted-foreground">
            You don&apos;t have permission to view statistics.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
      <DashboardHeader
        dateRange={dateRange}
        onDateRangeChange={setDateRange}
        onRefresh={fetchData}
        isLoading={isLoading}
        hasExportPermission={canExportStats}
      />

      <main className="container mx-auto px-4 py-6">
        {error && (
          <div className="mb-6 bg-destructive/10 border border-destructive/20 text-destructive p-4 rounded-lg">
            <p className="font-medium flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              Error
            </p>
            <p className="text-sm mt-1">{error}</p>
          </div>
        )}

        {/* Stats Cards */}
        <section className="mb-6">
          <StatsCards data={overview} isLoading={isLoading} />
        </section>

        {/* Charts Row */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <StatusChart data={statusDistribution} isLoading={isLoading} />
          <TrendsChart
            data={trends}
            isLoading={isLoading}
            period={trendsPeriod}
            onPeriodChange={handlePeriodChange}
          />
        </section>

        {/* Metrics Cards Row */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <EmailMetricsCard data={emailEffectiveness} isLoading={isLoading} />
          <ResolutionMetricsCard data={resolutionMetrics} isLoading={isLoading} />
        </section>

        {/* Brand Impacted Row */}
        <section className="mb-6">
          <BrandImpactedChart data={brandImpactedStats} isLoading={isLoading} />
        </section>

        {/* Tables Row */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <TopDomainsTable data={topDomains} isLoading={isLoading} />
          <TopRegistrarsTable data={topRegistrars} isLoading={isLoading} />
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t bg-white/50 dark:bg-slate-950/50 backdrop-blur-sm mt-8">
        <div className="container mx-auto px-4 py-6 text-center text-sm text-muted-foreground">
          <p>
            PhishTrack Statistics Dashboard • Real-time case analytics
          </p>
        </div>
      </footer>
    </div>
  );
}

export default function Dashboard() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}
