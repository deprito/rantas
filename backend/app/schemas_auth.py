"""Pydantic schemas for authentication and authorization."""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# Role schemas
class RoleBase(BaseModel):
    """Base role schema."""

    name: str = Field(..., min_length=1, max_length=50)
    description: str = Field(..., max_length=255)


class RoleCreate(RoleBase):
    """Schema for creating a role."""

    permissions: List[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    """Schema for updating a role."""

    description: Optional[str] = Field(None, max_length=255)
    permissions: Optional[List[str]] = None


class RoleResponse(RoleBase):
    """Schema for role response."""

    id: UUID
    permissions: List[str]
    created_at: datetime

    class Config:
        from_attributes = True


# User schemas
class UserBase(BaseModel):
    """Base user schema."""

    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr


class UserCreate(UserBase):
    """Schema for creating a user."""

    password: str = Field(..., min_length=8)
    role_id: UUID

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password requirements."""
        errors = []
        if len(v) < 8:
            errors.append("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            errors.append("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            errors.append("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            errors.append("Password must contain at least one number")

        if errors:
            raise ValueError("; ".join(errors))
        return v


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    role_id: Optional[UUID] = None


class UserResponse(UserBase):
    """Schema for user response."""

    id: UUID
    is_active: bool
    role: RoleResponse
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserWithPermissions(UserResponse):
    """User response with permissions included."""

    permissions: List[str]


# Auth schemas
class LoginRequest(BaseModel):
    """Schema for login request."""

    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    """Schema for registration request."""

    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password requirements."""
        errors = []
        if len(v) < 8:
            errors.append("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            errors.append("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            errors.append("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            errors.append("Password must contain at least one number")

        if errors:
            raise ValueError("; ".join(errors))
        return v


class ChangePasswordRequest(BaseModel):
    """Schema for changing password."""

    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password requirements."""
        errors = []
        if len(v) < 8:
            errors.append("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            errors.append("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            errors.append("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            errors.append("Password must contain at least one number")

        if errors:
            raise ValueError("; ".join(errors))
        return v


class ResetPasswordRequest(BaseModel):
    """Schema for admin password reset."""

    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password requirements."""
        errors = []
        if len(v) < 8:
            errors.append("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            errors.append("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            errors.append("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            errors.append("Password must contain at least one number")

        if errors:
            raise ValueError("; ".join(errors))
        return v


class TokenResponse(BaseModel):
    """Schema for token response."""

    access_token: str
    token_type: str = "bearer"
    user: UserWithPermissions


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""

    refresh_token: str


# User list response
class UserListResponse(BaseModel):
    """Schema for paginated user list."""

    users: List[UserResponse]
    total: int
    page: int
    page_size: int
    pages: int


# Audit log schemas
class AuditLogResponse(BaseModel):
    """Schema for audit log response."""

    id: UUID
    user_id: Optional[UUID]
    action: str
    resource_type: str
    resource_id: Optional[str]
    details: dict
    ip_address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """Schema for paginated audit log list."""

    logs: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
    pages: int


# Config schemas
class ConfigUpdate(BaseModel):
    """Schema for updating configuration."""

    # SMTP settings
    smtp_enabled: Optional[bool] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = Field(None, ge=1, le=65535)
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_email: Optional[EmailStr] = None
    smtp_from_name: Optional[str] = None
    smtp_use_tls: Optional[bool] = None

    # Graph API settings
    graph_enabled: Optional[bool] = None
    graph_tenant_id: Optional[str] = None
    graph_client_id: Optional[str] = None
    graph_client_secret: Optional[str] = None
    graph_from_email: Optional[EmailStr] = None

    # Monitoring settings
    monitor_interval_default: Optional[int] = Field(None, ge=1800, le=86400)

    # CORS origins
    cors_origins: Optional[List[str]] = None

    # Brand impacted settings
    brand_impacted: Optional[List[str]] = None

    # Security settings
    session_timeout_minutes: Optional[int] = Field(None, ge=5, le=1440)


class ConfigResponse(BaseModel):
    """Schema for configuration response (sanitized)."""

    # SMTP settings (password excluded)
    smtp_enabled: bool
    smtp_host: Optional[str]
    smtp_port: Optional[int]
    smtp_username: Optional[str]
    smtp_from_email: Optional[str]
    smtp_from_name: Optional[str]
    smtp_use_tls: Optional[bool]
    smtp_has_password: bool  # True if password is set

    # Graph API settings
    graph_enabled: bool
    graph_tenant_id: Optional[str]
    graph_client_id: Optional[str]
    graph_from_email: Optional[str]
    graph_has_secret: bool  # True if secret is set

    # Monitoring settings
    monitor_interval_default: int

    # CORS
    cors_origins: List[str]

    # Brand impacted
    brand_impacted: List[str]

    # Security settings
    session_timeout_minutes: int

    # Version
    version: str


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str
    success: bool = True


# Email template schemas
class EmailTemplateBase(BaseModel):
    """Base email template schema."""

    name: str = Field(..., min_length=1, max_length=255)
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)
    html_body: Optional[str] = None
    cc: Optional[str] = None
    prefer_xarf: bool = False
    xarf_reporter_ref_template: Optional[str] = None


class EmailTemplateCreate(EmailTemplateBase):
    """Schema for creating an email template."""

    pass


class EmailTemplateUpdate(BaseModel):
    """Schema for updating an email template."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    subject: Optional[str] = Field(None, min_length=1, max_length=500)
    body: Optional[str] = Field(None, min_length=1)
    html_body: Optional[str] = None
    cc: Optional[str] = None
    is_default: Optional[bool] = None
    prefer_xarf: Optional[bool] = None
    xarf_reporter_ref_template: Optional[str] = None


class EmailTemplateResponse(EmailTemplateBase):
    """Schema for email template response."""

    id: UUID
    html_body: Optional[str]
    cc: Optional[str]
    is_default: bool
    prefer_xarf: bool
    xarf_reporter_ref_template: Optional[str]
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
