"""Add XARF format support to email_templates.

Revision ID: 002_add_xarf_support
Revises: 001_initial_schema
Create Date: 2026-02-08

This migration adds XARF (eXtended Abuse Reporting Format) support
to the email_templates table. XARF is a JSON-based standard for abuse
reporting used by providers like DigitalOcean Abuse.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '002_add_xarf_support'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Add XARF support columns to email_templates table."""

    # Add prefer_xarf column if it doesn't exist
    if not column_exists('email_templates', 'prefer_xarf'):
        op.add_column(
            'email_templates',
            sa.Column('prefer_xarf', sa.Boolean, nullable=False, server_default='0')
        )

    # Add xarf_reporter_ref_template column if it doesn't exist
    if not column_exists('email_templates', 'xarf_reporter_ref_template'):
        op.add_column(
            'email_templates',
            sa.Column('xarf_reporter_ref_template', sa.String(255), nullable=True)
        )


def downgrade() -> None:
    """Remove XARF support columns from email_templates table."""

    # Remove columns if they exist
    if column_exists('email_templates', 'xarf_reporter_ref_template'):
        op.drop_column('email_templates', 'xarf_reporter_ref_template')

    if column_exists('email_templates', 'prefer_xarf'):
        op.drop_column('email_templates', 'prefer_xarf')
