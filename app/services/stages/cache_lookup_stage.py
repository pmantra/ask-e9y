import logging
import sqlalchemy as sa

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
        include_cached_explanation = context.metadata.get("include_cached_explanation", False)

        # Always fetch explanation for cache hits if either flag is true
        fetch_explanation = include_explanation or include_cached_explanation

        # Look up in cache
        cache_result = await self.cache_service.lookup_query(
            query, db_session, fetch_explanation
        )

        # Update context with results
        context.metadata["cache_status"] = cache_result["cache_status"]
        if cache_result["cache_hit"]:
            context.sql = cache_result["sql"]

            # Store explanations and embeddings as before
            if cache_result.get("explanation"):
                context.metadata["explanation"] = cache_result["explanation"]
                if include_cached_explanation:
                    context.results_explanation = cache_result["explanation"]

            context.metadata["embedding"] = cache_result["embedding"]

            # If this is a cache hit, store the mapping between new and original query IDs
            if "original_query_id" in cache_result and cache_result["original_query_id"]:
                original_id = cache_result["original_query_id"]
                context.metadata["original_query_id"] = original_id

                # Store the mapping in database
                await self._store_query_id_mapping(str(context.query_id), original_id, db_session)

        context.complete_stage("cache_lookup", cache_result)
        return cache_result

    async def _store_query_id_mapping(self, new_id: str, original_id: str, db_session):
        """Store a mapping between a new query ID and its original source ID."""
        try:
            query = sa.text("""
                INSERT INTO eligibility.query_id_mappings (new_query_id, original_query_id)
                VALUES (:new_id, :original_id)
                ON CONFLICT (new_query_id) DO UPDATE
                SET original_query_id = :original_id
            """)

            await db_session.execute(query, {
                "new_id": new_id,
                "original_id": original_id
            })
            await db_session.commit()
            logger.debug(f"Stored query ID mapping: {new_id} -> {original_id}")
        except Exception as e:
            logger.warning(f"Failed to store query ID mapping: {str(e)}")