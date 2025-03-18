"""add_query_id_column

Revision ID: e008f89c640d
Revises: ee218ec76260
Create Date: 2025-03-17 18:24:53.709162

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'e008f89c640d'
down_revision: Union[str, None] = 'ee218ec76260'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add query_id column to query_cache table."""
    # Add UUID column (nullable initially to safely add to existing table)
    op.add_column('query_cache',
                  sa.Column('query_id', sa.String(36), nullable=True),
                  schema='eligibility')

    # Optional: Generate UUIDs for existing records if needed
    op.execute(text("""
        UPDATE eligibility.query_cache 
        SET query_id = gen_random_uuid()::text 
        WHERE query_id IS NULL
    """))

    # Optional: If you want to make it non-nullable after populating
    # op.alter_column('query_cache', 'query_id', nullable=False, schema='eligibility')


def downgrade() -> None:
    """Remove query_id column from query_cache table."""
    op.drop_column('query_cache', 'query_id', schema='eligibility')
