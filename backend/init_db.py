"""Initialize database with default admin user and roles."""
import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import init_db, async_session_factory
from app.models import User, Role
from app.auth.security import hash_password
from app.permissions import ROLE_PERMISSIONS, ROLE_DESCRIPTIONS
from app.config import settings
from app.utils.timezone import now_utc
from sqlalchemy import select


async def create_default_admin():
    """Create default admin user and roles."""
    await init_db()

    async with async_session_factory() as db:
        # Create default roles
        for role_name, permissions in ROLE_PERMISSIONS.items():
            existing = await db.execute(
                select(Role).where(Role.name == role_name)
            )
            if not existing.scalar_one_or_none():
                # Convert permissions to strings
                perm_list = [str(p.value) if hasattr(p, 'value') else str(p) for p in permissions]

                role = Role(
                    name=role_name,
                    description=ROLE_DESCRIPTIONS.get(role_name, ""),
                    permissions=perm_list,
                    created_at=now_utc(),
                )
                db.add(role)
                print(f"Created role: {role_name}")
            else:
                print(f"Role already exists: {role_name}")

        # Commit roles before querying
        await db.commit()

        # Get admin role
        admin_role = await db.execute(
            select(Role).where(Role.name.in_(["admin", "ADMIN"]))
        )
        admin_role = admin_role.scalar_one_or_none()

        if not admin_role:
            print("ERROR: Admin role not found!")
            return

        # Create default admin user
        existing_admin = await db.execute(
            select(User).where(User.username == "admin")
        )
        if not existing_admin.scalar_one_or_none():
            # Use environment variable for default password, fallback to secure random
            import secrets
            default_password = os.getenv("DEFAULT_ADMIN_PASSWORD", secrets.token_urlsafe(16))
            admin_user = User(
                username="admin",
                email="admin@phishtrack.dev",
                hashed_password=hash_password(default_password),
                role_id=str(admin_role.id),
                is_active=True,
                created_at=now_utc(),
                updated_at=now_utc(),
            )
            db.add(admin_user)
            await db.commit()
            print("\n[+] Default admin user created!")
            print("  Username: admin")
            print(f"  Password: {default_password}")
            print("  [!] Store this password securely - it won't be shown again")
        else:
            print("\n[+] Admin user already exists!")


if __name__ == "__main__":
    asyncio.run(create_default_admin())
