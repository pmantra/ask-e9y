from http.client import HTTPException

from app.database import get_async_db
from app.services.orchestration.factory import create_query_orchestrator
from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter(
    prefix="/api",
    tags=["Query"]
)

@router.get("/embeddings/status", tags=["Schema"])
async def schema_embeddings_status(
        refresh: bool = False,
        db: AsyncSession = Depends(get_async_db)
):
    """Check status of schema embeddings."""
    orchestrator = create_query_orchestrator()
    schema_embedding_service = orchestrator.sql_generation_stage.schema_embedding_service

    if not schema_embedding_service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schema embedding service not configured"
        )

    # Force refresh if requested
    if refresh:
        # Get schema info
        schema_service = orchestrator.sql_generation_stage.schema_service
        schema_info = await schema_service.get_schema_info()

        # Rebuild embeddings
        result = await schema_embedding_service.build_schema_embeddings(schema_info)

        return {
            "status": "refreshed",
            "tables_processed": result["tables_processed"],
            "success": result["storage_success"]
        }

    # Otherwise just check status
    embeddings_loaded = await schema_embedding_service.load_all_embeddings()

    if embeddings_loaded:
        return {
            "status": "active",
            "tables_count": len(schema_embedding_service._embedding_cache),
            "last_refresh": schema_embedding_service._last_refresh
        }
    else:
        return {
            "status": "not_initialized",
            "message": "Schema embeddings not found or failed to load"
        }