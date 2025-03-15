"""add_query_cache_table

Revision ID: 7494a737b210
Revises: 
Create Date: 2025-03-12 15:06:02.182338

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7494a737b210'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create table for exact query matching
    # We're now using this table only for exact matches, not for vector storage
    op.create_table('query_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('natural_query', sa.Text(), nullable=False),
        sa.Column('generated_sql', sa.Text(), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('execution_count', sa.Integer(), server_default='1', nullable=False),
        sa.Column('last_used', sa.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('execution_time_ms', sa.Float(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('source', sa.String(length=50), server_default='direct', nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('natural_query'),
        schema='eligibility'
    )

    # Create index for efficient text lookups
    op.create_index(op.f('idx_query_cache_natural'), 'query_cache', ['natural_query'], unique=True, schema='eligibility')

    # Performance index for last_used timestamp (for cleanup jobs)
    op.create_index(op.f('idx_query_cache_last_used'), 'query_cache', ['last_used'], schema='eligibility')


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index(op.f('idx_query_cache_last_used'), table_name='query_cache', schema='eligibility')
    op.drop_index(op.f('idx_query_cache_natural'), table_name='query_cache', schema='eligibility')

    # Drop table
    op.drop_table('query_cache', schema='eligibility')