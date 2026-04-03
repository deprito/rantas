"""Pydantic schemas for PhishTrack API."""
from datetime import datetime
from enum import Enum
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator


class CaseStatus(str, Enum):
    """Status of a phishing takedown case."""

    ANALYZING = "ANALYZING"
    READY_TO_REPORT = "READY_TO_REPORT"
    REPORTING = "REPORTING"
    REPORTED = "REPORTED"
    MONITORING = "MONITORING"
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"


class CaseSource(str, Enum):
    """Source of a case."""

    INTERNAL = "internal"
    PUBLIC = "public"


class HistoryType(str, Enum):
    """Type of history entry."""

    DNS_CHECK = "dns_check"
    HTTP_CHECK = "http_check"
    EMAIL_SENT = "email_sent"
    EMAIL_RECEIVED = "email_received"
    SYSTEM = "system"


class ContactType(str, Enum):
    """Type of abuse contact."""

    REGISTRAR = "registrar"
    HOSTING = "hosting"
    DNS = "dns"


class AbuseContact(BaseModel):
    """Abuse contact information."""

    type: ContactType
    email: str


class DomainInfo(BaseModel):
    """Domain information from OSINT."""

    domain: str
    age_days: Optional[int] = None
    registrar: Optional[str] = None
    ip: Optional[str] = None
    asn: Optional[str] = None
    ns_records: list[str] = Field(default_factory=list)
    created_date: Optional[str] = None
    whois_created: Optional[str] = None
    whois_updated: Optional[str] = None
    whois_expires: Optional[str] = None


class HistoryEntry(BaseModel):
    """History entry for a case."""

    id: str
    timestamp: datetime
    type: HistoryType
    status: Optional[int] = None
    message: str


class CaseBase(BaseModel):
    """Base case schema."""

    url: str = Field(..., description="URL of the phishing site")


class CaseCreate(CaseBase):
    """Schema for creating a new case."""

    monitor_interval: Optional[int] = Field(
        default=None,
        ge=1800,
        le=86400,
        description="Monitoring interval in seconds (30 min to 24 hours)",
    )


class CaseUpdate(BaseModel):
    """Schema for updating a case."""

    status: Optional[CaseStatus] = None
    domain_info: Optional[DomainInfo] = None
    abuse_contacts: Optional[list[AbuseContact]] = None
    history: Optional[list[HistoryEntry]] = None
    brand_impacted: Optional[str] = None


class Case(CaseBase):
    """Full case schema."""

    id: UUID
    status: CaseStatus
    source: CaseSource = Field(default=CaseSource.INTERNAL)
    domain_info: Optional[DomainInfo] = None
    abuse_contacts: list[AbuseContact] = Field(default_factory=list)
    history: list[HistoryEntry] = Field(default_factory=list)
    monitor_interval: int
    brand_impacted: Optional[str] = Field(default=None, description="Brand impacted by this case")
    created_by: Optional[str] = Field(default=None, description="ID of user who created this case")
    created_by_username: Optional[str] = Field(default=None, description="Username of user who created this case")
    created_by_email: Optional[str] = Field(default=None, description="Email of user who created this case")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CaseList(BaseModel):
    """Schema for case list response."""

    cases: list[Case]
    total: int
    page: int
    page_size: int


class CaseSummary(BaseModel):
    """Brief case summary for list views."""

    id: UUID
    url: str
    status: CaseStatus
    source: CaseSource = Field(default=CaseSource.INTERNAL)
    created_at: datetime
    updated_at: datetime
    has_domain_info: bool = False
    history_count: int = 0

    class Config:
        from_attributes = True


class WebhookEmailData(BaseModel):
    """Schema for incoming email webhook data."""

    from_email: str = Field(..., alias="from")
    to_email: str = Field(..., alias="to")
    subject: str
    body: str
    headers: dict[str, str] = Field(default_factory=dict)
    timestamp: datetime

    @field_validator("subject")
    @classmethod
    def extract_case_id(cls, v: str) -> str:
        """Extract case ID from subject line."""
        # Case IDs are in format [Case-ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx]
        return v

    class Config:
        populate_by_name = True


class WebhookResponse(BaseModel):
    """Response schema for webhook endpoints."""

    success: bool
    message: str
    case_id: Optional[UUID] = None


class TaskResult(BaseModel):
    """Schema for Celery task results."""

    task_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None


class AnalysisResult(BaseModel):
    """Schema for OSINT analysis results."""

    domain_info: DomainInfo
    abuse_contacts: list[AbuseContact]
    is_phishing: bool
    confidence: float
    threat_indicators: list[str]


class EmailReportData(BaseModel):
    """Data for generating takedown emails."""

    case_id: UUID
    target_url: str
    domain_info: DomainInfo
    abuse_contacts: list[AbuseContact]
    recipient_type: ContactType


class SendReportRequest(BaseModel):
    """Request schema for sending an abuse report."""

    template_id: Optional[UUID] = Field(
        None,
        description="Optional email template ID to use. If not provided, the default template will be used.",
    )
    selected_contacts: Optional[list[str]] = Field(
        None,
        description="Optional list of email addresses to send the report to. If not provided, sends to all abuse contacts.",
    )
    brand_impacted: Optional[str] = Field(
        None,
        description="Optional brand impacted by this phishing case",
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    database: str
    celery: str


class EvidenceSchema(BaseModel):
    """Schema for evidence records."""

    id: UUID
    case_id: UUID
    type: str
    file_path: Optional[str] = None
    content_hash: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True


class CaptureScreenshotRequest(BaseModel):
    """Request schema for capturing a screenshot."""

    case_id: UUID = Field(..., description="Case ID to capture screenshot for")
    url: Optional[str] = Field(None, description="URL to capture (defaults to case URL if not provided)")
    full_page: bool = Field(True, description="Capture full page or just viewport")


class ReportType(str, Enum):
    """Type of report."""

    RESOLVED_CASES_CSV = "resolved_cases_csv"


class ReportStatus(str, Enum):
    """Status of a generated report."""

    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class ReportCreate(BaseModel):
    """Schema for creating a new report request."""

    report_type: ReportType = Field(
        ...,
        description="Type of report to generate",
    )


class ReportResponse(BaseModel):
    """Schema for report response."""

    id: UUID
    report_type: ReportType
    status: ReportStatus
    file_path: Optional[str] = None
    created_at: datetime
    created_by: Optional[UUID] = None
    cases_count: Optional[int] = None
    file_size_bytes: Optional[int] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class ReportListResponse(BaseModel):
    """Schema for report list response."""

    reports: list[ReportResponse]
    total: int


class GenerateReportResponse(BaseModel):
    """Schema for generate report response."""

    report_id: UUID
    status: ReportStatus
    message: str


# ==================== Statistics Schemas ====================


class StatsOverview(BaseModel):
    """Overview statistics for the dashboard."""

    total_cases: int
    active_cases: int
    resolved_cases: int
    failed_cases: int
    success_rate: float
    average_resolution_time_hours: Optional[float] = None
    total_emails_sent: int
    cases_created_today: int
    cases_resolved_today: int
    internal_cases: int
    public_cases: int
    pending_submissions: int
    top_brands: list[str] = Field(default_factory=list, description="Top 5 brands by case count")
    total_cases_with_brand: int = Field(default=0, description="Total cases with brand specified")
    total_cases_without_brand: int = Field(default=0, description="Total cases without brand specified")


class StatusDistributionItem(BaseModel):
    """Status distribution item for pie chart."""

    status: str
    count: int
    percentage: float


class StatusDistribution(BaseModel):
    """Status distribution response."""

    distribution: list[StatusDistributionItem]
    total: int


class TrendDataPoint(BaseModel):
    """Single data point in trends chart."""

    date: str
    created: int
    resolved: int
    failed: int


class TrendsResponse(BaseModel):
    """Trends response for line chart."""

    period: str
    start_date: str
    end_date: str
    data: list[TrendDataPoint]


class TopDomainItem(BaseModel):
    """Top reported domain item."""

    domain: str
    case_count: int
    resolved_count: int
    failed_count: int
    resolution_rate: float


class TopDomainsResponse(BaseModel):
    """Top domains response."""

    domains: list[TopDomainItem]
    total: int


class TopRegistrarItem(BaseModel):
    """Top registrar item."""

    registrar: str
    case_count: int
    resolved_count: int
    resolution_rate: float
    avg_resolution_hours: Optional[float] = None


class TopRegistrarsResponse(BaseModel):
    """Top registrars response."""

    registrars: list[TopRegistrarItem]
    total: int


class EmailEffectiveness(BaseModel):
    """Email effectiveness metrics."""

    total_emails_sent: int
    cases_with_emails: int
    avg_emails_per_case: float
    cases_resolved_after_email: int
    email_success_rate: float


class ResolutionMetrics(BaseModel):
    """Resolution time metrics."""

    average_hours: Optional[float] = None
    median_hours: Optional[float] = None
    min_hours: Optional[float] = None
    max_hours: Optional[float] = None
    resolved_count: int


class BrandImpactedItem(BaseModel):
    """Brand impacted statistics item."""

    brand: str
    case_count: int
    resolved_count: int
    failed_count: int
    resolution_rate: float


class BrandImpactedResponse(BaseModel):
    """Response for brand impacted statistics."""

    brands: list[BrandImpactedItem]
    total_cases_with_brand: int
    total_cases_without_brand: int


class PeriodType(str, Enum):
    """Time period for trends."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class StatsExportFormat(str, Enum):
    """Export format type."""

    CSV = "csv"
    PDF = "pdf"


class UserStatsItem(BaseModel):
    """User statistics item for leaderboard."""

    user_id: str
    username: str
    email: str
    total_cases: int
    internal_cases: int
    public_cases: int
    resolved_count: int
    failed_count: int
    resolution_rate: float


class UserStatsResponse(BaseModel):
    """Response for user statistics leaderboard."""

    users: list[UserStatsItem]
    total: int


class HistoricalCaseImport(BaseModel):
    """Schema for importing historical cases."""

    url: str
    status: str = "RESOLVED"
    source: str = "internal"
    brand_impacted: Optional[str] = None
    emails_sent: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None
    registrar: Optional[str] = None
    ip: Optional[str] = None


class ImportResponse(BaseModel):
    """Response for historical import."""

    success: bool
    imported_count: int
    skipped_count: int
    errors: list[str] = Field(default_factory=list)


# ==================== Case Export Schemas ====================


class CaseExportRequest(BaseModel):
    """Request schema for exporting cases."""

    format: Literal["csv", "json"] = Field(
        default="csv",
        description="Export format: csv or json",
    )
    start_date: Optional[str] = Field(
        None,
        description="Start date filter (ISO format: YYYY-MM-DD)",
    )
    end_date: Optional[str] = Field(
        None,
        description="End date filter (ISO format: YYYY-MM-DD)",
    )
    status: Optional[CaseStatus] = Field(
        None,
        description="Filter by case status",
    )
    source: Optional[CaseSource] = Field(
        None,
        description="Filter by case source",
    )
    send_to_teams: bool = Field(
        default=True,
        description="Send Teams notification when export is ready",
    )


class CaseExportResponse(BaseModel):
    """Response schema for case export."""

    export_id: str = Field(..., description="Unique export identifier")
    download_url: str = Field(..., description="URL to download the exported file")
    format: str = Field(..., description="Export format (csv or json)")
    cases_count: int = Field(..., description="Number of cases in the export")
    status: str = Field(..., description="Export status")
    file_size_bytes: Optional[int] = Field(
        None,
        description="Size of the exported file in bytes",
    )


# ==================== Hunting Schemas ====================


class DetectedDomainStatus(str, Enum):
    """Status of a detected domain from hunting."""

    PENDING = "pending"
    REVIEWED = "reviewed"
    IGNORED = "ignored"
    CASE_CREATED = "case_created"


class DetectedDomain(BaseModel):
    """Detected domain from CertStream monitoring."""

    id: UUID
    domain: str
    cert_data: dict = Field(default_factory=dict)
    matched_brand: Optional[str] = None
    matched_pattern: Optional[str] = None
    detection_score: int
    cert_seen_at: datetime
    created_at: datetime
    status: DetectedDomainStatus
    http_status_code: Optional[int] = None
    http_checked_at: Optional[datetime] = None
    notes: Optional[str] = None
    case_id: Optional[UUID] = None

    class Config:
        from_attributes = True


class DetectedDomainUpdate(BaseModel):
    """Schema for updating a detected domain."""

    status: Optional[DetectedDomainStatus] = None
    notes: Optional[str] = None


class DetectedDomainList(BaseModel):
    """Schema for detected domains list response."""

    domains: list[DetectedDomain]
    total: int
    page: int
    page_size: int


class HuntingStats(BaseModel):
    """Statistics for the hunting feature."""

    total_detected: int
    pending: int
    reviewed: int
    ignored: int
    cases_created: int
    high_confidence: int  # Count of detections with score >= 80
    top_brands: list[str]  # Top 5 most targeted brands
    http_status_counts: dict[str, int]  # Count by HTTP status code (e.g., {"200": 10, "404": 5})


class HuntingConfig(BaseModel):
    """Configuration for the hunting feature."""

    monitor_enabled: bool = Field(
        default=True,
        description="Whether CertStream monitoring is enabled",
    )
    min_score_threshold: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Minimum detection score to store a domain",
    )
    alert_threshold: int = Field(
        default=80,
        ge=0,
        le=100,
        description="Minimum score to send Teams alert",
    )
    monitored_brands: list[str] = Field(
        default_factory=list,
        description="List of brands to monitor for typosquatting",
    )
    retention_days: int = Field(
        default=90,
        ge=1,
        le=365,
        description="Days to retain detected domains before auto-cleanup",
    )
    raw_log_retention_days: int = Field(
        default=3,
        ge=1,
        le=30,
        description="Days to retain raw CT log entries in Redis before auto-cleanup",
    )
    custom_brand_patterns: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Custom brand patterns for typosquat detection. Format: {'brand': ['pattern1', 'pattern2']}",
    )
    custom_brand_regex_patterns: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Custom regex patterns for typosquat detection. Format: {'brand': ['^pattern.*$', '.*regex$']}",
    )
    default_brand_patterns: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Editable default brand patterns for typosquat detection. Format: {'brand': ['pattern1', 'pattern2']}",
    )
    whitelist_patterns: list[str] = Field(
        default_factory=list,
        description="Whitelist patterns (regex) to exclude from detection. Format: ['^example\\.com$', '.*\\.whitelist\\.org$']",
    )


class HuntingStatus(BaseModel):
    """Real-time status of the CertStream monitor."""

    monitor_is_running: bool
    monitor_enabled: bool
    monitor_started_at: Optional[datetime] = None
    monitor_last_heartbeat: Optional[datetime] = None
    monitor_last_seen_at: Optional[datetime] = None
    certificates_processed: int
    domains_detected: int
    error_message: Optional[str] = None


class CaseFromDetectionRequest(BaseModel):
    """Request schema for creating a case from a detected domain."""

    monitor_interval: Optional[int] = Field(
        default=None,
        ge=1800,
        le=86400,
        description="Monitoring interval in seconds (30 min to 24 hours)",
    )
    brand_impacted: Optional[str] = Field(
        None,
        description="Brand impacted (auto-filled from detection if not provided)",
    )
