"""Migrate existing timestamps from UTC to Asia/Jakarta timezone.

This script adds 7 hours to all existing datetime fields in the database
to convert from UTC (GMT+0) to Asia/Jakarta (GMT+7).
"""
import asyncio
import sys
from pathlib import Path
from datetime import timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import sync_engine, sync_session_factory, Session
from app.models import Role, User, AuditLog, Case, EmailTemplate, Evidence, GeneratedReport


def migrate_table(session: Session, model_class, datetime_fields: list[str]) -> int:
    """Migrate datetime fields for a table.

    Args:
        session: Database session
        model_class: SQLAlchemy model class
        datetime_fields: List of datetime field names to migrate

    Returns:
        Number of records updated
    """
    count = 0
    offset = timedelta(hours=7)  # UTC to Asia/Jakarta

    records = session.query(model_class).all()
    for record in records:
        updated = False
        for field in datetime_fields:
            value = getattr(record, field, None)
            if value is not None:
                # Add 7 hours to convert UTC to WIB
                new_value = value + offset
                setattr(record, field, new_value)
                updated = True

        if updated:
            count += 1

    if count > 0:
        session.commit()

    return count


def migrate_json_history(session: Session) -> int:
    """Migrate timestamps in JSON history fields of cases.

    Args:
        session: Database session

    Returns:
        Number of records updated
    """
    import json

    count = 0
    offset_hours = 7  # UTC to Asia/Jakarta

    cases = session.query(Case).all()
    for case in cases:
        if case.history:
            updated = False
            new_history = []

            for entry in case.history:
                if isinstance(entry, dict):
                    new_entry = entry.copy()
                    timestamp = new_entry.get("timestamp")
                    if timestamp:
                        # Parse ISO timestamp, add 7 hours, and reformat
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                            dt = dt + timedelta(hours=offset_hours)
                            # Remove timezone info for SQLite compatibility
                            new_entry["timestamp"] = dt.replace(tzinfo=None).isoformat()
                            updated = True
                        except Exception:
                            pass
                    new_history.append(new_entry)
                else:
                    new_history.append(entry)

            if updated:
                case.history = new_history
                count += 1

    if count > 0:
        session.commit()

    return count


def migrate_json_domain_info(session: Session) -> int:
    """Migrate timestamps in JSON domain_info fields of cases.

    Args:
        session: Database session

    Returns:
        Number of records updated
    """
    count = 0
    offset_hours = 7  # UTC to Asia/Jakarta

    cases = session.query(Case).all()
    for case in cases:
        if case.domain_info:
            updated = False
            new_domain_info = case.domain_info.copy()

            # Check for whois timestamp fields
            for field in ["whois_created", "whois_updated", "whois_expires", "created_date"]:
                if field in new_domain_info and new_domain_info[field]:
                    try:
                        from datetime import datetime
                        timestamp_str = new_domain_info[field]
                        dt = datetime.fromisoformat(timestamp_str)
                        dt = dt + timedelta(hours=offset_hours)
                        new_domain_info[field] = dt.isoformat()
                        updated = True
                    except Exception:
                        pass

            if updated:
                case.domain_info = new_domain_info
                count += 1

    if count > 0:
        session.commit()

    return count


def main():
    """Run the timezone migration."""
    print("=" * 60)
    print("Timezone Migration: UTC -> Asia/Jakarta (GMT+7)")
    print("=" * 60)

    session = sync_session_factory()

    try:
        # Migrate each table
        print("\nMigrating tables...")

        count = migrate_table(session, Role, ["created_at"])
        print(f"  - roles: {count} records updated")

        count = migrate_table(session, User, ["created_at", "updated_at", "last_login_at"])
        print(f"  - users: {count} records updated")

        count = migrate_table(session, AuditLog, ["created_at"])
        print(f"  - audit_logs: {count} records updated")

        count = migrate_table(
            session,
            Case,
            [
                "created_at",
                "updated_at",
                "last_monitored_at",
                "next_monitor_at",
                "last_email_sent_at",
            ],
        )
        print(f"  - cases: {count} records updated")

        count = migrate_table(session, EmailTemplate, ["created_at", "updated_at"])
        print(f"  - email_templates: {count} records updated")

        count = migrate_table(session, Evidence, ["created_at"])
        print(f"  - evidence: {count} records updated")

        count = migrate_table(session, GeneratedReport, ["created_at"])
        print(f"  - generated_reports: {count} records updated")

        # Migrate JSON fields
        print("\nMigrating JSON fields...")

        count = migrate_json_history(session)
        print(f"  - cases.history: {count} records updated")

        count = migrate_json_domain_info(session)
        print(f"  - cases.domain_info: {count} records updated")

        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError during migration: {e}")
        session.rollback()
        raise
    finally:
        session.close()
        sync_engine.dispose()


if __name__ == "__main__":
    main()
