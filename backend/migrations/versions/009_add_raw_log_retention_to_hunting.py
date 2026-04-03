"""Add raw_log_retention_days to hunting_config table

Revision ID: 009_add_raw_log_retention
Revises: 008_add_http_status
Create Date: 2026-02-24 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009_add_raw_log_retention'
down_revision: Union[str, None] = '008_add_http_status'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add raw_log_retention_days column to hunting_config table."""
    # Check if the column exists before adding it
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('hunting_config')]

    if 'raw_log_retention_days' not in columns:
        op.add_column(
            'hunting_config',
            sa.Column('raw_log_retention_days', sa.Integer(), nullable=False, server_default='3')
        )


def downgrade() -> None:
    """Remove raw_log_retention_days column from hunting_config table."""
    op.drop_column('hunting_config', 'raw_log_retention_days')
