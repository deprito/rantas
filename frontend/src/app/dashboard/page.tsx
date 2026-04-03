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
  UserStatsResponse,
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
import { UserLeaderboard } from './components/UserLeaderboard';
import { AlertTriangle } from 'lucide-react';

function DashboardContent() {
  const { hasPermission } = useAuth();

  // State for filters
  const [dateRange, setDateRange] = useState<DateRangeFilter>({
    startDate: null,
    endDate: null,
  });
  const [trendsPeriod, setTrendsPeriod] = useState<PeriodType>('week');

  // State for historical data toggle (persisted in localStorage)
  const [includeHistorical, setIncludeHistorical] = useState<boolean>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('includeHistoricalData');
      return saved === 'true';
    }
    return false;
  });

  // Update localStorage when toggle changes
  useEffect(() => {
    localStorage.setItem('includeHistoricalData', String(includeHistorical));
  }, [includeHistorical]);

  // State for data
  const [overview, setOverview] = useState<StatsOverview | null>(null);
  const [statusDistribution, setStatusDistribution] = useState<StatusDistribution | null>(null);
  const [trends, setTrends] = useState<TrendsResponse | null>(null);
  const [topDomains, setTopDomains] = useState<TopDomainsResponse | null>(null);
  const [topRegistrars, setTopRegistrars] = useState<TopRegistrarsResponse | null>(null);
  const [emailEffectiveness, setEmailEffectiveness] = useState<EmailEffectiveness | null>(null);
  const [resolutionMetrics, setResolutionMetrics] = useState<ResolutionMetrics | null>(null);
  const [brandImpactedStats, setBrandImpactedStats] = useState<BrandImpactedStats | null>(null);
  const [userStats, setUserStats] = useState<UserStatsResponse | null>(null);

  // Per-component loading states for progressive loading
  const [isLoadingOverview, setIsLoadingOverview] = useState(true);
  const [isLoadingStatus, setIsLoadingStatus] = useState(true);
  const [isLoadingTrends, setIsLoadingTrends] = useState(true);
  const [isLoadingDomains, setIsLoadingDomains] = useState(true);
  const [isLoadingRegistrars, setIsLoadingRegistrars] = useState(true);
  const [isLoadingEmail, setIsLoadingEmail] = useState(true);
  const [isLoadingResolution, setIsLoadingResolution] = useState(true);
  const [isLoadingBrand, setIsLoadingBrand] = useState(true);
  const [isLoadingUsers, setIsLoadingUsers] = useState(true);

  // General loading state for initial page load
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Permission checks
  const canViewStats = hasPermission(Permission.STATS_VIEW);
  const canExportStats = hasPermission(Permission.STATS_EXPORT);
  const canImportStats = hasPermission(Permission.STATS_IMPORT);

  // Fetch individual data sources for progressive loading
  const fetchOverview = useCallback(async (params: Record<string, unknown>) => {
    setIsLoadingOverview(true);
    try {
      const data = await api.getStatsOverview(params);
      setOverview(data);
    } catch (err) {
      console.error('Failed to fetch overview:', err);
    } finally {
      setIsLoadingOverview(false);
    }
  }, []);

  const fetchStatusDistribution = useCallback(async (params: Record<string, unknown>) => {
    setIsLoadingStatus(true);
    try {
      const data = await api.getStatusDistribution(params);
      setStatusDistribution(data);
    } catch (err) {
      console.error('Failed to fetch status distribution:', err);
    } finally {
      setIsLoadingStatus(false);
    }
  }, []);

  const fetchTrends = useCallback(async (params: Record<string, unknown>) => {
    setIsLoadingTrends(true);
    try {
      const data = await api.getTrends(params);
      setTrends(data);
    } catch (err) {
      console.error('Failed to fetch trends:', err);
    } finally {
      setIsLoadingTrends(false);
    }
  }, []);

  const fetchTopDomains = useCallback(async (params: Record<string, unknown>) => {
    setIsLoadingDomains(true);
    try {
      const data = await api.getTopDomains({ limit: 10, ...params });
      setTopDomains(data);
    } catch (err) {
      console.error('Failed to fetch top domains:', err);
    } finally {
      setIsLoadingDomains(false);
    }
  }, []);

  const fetchTopRegistrars = useCallback(async (params: Record<string, unknown>) => {
    setIsLoadingRegistrars(true);
    try {
      const data = await api.getTopRegistrars({ limit: 10, ...params });
      setTopRegistrars(data);
    } catch (err) {
      console.error('Failed to fetch top registrars:', err);
    } finally {
      setIsLoadingRegistrars(false);
    }
  }, []);

  const fetchEmailEffectiveness = useCallback(async (params: Record<string, unknown>) => {
    setIsLoadingEmail(true);
    try {
      const data = await api.getEmailEffectiveness(params);
      setEmailEffectiveness(data);
    } catch (err) {
      console.error('Failed to fetch email effectiveness:', err);
    } finally {
      setIsLoadingEmail(false);
    }
  }, []);

  const fetchResolutionMetrics = useCallback(async (params: Record<string, unknown>) => {
    setIsLoadingResolution(true);
    try {
      const data = await api.getResolutionMetrics(params);
      setResolutionMetrics(data);
    } catch (err) {
      console.error('Failed to fetch resolution metrics:', err);
    } finally {
      setIsLoadingResolution(false);
    }
  }, []);

  const fetchBrandImpactedStats = useCallback(async (params: Record<string, unknown>) => {
    setIsLoadingBrand(true);
    try {
      const data = await api.getBrandImpactedStats(params);
      setBrandImpactedStats(data);
    } catch (err) {
      console.error('Failed to fetch brand impacted stats:', err);
    } finally {
      setIsLoadingBrand(false);
    }
  }, []);

  const fetchUserStats = useCallback(async (params: Record<string, unknown>) => {
    setIsLoadingUsers(true);
    try {
      const data = await api.getUserStats(params);
      setUserStats(data);
    } catch (err) {
      console.error('Failed to fetch user stats:', err);
    } finally {
      setIsLoadingUsers(false);
    }
  }, []);

  // Fetch all data (progressively - each updates independently)
  const fetchData = useCallback(async () => {
    if (!canViewStats) return;

    setIsInitialLoad(true);
    setError(null);

    const params = {
      start_date: dateRange.startDate || undefined,
      end_date: dateRange.endDate || undefined,
      include_historical: includeHistorical,
    };

    const trendsParams = {
      period: trendsPeriod,
      days: 30,
      include_historical: includeHistorical,
    };

    // Fetch all data in parallel, but each updates its own loading state
    try {
      await Promise.allSettled([
        fetchOverview(params),
        fetchStatusDistribution(params),
        fetchTrends(trendsParams),
        fetchTopDomains(params),
        fetchTopRegistrars(params),
        fetchEmailEffectiveness(params),
        fetchResolutionMetrics(params),
        fetchBrandImpactedStats(params),
        fetchUserStats(params),
      ]);
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err);
      setError(err instanceof Error ? err.message : 'Failed to load dashboard data');
    } finally {
      setIsInitialLoad(false);
    }
  }, [canViewStats, dateRange, trendsPeriod, includeHistorical, fetchOverview, fetchStatusDistribution, fetchTrends, fetchTopDomains, fetchTopRegistrars, fetchEmailEffectiveness, fetchResolutionMetrics, fetchBrandImpactedStats, fetchUserStats]);

  // Initial load and refresh on filter changes
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Handle trends period change separately (only refetch trends)
  const handlePeriodChange = async (period: PeriodType) => {
    setTrendsPeriod(period);
    await fetchTrends({ period, days: 30, include_historical: includeHistorical });
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
        isLoading={isInitialLoad}
        hasExportPermission={canExportStats}
        hasImportPermission={canImportStats}
        includeHistorical={includeHistorical}
        onIncludeHistoricalChange={setIncludeHistorical}
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
          <StatsCards data={overview} isLoading={isLoadingOverview} />
        </section>

        {/* Charts Row */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <StatusChart data={statusDistribution} isLoading={isLoadingStatus} />
          <TrendsChart
            data={trends}
            isLoading={isLoadingTrends}
            period={trendsPeriod}
            onPeriodChange={handlePeriodChange}
          />
        </section>

        {/* Metrics Cards Row */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <EmailMetricsCard data={emailEffectiveness} isLoading={isLoadingEmail} />
          <ResolutionMetricsCard data={resolutionMetrics} isLoading={isLoadingResolution} />
        </section>

        {/* Brand Impacted Row */}
        <section className="mb-6">
          <BrandImpactedChart data={brandImpactedStats} isLoading={isLoadingBrand} />
        </section>

        {/* User Leaderboard Row */}
        <section className="mb-6">
          <UserLeaderboard data={userStats} isLoading={isLoadingUsers} />
        </section>

        {/* Tables Row */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <TopDomainsTable data={topDomains} isLoading={isLoadingDomains} />
          <TopRegistrarsTable data={topRegistrars} isLoading={isLoadingRegistrars} />
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
