"""Add default_brand_patterns and whitelist_patterns to hunting_config

Revision ID: 010_add_editable_patterns
Revises: 009_add_raw_log_retention_to_hunting
Create Date: 2026-02-27 10:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '010_add_editable_patterns'
down_revision: Union[str, None] = '009_add_raw_log_retention'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Check if the column exists before adding it
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('hunting_config')]

    if 'default_brand_patterns' not in columns:
        # For PostgreSQL, use JSONB; for SQLite, use JSON
        if op.get_context().dialect.name == 'postgresql':
            op.add_column(
                'hunting_config',
                sa.Column(
                    'default_brand_patterns',
                    postgresql.JSONB(),
                    nullable=False,
                    server_default='{}'
                )
            )
        else:
            op.add_column(
                'hunting_config',
                sa.Column(
                    'default_brand_patterns',
                    sa.JSON(),
                    nullable=False,
                    server_default='{}'
                )
            )

    if 'whitelist_patterns' not in columns:
        # For PostgreSQL, use JSONB; for SQLite, use JSON
        if op.get_context().dialect.name == 'postgresql':
            op.add_column(
                'hunting_config',
                sa.Column(
                    'whitelist_patterns',
                    postgresql.JSONB(),
                    nullable=False,
                    server_default='[]'
                )
            )
        else:
            op.add_column(
                'hunting_config',
                sa.Column(
                    'whitelist_patterns',
                    sa.JSON(),
                    nullable=False,
                    server_default='[]'
                )
            )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_column('hunting_config', 'whitelist_patterns')
    op.drop_column('hunting_config', 'default_brand_patterns')
