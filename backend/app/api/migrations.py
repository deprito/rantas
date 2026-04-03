"""Database Migrations API for PhishTrack Admin.

Provides admin-only endpoints for managing Alembic migrations via the UI.
"""
from typing import Optional
import subprocess
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.dependencies import get_current_user, require_admin
from app.models import User

router = APIRouter()


class MigrationInfo(BaseModel):
    """Information about a single migration."""
    revision: str
    description: str
    is_head: bool
    is_current: bool


class MigrationStatus(BaseModel):
    """Current migration status."""
    current_revision: Optional[str]
    head_revision: Optional[str]
    is_up_to_date: bool
    pending_count: int
    migrations: list[MigrationInfo]


class MigrationResult(BaseModel):
    """Result of a migration operation."""
    success: bool
    message: str
    output: str
    from_revision: Optional[str]
    to_revision: Optional[str]


class UpgradeRequest(BaseModel):
    """Request body for upgrade."""
    revision: str = "head"


class DowngradeRequest(BaseModel):
    """Request body for downgrade."""
    revision: str = "-1"


class StampRequest(BaseModel):
    """Request body for stamp."""
    revision: str


def get_alembic_dir() -> str:
    """Get the directory containing alembic.ini.
    
    In the container, alembic.ini is at /app/alembic.ini
    The app module is at /app/app/, so we go up two levels.
    """
    # /app/app/api/migrations.py -> /app/app/api -> /app/app -> /app
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_alembic_command(args: list[str], timeout: int = 60) -> tuple[bool, str]:
    """Run an alembic command and return the result.
    
    Args:
        args: Command arguments (e.g., ['current', '-v'])
        timeout: Timeout in seconds
        
    Returns:
        Tuple of (success, output)
    """
    alembic_dir = get_alembic_dir()
    
    try:
        result = subprocess.run(
            ['alembic'] + args,
            cwd=alembic_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, 'PYTHONPATH': alembic_dir}
        )
        
        output = result.stdout + result.stderr
        success = result.returncode == 0
        
        return success, output.strip()
        
    except subprocess.TimeoutExpired:
        return False, "Migration command timed out"
    except FileNotFoundError:
        return False, "Alembic not found. Please ensure it is installed."
    except Exception as e:
        return False, f"Error running migration: {str(e)}"


def parse_migration_history(output: str) -> list[MigrationInfo]:
    """Parse alembic history output into MigrationInfo objects."""
    migrations = []
    lines = output.strip().split('\n')
    
    for line in lines:
        if not line.strip() or line.startswith('<'):
            continue
            
        # Parse lines like: "001_initial_schema -> 002_add_column (head), Add column"
        # or: "001_initial_schema (current) (head), Initial schema"
        is_head = '(head)' in line
        is_current = '(current)' in line
        
        # Extract revision and description
        parts = line.split(',', 1)
        if len(parts) >= 1:
            rev_part = parts[0].strip()
            description = parts[1].strip() if len(parts) > 1 else ''
            
            # Clean up revision
            revision = rev_part.split('->')[0].strip() if '->' in rev_part else rev_part
            revision = revision.replace('(head)', '').replace('(current)', '').strip()
            
            if revision:
                migrations.append(MigrationInfo(
                    revision=revision,
                    description=description,
                    is_head=is_head,
                    is_current=is_current,
                ))
    
    return migrations


@router.get("/admin/migrations", response_model=MigrationStatus)
async def get_migration_status(
    current_user: User = Depends(require_admin),
) -> MigrationStatus:
    """Get current migration status and history.
    
    Requires ADMIN role.
    """
    # Get current revision
    success, current_output = run_alembic_command(['current'])
    current_revision = None
    if success and current_output:
        # Parse output like "001_initial_schema (head)"
        current_revision = current_output.split()[0] if current_output else None
    
    # Get head revision
    success, head_output = run_alembic_command(['heads'])
    head_revision = None
    if success and head_output:
        head_revision = head_output.split()[0] if head_output else None
    
    # Get history
    success, history_output = run_alembic_command(['history', '-v'])
    migrations = []
    if success:
        migrations = parse_migration_history(history_output)
    
    # Calculate pending
    is_up_to_date = current_revision == head_revision if (current_revision and head_revision) else False
    pending_count = 0
    if not is_up_to_date and migrations:
        # Count migrations after current
        found_current = False
        for m in reversed(migrations):
            if m.is_current:
                found_current = True
            elif found_current:
                pending_count += 1
    
    return MigrationStatus(
        current_revision=current_revision,
        head_revision=head_revision,
        is_up_to_date=is_up_to_date,
        pending_count=pending_count,
        migrations=migrations,
    )


@router.post("/admin/migrations/upgrade", response_model=MigrationResult)
async def upgrade_database(
    request: UpgradeRequest,
    current_user: User = Depends(require_admin),
) -> MigrationResult:
    """Apply pending migrations.
    
    Args:
        revision: Target revision (default: "head" for latest)
        
    Requires ADMIN role.
    """
    # Get current revision before upgrade
    _, current_output = run_alembic_command(['current'])
    from_revision = current_output.split()[0] if current_output else None
    
    # Run upgrade
    success, output = run_alembic_command(['upgrade', request.revision])
    
    # Get new revision after upgrade
    _, new_output = run_alembic_command(['current'])
    to_revision = new_output.split()[0] if new_output else None
    
    if success:
        return MigrationResult(
            success=True,
            message=f"Successfully upgraded to {to_revision or request.revision}",
            output=output,
            from_revision=from_revision,
            to_revision=to_revision,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Migration failed: {output}",
        )


@router.post("/admin/migrations/downgrade", response_model=MigrationResult)
async def downgrade_database(
    request: DowngradeRequest,
    current_user: User = Depends(require_admin),
) -> MigrationResult:
    """Rollback to a previous migration.
    
    Args:
        revision: Target revision (default: "-1" for one step back)
        
    Requires ADMIN role.
    
    WARNING: This may result in data loss!
    """
    # Get current revision before downgrade
    _, current_output = run_alembic_command(['current'])
    from_revision = current_output.split()[0] if current_output else None
    
    # Run downgrade
    success, output = run_alembic_command(['downgrade', request.revision])
    
    # Get new revision after downgrade
    _, new_output = run_alembic_command(['current'])
    to_revision = new_output.split()[0] if new_output else None
    
    if success:
        return MigrationResult(
            success=True,
            message=f"Successfully downgraded from {from_revision} to {to_revision or 'base'}",
            output=output,
            from_revision=from_revision,
            to_revision=to_revision,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Downgrade failed: {output}",
        )


@router.post("/admin/migrations/stamp", response_model=MigrationResult)
async def stamp_database(
    request: StampRequest,
    current_user: User = Depends(require_admin),
) -> MigrationResult:
    """Set the alembic version to a specific revision without running migrations.

    Use this when the database schema is already at a certain state
    but alembic's tracking is out of sync.

    Args:
        revision: Target revision to stamp as current

    Requires ADMIN role.

    WARNING: Use with caution! This bypasses migration safety checks.
    """
    # Get current revision before stamp
    _, current_output = run_alembic_command(['current'])
    from_revision = current_output.split()[0] if current_output else None

    # Run stamp
    success, output = run_alembic_command(['stamp', request.revision])

    # Verify new revision
    _, new_output = run_alembic_command(['current'])
    to_revision = new_output.split()[0] if new_output else None

    if success:
        return MigrationResult(
            success=True,
            message=f"Stamped database as {to_revision or request.revision}",
            output=output,
            from_revision=from_revision,
            to_revision=to_revision,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stamp failed: {output}",
        )
