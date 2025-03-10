"""Database connection and session management."""

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from app.config import settings

# Create synchronous engine and session for DB operations
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create async engine and session for async operations
# Convert DATABASE_URL from postgresql:// to postgresql+asyncpg://
async_database_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
async_engine = create_async_engine(
    async_database_url,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
)
AsyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_engine,
    class_=AsyncSession
)

# Base class for SQLAlchemy models
Base = declarative_base()


@contextmanager
def get_db():
    """Provide a transactional scope around a series of operations."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db():
    """Get async DB session."""
    async with AsyncSessionLocal() as session:
        yield session


def test_connection():
    """Test the database connection."""
    with get_db() as db:
        result = db.execute(text("SELECT 1")).scalar()
        return result == 1


async def get_table_names(schema=settings.DEFAULT_SCHEMA):
    """Get all table names in the specified schema."""
    async with AsyncSessionLocal() as session:
        query = text(
            f"""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = :schema
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        )
        result = await session.execute(query, {"schema": schema})
        return [row[0] for row in result.fetchall()]


async def get_column_info(table_name, schema=settings.DEFAULT_SCHEMA):
    """Get column information for a table."""
    async with AsyncSessionLocal() as session:
        query = text(
            f"""
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
        result = await session.execute(
            query, {"schema": schema, "table_name": table_name}
        )
        columns = []
        for row in result.fetchall():
            columns.append({
                "name": row[0],
                "type": row[1],
                "nullable": row[2] == "YES",
                "default": row[3],
            })
        return columns


async def get_table_schema_info(schema=settings.DEFAULT_SCHEMA):
    """
    Get comprehensive schema information including tables, columns,
    and relationships.
    """
    # Import here to avoid circular imports
    from app.utils.schema_loader import get_full_schema_details

    # Get full schema details
    return await get_full_schema_details(schema)


async def get_schema_metadata():
    """Get metadata from the schema_metadata table if it exists."""
    try:
        async with AsyncSessionLocal() as session:
            query = text(
                """
                SELECT 
                    table_name, 
                    column_name, 
                    description, 
                    example_value
                FROM 
                    eligibility.schema_metadata
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
    except Exception:
        # Table might not exist yet
        return {}