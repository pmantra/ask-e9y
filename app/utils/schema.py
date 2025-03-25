"""Schema utilities to work with database schema information."""

import logging
from typing import Dict, List, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def get_table_names(session: AsyncSession, schema: str) -> List[str]:
    """Get all table names in the specified schema."""
    query = text(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = :schema
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )
    result = await session.execute(query, {"schema": schema})
    return [row[0] for row in result.fetchall()]


async def get_column_info(session: AsyncSession, table_name: str, schema: str) -> List[Dict[str, Any]]:
    """Get column information for a table."""
    query = text(
        """
        SELECT 
            column_name, 
            data_type, 
            is_nullable,
            column_default
        FROM 
            information_schema.columns
        WHERE 
            table_schema = :schema AND 
            table_name = :table_name
        ORDER BY 
            ordinal_position
        """
    )
    result = await session.execute(query, {"schema": schema, "table_name": table_name})
    columns = []
    for row in result.fetchall():
        columns.append({
            "name": row[0],
            "type": row[1],
            "nullable": row[2] == "YES",
            "default": row[3],
        })
    return columns


async def get_foreign_keys(session: AsyncSession, table_name: str, schema: str) -> List[Dict[str, Any]]:
    """Get foreign key information for a table."""
    query = text(
        """
        SELECT DISTINCT
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM
            information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
        WHERE
            tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = :schema
            AND tc.table_name = :table_name
        """
    )
    result = await session.execute(query, {"schema": schema, "table_name": table_name})

    # First collect all the foreign keys
    all_foreign_keys = []
    for row in result.fetchall():
        all_foreign_keys.append({
            "column": row[0],
            "foreign_table": row[1],
            "foreign_column": row[2],
        })

    # Deduplicate by creating a unique set of tuples
    unique_fk_tuples = set()
    deduplicated_foreign_keys = []

    for fk in all_foreign_keys:
        fk_tuple = (fk["column"], fk["foreign_table"], fk["foreign_column"])
        if fk_tuple not in unique_fk_tuples:
            unique_fk_tuples.add(fk_tuple)
            deduplicated_foreign_keys.append(fk)

    return deduplicated_foreign_keys


async def get_table_schema_info_with_session(session: AsyncSession, schema: str) -> Dict[str, Any]:
    """
    Get comprehensive schema information including tables, columns,
    and relationships with an existing session.
    """
    tables = await get_table_names(session, schema)
    schema_info = {}

    for table in tables:
        columns = await get_column_info(session, table, schema)
        foreign_keys = await get_foreign_keys(session, table, schema)

        schema_info[table] = {
            "columns": columns,
            "foreign_keys": foreign_keys
        }

    return schema_info


async def get_schema_metadata_with_session(session: AsyncSession, schema: str) -> Dict[str, Any]:
    """Get metadata from the schema_metadata table if it exists."""
    try:
        query = text(
            f"""
            SELECT 
                table_name, 
                column_name, 
                description, 
                example_value
            FROM 
                {schema}.schema_metadata
            """
        )
        result = await session.execute(query)
        metadata = {}
        for row in result.fetchall():
            table_name = row[0]
            if table_name not in metadata:
                metadata[table_name] = {}
            metadata[table_name][row[1]] = {
                "description": row[2],
                "example": row[3]
            }
        return metadata
    except Exception as e:
        logger.warning(f"Error getting schema metadata: {str(e)}")
        # Table might not exist yet
        return {}