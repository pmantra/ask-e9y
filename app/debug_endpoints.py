"""Debug endpoints for API troubleshooting."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_async_db, test_connection, engine, async_engine

router = APIRouter(
    prefix="/debug",
    tags=["Debug"]
)


@router.get("/database")
async def debug_database(db: AsyncSession = Depends(get_async_db)):
    """Debug database connection issues."""

    # Information about configuration
    config_info = {
        "database_url": settings.DATABASE_URL,
        "async_database_url": settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        "sync_engine_url": str(engine.url),
        "async_engine_url": str(async_engine.url),
    }

    # Test synchronous connection
    sync_connection_result = None
    sync_current_user = None
    try:
        sync_connection_result = test_connection()
        from sqlalchemy.orm import Session
        with engine.connect() as connection:
            sync_current_user = connection.execute(text("SELECT current_user")).scalar()
    except Exception as e:
        sync_connection_result = f"Error: {str(e)}"

    # Test async connection
    async_connection_result = None
    async_current_user = None
    eligibility_schema_exists = False
    tables = []

    try:
        result = await db.execute(text("SELECT 1"))
        async_connection_result = result.scalar()

        result = await db.execute(text("SELECT current_user"))
        async_current_user = result.scalar()

        # Test schema access
        result = await db.execute(text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name = 'eligibility'"
        ))
        eligibility_schema_exists = result.scalar() is not None

        # Test table access
        if eligibility_schema_exists:
            result = await db.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'eligibility'"
            ))
            tables = [row[0] for row in result.fetchall()]
    except Exception as e:
        async_connection_result = f"Error: {str(e)}"

    return {
        "config": config_info,
        "sync_connection": {
            "result": sync_connection_result,
            "current_user": sync_current_user
        },
        "async_connection": {
            "result": async_connection_result,
            "current_user": async_current_user,
            "eligibility_schema_exists": eligibility_schema_exists,
            "tables": tables
        }
    }


@router.get("/types")
async def debug_types(db: AsyncSession = Depends(get_async_db)):
    """Debug serialization issues by returning examples of all data types."""

    try:
        # Get range types which can cause serialization issues
        sample_data = {}

        # Try to get a member with a daterange
        if await schema_has_table(db, 'eligibility', 'member'):
            result = await db.execute(text("SELECT * FROM eligibility.member LIMIT 1"))
            member = result.mappings().first()
            if member:
                sample_data["member"] = dict(member)

                # Specifically check the effective_range field
                if 'effective_range' in member and member['effective_range'] is not None:
                    range_type = type(member['effective_range']).__name__
                    range_module = type(member['effective_range']).__module__
                    sample_data["effective_range_type"] = f"{range_module}.{range_type}"

                    # Inspect the range properties
                    if hasattr(member['effective_range'], 'lower'):
                        sample_data["range_lower"] = {
                            "value": member['effective_range'].lower,
                            "type": type(member['effective_range'].lower).__name__
                        }

                    if hasattr(member['effective_range'], 'upper'):
                        sample_data["range_upper"] = {
                            "value": member['effective_range'].upper,
                            "type": type(member['effective_range'].upper).__name__
                        }

        return {
            "sample_data": sample_data,
            "serialization_test": "success"
        }
    except Exception as e:
        return {
            "error": str(e),
            "error_type": type(e).__name__,
            "serialization_test": "failed"
        }


async def schema_has_table(db: AsyncSession, schema_name: str, table_name: str) -> bool:
    """Check if a table exists in the schema."""
    query = text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = :schema AND table_name = :table)"
    )
    result = await db.execute(query, {"schema": schema_name, "table": table_name})
    return result.scalar()