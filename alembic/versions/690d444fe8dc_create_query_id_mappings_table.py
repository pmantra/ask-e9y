"""create query_id_mappings table

Revision ID: 690d444fe8dc
Revises: e008f89c640d
Create Date: 2025-03-19 22:35:51.172648

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '690d444fe8dc'
down_revision: Union[str, None] = 'e008f89c640d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add query_id_mappings table."""
    # Create the query_id_mappings table
    op.create_table(
        'query_id_mappings',
        sa.Column('new_query_id', sa.String(36), primary_key=True),
        sa.Column('original_query_id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        schema='eligibility'
    )

    # Create an index on original_query_id for faster lookups
    op.create_index(
        'idx_query_id_mappings_original_id',
        'query_id_mappings',
        ['original_query_id'],
        schema='eligibility'
    )


def downgrade() -> None:
    """Downgrade schema by removing query_id_mappings table."""
    # Drop the index first
    op.drop_index('idx_query_id_mappings_original_id', table_name='query_id_mappings', schema='eligibility')

    # Then drop the table
    op.drop_table('query_id_mappings', schema='eligibility')