#!/usr/bin/env python
"""Database initialization script for Railway deployment."""

import os
import asyncio
import asyncpg
import logging
from typing import List, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def read_sql_file(file_path):
    """Read the content of a SQL file."""
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return None


async def execute_sql_with_error_handling(conn, sql, continue_on_error=False):
    """
    Execute SQL statements with better error handling.

    Args:
        conn: Database connection
        sql: SQL statements to execute
        continue_on_error: If True, continue executing statements even if some fail

    Returns:
        Tuple of (success_count, error_count)
    """
    # Split the script into individual statements
    statements = []
    current_statement = []

    # Basic statement parsing - handles simple cases
    for line in sql.split('\n'):
        line = line.strip()

        # Skip comments and empty lines
        if not line or line.startswith('--'):
            continue

        current_statement.append(line)

        # If line ends with semicolon, it's end of statement
        if line.endswith(';'):
            statements.append('\n'.join(current_statement))
            current_statement = []

    # Add any remaining statements
    if current_statement:
        statements.append('\n'.join(current_statement))

    success_count = 0
    error_count = 0

    for i, statement in enumerate(statements, 1):
        statement = statement.strip()
        if not statement:
            continue  # Skip empty statements

        try:
            await conn.execute(statement)
            success_count += 1
            if i % 10 == 0:  # Log progress periodically
                logger.info(f"Executed {i}/{len(statements)} statements")
        except Exception as e:
            error_count += 1
            logger.error(f"Error executing SQL statement {i}/{len(statements)}: {e}")
            if len(statement) > 100:
                # Truncate long statements in logs
                logger.error(f"Statement (truncated): {statement[:100]}...")
            else:
                logger.error(f"Statement: {statement}")

            if not continue_on_error:
                logger.error("Stopping execution due to error")
                return success_count, error_count

    logger.info(f"SQL execution complete: {success_count} statements succeeded, {error_count} failed")
    return success_count, error_count


async def ensure_critical_tables(conn):
    """Ensure critical tables that might be missing are created."""
    # Check if query_cache table exists
    query_cache_exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'eligibility' 
            AND table_name = 'query_cache'
        )
    """)

    if not query_cache_exists:
        logger.info("Creating missing query_cache table...")
        try:
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
                    CONSTRAINT unique_natural_query UNIQUE (natural_query)
                );

                CREATE INDEX IF NOT EXISTS idx_query_cache_natural ON eligibility.query_cache (natural_query);
                CREATE INDEX IF NOT EXISTS idx_query_cache_last_used ON eligibility.query_cache (last_used);
            """)

            # Try to add vector column if extension exists
            try:
                vector_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_extension WHERE extname = 'vector'
                    )
                """)

                if vector_exists:
                    await conn.execute("""
                        ALTER TABLE eligibility.query_cache ADD COLUMN query_embedding VECTOR(1536);

                        CREATE INDEX IF NOT EXISTS idx_query_cache_embedding 
                        ON eligibility.query_cache USING ivfflat (query_embedding vector_cosine_ops) 
                        WITH (lists = 100);
                    """)
                    logger.info("Added vector column and index to query_cache table")
                else:
                    logger.warning("Vector extension not available - skipping vector column creation")
            except Exception as e:
                logger.warning(f"Could not add vector column: {e}")

            logger.info("query_cache table created successfully")
        except Exception as e:
            logger.error(f"Failed to create query_cache table: {e}")

    # Check if query_id_mappings table exists
    mappings_exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'eligibility' 
            AND table_name = 'query_id_mappings'
        )
    """)

    if not mappings_exists:
        logger.info("Creating missing query_id_mappings table...")
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS eligibility.query_id_mappings (
                    new_query_id TEXT PRIMARY KEY,
                    original_query_id TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_query_id_mappings_original_id 
                ON eligibility.query_id_mappings (original_query_id);
            """)
            logger.info("query_id_mappings table created successfully")
        except Exception as e:
            logger.error(f"Failed to create query_id_mappings table: {e}")


async def check_database_structure(conn):
    """Check the current structure of the database and log details."""
    # Check schemas
    schemas = await conn.fetch("SELECT schema_name FROM information_schema.schemata")
    logger.info(f"Found schemas: {', '.join(row['schema_name'] for row in schemas)}")

    # Check tables in eligibility schema
    tables = await conn.fetch("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'eligibility'
    """)

    if tables:
        logger.info(f"Found eligibility tables: {', '.join(row['table_name'] for row in tables)}")
    else:
        logger.warning("No tables found in eligibility schema")

    # Check extensions
    extensions = await conn.fetch("SELECT extname FROM pg_extension")
    logger.info(f"Installed extensions: {', '.join(row['extname'] for row in extensions)}")


async def init_db():
    """Initialize the database with schema and sample data."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        return False

    try:
        # Connect to the database
        logger.info(f"Connecting to database: {database_url}")
        conn = await asyncpg.connect(database_url)

        # First check the database structure
        await check_database_structure(conn)

        # Check if eligibility schema exists
        schema_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = 'eligibility')"
        )

        if not schema_exists:
            logger.info("Creating schema and tables from scratch...")

            # Create vector extension first (outside transaction)
            try:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                logger.info("Vector extension created")
            except Exception as e:
                logger.warning(f"Could not create vector extension: {e}")

            # Create pg_trgm extension
            try:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
                logger.info("pg_trgm extension created")
            except Exception as e:
                logger.warning(f"Could not create pg_trgm extension: {e}")

            # Read and execute schema.sql
            schema_sql = await read_sql_file('db/schema.sql')
            if schema_sql:
                success_count, error_count = await execute_sql_with_error_handling(
                    conn, schema_sql, continue_on_error=True
                )
                if error_count == 0:
                    logger.info("Schema created successfully")
                else:
                    logger.warning(f"Schema created with {error_count} errors")
            else:
                logger.error("Failed to read schema file")
                return False

            # Read and execute sample_data.sql if needed
            if os.path.exists('db/sample_data.sql'):
                sample_data_sql = await read_sql_file('db/sample_data.sql')
                if sample_data_sql:
                    logger.info("Applying sample data...")
                    success_count, error_count = await execute_sql_with_error_handling(
                        conn, sample_data_sql, continue_on_error=True
                    )
                    if error_count == 0:
                        logger.info("Sample data loaded successfully")
                    else:
                        logger.warning(f"Sample data loaded with {error_count} errors")
        else:
            logger.info("Eligibility schema already exists - verifying critical tables")

            # Ensure critical tables exist
            await ensure_critical_tables(conn)

        # Final structure verification
        logger.info("Verifying final database structure...")
        await check_database_structure(conn)

        await conn.close()
        logger.info("Database initialization completed")
        return True

    except Exception as e:
        logger.error(f"Database initialization error: {str(e)}")
        return False


if __name__ == "__main__":
    success = asyncio.run(init_db())
    if not success:
        logger.error("Database initialization failed")
        exit(1)
    else:
        logger.info("Database initialization completed successfully")