"""Utility for loading and formatting database schema information."""

import json
import logging
from typing import Dict, List, Any, Optional
# Import AsyncSessionLocal without causing circular imports
import sys
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings

# We no longer need this import logic since we reorganized the code
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def get_full_schema_details(schema_name: str = settings.DEFAULT_SCHEMA) -> Dict[str, Any]:
    """
    Get comprehensive details about the database schema.

    Args:
        schema_name: Name of the database schema

    Returns:
        Dictionary with schema details
    """
    from app.utils.schema import get_table_schema_info_with_session

    async with AsyncSessionLocal() as session:
        return await get_table_schema_info_with_session(session, schema_name)


def format_schema_for_llm(schema_info: Dict[str, Any]) -> str:
    """
    Format schema information in a way that's easy for LLMs to understand.

    Args:
        schema_info: Schema information dictionary

    Returns:
        Formatted schema string
    """
    formatted = "DATABASE SCHEMA:\n\n"

    for table_name, table_info in schema_info.items():
        formatted += f"Table: {table_name}\n"
        formatted += "Columns:\n"

        for column in table_info["columns"]:
            nullable = "NULL" if column["nullable"] else "NOT NULL"
            formatted += f"  - {column['name']} ({column['type']}, {nullable})\n"

        if "primary_keys" in table_info and table_info["primary_keys"]:
            formatted += "Primary Key: "
            formatted += ", ".join(table_info["primary_keys"])
            formatted += "\n"

        if "foreign_keys" in table_info and table_info["foreign_keys"]:
            formatted += "Foreign Keys:\n"
            for fk in table_info["foreign_keys"]:
                formatted += f"  - {fk['column']} → {fk['foreign_table']}.{fk['foreign_column']}\n"

        formatted += "\n"

    return formatted


def serialize_schema_info(schema_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize schema information to JSON-compatible format.

    Args:
        schema_info: Schema information dictionary

    Returns:
        JSON-serializable schema information
    """
    serialized = {}

    for table_name, table_info in schema_info.items():
        serialized[table_name] = {
            "columns": [],
            "primary_keys": table_info.get("primary_keys", []),
            "foreign_keys": []
        }

        # Serialize columns
        for column in table_info["columns"]:
            serialized_column = {
                "name": column["name"],
                "type": column["type"],
                "nullable": column["nullable"]
            }

            if column["default"] is not None:
                serialized_column["default"] = str(column["default"])

            serialized[table_name]["columns"].append(serialized_column)

        # Serialize foreign keys
        for fk in table_info.get("foreign_keys", []):
            serialized[table_name]["foreign_keys"].append({
                "column": fk["column"],
                "foreign_table": fk["foreign_table"],
                "foreign_column": fk["foreign_column"]
            })

    return serialized