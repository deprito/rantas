"""Add public submissions table.

Revision ID: 004_add_submissions_table
Revises: 003_add_brand_and_monitoring
Create Date: 2026-02-18
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '004_add_submissions_table'
down_revision: Union[str, None] = '003_add_brand_and_monitoring'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """Create public_submissions table."""
    if not table_exists('public_submissions'):
        op.create_table(
            'public_submissions',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('url', sa.String(2048), nullable=False),
            sa.Column('email', sa.String(255), nullable=True),
            sa.Column('notes', sa.Text, nullable=True),
            sa.Column('submitter_name', sa.String(255), nullable=True),
            sa.Column('ip_address', sa.String(45), nullable=True),
            sa.Column('status', sa.String(50), nullable=False, server_default='pending', index=True),
            sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('reviewed_by', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('case_id', sa.String(36), sa.ForeignKey('cases.id', ondelete='SET NULL'), nullable=True),
            sa.Column('rejection_reason', sa.Text, nullable=True),
            sa.Column('additional_notes', sa.Text, nullable=True),
        )


def downgrade() -> None:
    """Drop public_submissions table."""
    if table_exists('public_submissions'):
        op.drop_table('public_submissions')
