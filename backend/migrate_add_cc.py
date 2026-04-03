"""Migration script to add cc column to email_templates table.

Run this script on the deployed database to add the missing cc column.

Usage:
    docker exec -it phishtrack-backend python migrate_add_cc.py
    or
    docker compose exec backend python migrate_add_cc.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import async_session_factory, engine
from sqlalchemy import text, inspect


async def check_and_add_cc_column():
    """Check if cc column exists and add it if missing."""

    async with engine.begin() as conn:
        # Check if the column exists using raw SQL
        result = await conn.execute(text("""
            SELECT COUNT(*) as cc_exists
            FROM information_schema.columns
            WHERE table_name = 'email_templates'
            AND column_name = 'cc'
        """))
        row = result.fetchone()
        cc_exists = row[0] > 0 if row else False

        if cc_exists:
            print("✓ Column 'cc' already exists. No migration needed.")
            return

        print("✗ Column 'cc' is missing. Adding it now...")

        # Add the cc column
        await conn.execute(text("""
            ALTER TABLE email_templates
            ADD COLUMN cc VARCHAR(500)
        """))

        print("✓ Column 'cc' added successfully.")

        # Verify the column was added
        result_after = await conn.execute(text("""
            SELECT COUNT(*) as cc_exists
            FROM information_schema.columns
            WHERE table_name = 'email_templates'
            AND column_name = 'cc'
        """))
        row_after = result_after.fetchone()
        cc_exists_after = row_after[0] > 0 if row_after else False

        if cc_exists_after:
            print("✓ Migration completed successfully!")
        else:
            print("✗ Migration failed - column not found after ALTER.")
            sys.exit(1)


async def main():
    """Run the migration."""
    print("=" * 60)
    print("Email Templates Migration: Add cc column")
    print("=" * 60)
    print()

    try:
        await check_and_add_cc_column()
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print()
    print("=" * 60)
    print("Migration completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
