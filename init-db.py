#!/usr/bin/env python
"""Ensure critical tables exist for our application."""

import os
import asyncio
import asyncpg
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Create critical tables if they don't exist."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        return False

    try:
        # Connect to the database
        logger.info(f"Connecting to database")
        conn = await asyncpg.connect(database_url)

        # Create schema if it doesn't exist
        await conn.execute("CREATE SCHEMA IF NOT EXISTS eligibility;")

        # Create query_cache table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS eligibility.query_cache (
                id SERIAL PRIMARY KEY,
                natural_query TEXT NOT NULL,
                generated_sql TEXT NOT NULL,
                explanation TEXT,
                execution_count INTEGER DEFAULT 1,
                last_used TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                execution_time_ms FLOAT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                query_id TEXT,
                query_embedding VECTOR(1536),
                CONSTRAINT unique_natural_query UNIQUE (natural_query)
            );

            CREATE INDEX IF NOT EXISTS idx_query_cache_natural ON eligibility.query_cache (natural_query);
            CREATE INDEX IF NOT EXISTS idx_query_cache_last_used ON eligibility.query_cache (last_used);
        """)

        # Create query_id_mappings table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS eligibility.query_id_mappings (
                new_query_id TEXT PRIMARY KEY,
                original_query_id TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_query_id_mappings_original_id 
            ON eligibility.query_id_mappings (original_query_id);
        """)

        logger.info("Critical tables created successfully")
        await conn.close()
        return True
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    if not success:
        logger.error("Failed to create critical tables")
        exit(1)