"""add_overeligibility_query

Revision ID: ee218ec76260
Revises: 7494a737b210
Create Date: 2025-03-15 21:08:31.057503

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'ee218ec76260'
down_revision: Union[str, None] = '7494a737b210'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to support overeligibility queries."""
    # Add schema metadata to document the overeligibility concept
    # Using empty string instead of NULL for column_name
    op.execute(text("""
        INSERT INTO eligibility.schema_metadata (table_name, column_name, description, example_value) 
        VALUES ('member', '', 'A person is considered "overeligible" if they have active member records in more than one organization with the same first name, last name, and date of birth.', '')
    """))

    # Add example query templates for common overeligibility queries
    op.execute(text("""
        INSERT INTO eligibility.query_templates (natural_language_pattern, sql_template, last_used, success_count) 
        VALUES 
        ('Show me all overeligible members',
         'SELECT m.first_name, m.last_name, m.date_of_birth, COUNT(DISTINCT m.organization_id) as org_count, array_agg(DISTINCT o.name) as organizations FROM eligibility.member m JOIN eligibility.organization o ON m.organization_id = o.id WHERE m.effective_range @> CURRENT_DATE GROUP BY m.first_name, m.last_name, m.date_of_birth HAVING COUNT(DISTINCT m.organization_id) > 1',
         CURRENT_TIMESTAMP, 1),
        
        ('Is {first_name} {last_name} overeligible',
         'SELECT COUNT(DISTINCT organization_id) > 1 as is_overeligible FROM eligibility.member WHERE first_name ILIKE ''{first_name}'' AND last_name ILIKE ''{last_name}'' AND effective_range @> CURRENT_DATE',
         CURRENT_TIMESTAMP, 1),
         
        ('Check if member with ID {member_id} is overeligible',
         'WITH member_identity AS (SELECT first_name, last_name, date_of_birth FROM eligibility.member WHERE id = {member_id}) SELECT COUNT(DISTINCT m.organization_id) > 1 as is_overeligible FROM eligibility.member m JOIN member_identity mi ON m.first_name = mi.first_name AND m.last_name = mi.last_name AND m.date_of_birth = mi.date_of_birth WHERE m.effective_range @> CURRENT_DATE',
         CURRENT_TIMESTAMP, 1)
    """))

    # Create an index to optimize overeligibility queries
    op.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_member_name_dob ON eligibility.member (first_name, last_name, date_of_birth)
    """))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove query templates
    op.execute(text("""
        DELETE FROM eligibility.query_templates 
        WHERE natural_language_pattern IN (
            'Show me all overeligible members',
            'Is {first_name} {last_name} overeligible',
            'Check if member with ID {member_id} is overeligible'
        )
    """))

    # Remove schema metadata - using empty string instead of NULL
    op.execute(text("""
        DELETE FROM eligibility.schema_metadata 
        WHERE table_name = 'member' 
        AND column_name = '' 
        AND description LIKE '%overeligible%'
    """))

    # Drop the index
    op.execute(text("""
        DROP INDEX IF EXISTS eligibility.idx_member_name_dob
    """))