"""Add system_config table and historical_cases table.

Revision ID: 006_add_system_config
Revises: 005_add_user_sessions
Create Date: 2026-02-18
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '006_add_system_config'
down_revision: Union[str, None] = '005_add_user_sessions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Create system_config and historical_cases tables."""

    # Create historical_cases table if missing
    if not table_exists('historical_cases'):
        op.create_table(
            'historical_cases',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('url', sa.String(2048), nullable=False),
            sa.Column('status', sa.String(50), nullable=False, server_default='RESOLVED'),
            sa.Column('source', sa.String(50), nullable=False, server_default='internal'),
            sa.Column('brand_impacted', sa.String(255), nullable=True),
            sa.Column('emails_sent', sa.Integer, nullable=False, server_default='0'),
            sa.Column('domain_info', sa.JSON, nullable=False, server_default='{}'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('imported_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('reported_by', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        )

    # Add reported_by column if table exists but column is missing
    if table_exists('historical_cases') and not column_exists('historical_cases', 'reported_by'):
        op.add_column('historical_cases', sa.Column('reported_by', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))
        op.create_index('ix_historical_cases_reported_by', 'historical_cases', ['reported_by'])

    # Create blacklist_sources table if missing
    if not table_exists('blacklist_sources'):
        op.create_table(
            'blacklist_sources',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('source_type', sa.String(50), nullable=False),
            sa.Column('url', sa.String(2048), nullable=True),
            sa.Column('file_path', sa.String(1024), nullable=True),
            sa.Column('threat_category', sa.String(100), nullable=True),
            sa.Column('sync_interval_hours', sa.Integer, nullable=True),
            sa.Column('is_active', sa.Boolean, nullable=False, server_default='1'),
            sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('entry_count', sa.Integer, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )

    # Create blacklist_entries table if missing
    if not table_exists('blacklist_entries'):
        op.create_table(
            'blacklist_entries',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('domain', sa.String(255), nullable=False),
            sa.Column('is_wildcard', sa.Boolean, nullable=False, server_default='0'),
            sa.Column('threat_category', sa.String(100), nullable=True),
            sa.Column('source_id', sa.String(36), sa.ForeignKey('blacklist_sources.id', ondelete='CASCADE'), nullable=True),
            sa.Column('added_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('added_by', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        )

    # Create whitelist_entries table if missing
    if not table_exists('whitelist_entries'):
        op.create_table(
            'whitelist_entries',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('domain', sa.String(255), nullable=False),
            sa.Column('reason', sa.Text, nullable=True),
            sa.Column('added_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('added_by', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        )


def downgrade() -> None:
    """Drop new tables."""
    if table_exists('whitelist_entries'):
        op.drop_table('whitelist_entries')
    if table_exists('blacklist_entries'):
        op.drop_table('blacklist_entries')
    if table_exists('blacklist_sources'):
        op.drop_table('blacklist_sources')
    if table_exists('historical_cases'):
        op.drop_table('historical_cases')
