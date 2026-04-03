/**
 * TypeScript interfaces for statistics dashboard
 */

export interface StatsOverview {
  total_cases: number;
  active_cases: number;
  resolved_cases: number;
  failed_cases: number;
  success_rate: number;
  average_resolution_time_hours: number | null;
  total_emails_sent: number;
  cases_created_today: number;
  cases_resolved_today: number;
  internal_cases: number;
  public_cases: number;
  pending_submissions: number;
  top_brands: string[];
  total_cases_with_brand: number;
  total_cases_without_brand: number;
}

export interface StatusDistributionItem {
  status: string;
  count: number;
  percentage: number;
}

export interface StatusDistribution {
  distribution: StatusDistributionItem[];
  total: number;
}

export interface TrendDataPoint {
  date: string;
  created: number;
  resolved: number;
  failed: number;
}

export interface TrendsResponse {
  period: string;
  start_date: string;
  end_date: string;
  data: TrendDataPoint[];
}

export interface TopDomainItem {
  domain: string;
  case_count: number;
  resolved_count: number;
  failed_count: number;
  resolution_rate: number;
}

export interface TopDomainsResponse {
  domains: TopDomainItem[];
  total: number;
}

export interface TopRegistrarItem {
  registrar: string;
  case_count: number;
  resolved_count: number;
  resolution_rate: number;
  avg_resolution_hours: number | null;
}

export interface TopRegistrarsResponse {
  registrars: TopRegistrarItem[];
  total: number;
}

export interface EmailEffectiveness {
  total_emails_sent: number;
  cases_with_emails: number;
  avg_emails_per_case: number;
  cases_resolved_after_email: number;
  email_success_rate: number;
}

export interface ResolutionMetrics {
  average_hours: number | null;
  median_hours: number | null;
  min_hours: number | null;
  max_hours: number | null;
  resolved_count: number;
}

export interface BrandImpactedItem {
  brand: string;
  case_count: number;
  resolved_count: number;
  failed_count: number;
  resolution_rate: number;
}

export interface BrandImpactedStats {
  brands: BrandImpactedItem[];
  total_cases_with_brand: number;
  total_cases_without_brand: number;
}

export type PeriodType = 'day' | 'week' | 'month';

export interface UserStatsItem {
  user_id: string;
  username: string;
  email: string;
  total_cases: number;
  internal_cases: number;
  public_cases: number;
  resolved_count: number;
  failed_count: number;
  resolution_rate: number;
}

export interface UserStatsResponse {
  users: UserStatsItem[];
  total: number;
}

export interface DateRangeFilter {
  startDate: string | null;
  endDate: string | null;
}

export interface StatsFilters {
  dateRange: DateRangeFilter;
  period: PeriodType;
}

// Status colors for charts
export const STATUS_COLORS: Record<string, string> = {
  ANALYZING: '#3b82f6',      // blue
  READY_TO_REPORT: '#f59e0b', // amber
  REPORTING: '#8b5cf6',       // violet
  REPORTED: '#06b6d4',        // cyan
  MONITORING: '#6366f1',      // indigo
  RESOLVED: '#22c55e',        // green
  FAILED: '#ef4444',          // red
};

export const STATUS_LABELS: Record<string, string> = {
  ANALYZING: 'Analyzing',
  READY_TO_REPORT: 'Ready to Report',
  REPORTING: 'Reporting',
  REPORTED: 'Reported',
  MONITORING: 'Monitoring',
  RESOLVED: 'Resolved',
  FAILED: 'Failed',
};

// Historical import types
export interface ImportResponse {
  success: boolean;
  imported_count: number;
  skipped_count: number;
  errors: string[];
}

export interface HistoricalCaseImport {
  url: string;
  status?: string;
  source?: string;
  brand_impacted?: string;
  emails_sent?: number;
  created_at: string;
  updated_at?: string;
  registrar?: string;
  ip?: string;
}
