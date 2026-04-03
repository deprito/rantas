/**
 * XARF (eXtended Abuse Reporting Format) v4 Type Definitions
 *
 * XARF is a JSON-based standard for abuse reporting used by providers
 * like DigitalOcean Abuse.
 *
 * Specification: https://xarf.org/docs/specification/
 */

/**
 * XARF Entity information (reporter or sender)
 */
export interface XARFEntity {
  org: string;
  contact: string;
  domain: string;
}

/**
 * XARF v4 Report Structure
 */
export interface XARFReport {
  /** XARF specification version */
  xarf_version: string;

  /** Unique report identifier (UUID) */
  report_id: string;

  /** ISO 8601 timestamp of when the report was created */
  timestamp: string;

  /** Report category (e.g., "content", "fraud", "malware") */
  category: string;

  /** Report type (e.g., "phishing", "spam", "malware") */
  type: string;

  /** Entity reporting the abuse */
  reporter: XARFEntity;

  /** Entity sending the report (may differ from reporter) */
  sender: XARFEntity;

  /** Source of the abuse (IP address or domain) */
  source_identifier: string;

  /** The abusive URL */
  url: string;

  /** Optional: The brand being impersonated */
  target_brand?: string;

  /** Optional: Domain name if different from source_identifier */
  domain?: string;

  /** Optional: IP address if different from source_identifier */
  ip?: string;

  /** Optional: Registrar information */
  registrar?: {
    name: string;
  };

  /** Optional: Evidence source (e.g., "automated_scan", "manual_review") */
  evidence_source?: string;

  /** Optional: Confidence level (0.0 to 1.0) */
  confidence?: number;

  /** Optional: Additional notes */
  notes?: string[];
}

/**
 * XARF Report creation options
 */
export interface XARFCreationOptions {
  /** Reporter organization name */
  reporter_org: string;

  /** Reporter contact email */
  reporter_contact: string;

  /** Reporter domain */
  reporter_domain: string;

  /** Storage path for XARF files */
  storage_path?: string;
}

/**
 * XARF validation error
 */
export interface XARFValidationError {
  field: string;
  message: string;
}

/**
 * XARF generation result
 */
export interface XARFGenerationResult {
  success: boolean;
  report?: XARFReport;
  file_path?: string;
  errors?: XARFValidationError[];
}

// XARF category constants
export const XARF_CATEGORY = {
  CONTENT: 'content',
  FRAUD: 'fraud',
  MALWARE: 'malware',
  ABUSE: 'abuse',
} as const;

// XARF type constants
export const XARF_TYPE = {
  PHISHING: 'phishing',
  SPAM: 'spam',
  MALWARE: 'malware',
  BOTNET: 'botnet',
} as const;
