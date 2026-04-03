"""Add http_status_code and http_checked_at to detected_domains

Revision ID: 008_add_http_status
Revises: 007_add_custom_brand_patterns
Create Date: 2026-02-23 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '008_add_http_status'
down_revision: Union[str, None] = '007_add_custom_brand_patterns'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Get the database connection and inspector
    conn = op.get_bind()
    inspector = inspect(conn)

    # Get existing columns in detected_domains table
    columns = [col['name'] for col in inspector.get_columns('detected_domains')]

    # Add http_status_code column if it doesn't exist
    if 'http_status_code' not in columns:
        op.add_column(
            'detected_domains',
            sa.Column('http_status_code', sa.Integer(), nullable=True)
        )
        # Create index on http_status_code
        op.create_index(
            'ix_detected_domains_http_status_code',
            'detected_domains',
            ['http_status_code']
        )

    # Add http_checked_at column if it doesn't exist
    if 'http_checked_at' not in columns:
        op.add_column(
            'detected_domains',
            sa.Column('http_checked_at', sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    # Drop columns
    op.drop_index('ix_detected_domains_http_status_code', table_name='detected_domains')
    op.drop_column('detected_domains', 'http_status_code')
    op.drop_column('detected_domains', 'http_checked_at')
