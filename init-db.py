import os
import asyncio
import asyncpg
import logging

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


async def execute_sql(conn, sql, description="SQL"):
    """Execute SQL statements with better error handling."""
    try:
        await conn.execute(sql)
        logger.info(f"Successfully executed {description}")
        return True
    except Exception as e:
        logger.error(f"Error executing {description}: {e}")
        return False


async def ensure_critical_tables(conn):
    """Ensure critical tables exist, create them if missing."""
    # Check and create query_cache table if needed
    query_cache_exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'eligibility' 
            AND table_name = 'query_cache'
        )
    """)

    if not query_cache_exists:
        logger.info("Creating missing query_cache table...")
        await execute_sql(conn, """
            CREATE TABLE IF NOT EXISTS eligibility.query_cache (
                id SERIAL PRIMARY KEY,
                natural_query TEXT NOT NULL,
                query_embedding VECTOR(1536),
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
        """, "query_cache table creation")

        # Try to create vector extension and index
        try:
            await conn.execute("""
                CREATE EXTENSION IF NOT EXISTS vector;
                CREATE INDEX IF NOT EXISTS idx_query_cache_embedding ON eligibility.query_cache 
                USING ivfflat (query_embedding vector_cosine_ops) WITH (lists = 100);
            """)
            logger.info("Vector index created successfully")
        except Exception as e:
            logger.warning(f"Could not create vector index: {e}")

    # Check and create query_id_mappings table if needed
    mappings_exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'eligibility' 
            AND table_name = 'query_id_mappings'
        )
    """)

    if not mappings_exists:
        logger.info("Creating missing query_id_mappings table...")
        await execute_sql(conn, """
            CREATE TABLE IF NOT EXISTS eligibility.query_id_mappings (
                new_query_id TEXT PRIMARY KEY,
                original_query_id TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_query_id_mappings_original_id 
            ON eligibility.query_id_mappings (original_query_id);
        """, "query_id_mappings table creation")


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

        # Check if eligibility schema exists
        schema_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = 'eligibility')"
        )

        if not schema_exists:
            logger.info("Creating schema and tables...")

            # Read and execute schema.sql
            schema_sql = await read_sql_file('db/schema.sql')
            if schema_sql and await execute_sql(conn, schema_sql, "schema.sql"):
                logger.info("Schema created successfully")
            else:
                logger.error("Failed to create schema")
                return False

            # Read and execute sample_data.sql if needed
            sample_data_sql = await read_sql_file('db/sample_data.sql')
            if os.path.exists('db/sample_data.sql') and sample_data_sql:
                if await execute_sql(conn, sample_data_sql, "sample_data.sql"):
                    logger.info("Sample data loaded successfully")
                else:
                    logger.warning("Failed to load sample data")
        else:
            logger.info("Eligibility schema already exists - skipping full schema creation")

            # ✅ Important: We now ensure critical tables exist instead of reapplying migrations
            logger.info("Checking for critical tables...")
            await ensure_critical_tables(conn)

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