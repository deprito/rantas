"""Permission definitions and role-based access control for PhishTrack."""

from enum import Enum
from typing import List


class Permission(str, Enum):
    """Permission strings for RBAC."""

    # Case permissions
    CASE_VIEW_ANY = "case:view_any"
    CASE_VIEW_OWN = "case:view_own"
    CASE_CREATE = "case:create"
    CASE_UPDATE = "case:update"
    CASE_DELETE = "case:delete"
    CASE_SEND_REPORT = "case:send_report"

    # User management
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    USER_VIEW_ANY = "user:view_any"
    USER_RESET_PASSWORD = "user:reset_password"

    # Role management
    ROLE_CREATE = "role:create"
    ROLE_UPDATE = "role:update"
    ROLE_DELETE = "role:delete"
    ROLE_VIEW = "role:view"

    # Config management
    CONFIG_VIEW = "config:view"
    CONFIG_UPDATE = "config:update"

    # Audit log
    AUDIT_VIEW = "audit:view"

    # Email templates
    EMAIL_TEMPLATE_VIEW = "email_template:view"
    EMAIL_TEMPLATE_CREATE = "email_template:create"
    EMAIL_TEMPLATE_UPDATE = "email_template:update"
    EMAIL_TEMPLATE_DELETE = "email_template:delete"

    # Evidence (screenshots, HTML captures, etc.)
    EVIDENCE_VIEW = "evidence:view"
    EVIDENCE_CREATE = "evidence:create"
    EVIDENCE_DELETE = "evidence:delete"

    # Auth
    SELF_CHANGE_PASSWORD = "self:change_password"

    # Statistics
    STATS_VIEW = "stats:view"
    STATS_EXPORT = "stats:export"
    STATS_IMPORT = "stats:import"

    # Public submissions
    SUBMISSION_VIEW = "submission:view"
    SUBMISSION_APPROVE = "submission:approve"
    SUBMISSION_DELETE = "submission:delete"

    # Blacklist management
    BLACKLIST_VIEW = "blacklist:view"
    BLACKLIST_MANAGE = "blacklist:manage"

    # Hunting (CertStream monitoring)
    HUNTING_VIEW = "hunting:view"
    HUNTING_UPDATE = "hunting:update"
    HUNTING_DELETE = "hunting:delete"


# Role permissions mapping
ROLE_PERMISSIONS: dict[str, List[str]] = {
    "VIEW_ONLY": [
        Permission.CASE_VIEW_ANY,
        Permission.EVIDENCE_VIEW,
        Permission.STATS_VIEW,
    ],
    "REPORTER": [
        Permission.CASE_CREATE,
        Permission.CASE_VIEW_OWN,
        Permission.EVIDENCE_VIEW,
        Permission.EVIDENCE_CREATE,
        Permission.SELF_CHANGE_PASSWORD,
    ],
    "CTI_USER": [
        Permission.CASE_VIEW_ANY,
        Permission.CASE_CREATE,
        Permission.CASE_UPDATE,
        Permission.CASE_SEND_REPORT,
        Permission.CONFIG_VIEW,
        Permission.EMAIL_TEMPLATE_VIEW,
        Permission.EMAIL_TEMPLATE_CREATE,
        Permission.EMAIL_TEMPLATE_UPDATE,
        Permission.EVIDENCE_VIEW,
        Permission.EVIDENCE_CREATE,
        Permission.SELF_CHANGE_PASSWORD,
        Permission.STATS_VIEW,
        Permission.STATS_EXPORT,
        Permission.STATS_IMPORT,
        Permission.SUBMISSION_VIEW,
        Permission.SUBMISSION_APPROVE,
        Permission.SUBMISSION_DELETE,
        Permission.BLACKLIST_VIEW,
        Permission.BLACKLIST_MANAGE,
        Permission.HUNTING_VIEW,
        Permission.HUNTING_UPDATE,
    ],
    "ADMIN": ["*"],  # All permissions (including BRANDING_UPDATE via wildcard)
}


# Role names enum
class RoleName(str, Enum):
    """Available role names."""

    VIEW_ONLY = "VIEW_ONLY"
    REPORTER = "REPORTER"
    CTI_USER = "CTI_USER"
    ADMIN = "ADMIN"


# Role descriptions
ROLE_DESCRIPTIONS: dict[str, str] = {
    "VIEW_ONLY": "Can view all cases but cannot modify or create new ones",
    "REPORTER": "Can submit URLs for analysis and view their own cases",
    "CTI_USER": "Can view any cases, submit URLs, and send abuse reports",
    "ADMIN": "Full access including user management and configuration",
}


def get_role_permissions(role_name: str) -> List[str]:
    """Get the list of permissions for a given role.

    Args:
        role_name: Name of the role

    Returns:
        List of permission strings
    """
    return ROLE_PERMISSIONS.get(role_name, [])


def has_permission(user_permissions: List[str], required_permission: str) -> bool:
    """Check if a user has a specific permission.

    Args:
        user_permissions: List of permissions the user has
        required_permission: Permission to check for

    Returns:
        True if user has the permission or wildcard
    """
    return "*" in user_permissions or required_permission in user_permissions


def has_any_permission(user_permissions: List[str], required_permissions: List[str]) -> bool:
    """Check if a user has any of the specified permissions.

    Args:
        user_permissions: List of permissions the user has
        required_permissions: List of permissions to check for

    Returns:
        True if user has any of the permissions or wildcard
    """
    if "*" in user_permissions:
        return True
    return any(perm in user_permissions for perm in required_permissions)


def has_all_permissions(user_permissions: List[str], required_permissions: List[str]) -> bool:
    """Check if a user has all of the specified permissions.

    Args:
        user_permissions: List of permissions the user has
        required_permissions: List of permissions to check for

    Returns:
        True if user has all permissions or wildcard
    """
    if "*" in user_permissions:
        return True
    return all(perm in user_permissions for perm in required_permissions)


# All available permissions for reference
ALL_PERMISSIONS = [p.value for p in Permission]
