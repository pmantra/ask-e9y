"""create api_metrics table

Revision ID: 1c2def96078e
Revises: 690d444fe8dc
Create Date: 2025-03-21 20:17:11.045839

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = '1c2def96078e'
down_revision: Union[str, None] = '690d444fe8dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the api_metrics table
    op.create_table('api_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('query_id', sa.String(), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('original_query', sa.Text(), nullable=False),
        sa.Column('cache_status', sa.String(), nullable=True),
        sa.Column('execution_time_ms', sa.Float(), nullable=True),
        sa.Column('total_time_ms', sa.Float(), nullable=True),
        sa.Column('row_count', sa.Integer(), nullable=True),
        sa.Column('schema_size', sa.Integer(), nullable=True),
        sa.Column('token_usage', JSONB(), nullable=True),
        sa.Column('stage_timings', JSONB(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='eligibility'
    )

    # Create indexes for efficient queries
    op.create_index('idx_api_metrics_query_id', 'api_metrics', ['query_id'], schema='eligibility')
    op.create_index('idx_api_metrics_timestamp', 'api_metrics', ['timestamp'], schema='eligibility')


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes first
    op.drop_index('idx_api_metrics_timestamp', table_name='api_metrics', schema='eligibility')
    op.drop_index('idx_api_metrics_query_id', table_name='api_metrics', schema='eligibility')