"""SQLAlchemy ORM models for PhishTrack."""
from datetime import datetime
from typing import Optional
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship as sa_orm_relationship

# Use JSON for SQLite compatibility, JSON_TYPE for PostgreSQL
JSON_TYPE = sa.JSON

from app.database import Base
from app.utils.timezone import now_utc


class Role(Base):
    """Database model for user roles."""

    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        index=True,
    )
    name: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        unique=True,
        index=True,
    )
    description: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        default="",
    )
    permissions: Mapped[dict] = mapped_column(
        JSON_TYPE,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=now_utc,
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "permissions": self.permissions,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class User(Base):
    """Database model for application users."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        index=True,
    )
    username: Mapped[str] = mapped_column(
        sa.String(100),
        nullable=False,
        unique=True,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    role_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Relationship to Role (for selectinload optimization)
    role: Mapped["Role"] = sa_orm_relationship(
        "Role",
        backref="users",
        lazy="selectin",
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=now_utc,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=now_utc,
        onupdate=now_utc,
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary (excluding sensitive data)."""
        return {
            "id": str(self.id),
            "username": self.username,
            "email": self.email,
            "is_active": self.is_active,
            "role_id": str(self.role_id),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }


class UserSession(Base):
    """Database model for user sessions (single active session per user)."""

    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        sa.String(64),
        nullable=False,
        index=True,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        sa.String(45),
        nullable=True,
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        sa.Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=now_utc,
    )
    expires_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary (excluding sensitive data)."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active,
        }


class AuditLog(Base):
    """Database model for audit logging."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        sa.String(100),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        index=True,
    )
    resource_id: Mapped[Optional[str]] = mapped_column(
        sa.String(255),
        nullable=True,
        index=True,
    )
    details: Mapped[dict] = mapped_column(
        JSON_TYPE,
        nullable=False,
        default=dict,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        sa.String(45),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=now_utc,
        index=True,
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Case(Base):
    """Database model for a phishing takedown case."""

    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        index=True,
    )
    url: Mapped[str] = mapped_column(
        sa.String(2048),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        default="ANALYZING",
        index=True,
    )
    source: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        default="internal",
        server_default="internal",
    )
    # JSON_TYPE fields for flexible data storage
    domain_info: Mapped[dict] = mapped_column(
        JSON_TYPE,
        nullable=False,
        default=dict,
    )
    abuse_contacts: Mapped[list] = mapped_column(
        JSON_TYPE,
        nullable=False,
        default=list,
    )
    history: Mapped[list] = mapped_column(
        JSON_TYPE,
        nullable=False,
        default=list,
    )
    # Monitoring configuration
    monitor_interval: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=21600,  # 6 hours in seconds
    )
    last_monitored_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    next_monitor_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    # Email tracking
    emails_sent: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
    )
    last_email_sent_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    # Brand impacted by this case
    brand_impacted: Mapped[Optional[str]] = mapped_column(
        sa.String(255),
        nullable=True,
    )
    # User who created this case
    created_by: Mapped[Optional[str]] = mapped_column(
        sa.String(36),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=now_utc,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=now_utc,
        onupdate=now_utc,
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "url": self.url,
            "status": self.status,
            "source": self.source,
            "domain_info": self.domain_info,
            "abuse_contacts": self.abuse_contacts,
            "history": self.history,
            "monitor_interval": self.monitor_interval,
            "last_monitored_at": self.last_monitored_at.isoformat() if self.last_monitored_at else None,
            "next_monitor_at": self.next_monitor_at.isoformat() if self.next_monitor_at else None,
            "emails_sent": self.emails_sent,
            "last_email_sent_at": self.last_email_sent_at.isoformat() if self.last_email_sent_at else None,
            "brand_impacted": self.brand_impacted,
            "created_by": str(self.created_by) if self.created_by else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def add_history_entry(
        self,
        entry_type: str,
        message: str,
        status: Optional[int] = None,
    ) -> None:
        """Add a history entry to this case."""
        from uuid import uuid4

        entry = {
            "id": str(uuid4()),
            "timestamp": now_utc().isoformat(),
            "type": entry_type,
            "message": message,
        }
        if status is not None:
            entry["status"] = status

        # Convert JSON_TYPE dict to list for history
        if self.history is None:
            self.history = [entry]
        elif isinstance(self.history, dict):
            self.history = [entry]
        else:
            self.history = list(self.history) + [entry]

    def update_status(self, new_status: str) -> None:
        """Update case status and add history entry."""
        old_status = self.status
        self.status = new_status
        self.add_history_entry(
            "system",
            f"Status changed from {old_status} to {new_status}",
        )


class HistoricalCase(Base):
    """Database model for imported historical cases (statistics only)."""

    __tablename__ = "historical_cases"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        index=True,
    )
    url: Mapped[str] = mapped_column(
        sa.String(2048),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        default="RESOLVED",
    )
    source: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        default="internal",
    )
    brand_impacted: Mapped[Optional[str]] = mapped_column(
        sa.String(255),
        nullable=True,
    )
    emails_sent: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
    )
    domain_info: Mapped[dict] = mapped_column(
        JSON_TYPE,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
    )
    imported_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=now_utc,
    )
    reported_by: Mapped[Optional[str]] = mapped_column(
        sa.String(36),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "url": self.url,
            "status": self.status,
            "source": self.source,
            "brand_impacted": self.brand_impacted,
            "emails_sent": self.emails_sent,
            "domain_info": self.domain_info,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "imported_at": self.imported_at.isoformat() if self.imported_at else None,
            "reported_by": self.reported_by,
        }


class EmailTemplate(Base):
    """Database model for email templates."""

    __tablename__ = "email_templates"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        index=True,
    )
    name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(
        sa.String(500),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
    )
    html_body: Mapped[Optional[str]] = mapped_column(
        sa.Text,
        nullable=True,
    )
    cc: Mapped[Optional[str]] = mapped_column(
        sa.String(500),
        nullable=True,
    )
    is_default: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    prefer_xarf: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
    )
    xarf_reporter_ref_template: Mapped[Optional[str]] = mapped_column(
        sa.String(255),
        nullable=True,
    )
    created_by: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=now_utc,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=now_utc,
        onupdate=now_utc,
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "subject": self.subject,
            "body": self.body,
            "html_body": self.html_body,
            "cc": self.cc,
            "is_default": self.is_default,
            "prefer_xarf": self.prefer_xarf,
            "xarf_reporter_ref_template": self.xarf_reporter_ref_template,
            "created_by": str(self.created_by) if self.created_by else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Evidence(Base):
    """Database model for evidence files (screenshots, HTML content, etc.)."""

    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        index=True,
    )
    case_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        index=True,
    )  # 'screenshot', 'html'
    file_path: Mapped[Optional[str]] = mapped_column(
        sa.String(500),
        nullable=True,
    )
    content_hash: Mapped[Optional[str]] = mapped_column(
        sa.String(64),
        nullable=True,
    )
    meta: Mapped[dict] = mapped_column(
        JSON_TYPE,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=now_utc,
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "case_id": str(self.case_id),
            "type": self.type,
            "file_path": self.file_path,
            "content_hash": self.content_hash,
            "metadata": self.meta,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class GeneratedReport(Base):
    """Database model for generated reports."""

    __tablename__ = "generated_reports"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        index=True,
    )
    report_type: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        index=True,
    )  # "resolved_cases_csv"
    status: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        default="generating",
        index=True,
    )  # "generating", "completed", "failed"
    file_path: Mapped[Optional[str]] = mapped_column(
        sa.String(500),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=now_utc,
        index=True,
    )
    created_by: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cases_count: Mapped[Optional[int]] = mapped_column(
        sa.Integer,
        nullable=True,
    )
    file_size_bytes: Mapped[Optional[int]] = mapped_column(
        sa.Integer,
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        sa.String(1000),
        nullable=True,
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "report_type": self.report_type,
            "status": self.status,
            "file_path": self.file_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": str(self.created_by) if self.created_by else None,
            "cases_count": self.cases_count,
            "file_size_bytes": self.file_size_bytes,
            "error_message": self.error_message,
        }


class PublicSubmission(Base):
    """Database model for public URL submissions."""

    __tablename__ = "public_submissions"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        index=True,
    )
    url: Mapped[str] = mapped_column(
        sa.String(2048),
        nullable=False,
    )
    submitter_email: Mapped[Optional[str]] = mapped_column(
        sa.String(255),
        nullable=True,
    )
    additional_notes: Mapped[Optional[str]] = mapped_column(
        sa.Text,
        nullable=True,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        sa.String(45),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        default="pending",
        index=True,
    )  # 'pending', 'approved', 'rejected'
    submitted_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=now_utc,
        index=True,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    reviewed_by: Mapped[Optional[str]] = mapped_column(
        sa.String(36),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    case_id: Mapped[Optional[str]] = mapped_column(
        sa.String(36),
        sa.ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True,
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "url": self.url,
            "submitter_email": self.submitter_email,
            "status": self.status,
            "additional_notes": self.additional_notes,
            "ip_address": self.ip_address,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by": str(self.reviewed_by) if self.reviewed_by else None,
            "case_id": str(self.case_id) if self.case_id else None,
        }


class BlacklistSource(Base):
    """Database model for blacklist sources."""

    __tablename__ = "blacklist_sources"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        index=True,
    )
    name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        default="remote",
    )  # 'local', 'remote', 'manual'
    url: Mapped[Optional[str]] = mapped_column(
        sa.String(2048),
        nullable=True,
    )  # For remote sources
    file_path: Mapped[Optional[str]] = mapped_column(
        sa.String(500),
        nullable=True,
    )  # For local file sources
    threat_category: Mapped[Optional[str]] = mapped_column(
        sa.String(100),
        nullable=True,
    )  # e.g., 'phishing', 'malware'
    sync_interval_hours: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=24,
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    entry_count: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
    )  # Number of domains in this source
    created_by: Mapped[Optional[str]] = mapped_column(
        sa.String(36),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=now_utc,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=now_utc,
        onupdate=now_utc,
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "source_type": self.source_type,
            "url": self.url,
            "file_path": self.file_path,
            "threat_category": self.threat_category,
            "sync_interval_hours": self.sync_interval_hours,
            "is_active": self.is_active,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "entry_count": self.entry_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": str(self.created_by) if self.created_by else None,
        }


class BlacklistDomain(Base):
    """Database model for individual blacklisted domains."""

    __tablename__ = "blacklist_domains"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        index=True,
    )
    domain: Mapped[str] = mapped_column(
        sa.String(500),
        nullable=False,
        index=True,
    )
    is_wildcard: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
    )  # If True, matches *.domain.com
    threat_category: Mapped[Optional[str]] = mapped_column(
        sa.String(100),
        nullable=True,
    )
    source_id: Mapped[Optional[str]] = mapped_column(
        sa.String(36),
        sa.ForeignKey("blacklist_sources.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )  # If from a source, otherwise manually added
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        sa.Text,
        nullable=True,
    )
    created_by: Mapped[Optional[str]] = mapped_column(
        sa.String(36),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=now_utc,
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "domain": self.domain,
            "is_wildcard": self.is_wildcard,
            "threat_category": self.threat_category,
            "source_id": str(self.source_id) if self.source_id else None,
            "is_active": self.is_active,
            "notes": self.notes,
            "created_by": str(self.created_by) if self.created_by else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class WhitelistEntry(Base):
    """Database model for whitelisted domains (override blacklist)."""

    __tablename__ = "whitelist_entries"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        index=True,
    )
    domain: Mapped[str] = mapped_column(
        sa.String(500),
        nullable=False,
        unique=True,
        index=True,
    )
    reason: Mapped[Optional[str]] = mapped_column(
        sa.Text,
        nullable=True,
    )
    added_by: Mapped[Optional[str]] = mapped_column(
        sa.String(36),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    added_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=now_utc,
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "domain": self.domain,
            "reason": self.reason,
            "added_at": self.added_at.isoformat() if self.added_at else None,
            "added_by": str(self.added_by) if self.added_by else None,
        }


class DetectedDomain(Base):
    """Database model for domains detected via CertStream monitoring."""

    __tablename__ = "detected_domains"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        index=True,
    )
    domain: Mapped[str] = mapped_column(
        sa.String(500),
        nullable=False,
        index=True,
    )
    cert_data: Mapped[dict] = mapped_column(
        JSON_TYPE,
        nullable=False,
        default=dict,
    )  # Full certificate information from CertStream
    matched_brand: Mapped[Optional[str]] = mapped_column(
        sa.String(255),
        nullable=True,
        index=True,
    )  # Which brand was typosquatted (e.g., "example")
    matched_pattern: Mapped[Optional[str]] = mapped_column(
        sa.String(255),
        nullable=True,
    )  # The pattern that matched (e.g., "Character omission")
    detection_score: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
        index=True,
    )  # Confidence score (0-100)
    cert_seen_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=now_utc,
        index=True,
    )  # When certificate was first seen via CertStream
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=now_utc,
    )
    status: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        default="pending",
        index=True,
    )  # pending, reviewed, ignored, case_created
    http_status_code: Mapped[Optional[int]] = mapped_column(
        sa.Integer,
        nullable=True,
        index=True,
    )  # HTTP status code from latest check (200, 404, 500, etc.)
    http_checked_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )  # When HTTP status was last checked
    notes: Mapped[Optional[str]] = mapped_column(
        sa.Text,
        nullable=True,
    )
    case_id: Mapped[Optional[str]] = mapped_column(
        sa.String(36),
        sa.ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )  # Link to Case if action was taken

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "domain": self.domain,
            "cert_data": self.cert_data,
            "matched_brand": self.matched_brand,
            "matched_pattern": self.matched_pattern,
            "detection_score": self.detection_score,
            "cert_seen_at": self.cert_seen_at.isoformat() if self.cert_seen_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "status": self.status,
            "notes": self.notes,
            "case_id": str(self.case_id) if self.case_id else None,
        }


# Create indexes for common queries
sa.Index("ix_cases_status_created", Case.status, Case.created_at)
sa.Index("ix_cases_next_monitor", Case.next_monitor_at)
sa.Index("ix_email_templates_default", EmailTemplate.is_default)
sa.Index("ix_evidence_case_type", Evidence.case_id, Evidence.type)
sa.Index("ix_reports_type_status", GeneratedReport.report_type, GeneratedReport.status)
sa.Index("ix_blacklist_sources_active", BlacklistSource.is_active)
sa.Index("ix_blacklist_domains_active", BlacklistDomain.is_active, BlacklistDomain.domain)
sa.Index("ix_whitelist_domains", WhitelistEntry.domain)
# Hunting indexes
sa.Index("ix_detected_domains_status_seen", DetectedDomain.status, DetectedDomain.cert_seen_at)
sa.Index("ix_detected_domains_brand_score", DetectedDomain.matched_brand, DetectedDomain.detection_score)
# Note: public_submissions indexes (status, submitted_at) are created inline via index=True
# Note: user_sessions indexes (user_id, token_hash, expires_at, is_active) are created inline via index=True


class HuntingConfig(Base):
    """Database model for hunting configuration and monitor status."""

    __tablename__ = "hunting_config"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    monitor_enabled: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    min_score_threshold: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=50,
    )
    alert_threshold: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=80,
    )
    monitored_brands: Mapped[list] = mapped_column(
        JSON_TYPE,
        nullable=False,
        default=list,
    )
    retention_days: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=90,
    )
    raw_log_retention_days: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=3,
    )
    # Custom brand patterns - stores dict of {brand: [patterns]}
    custom_brand_patterns: Mapped[dict] = mapped_column(
        JSON_TYPE,
        nullable=False,
        default=dict,
    )
    # Custom brand regex patterns - stores dict of {brand: [regex_patterns]}
    custom_brand_regex_patterns: Mapped[dict] = mapped_column(
        JSON_TYPE,
        nullable=False,
        default=dict,
    )
    # Default brand patterns - editable version of StaticURLAnalyzer.TYPOSQUAT_PATTERNS
    # Stores dict of {brand: [patterns]}
    default_brand_patterns: Mapped[dict] = mapped_column(
        JSON_TYPE,
        nullable=False,
        default=dict,
    )
    # Whitelist patterns - stores list of regex patterns for domain whitelisting
    whitelist_patterns: Mapped[list] = mapped_column(
        JSON_TYPE,
        nullable=False,
        default=list,
    )
    # Monitor status fields
    monitor_is_running: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    monitor_started_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    monitor_last_heartbeat: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    monitor_last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )  # Last time a certificate was processed
    certificates_processed: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
    )  # Total certificates processed
    domains_detected: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
    )  # Total domains detected
    error_message: Mapped[Optional[str]] = mapped_column(
        sa.Text,
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=now_utc,
        onupdate=now_utc,
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "monitor_enabled": self.monitor_enabled,
            "min_score_threshold": self.min_score_threshold,
            "alert_threshold": self.alert_threshold,
            "monitored_brands": self.monitored_brands,
            "retention_days": self.retention_days,
            "raw_log_retention_days": self.raw_log_retention_days,
            "monitor_is_running": self.monitor_is_running,
            "monitor_started_at": self.monitor_started_at.isoformat() if self.monitor_started_at else None,
            "monitor_last_heartbeat": self.monitor_last_heartbeat.isoformat() if self.monitor_last_heartbeat else None,
            "monitor_last_seen_at": self.monitor_last_seen_at.isoformat() if self.monitor_last_seen_at else None,
            "certificates_processed": self.certificates_processed,
            "domains_detected": self.domains_detected,
            "error_message": self.error_message,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
