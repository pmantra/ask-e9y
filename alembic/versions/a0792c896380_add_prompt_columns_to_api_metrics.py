"""add prompt columns to api_metrics

Revision ID: a0792c896380
Revises: 1c2def96078e
Create Date: 2025-03-22 22:53:37.962075

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a0792c896380'
down_revision: Union[str, None] = '1c2def96078e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add prompt_system and prompt_user columns to api_metrics table."""
    # Check if api_metrics table exists
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'eligibility' 
            AND table_name = 'api_metrics'
        )
    """))
    
    table_exists = result.scalar()
    
    if table_exists:
        # Add prompt_system column if it doesn't exist
        op.execute(sa.text("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_schema = 'eligibility' 
                    AND table_name = 'api_metrics' 
                    AND column_name = 'prompt_system'
                ) THEN
                    ALTER TABLE eligibility.api_metrics ADD COLUMN prompt_system TEXT;
                END IF;
            END $$;
        """))
        
        # Add prompt_user column if it doesn't exist
        op.execute(sa.text("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_schema = 'eligibility' 
                    AND table_name = 'api_metrics' 
                    AND column_name = 'prompt_user'
                ) THEN
                    ALTER TABLE eligibility.api_metrics ADD COLUMN prompt_user TEXT;
                END IF;
            END $$;
        """))
    else:
        # The api_metrics table doesn't exist yet
        # This is a safety check, and we'll let the previous migration create the table
        pass


def downgrade() -> None:
    """Remove prompt_system and prompt_user columns from api_metrics table."""
    # Check if api_metrics table exists
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'eligibility' 
            AND table_name = 'api_metrics'
        )
    """))
    
    table_exists = result.scalar()
    
    if table_exists:
        # Drop prompt_system column if it exists
        op.execute(sa.text("""
            DO $$ 
            BEGIN
                IF EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_schema = 'eligibility' 
                    AND table_name = 'api_metrics' 
                    AND column_name = 'prompt_system'
                ) THEN
                    ALTER TABLE eligibility.api_metrics DROP COLUMN prompt_system;
                END IF;
            END $$;
        """))
        
        # Drop prompt_user column if it exists
        op.execute(sa.text("""
            DO $$ 
            BEGIN
                IF EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_schema = 'eligibility' 
                    AND table_name = 'api_metrics' 
                    AND column_name = 'prompt_user'
                ) THEN
                    ALTER TABLE eligibility.api_metrics DROP COLUMN prompt_user;
                END IF;
            END $$;
        """))
    else:
        # The api_metrics table doesn't exist
        pass
