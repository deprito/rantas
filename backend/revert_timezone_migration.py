"""Revert timezone migration back to UTC storage.

This script subtracts 7 hours from all datetime fields to convert
from Asia/Jakarta (GMT+7) back to UTC (GMT+0).
"""
import asyncio
import sys
from pathlib import Path
from datetime import timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import sync_engine, sync_session_factory, Session
from app.models import Role, User, AuditLog, Case, EmailTemplate, Evidence, GeneratedReport


def revert_table(session: Session, model_class, datetime_fields: list[str]) -> int:
    """Revert datetime fields for a table.

    Args:
        session: Database session
        model_class: SQLAlchemy model class
        datetime_fields: List of datetime field names to revert

    Returns:
        Number of records updated
    """
    count = 0
    offset = timedelta(hours=7)  # Subtract 7 hours to revert to UTC

    records = session.query(model_class).all()
    for record in records:
        updated = False
        for field in datetime_fields:
            value = getattr(record, field, None)
            if value is not None:
                # Subtract 7 hours to convert back to UTC
                new_value = value - offset
                setattr(record, field, new_value)
                updated = True

        if updated:
            count += 1

    if count > 0:
        session.commit()

    return count


def revert_json_history(session: Session) -> int:
    """Revert timestamps in JSON history fields of cases.

    Args:
        session: Database session

    Returns:
        Number of records updated
    """
    import json

    count = 0
    offset_hours = 7  # Subtract 7 hours to revert to UTC

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
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(timestamp)
                            dt = dt - timedelta(hours=offset_hours)
                            new_entry["timestamp"] = dt.isoformat()
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


def revert_json_domain_info(session: Session) -> int:
    """Revert timestamps in JSON domain_info fields of cases.

    Args:
        session: Database session

    Returns:
        Number of records updated
    """
    count = 0
    offset_hours = 7  # Subtract 7 hours to revert to UTC

    cases = session.query(Case).all()
    for case in cases:
        if case.domain_info:
            updated = False
            new_domain_info = case.domain_info.copy()

            for field in ["whois_created", "whois_updated", "whois_expires", "created_date"]:
                if field in new_domain_info and new_domain_info[field]:
                    try:
                        from datetime import datetime
                        timestamp_str = new_domain_info[field]
                        dt = datetime.fromisoformat(timestamp_str)
                        dt = dt - timedelta(hours=offset_hours)
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
    """Run the timezone revert."""
    print("=" * 60)
    print("Reverting to UTC Storage (Asia/Jakarta -> UTC)")
    print("=" * 60)

    session = sync_session_factory()

    try:
        print("\nReverting tables...")

        count = revert_table(session, Role, ["created_at"])
        print(f"  - roles: {count} records reverted")

        count = revert_table(session, User, ["created_at", "updated_at", "last_login_at"])
        print(f"  - users: {count} records reverted")

        count = revert_table(session, AuditLog, ["created_at"])
        print(f"  - audit_logs: {count} records reverted")

        count = revert_table(
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
        print(f"  - cases: {count} records reverted")

        count = revert_table(session, EmailTemplate, ["created_at", "updated_at"])
        print(f"  - email_templates: {count} records reverted")

        count = revert_table(session, Evidence, ["created_at"])
        print(f"  - evidence: {count} records reverted")

        count = revert_table(session, GeneratedReport, ["created_at"])
        print(f"  - generated_reports: {count} records reverted")

        print("\nReverting JSON fields...")

        count = revert_json_history(session)
        print(f"  - cases.history: {count} records reverted")

        count = revert_json_domain_info(session)
        print(f"  - cases.domain_info: {count} records reverted")

        print("\n" + "=" * 60)
        print("Revert completed! Database is back to UTC.")
        print("=" * 60)

    except Exception as e:
        print(f"\nError during revert: {e}")
        session.rollback()
        raise
    finally:
        session.close()
        sync_engine.dispose()


if __name__ == "__main__":
    main()
