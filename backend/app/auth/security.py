"""Security utilities for authentication and authorization."""

import bcrypt
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_

from app.config import settings


# JWT settings
ALGORITHM = "HS256"


def get_token_expire_minutes() -> int:
    """Get the token expiration time in minutes from settings."""
    return settings.SESSION_TIMEOUT_MINUTES


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    # Convert to bytes and hash
    pwd_bytes = password.encode('utf-8')
    # Use 10 rounds for faster login (default is 12, ~200-500ms -> ~50-100ms)
    salt = bcrypt.gensalt(rounds=10)
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against

    Returns:
        True if password matches hash
    """
    pwd_bytes = plain_password.encode('utf-8')
    hash_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(pwd_bytes, hash_bytes)


def hash_token(token: str) -> str:
    """Hash a JWT token for storage in the database.

    Uses SHA-256 to create a one-way hash of the token.

    Args:
        token: JWT token string

    Returns:
        Hexadecimal hash of the token
    """
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
    session_id: Optional[str] = None,
) -> str:
    """Create a JWT access token.

    Args:
        data: Data to encode in the token (typically user_id and username)
        expires_delta: Optional custom expiration time
        session_id: Optional session ID for session validation

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=get_token_expire_minutes())

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    })

    if session_id:
        to_encode["session_id"] = session_id

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token.

    Args:
        token: JWT token to decode

    Returns:
        Decoded token data (including session_id if present)

    Raises:
        JWTError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise JWTError(f"Invalid token: {str(e)}")


async def create_user_session(
    db: AsyncSession,
    user_id: str,
    token: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[str] = None,
) -> str:
    """Create a new user session and revoke all existing active sessions.

    This implements the single active session per user requirement.

    Args:
        db: Database session
        user_id: User ID
        token: JWT access token
        ip_address: Optional IP address of the client
        user_agent: Optional user agent string
        session_id: Optional session ID (if not provided, one will be generated)

    Returns:
        Session ID of the new session
    """
    from app.models import UserSession
    from app.utils.timezone import now_utc

    # First, revoke all existing active sessions for this user
    await revoke_user_sessions(db, user_id)

    # Use provided session_id or generate a new one
    if not session_id:
        session_id = str(uuid4())

    # Calculate expiration time
    expires_at = now_utc() + timedelta(minutes=get_token_expire_minutes())

    # Create new session with the session_id
    token_hash = hash_token(token)

    new_session = UserSession(
        id=session_id,
        user_id=user_id,
        token_hash=token_hash,
        ip_address=ip_address,
        user_agent=user_agent,
        created_at=now_utc(),
        expires_at=expires_at,
        is_active=True,
    )

    db.add(new_session)
    await db.flush()

    return session_id


async def revoke_user_sessions(
    db: AsyncSession,
    user_id: str,
    exclude_session_id: Optional[str] = None,
) -> int:
    """Revoke all active sessions for a user.

    Args:
        db: Database session
        user_id: User ID
        exclude_session_id: Optional session ID to exclude from revocation

    Returns:
        Number of sessions revoked
    """
    from app.models import UserSession

    # Build the update statement
    if exclude_session_id:
        # Revoke all sessions except the specified one
        stmt = (
            update(UserSession)
            .where(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.is_active == True,
                    UserSession.id != exclude_session_id,
                )
            )
            .values(is_active=False)
        )
    else:
        # Revoke all sessions for the user
        stmt = (
            update(UserSession)
            .where(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.is_active == True,
                )
            )
            .values(is_active=False)
        )

    result = await db.execute(stmt)
    return result.rowcount


async def revoke_session(db: AsyncSession, session_id: str) -> bool:
    """Revoke a specific session by ID.

    Args:
        db: Database session
        session_id: Session ID to revoke

    Returns:
        True if session was found and revoked, False otherwise
    """
    from app.models import UserSession

    stmt = (
        update(UserSession)
        .where(
            and_(
                UserSession.id == session_id,
                UserSession.is_active == True,
            )
        )
        .values(is_active=False)
    )

    result = await db.execute(stmt)
    return result.rowcount > 0


async def validate_session(
    db: AsyncSession,
    token: str,
    session_id: str,
    user_id: str,
) -> bool:
    """Validate a session against the database.

    Checks that:
    1. The session exists
    2. The session is active
    3. The token hash matches
    4. The session belongs to the correct user
    5. The session has not expired

    Args:
        db: Database session
        token: JWT token
        session_id: Session ID from token
        user_id: User ID from token

    Returns:
        True if session is valid, False otherwise
    """
    from app.models import UserSession
    from app.utils.timezone import now_utc

    # Get the session from database
    stmt = select(UserSession).where(
        and_(
            UserSession.id == session_id,
            UserSession.user_id == user_id,
            UserSession.is_active == True,
        )
    )

    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        return False

    # Check if session has expired
    if session.expires_at < now_utc():
        # Mark as inactive
        session.is_active = False
        await db.flush()
        return False

    # Verify token hash matches
    token_hash = hash_token(token)
    if session.token_hash != token_hash:
        return False

    return True


async def get_active_sessions(
    db: AsyncSession,
    user_id: str,
) -> list:
    """Get all active sessions for a user.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        List of active UserSession objects
    """
    from app.models import UserSession

    stmt = select(UserSession).where(
        and_(
            UserSession.user_id == user_id,
            UserSession.is_active == True,
        )
    ).order_by(UserSession.created_at.desc())

    result = await db.execute(stmt)
    return list(result.scalars().all())


def validate_password_requirements(password: str) -> tuple[bool, list[str]]:
    """Validate password against security requirements.

    Requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number

    Args:
        password: Password to validate

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")

    if not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")

    if not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")

    if not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one number")

    return len(errors) == 0, errors
