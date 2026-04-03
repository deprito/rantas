export type CaseStatus = 'ANALYZING' | 'READY_TO_REPORT' | 'REPORTING' | 'REPORTED' | 'MONITORING' | 'RESOLVED' | 'FAILED';
export type CaseSource = 'internal' | 'public';

export interface AbuseContact {
  type: 'registrar' | 'hosting' | 'dns';
  email: string;
}

export interface DomainInfo {
  domain: string;
  age_days?: number;
  registrar?: string;
  ip?: string;
  asn?: string;
  ns_records: string[];
  created_date?: string;
}

export interface HistoryEntry {
  id: string;
  timestamp: string;
  type: 'dns_check' | 'http_check' | 'email_sent' | 'email_received' | 'system';
  status?: number;
  message: string;
}

export interface Case {
  id: string;
  url: string;
  status: CaseStatus;
  source: CaseSource;
  domain_info: DomainInfo | null;
  abuse_contacts: AbuseContact[];
  history: HistoryEntry[];
  monitor_interval: number;
  brand_impacted: string;
  created_at: string;
  updated_at: string;
  created_by?: string;
  created_by_username?: string;
  created_by_email?: string;
}

export const statusLabels: Record<CaseStatus, string> = {
  ANALYZING: 'Analyzing',
  READY_TO_REPORT: 'Ready to Report',
  REPORTING: 'Sending Report',
  REPORTED: 'Report Sent',
  MONITORING: 'Monitoring',
  RESOLVED: 'Resolved',
  FAILED: 'Failed',
};

export const statusColors: Record<CaseStatus, string> = {
  ANALYZING: 'bg-yellow-500',
  READY_TO_REPORT: 'bg-blue-500',
  REPORTING: 'bg-indigo-500',
  REPORTED: 'bg-purple-500',
  MONITORING: 'bg-orange-500',
  RESOLVED: 'bg-green-500',
  FAILED: 'bg-red-500',
};

// ==================== Export Types ====================

export type ExportFormat = 'csv' | 'json';

export interface CaseExportRequest {
  format: ExportFormat;
  start_date?: string;
  end_date?: string;
  status?: CaseStatus;
  source?: CaseSource;
  send_to_teams?: boolean;
}

export interface CaseExportResponse {
  export_id: string;
  download_url: string;
  format: string;
  cases_count: number;
  status: string;
  file_size_bytes?: number;
}

// ==================== Hunting Types ====================

export type DetectedDomainStatus = 'pending' | 'reviewed' | 'ignored' | 'case_created';

export interface DetectedDomain {
  id: string;
  domain: string;
  cert_data: Record<string, any>;
  matched_brand: string | null;
  matched_pattern: string | null;
  detection_score: number;
  cert_seen_at: string;
  created_at: string;
  status: DetectedDomainStatus;
  http_status_code: number | null;
  http_checked_at: string | null;
  notes: string | null;
  case_id: string | null;
}

export interface DetectedDomainListResponse {
  domains: DetectedDomain[];
  total: number;
  page: number;
  page_size: number;
}

export interface DetectedDomainUpdate {
  status?: DetectedDomainStatus;
  notes?: string;
}

export interface HuntingStats {
  total_detected: number;
  pending: number;
  reviewed: number;
  ignored: number;
  cases_created: number;
  high_confidence: number;
  top_brands: string[];
  http_status_counts: Record<string, number>;
}

export interface HuntingConfig {
  monitor_enabled: boolean;
  min_score_threshold: number;
  alert_threshold: number;
  monitored_brands: string[];
  retention_days: number;
  raw_log_retention_days: number;
  custom_brand_patterns: Record<string, string[]>;
  custom_brand_regex_patterns: Record<string, string[]>;
  default_brand_patterns: Record<string, string[]>;
  whitelist_patterns: string[];
}

export interface HuntingStatus {
  monitor_is_running: boolean;
  monitor_enabled: boolean;
  monitor_started_at: string | null;
  monitor_last_heartbeat: string | null;
  monitor_last_seen_at: string | null;
  certificates_processed: number;
  domains_detected: number;
  error_message: string | null;
}

export interface CaseFromDetectionRequest {
  monitor_interval?: number;
  brand_impacted?: string;
}

export const detectedDomainStatusLabels: Record<DetectedDomainStatus, string> = {
  pending: 'Pending',
  reviewed: 'Reviewed',
  ignored: 'Ignored',
  case_created: 'Case Created',
};

export const detectedDomainStatusColors: Record<DetectedDomainStatus, string> = {
  pending: 'bg-yellow-500',
  reviewed: 'bg-blue-500',
  ignored: 'bg-gray-500',
  case_created: 'bg-green-500',
};
