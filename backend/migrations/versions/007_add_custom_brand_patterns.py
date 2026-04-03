"""Add custom_brand_patterns to hunting_config

Revision ID: 007_add_custom_brand_patterns
Revises: 006_add_system_config
Create Date: 2026-02-23 15:30:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '007_add_custom_brand_patterns'
down_revision: Union[str, None] = '006_add_system_config'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Check if the column exists before adding it
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('hunting_config')]

    if 'custom_brand_patterns' not in columns:
        op.add_column(
            'hunting_config',
            sa.Column(
                'custom_brand_patterns',
                postgresql.JSONB(),
                nullable=False,
                server_default='{}'
            )
        )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_column('hunting_config', 'custom_brand_patterns')
