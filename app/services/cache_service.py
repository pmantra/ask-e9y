import logging
import time
from typing import Dict, Any, Optional
from sqlalchemy import text

logger = logging.getLogger(__name__)


class CacheService:
    """Service for handling query caching."""

    def __init__(self, embedding_service, chroma_service):
        self.embedding_service = embedding_service
        self.chroma_service = chroma_service

    async def lookup_query(self, query: str, db_session, include_explanation=False):
        """Look up a query in cache."""
        normalized_query = self.embedding_service.normalize_query(query)

        # Track timing
        start_time = time.time()
        result = {
            "cache_hit": False,
            "sql": None,
            "explanation": None,
            "cache_status": "miss",
            "timing_ms": 0,
            "embedding": None
        }

        try:
            # Try PostgreSQL cache first (exact match)
            db_result = await self._lookup_in_postgres(normalized_query, db_session, include_explanation)

            if db_result["sql"]:
                result.update(db_result)
                result["cache_hit"] = True
            else:
                # Try vector similarity with Chroma
                embedding = await self.embedding_service.get_embedding(query)
                result["embedding"] = embedding  # Store for later use if needed

                if embedding:
                    similar_query = await self.chroma_service.find_similar_query(embedding)

                    if similar_query:
                        result["sql"] = similar_query["generated_sql"]
                        if include_explanation:
                            result["explanation"] = similar_query["explanation"]
                        result["cache_status"] = "vector_hit"
                        result["cache_hit"] = True

                        # Update usage in Chroma
                        await self.chroma_service.update_usage(normalized_query)
        except Exception as e:
            logger.error(f"Error during cache lookup: {str(e)}")

        result["timing_ms"] = (time.time() - start_time) * 1000
        return result

    async def _lookup_in_postgres(self, normalized_query: str, db_session, include_explanation: bool):
        """Look up a query in PostgreSQL cache."""
        result = {
            "sql": None,
            "explanation": None,
            "cache_status": "miss"
        }

        try:
            exact_query = text("""
                SELECT generated_sql, explanation 
                FROM eligibility.query_cache
                WHERE natural_query = :query
            """)

            db_result = await db_session.execute(exact_query, {"query": normalized_query})
            cache_hit = db_result.mappings().first()

            if cache_hit:
                logger.info(f"Cache hit! Query: '{normalized_query[:50]}...'")
                result["sql"] = cache_hit["generated_sql"]
                if include_explanation:
                    result["explanation"] = cache_hit["explanation"]
                result["cache_status"] = "db_exact_hit"

                # Update usage stats
                try:
                    await db_session.execute(
                        text("""
                            UPDATE eligibility.query_cache
                            SET execution_count = execution_count + 1,
                                last_used = CURRENT_TIMESTAMP
                            WHERE natural_query = :query
                        """),
                        {"query": normalized_query}
                    )
                    await db_session.commit()
                except Exception as e:
                    logger.warning(f"Failed to update cache usage: {str(e)}")
        except Exception as e:
            logger.warning(f"PostgreSQL cache lookup error: {str(e)}")

        return result

    async def store_query(self, query, embedding, sql, explanation, execution_time_ms, query_id, db_session):
        """Store a query in cache."""
        normalized_query = self.embedding_service.normalize_query(query)
        success = True

        # Store in Chroma
        try:
            await self.chroma_service.store_query(
                normalized_query, embedding, sql, explanation,
                execution_time_ms, query_id=str(query_id)
            )
            logger.debug(f"Stored query in Chroma: '{normalized_query[:50]}...'")
        except Exception as e:
            logger.warning(f"Failed to store in Chroma: {str(e)}")
            success = False

        # Store in PostgreSQL
        try:
            store_query = text("""
                INSERT INTO eligibility.query_cache 
                    (natural_query, generated_sql, explanation, execution_time_ms, query_id)
                VALUES (:query, :sql, :explanation, :time, :query_id)
                ON CONFLICT (natural_query) DO UPDATE
                SET generated_sql = :sql,
                    explanation = :explanation,
                    execution_time_ms = :time,
                    query_id = :query_id,
                    execution_count = eligibility.query_cache.execution_count + 1,
                    last_used = CURRENT_TIMESTAMP
            """)

            params = {
                "query": normalized_query,
                "sql": sql,
                "explanation": explanation,
                "time": execution_time_ms,
                "query_id": str(query_id)
            }

            await db_session.execute(store_query, params)
            await db_session.commit()
            logger.info(f"Successfully stored query in PostgreSQL cache")
        except Exception as e:
            logger.warning(f"Failed to store in PostgreSQL: {str(e)}")
            success = False

        return success