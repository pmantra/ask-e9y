import logging

logger = logging.getLogger(__name__)


class CacheLookupStage:
    """Stage for looking up queries in cache."""

    def __init__(self, cache_service):
        self.cache_service = cache_service

    async def execute(self, context, db_session):
        """Execute the cache lookup stage."""
        context.start_stage("cache_lookup")

        # Extract from context
        query = context.original_query
        include_explanation = context.metadata.get("include_explanation", False)

        # Look up in cache
        cache_result = await self.cache_service.lookup_query(
            query, db_session, include_explanation
        )

        # Update context with results
        context.metadata["cache_status"] = cache_result["cache_status"]
        if cache_result["cache_hit"]:
            context.sql = cache_result["sql"]
            context.metadata["explanation"] = cache_result["explanation"]
            context.metadata["embedding"] = cache_result["embedding"]

        context.complete_stage("cache_lookup", cache_result)
        return cache_result