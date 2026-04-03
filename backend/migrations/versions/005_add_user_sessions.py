"""Add user_sessions table for session management.

Revision ID: 005_add_user_sessions
Revises: 004_add_submissions_table
Create Date: 2026-02-18
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '005_add_user_sessions'
down_revision: Union[str, None] = '004_add_submissions_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """Create user_sessions table."""
    if not table_exists('user_sessions'):
        op.create_table(
            'user_sessions',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('token_hash', sa.String(64), nullable=False, index=True),
            sa.Column('ip_address', sa.String(45), nullable=True),
            sa.Column('user_agent', sa.Text, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False, index=True),
            sa.Column('is_active', sa.Boolean, nullable=False, server_default='1', index=True),
        )


def downgrade() -> None:
    """Drop user_sessions table."""
    if table_exists('user_sessions'):
        op.drop_table('user_sessions')
