"""Migration script to add html_body column to email_templates table.

Run this script on the deployed database to add the missing html_body column.

Usage:
    docker exec -it phishtrack-backend python migrate_add_html_body.py
    or
    docker compose exec backend python migrate_add_html_body.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import async_session_factory, engine
from sqlalchemy import text, inspect
import asyncio


async def check_and_add_html_body_column():
    """Check if html_body column exists and add it if missing."""

    async with engine.begin() as conn:
        # Check if the column exists
        inspector = inspect(engine.sync_engine if hasattr(engine, 'sync_engine') else engine)
        columns = await conn.run_sync(lambda sync_conn: inspector.get_columns('email_templates'))
        column_names = [col['name'] for col in columns]

        print(f"Current columns in email_templates: {column_names}")

        if 'html_body' in column_names:
            print("✓ Column 'html_body' already exists. No migration needed.")
            return

        print("✗ Column 'html_body' is missing. Adding it now...")

        # Add the html_body column
        await conn.execute(text("""
            ALTER TABLE email_templates
            ADD COLUMN html_body TEXT
        """))

        print("✓ Column 'html_body' added successfully.")

        # Verify the column was added
        columns_after = await conn.run_sync(lambda sync_conn: inspector.get_columns('email_templates'))
        column_names_after = [col['name'] for col in columns_after]
        print(f"Updated columns in email_templates: {column_names_after}")

        if 'html_body' in column_names_after:
            print("✓ Migration completed successfully!")
        else:
            print("✗ Migration failed - column not found after ALTER.")
            sys.exit(1)


async def migrate_default_templates():
    """Migrate existing templates to have html_body based on body."""

    async with async_session_factory() as db:
        # Check if any templates need html_body
        result = await db.execute(text("""
            SELECT id, name, body, html_body
            FROM email_templates
            WHERE html_body IS NULL
        """))
        templates = result.fetchall()

        if not templates:
            print("✓ All templates have html_body set.")
            return

        print(f"Found {len(templates)} template(s) without html_body. Migrating...")

        for template in templates:
            template_id, name, body, html_body = template

            # Convert plain text body to basic HTML
            if body and not html_body:
                # Basic HTML conversion - escape HTML entities and wrap in paragraph
                import html
                escaped_body = html.escape(body)
                html_body = f"<p>{escaped_body.replace(chr(10), '</p><p>')}</p>"

                await db.execute(text("""
                    UPDATE email_templates
                    SET html_body = :html_body
                    WHERE id = :template_id
                """), {"html_body": html_body, "template_id": template_id})

                print(f"  - Migrated template: {name}")

        await db.commit()
        print("✓ Template migration completed successfully!")


async def main():
    """Run the migration."""
    print("=" * 60)
    print("Email Templates Migration: Add html_body column")
    print("=" * 60)
    print()

    try:
        await check_and_add_html_body_column()
        print()
        await migrate_default_templates()
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
