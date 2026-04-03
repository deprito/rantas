"""Add brand_impacted and monitoring columns to cases.

Revision ID: 003_add_brand_and_monitoring
Revises: 002_add_xarf_support
Create Date: 2026-02-18
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '003_add_brand_and_monitoring'
down_revision: Union[str, None] = '002_add_xarf_support'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Add brand_impacted and monitoring columns to cases table."""
    # Add brand_impacted column if missing
    if not column_exists('cases', 'brand_impacted'):
        op.add_column('cases', sa.Column('brand_impacted', sa.String(255), nullable=True))

    # Add source column if missing
    if not column_exists('cases', 'source'):
        op.add_column('cases', sa.Column('source', sa.String(50), nullable=False, server_default='internal'))

    # Add abuse_contacts column if missing
    if not column_exists('cases', 'abuse_contacts'):
        op.add_column('cases', sa.Column('abuse_contacts', sa.JSON, nullable=True))

    # Add domain_info column if missing
    if not column_exists('cases', 'domain_info'):
        op.add_column('cases', sa.Column('domain_info', sa.JSON, nullable=True))


def downgrade() -> None:
    """Remove brand_impacted and monitoring columns."""
    if column_exists('cases', 'domain_info'):
        op.drop_column('cases', 'domain_info')
    if column_exists('cases', 'abuse_contacts'):
        op.drop_column('cases', 'abuse_contacts')
    if column_exists('cases', 'source'):
        op.drop_column('cases', 'source')
    if column_exists('cases', 'brand_impacted'):
        op.drop_column('cases', 'brand_impacted')
