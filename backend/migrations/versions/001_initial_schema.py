"""Initial schema migration - captures existing tables.

Revision ID: 001
Revises: 
Create Date: 2026-02-08

This migration represents the initial database schema.
It is designed to be idempotent - it will not fail if tables already exist.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """Create initial database schema."""
    
    # Create roles table
    if not table_exists('roles'):
        op.create_table(
            'roles',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('name', sa.String(50), nullable=False, unique=True, index=True),
            sa.Column('description', sa.String(255), nullable=False, server_default=''),
            sa.Column('permissions', sa.JSON, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )
    
    # Create users table
    if not table_exists('users'):
        op.create_table(
            'users',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('username', sa.String(100), nullable=False, unique=True, index=True),
            sa.Column('email', sa.String(255), nullable=False, unique=True, index=True),
            sa.Column('hashed_password', sa.String(255), nullable=False),
            sa.Column('is_active', sa.Boolean, nullable=False, server_default='1', index=True),
            sa.Column('role_id', sa.String(36), sa.ForeignKey('roles.id', ondelete='RESTRICT'), nullable=False, index=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
    
    # Create cases table
    if not table_exists('cases'):
        op.create_table(
            'cases',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('url', sa.String(2048), nullable=False, index=True),
            sa.Column('domain', sa.String(255), nullable=True, index=True),
            sa.Column('ip', sa.String(45), nullable=True),
            sa.Column('status', sa.String(50), nullable=False, server_default='NEW', index=True),
            sa.Column('priority', sa.String(20), nullable=False, server_default='normal'),
            sa.Column('notes', sa.Text, nullable=True),
            sa.Column('tags', sa.JSON, nullable=True),
            sa.Column('osint_data', sa.JSON, nullable=True),
            sa.Column('history', sa.JSON, nullable=True),
            sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('last_monitored_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('next_monitor_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('monitor_interval', sa.Integer, nullable=True),
            sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        )
    
    # Create audit_logs table
    if not table_exists('audit_logs'):
        op.create_table(
            'audit_logs',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('action', sa.String(100), nullable=False, index=True),
            sa.Column('entity_type', sa.String(50), nullable=False, index=True),
            sa.Column('entity_id', sa.String(36), nullable=True),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('username', sa.String(100), nullable=True),
            sa.Column('ip_address', sa.String(45), nullable=True),
            sa.Column('details', sa.JSON, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )
    
    # Create email_templates table
    if not table_exists('email_templates'):
        op.create_table(
            'email_templates',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('name', sa.String(100), nullable=False, unique=True, index=True),
            sa.Column('subject', sa.String(500), nullable=False),
            sa.Column('body', sa.Text, nullable=False),
            sa.Column('html_body', sa.Text, nullable=True),
            sa.Column('cc', sa.String(500), nullable=True),
            sa.Column('is_default', sa.Boolean, nullable=False, server_default='0'),
            sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
    
    # Create sent_emails table
    if not table_exists('sent_emails'):
        op.create_table(
            'sent_emails',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('case_id', sa.String(36), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('template_id', sa.String(36), sa.ForeignKey('email_templates.id', ondelete='SET NULL'), nullable=True),
            sa.Column('recipient', sa.String(255), nullable=False),
            sa.Column('subject', sa.String(500), nullable=False),
            sa.Column('body', sa.Text, nullable=False),
            sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
            sa.Column('error_message', sa.Text, nullable=True),
            sa.Column('sent_by', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    """Drop all tables (use with caution!)."""
    # Drop in reverse order due to foreign keys
    op.drop_table('sent_emails')
    op.drop_table('email_templates')
    op.drop_table('audit_logs')
    op.drop_table('cases')
    op.drop_table('users')
    op.drop_table('roles')
