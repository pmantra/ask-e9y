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


async def execute_sql(conn, sql):
    """Execute SQL statements that might contain multiple commands."""
    try:
        await conn.execute(sql)
        return True
    except Exception as e:
        logger.error(f"Error executing SQL: {e}")
        return False


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
            if schema_sql and await execute_sql(conn, schema_sql):
                logger.info("Schema created successfully")
            else:
                logger.error("Failed to create schema")
                return False

            # Read and execute sample_data.sql if needed
            sample_data_sql = await read_sql_file('db/sample_data.sql')
            if sample_data_sql and await execute_sql(conn, sample_data_sql):
                logger.info("Sample data loaded successfully")
            else:
                logger.warning("Failed to load sample data")
        else:
            logger.info("Eligibility schema already exists")

            # Check for migrations in db/migrations directory
            migrations_dir = 'db/migrations'
            if os.path.exists(migrations_dir):
                for filename in sorted(os.listdir(migrations_dir)):
                    if filename.endswith('.sql'):
                        migration_path = os.path.join(migrations_dir, filename)
                        logger.info(f"Applying migration: {filename}")

                        migration_sql = await read_sql_file(migration_path)
                        if migration_sql and await execute_sql(conn, migration_sql):
                            logger.info(f"Migration {filename} applied successfully")
                        else:
                            logger.error(f"Failed to apply migration {filename}")

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