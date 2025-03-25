import asyncio
import logging
from app.database import get_async_db
from app.services.schema_service import SchemaService
from app.services.orchestration.factory import create_query_orchestrator

logger = logging.getLogger(__name__)


async def initialize_schema_embeddings():
    """Initialize schema embeddings on application startup."""
    logger.info("Initializing schema embeddings...")

    # Get services from orchestrator
    orchestrator = create_query_orchestrator()
    schema_service = orchestrator.sql_generation_stage.schema_service
    schema_embedding_service = orchestrator.sql_generation_stage.schema_embedding_service

    if not schema_embedding_service:
        logger.warning("Schema embedding service not configured, skipping initialization")
        return False

    # Get database session
    async for db in get_async_db():
        try:
            # Get full schema
            schema_info = await schema_service.get_schema_info()

            # Build embeddings
            result = await schema_embedding_service.build_schema_embeddings(schema_info)

            logger.info(f"Schema embeddings initialized: {result['tables_processed']} tables processed")
            return result["storage_success"]
        except Exception as e:
            logger.error(f"Error initializing schema embeddings: {str(e)}")
            return False
        finally:
            await db.close()

    return False