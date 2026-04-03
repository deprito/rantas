"""Configuration management API endpoints (admin only)."""

import os
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import log_audit_action, AuditAction, ResourceType
from app.auth.dependencies import require_admin, PermissionChecker
from app.config import settings
from app.permissions import Permission
from app.database import get_db, get_db_context
from app.models import User
from app.schemas_auth import ConfigUpdate, ConfigResponse, AuditLogResponse
from app.auth.audit import get_audit_logs, count_audit_logs
from app.utils.timezone import now_utc

router = APIRouter(prefix="/config", tags=["config"])


def update_env_file(updates: dict[str, str]) -> None:
    """Update the .env file with new values.

    Args:
        updates: Dictionary of env var names to values
    """
    env_path = Path(__file__).parent.parent / ".env"

    if not env_path.exists():
        return

    # Read current file
    content = env_path.read_text()
    lines = content.splitlines()
    updated_lines = []
    updated_keys = set(updates.keys())

    for line in lines:
        # Check if this line contains one of the keys we're updating
        matched = False
        for key in updated_keys:
            if line.startswith(f"{key}="):
                # Update this line with new value
                value = updates[key]
                # Quote values that contain spaces or special characters
                if value and any(c in value for c in [' ', '#', '"', "'"]):
                    value = f'"{value}"'
                updated_lines.append(f"{key}={value}")
                updated_keys.discard(key)
                matched = True
                break
        if not matched:
            updated_lines.append(line)

    # Add any new keys that weren't in the file
    for key in updated_keys:
        value = updates[key]
        if value and any(c in value for c in [' ', '#', '"', "'"]):
            value = f'"{value}"'
        updated_lines.append(f"{key}={value}")

    # Write back
    env_path.write_text('\n'.join(updated_lines) + '\n')


@router.get("", response_model=ConfigResponse)
async def get_config(
    current_user: Annotated[User, Depends(PermissionChecker(Permission.CONFIG_VIEW))],
):
    """Get current configuration (sanitized - no secrets).

    Returns the current configuration settings with sensitive values masked.
    Requires CONFIG_VIEW permission.
    """
    # Check if SMTP password is set
    smtp_has_password = bool(settings.SMTP_PASSWORD and settings.SMTP_PASSWORD.strip())

    # Check if Graph secret is set
    graph_has_secret = bool(settings.GRAPH_CLIENT_SECRET and settings.GRAPH_CLIENT_SECRET.strip())

    return ConfigResponse(
        smtp_enabled=settings.SMTP_ENABLED,
        smtp_host=settings.SMTP_HOST,
        smtp_port=settings.SMTP_PORT,
        smtp_username=settings.SMTP_USERNAME or None,
        smtp_from_email=settings.SMTP_FROM_EMAIL,
        smtp_from_name=settings.SMTP_FROM_NAME,
        smtp_use_tls=settings.SMTP_USE_TLS,
        smtp_has_password=smtp_has_password,
        graph_enabled=settings.GRAPH_ENABLED,
        graph_tenant_id=settings.GRAPH_TENANT_ID or None,
        graph_client_id=settings.GRAPH_CLIENT_ID or None,
        graph_from_email=settings.GRAPH_FROM_EMAIL,
        graph_has_secret=graph_has_secret,
        monitor_interval_default=settings.MONITOR_INTERVAL_DEFAULT,
        cors_origins=settings.CORS_ORIGINS,
        brand_impacted=settings.BRAND_IMPACTED,
        session_timeout_minutes=settings.SESSION_TIMEOUT_MINUTES,
        version=settings.APP_VERSION,
    )


@router.put("", response_model=ConfigResponse)
async def update_config(
    config_update: ConfigUpdate,
    current_user: Annotated[User, Depends(require_admin)],
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update configuration (admin only).

    Updates settings in memory and persists to .env file for future sessions.

    Args:
        config_update: Configuration updates
        current_user: Current authenticated user (must be admin)
        request: FastAPI request for IP address
        db: Database session

    Returns:
        Updated configuration

    Raises:
        HTTPException: If update fails
    """
    # Track changes for audit and .env file updates
    changes = {}
    env_updates = {}

    # Apply updates to settings (for current session) and prepare .env updates
    if config_update.smtp_enabled is not None:
        settings.SMTP_ENABLED = config_update.smtp_enabled
        changes["smtp_enabled"] = config_update.smtp_enabled
        env_updates["SMTP_ENABLED"] = str(config_update.smtp_enabled).lower()

    if config_update.smtp_host is not None:
        settings.SMTP_HOST = config_update.smtp_host
        changes["smtp_host"] = config_update.smtp_host
        env_updates["SMTP_HOST"] = config_update.smtp_host

    if config_update.smtp_port is not None:
        settings.SMTP_PORT = config_update.smtp_port
        changes["smtp_port"] = config_update.smtp_port
        env_updates["SMTP_PORT"] = str(config_update.smtp_port)

    if config_update.smtp_username is not None:
        settings.SMTP_USERNAME = config_update.smtp_username
        changes["smtp_username"] = config_update.smtp_username
        env_updates["SMTP_USERNAME"] = config_update.smtp_username

    if config_update.smtp_password is not None:
        settings.SMTP_PASSWORD = config_update.smtp_password
        changes["smtp_password"] = "***"  # Don't log actual password
        env_updates["SMTP_PASSWORD"] = config_update.smtp_password

    if config_update.smtp_from_email is not None:
        settings.SMTP_FROM_EMAIL = config_update.smtp_from_email
        changes["smtp_from_email"] = config_update.smtp_from_email
        env_updates["SMTP_FROM_EMAIL"] = config_update.smtp_from_email

    if config_update.smtp_from_name is not None:
        settings.SMTP_FROM_NAME = config_update.smtp_from_name
        changes["smtp_from_name"] = config_update.smtp_from_name
        env_updates["SMTP_FROM_NAME"] = config_update.smtp_from_name

    if config_update.smtp_use_tls is not None:
        settings.SMTP_USE_TLS = config_update.smtp_use_tls
        changes["smtp_use_tls"] = config_update.smtp_use_tls
        env_updates["SMTP_USE_TLS"] = str(config_update.smtp_use_tls).lower()

    # Graph API updates
    if config_update.graph_enabled is not None:
        settings.GRAPH_ENABLED = config_update.graph_enabled
        changes["graph_enabled"] = config_update.graph_enabled
        env_updates["GRAPH_ENABLED"] = str(config_update.graph_enabled).lower()

    if config_update.graph_tenant_id is not None:
        settings.GRAPH_TENANT_ID = config_update.graph_tenant_id
        changes["graph_tenant_id"] = config_update.graph_tenant_id
        env_updates["GRAPH_TENANT_ID"] = config_update.graph_tenant_id

    if config_update.graph_client_id is not None:
        settings.GRAPH_CLIENT_ID = config_update.graph_client_id
        changes["graph_client_id"] = config_update.graph_client_id
        env_updates["GRAPH_CLIENT_ID"] = config_update.graph_client_id

    if config_update.graph_client_secret is not None:
        settings.GRAPH_CLIENT_SECRET = config_update.graph_client_secret
        changes["graph_client_secret"] = "***"
        env_updates["GRAPH_CLIENT_SECRET"] = config_update.graph_client_secret

    if config_update.graph_from_email is not None:
        settings.GRAPH_FROM_EMAIL = config_update.graph_from_email
        changes["graph_from_email"] = config_update.graph_from_email
        env_updates["GRAPH_FROM_EMAIL"] = config_update.graph_from_email

    if config_update.monitor_interval_default is not None:
        settings.MONITOR_INTERVAL_DEFAULT = config_update.monitor_interval_default
        changes["monitor_interval_default"] = config_update.monitor_interval_default
        env_updates["MONITOR_INTERVAL_DEFAULT"] = str(config_update.monitor_interval_default)

    if config_update.cors_origins is not None:
        settings.CORS_ORIGINS = config_update.cors_origins
        changes["cors_origins"] = config_update.cors_origins
        import json
        env_updates["CORS_ORIGINS"] = json.dumps(config_update.cors_origins)

    if config_update.brand_impacted is not None:
        settings.BRAND_IMPACTED = config_update.brand_impacted
        changes["brand_impacted"] = config_update.brand_impacted
        import json
        env_updates["BRAND_IMPACTED"] = json.dumps(config_update.brand_impacted)

    # Security settings
    if config_update.session_timeout_minutes is not None:
        settings.SESSION_TIMEOUT_MINUTES = config_update.session_timeout_minutes
        changes["session_timeout_minutes"] = config_update.session_timeout_minutes
        env_updates["SESSION_TIMEOUT_MINUTES"] = str(config_update.session_timeout_minutes)

    # Persist to .env file
    try:
        update_env_file(env_updates)
    except Exception as e:
        print(f"Warning: Failed to update .env file: {e}")

    # Log configuration update
    await log_audit_action(
        db,
        user_id=current_user.id,
        action=AuditAction.CONFIG_UPDATED,
        resource_type=ResourceType.CONFIG,
        details={"changes": changes},
    )
    await db.commit()

    # Return updated config
    smtp_has_password = bool(settings.SMTP_PASSWORD and settings.SMTP_PASSWORD.strip())
    graph_has_secret = bool(settings.GRAPH_CLIENT_SECRET and settings.GRAPH_CLIENT_SECRET.strip())

    return ConfigResponse(
        smtp_enabled=settings.SMTP_ENABLED,
        smtp_host=settings.SMTP_HOST,
        smtp_port=settings.SMTP_PORT,
        smtp_username=settings.SMTP_USERNAME or None,
        smtp_from_email=settings.SMTP_FROM_EMAIL,
        smtp_from_name=settings.SMTP_FROM_NAME,
        smtp_use_tls=settings.SMTP_USE_TLS,
        smtp_has_password=smtp_has_password,
        graph_enabled=settings.GRAPH_ENABLED,
        graph_tenant_id=settings.GRAPH_TENANT_ID or None,
        graph_client_id=settings.GRAPH_CLIENT_ID or None,
        graph_from_email=settings.GRAPH_FROM_EMAIL,
        graph_has_secret=graph_has_secret,
        monitor_interval_default=settings.MONITOR_INTERVAL_DEFAULT,
        cors_origins=settings.CORS_ORIGINS,
        brand_impacted=settings.BRAND_IMPACTED,
        session_timeout_minutes=settings.SESSION_TIMEOUT_MINUTES,
        version=settings.APP_VERSION,
    )


@router.patch("", response_model=ConfigResponse)
async def patch_config(
    config_update: ConfigUpdate,
    current_user: Annotated[User, Depends(PermissionChecker(Permission.CONFIG_UPDATE))],
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Partially update configuration.

    Updates only the provided fields in settings.
    Requires CONFIG_UPDATE permission.

    Args:
        config_update: Configuration updates (only provided fields will be updated)
        current_user: Current authenticated user
        request: FastAPI request for IP address
        db: Database session

    Returns:
        Updated configuration
    """
    # Track changes for audit and .env file updates
    changes = {}
    env_updates = {}

    # Apply updates to settings (for current session) and prepare .env updates
    # Only update fields that are provided (not None)
    if hasattr(config_update, 'smtp_enabled') and config_update.smtp_enabled is not None:
        settings.SMTP_ENABLED = config_update.smtp_enabled
        changes["smtp_enabled"] = config_update.smtp_enabled
        env_updates["SMTP_ENABLED"] = str(config_update.smtp_enabled).lower()

    if hasattr(config_update, 'smtp_host') and config_update.smtp_host is not None:
        settings.SMTP_HOST = config_update.smtp_host
        changes["smtp_host"] = config_update.smtp_host
        env_updates["SMTP_HOST"] = config_update.smtp_host

    if hasattr(config_update, 'smtp_port') and config_update.smtp_port is not None:
        settings.SMTP_PORT = config_update.smtp_port
        changes["smtp_port"] = config_update.smtp_port
        env_updates["SMTP_PORT"] = str(config_update.smtp_port)

    if hasattr(config_update, 'smtp_username') and config_update.smtp_username is not None:
        settings.SMTP_USERNAME = config_update.smtp_username
        changes["smtp_username"] = config_update.smtp_username
        env_updates["SMTP_USERNAME"] = config_update.smtp_username

    if hasattr(config_update, 'smtp_password') and config_update.smtp_password is not None:
        settings.SMTP_PASSWORD = config_update.smtp_password
        changes["smtp_password"] = "***"
        env_updates["SMTP_PASSWORD"] = config_update.smtp_password

    if hasattr(config_update, 'smtp_from_email') and config_update.smtp_from_email is not None:
        settings.SMTP_FROM_EMAIL = config_update.smtp_from_email
        changes["smtp_from_email"] = config_update.smtp_from_email
        env_updates["SMTP_FROM_EMAIL"] = config_update.smtp_from_email

    if hasattr(config_update, 'smtp_from_name') and config_update.smtp_from_name is not None:
        settings.SMTP_FROM_NAME = config_update.smtp_from_name
        changes["smtp_from_name"] = config_update.smtp_from_name
        env_updates["SMTP_FROM_NAME"] = config_update.smtp_from_name

    if hasattr(config_update, 'smtp_use_tls') and config_update.smtp_use_tls is not None:
        settings.SMTP_USE_TLS = config_update.smtp_use_tls
        changes["smtp_use_tls"] = config_update.smtp_use_tls
        env_updates["SMTP_USE_TLS"] = str(config_update.smtp_use_tls).lower()

    # Graph API updates
    if hasattr(config_update, 'graph_enabled') and config_update.graph_enabled is not None:
        settings.GRAPH_ENABLED = config_update.graph_enabled
        changes["graph_enabled"] = config_update.graph_enabled
        env_updates["GRAPH_ENABLED"] = str(config_update.graph_enabled).lower()

    if hasattr(config_update, 'graph_tenant_id') and config_update.graph_tenant_id is not None:
        settings.GRAPH_TENANT_ID = config_update.graph_tenant_id
        changes["graph_tenant_id"] = config_update.graph_tenant_id
        env_updates["GRAPH_TENANT_ID"] = config_update.graph_tenant_id

    if hasattr(config_update, 'graph_client_id') and config_update.graph_client_id is not None:
        settings.GRAPH_CLIENT_ID = config_update.graph_client_id
        changes["graph_client_id"] = config_update.graph_client_id
        env_updates["GRAPH_CLIENT_ID"] = config_update.graph_client_id

    if hasattr(config_update, 'graph_client_secret') and config_update.graph_client_secret is not None:
        settings.GRAPH_CLIENT_SECRET = config_update.graph_client_secret
        changes["graph_client_secret"] = "***"
        env_updates["GRAPH_CLIENT_SECRET"] = config_update.graph_client_secret

    if hasattr(config_update, 'graph_from_email') and config_update.graph_from_email is not None:
        settings.GRAPH_FROM_EMAIL = config_update.graph_from_email
        changes["graph_from_email"] = config_update.graph_from_email
        env_updates["GRAPH_FROM_EMAIL"] = config_update.graph_from_email

    if hasattr(config_update, 'monitor_interval_default') and config_update.monitor_interval_default is not None:
        settings.MONITOR_INTERVAL_DEFAULT = config_update.monitor_interval_default
        changes["monitor_interval_default"] = config_update.monitor_interval_default
        env_updates["MONITOR_INTERVAL_DEFAULT"] = str(config_update.monitor_interval_default)

    if hasattr(config_update, 'cors_origins') and config_update.cors_origins is not None:
        settings.CORS_ORIGINS = config_update.cors_origins
        changes["cors_origins"] = config_update.cors_origins
        import json
        env_updates["CORS_ORIGINS"] = json.dumps(config_update.cors_origins)

    if hasattr(config_update, 'brand_impacted') and config_update.brand_impacted is not None:
        settings.BRAND_IMPACTED = config_update.brand_impacted
        changes["brand_impacted"] = config_update.brand_impacted
        import json
        env_updates["BRAND_IMPACTED"] = json.dumps(config_update.brand_impacted)

    # Security settings
    if hasattr(config_update, 'session_timeout_minutes') and config_update.session_timeout_minutes is not None:
        settings.SESSION_TIMEOUT_MINUTES = config_update.session_timeout_minutes
        changes["session_timeout_minutes"] = config_update.session_timeout_minutes
        env_updates["SESSION_TIMEOUT_MINUTES"] = str(config_update.session_timeout_minutes)

    # Persist to .env file
    if env_updates:
        try:
            update_env_file(env_updates)
        except Exception as e:
            print(f"Warning: Failed to update .env file: {e}")

    # Log configuration update
    if changes:
        await log_audit_action(
            db,
            user_id=current_user.id,
            action=AuditAction.CONFIG_UPDATED,
            resource_type=ResourceType.CONFIG,
            details={"changes": changes},
        )
        await db.commit()

    # Return updated config
    smtp_has_password = bool(settings.SMTP_PASSWORD and settings.SMTP_PASSWORD.strip())
    graph_has_secret = bool(settings.GRAPH_CLIENT_SECRET and settings.GRAPH_CLIENT_SECRET.strip())

    return ConfigResponse(
        smtp_enabled=settings.SMTP_ENABLED,
        smtp_host=settings.SMTP_HOST,
        smtp_port=settings.SMTP_PORT,
        smtp_username=settings.SMTP_USERNAME or None,
        smtp_from_email=settings.SMTP_FROM_EMAIL,
        smtp_from_name=settings.SMTP_FROM_NAME,
        smtp_use_tls=settings.SMTP_USE_TLS,
        smtp_has_password=smtp_has_password,
        graph_enabled=settings.GRAPH_ENABLED,
        graph_tenant_id=settings.GRAPH_TENANT_ID or None,
        graph_client_id=settings.GRAPH_CLIENT_ID or None,
        graph_from_email=settings.GRAPH_FROM_EMAIL,
        graph_has_secret=graph_has_secret,
        monitor_interval_default=settings.MONITOR_INTERVAL_DEFAULT,
        cors_origins=settings.CORS_ORIGINS,
        brand_impacted=settings.BRAND_IMPACTED,
        session_timeout_minutes=settings.SESSION_TIMEOUT_MINUTES,
        version=settings.APP_VERSION,
    )


@router.get("/audit", response_model=dict)
async def get_config_audit_history(
    current_user: Annotated[User, Depends(require_admin)],
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Get configuration change history (admin only).

    Args:
        current_user: Current authenticated user (must be admin)
        page: Page number
        page_size: Items per page
        db: Database session

    Returns:
        Paginated list of config-related audit logs
    """
    from uuid import UUID

    # Get config-related audit logs
    logs = await get_audit_logs(
        db,
        resource_type="config",
        limit=page_size,
        offset=(page - 1) * page_size,
    )

    total = await count_audit_logs(db, resource_type="config")

    return {
        "logs": [
            AuditLogResponse(
                id=log.id,
                user_id=log.user_id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                details=log.details,
                ip_address=log.ip_address,
                created_at=log.created_at,
            )
            for log in logs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.post("/initialize", response_model=dict)
async def initialize_system(
    current_user: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    """Initialize system with default roles and admin user (admin only).

    This should be run once on first setup.

    Args:
        current_user: Current authenticated user (must be admin)
        db: Database session

    Returns:
        Initialization status
    """
    from uuid import uuid4
    from datetime import datetime
    from app.permissions import ROLE_PERMISSIONS, RoleName, ROLE_DESCRIPTIONS
    from app.models import Role
    from sqlalchemy import select

    results = {"roles_created": [], "users_created": []}

    # Create default roles
    for role_name, permissions in ROLE_PERMISSIONS.items():
        existing = await db.execute(
            select(Role).where(Role.name == role_name)
        )
        if not existing.scalar_one_or_none():
            role = Role(
                id=str(uuid4()),
                name=role_name,
                description=ROLE_DESCRIPTIONS.get(role_name, ""),
                permissions={"permissions": permissions},
                created_at=now_utc(),
            )
            db.add(role)
            results["roles_created"].append(role_name)

    await db.flush()

    # Check if admin user exists
    from app.models import User

    existing_admin = await db.execute(
        select(User).where(User.username == "admin")
    )

    if not existing_admin.scalar_one_or_none():
        # Get admin role
        admin_role_result = await db.execute(
            select(Role).where(Role.name == RoleName.ADMIN.value)
        )
        admin_role = admin_role_result.scalar_one_or_none()

        if admin_role:
            # Create default admin user with secure random password
            import secrets
            from app.auth.security import hash_password

            default_password = os.getenv("DEFAULT_ADMIN_PASSWORD", secrets.token_urlsafe(16))
            admin_user = User(
                id=str(uuid4()),
                username="admin",
                email="admin@phishtrack.local",
                hashed_password=hash_password(default_password),
                is_active=True,
                role_id=admin_role.id,
                created_at=now_utc(),
                updated_at=now_utc(),
            )
            db.add(admin_user)
            results["users_created"].append({
                "username": "admin",
                "email": "admin@phishtrack.local",
                "note": "Password generated - check server logs or set DEFAULT_ADMIN_PASSWORD env var",
            })

    await db.commit()

    return results


@router.post("/test-smtp")
async def test_smtp(
    request_data: dict,
    current_user: Annotated[User, Depends(require_admin)],
):
    """Test SMTP configuration by sending a test email (admin only).

    Args:
        request_data: Dictionary containing test_email (recipient) and optionally template_id
        current_user: Current authenticated user (must be admin)

    Returns:
        Test result with success status and message
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    test_email = request_data.get("test_email")
    template_id = request_data.get("template_id")

    if not test_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="test_email is required",
        )

    # Validate email format
    if "@" not in test_email or "." not in test_email.split("@")[1]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email address",
        )

    # Check if SMTP is configured
    if not settings.SMTP_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMTP is not enabled",
        )

    if not settings.SMTP_HOST or not settings.SMTP_PORT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMTP host and port are required",
        )

    # Prepare email content
    subject = "PhishTrack SMTP Test Email"
    body = """This is a test email from PhishTrack.

Your SMTP configuration is working correctly!

---
If you did not request this test, please ignore this email.
PhishTrack Automated Takedown System
"""

    # If template_id is provided, use that template
    html_body = None
    if template_id:
        from sqlalchemy import select
        from app.database import get_db_context
        from app.models import EmailTemplate

        async with get_db_context() as db:
            template = await db.get(EmailTemplate, template_id)
            if template:
                subject = template.subject
                body = template.body
                html_body = template.html_body
                # Render template with test variables
                test_vars = {
                    "{{ case_id }}": "TEST-CASE-123",
                    "{{ target_url }}": "https://example.com/phishing",
                    "{{ domain }}": "example.com",
                    "{{ ip }}": "192.168.1.1",
                    "{{ organization }}": "Test Organization",
                    "{{ reporter_email }}": test_email,
                    "{{ reported_date }}": now_utc().strftime("%Y-%m-%d %H:%M:%S"),
                }
                # Replace variables in both subject and body
                for var, value in test_vars.items():
                    subject = subject.replace(var, value)
                    body = body.replace(var, value)
                    if html_body:
                        html_body = html_body.replace(var, value)

    try:
        # Create email message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM_EMAIL
        msg["To"] = test_email

        # Attach plain text body
        msg.attach(MIMEText(body, "plain"))

        # Attach HTML body if available
        if html_body:
            msg.attach(MIMEText(html_body, "html"))

        # Connect to SMTP server and send with debug logging
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
            server.set_debuglevel(1)  # Enable debug output
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)

            # Use sendmail instead of send_message for better compatibility
            response = server.sendmail(settings.SMTP_FROM_EMAIL, [test_email], msg.as_string())
            print(f"SMTP Response: {response}")

        return {
            "success": True,
            "message": f"Test email sent successfully to {test_email}",
            "details": {
                "to": test_email,
                "from": settings.SMTP_FROM_EMAIL,
                "subject": subject,
                "host": settings.SMTP_HOST,
                "port": settings.SMTP_PORT,
                "tls": settings.SMTP_USE_TLS,
            }
        }
    except smtplib.SMTPAuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SMTP authentication failed: {str(e)}",
        )
    except smtplib.SMTPException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SMTP error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send test email: {str(e)}",
        )


@router.post("/test-graph")
async def test_graph_api(
    request_data: dict,
    current_user: Annotated[User, Depends(require_admin)],
):
    """Test Graph API configuration by sending a test email (admin only).

    Args:
        request_data: Dictionary containing test_email (recipient) and optionally template_id
        current_user: Current authenticated user (must be admin)

    Returns:
        Test result with success status and message
    """
    from app.services.graph_email import send_graph_email

    test_email = request_data.get("test_email")
    template_id = request_data.get("template_id")

    if not test_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="test_email is required",
        )

    # Validate email format
    if "@" not in test_email or "." not in test_email.split("@")[1]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email address",
        )

    # Check if Graph API is configured
    if not settings.GRAPH_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Graph API is not enabled",
        )

    required_fields = [settings.GRAPH_TENANT_ID, settings.GRAPH_CLIENT_ID, settings.GRAPH_CLIENT_SECRET]
    if not all(required_fields):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Graph API credentials are not fully configured",
        )

    # Prepare email content
    subject = "PhishTrack Graph API Test Email"
    body = """This is a test email from PhishTrack.

Your Graph API configuration is working correctly!

---
If you did not request this test, please ignore this email.
PhishTrack Automated Takedown System
"""
    html_body = None
    template_name = None

    # If template_id is provided, use that template
    if template_id:
        from sqlalchemy import select
        from app.database import get_db_context
        from app.models import EmailTemplate

        async with get_db_context() as db:
            result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
            template = result.scalar_one_or_none()
            if template:
                subject = template.subject
                body = template.body
                html_body = template.html_body
                template_name = template.name
                # Render template with test variables
                sample_vars = {
                    "{{ case_id }}": "TEST-001",
                    "{{ target_url }}": "https://example.com/verify-login",
                    "{{ domain }}": "example.com",
                    "{{ ip }}": "192.0.2.1",
                    "{{ organization }}": "Example Provider Inc.",
                    "{{ reporter_email }}": test_email,
                    "{{ reported_date }}": now_utc().strftime("%Y-%m-%d"),
                }
                # Replace variables in both subject and body
                for var, value in sample_vars.items():
                    subject = subject.replace(var, value)
                    body = body.replace(var, value)
                    if html_body:
                        html_body = html_body.replace(var, value)

    try:
        result = send_graph_email(test_email, subject, body, html_body)

        if result.get("success"):
            details = {
                "to": test_email,
                "from": settings.GRAPH_FROM_EMAIL,
                "subject": subject,
                "method": "graph_api",
            }
            if template_name:
                details["template"] = template_name
            return {
                "success": True,
                "message": f"Test email sent successfully to {test_email}",
                "details": details,
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to send test email"),
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send test email: {str(e)}",
        )
