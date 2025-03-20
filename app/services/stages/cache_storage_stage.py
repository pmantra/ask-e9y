import logging

logger = logging.getLogger(__name__)


class CacheStorageStage:
    """Stage for storing queries in cache."""

    def __init__(self, cache_service, embedding_service):
        self.cache_service = cache_service
        self.embedding_service = embedding_service

    async def execute(self, context, db_session):
        """Execute the cache storage stage."""
        # Skip if we found this in cache
        if context.metadata.get("cache_status", "miss") != "miss":
            return {"stored": False, "skipped": True}

        context.start_stage("cache_storage")

        # Get or reuse embedding
        embedding = context.metadata.get("embedding")
        if not embedding:
            embedding = await self.embedding_service.get_embedding(context.original_query)

        # Only store if we have an embedding
        stored = False
        explanation = context.results_explanation

        if embedding:
            # Get explanation (if available)
            explanation = context.results_explanation
            # Check if explanation is the default placeholder
            if explanation == "Results found. Request an explanation to learn more about this data.":
                # Replace with None to indicate no real explanation exists
                explanation = None
            # Store in cache
            stored = await self.cache_service.store_query(
                context.original_query,
                embedding,
                context.sql,
                explanation,
                context.metadata.get("execution_time_ms", 0),
                context.query_id,
                db_session
            )

        context.complete_stage("cache_storage", {"stored": stored})
        return {"stored": stored}