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
