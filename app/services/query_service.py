"""Service for processing natural language queries and executing SQL."""
from __future__ import annotations

import logging
import time
import uuid
from typing import Dict, Any, Tuple, List, re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_table_schema_info
from app.models.requests import QueryRequest
from app.models.responses import QueryResponse, QueryDetails, ErrorResponse, ErrorDetail
from app.services.chroma_service import ChromaService
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.openai_llm import OpenAILLMService
from app.utils.db_utils import sanitize_for_json

logger = logging.getLogger(__name__)


class QueryService:
    """Service for processing natural language queries and executing SQL."""

    def __init__(self):
        """Initialize the query service."""
        self._llm_service = self._get_llm_service()
        self._schema_cache = {}
        self._schema_cache_timestamp = 0
        self._embedding_service = EmbeddingService()
        self._chroma_service = ChromaService(persist_directory="./chroma_db")

    def _get_llm_service(self) -> LLMService:
        """Get the appropriate LLM service based on configuration."""
        if settings.LLM_PROVIDER == "openai":
            return OpenAILLMService()
        # Add more LLM providers here as they are implemented
        else:
            logger.warning(f"Unknown LLM provider: {settings.LLM_PROVIDER}, falling back to OpenAI")
            return OpenAILLMService()

    async def process_query(
        self,
        request: QueryRequest,
        db: AsyncSession
    ) -> Tuple[QueryResponse, None] | Tuple[None, ErrorResponse]:
        """
        Process a natural language query and return the results.

        Args:
            request: The query request
            db: Database session

        Returns:
            Either a successful QueryResponse or an ErrorResponse
        """
        try:
            # Initialize timing metrics
            timing_stats = {
                "start_time": time.time(),
                "cache_lookup_time": 0,
                "embedding_time": 0,
                "schema_info_time": 0,
                "translation_time": 0,
                "validation_time": 0,
                "execution_time": 0,
                "explanation_time": 0,
                "total_time": 0,
                "cache_status": "miss"  # Default status
            }

            # Normalize the query
            normalized_query = self._embedding_service.normalize_query(request.query)
            sql = None
            explanation = None
            query_id = uuid.uuid4()

            # Check if explanation is requested
            include_explanation = request.include_explanation

            # Check for cache hits - start with traditional DB
            cache_lookup_start = time.time()
            try:
                # Try PostgreSQL cache first (for exact matches)
                exact_query = text("""
                    SELECT generated_sql, explanation 
                    FROM eligibility.query_cache
                    WHERE natural_query = :query
                """)

                try:
                    result = await db.execute(exact_query, {"query": normalized_query})
                    cache_hit = result.mappings().first()

                    if cache_hit:
                        sql = cache_hit["generated_sql"]
                        if include_explanation:
                            explanation = cache_hit["explanation"]
                        timing_stats["cache_status"] = "db_exact_hit"

                        # Update usage stats
                        try:
                            await db.execute(
                                text("""
                                    UPDATE eligibility.query_cache
                                    SET execution_count = execution_count + 1,
                                        last_used = CURRENT_TIMESTAMP
                                    WHERE natural_query = :query
                                """),
                                {"query": normalized_query}
                            )
                            await db.commit()
                        except Exception as e:
                            logger.warning(f"Failed to update cache usage: {str(e)}")
                except Exception as e:
                    # Table might not exist yet
                    logger.warning(f"PostgreSQL cache lookup error: {str(e)}")

                # If no exact match, try vector similarity with Chroma
                if not sql:
                    # Generate embedding
                    embedding_start = time.time()
                    embedding = await self._embedding_service.get_embedding(request.query)
                    timing_stats["embedding_time"] = time.time() - embedding_start

                    if embedding:
                        # Query Chroma for similar vectors
                        similar_query = await self._chroma_service.find_similar_query(embedding)

                        if similar_query:
                            sql = similar_query["generated_sql"]
                            if include_explanation:
                                explanation = similar_query["explanation"]
                            timing_stats["cache_status"] = "vector_hit"

                            # Update usage statistics in Chroma
                            await self._chroma_service.update_usage(normalized_query)
            except Exception as e:
                logger.error(f"Error during cache lookup: {str(e)}")

            timing_stats["cache_lookup_time"] = time.time() - cache_lookup_start

            # If no cache hit, generate SQL with LLM
            if not sql:
                # Get schema information
                schema_start = time.time()
                schema_info = await self._get_schema_info()
                timing_stats["schema_info_time"] = time.time() - schema_start

                # Generate SQL from natural language
                translation_start = time.time()
                sql, brief_explanation = await self._llm_service.translate_to_sql(
                    request.query,
                    schema_info,
                    request.conversation_id
                )
                timing_stats["translation_time"] = time.time() - translation_start
                logger.info(f"Generated SQL: {sql}")

                # Validate the SQL
                validation_start = time.time()
                is_valid, errors = await self._llm_service.validate_sql(sql, schema_info)
                timing_stats["validation_time"] = time.time() - validation_start

                if not is_valid:
                    error_details = [
                        ErrorDetail(
                            code=error.get("code", "VALIDATION_ERROR"),
                            message=error.get("message", "Unknown validation error"),
                            location=error.get("location"),
                            suggestion=error.get("suggestion")
                        )
                        for error in errors
                    ]

                    # Calculate total time
                    timing_stats["total_time"] = time.time() - timing_stats["start_time"]

                    return None, ErrorResponse(
                        error="SQL validation failed",
                        details=error_details,
                        query_id=query_id
                    )

            # Execute the SQL
            execution_start = time.time()
            try:
                # Execute query against database
                result = await db.execute(text(sql))
                rows = result.mappings().all()
                results = [sanitize_for_json(dict(row)) for row in rows]
                timing_stats["execution_time"] = time.time() - execution_start

            except Exception as e:
                logger.error(f"SQL execution error: {str(e)}")

                # For failures from cache, try regenerating
                if timing_stats["cache_status"] != "miss":
                    logger.warning("Cached SQL execution failed, trying fresh generation")
                    # Create a copy with skip_cache flag
                    fresh_request = QueryRequest(**request.dict())
                    fresh_request.parameters = fresh_request.parameters or {}
                    fresh_request.parameters["skip_cache"] = True
                    return await self.process_query(fresh_request, db)

                # Handle error for fresh generation
                schema_info = await self._get_schema_info()
                error_help = await self._llm_service.handle_error(request.query, str(e), schema_info)

                # Calculate total time
                timing_stats["total_time"] = time.time() - timing_stats["start_time"]

                return None, ErrorResponse(
                    error="SQL execution failed",
                    details=[
                        ErrorDetail(
                            code=error_help.get("code", "EXECUTION_ERROR"),
                            message=error_help.get("message", str(e)),
                            location=None,
                            suggestion=error_help.get("suggestion", "Please try a different query")
                        )
                    ],
                    query_id=query_id
                )

            # Check if results are empty
            has_results = len(results) > 0

            # For empty results, provide a simple message without LLM call
            if not has_results:
                results_explanation = "Your query did not return any results. This might be because no data matches your search criteria."
            elif include_explanation and timing_stats["cache_status"] == "miss":
                # Generate explanation for new results only if requested
                explanation_start = time.time()
                results_explanation = await self._llm_service.explain_results(
                    request.query,
                    sql,
                    results
                )
                timing_stats["explanation_time"] = time.time() - explanation_start
            elif include_explanation and explanation:
                # Use cached explanation if available and requested
                results_explanation = explanation
            else:
                # Skip explanation if not requested
                results_explanation = "Results found. Request an explanation to learn more about this data."

            # Store query context for later explanation requests
            # Store in caches for future use
            embedding = await self._embedding_service.get_embedding(request.query)
            if embedding:
                # Store in Chroma - still store explanation if we have it
                await self._chroma_service.store_query(
                    normalized_query,
                    embedding,
                    sql,
                    explanation or results_explanation if include_explanation else None,
                    timing_stats["execution_time"] * 1000,
                    query_id=str(query_id)  # Store query_id for later retrieval
                )

                # Try storing in PostgreSQL too (if available)
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

                    await db.execute(
                        store_query,
                        {
                            "query": normalized_query,
                            "sql": sql,
                            "explanation": explanation or results_explanation if include_explanation else None,
                            "time": timing_stats["execution_time"] * 1000,
                            "query_id": str(query_id)
                        }
                    )
                    await db.commit()
                except Exception as e:
                    logger.warning(f"Failed to store in PostgreSQL: {str(e)}")

            # Calculate total time
            timing_stats["total_time"] = time.time() - timing_stats["start_time"]

            # Create the response
            query_details = QueryDetails(
                generated_sql=sql,
                execution_time_ms=timing_stats["execution_time"] * 1000,  # Convert to ms
                row_count=len(results)
            )

            if not request.include_sql:
                query_details = None

            # Convert timing stats to milliseconds for response
            response_timing_stats = {}
            for k, v in timing_stats.items():
                if k == "cache_status" or k == "start_time":
                    response_timing_stats[k] = v
                else:
                    response_timing_stats[k] = round(v * 1000, 2)  # Convert to ms

            response = QueryResponse(
                query_id=query_id,
                results=results[:request.max_results],
                query_details=query_details,
                conversation_id=request.conversation_id,
                message=results_explanation,
                timing_stats=response_timing_stats,
                has_results=has_results  # Add the new flag
            )

            return response, None

        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            return None, ErrorResponse(
                error="Query processing failed",
                details=[
                    ErrorDetail(
                        code="PROCESSING_ERROR",
                        message=str(e),
                        location=None,
                        suggestion="Please try again with a different query"
                    )
                ],
                query_id=uuid.uuid4()
            )

    async def _get_schema_info(self) -> Dict[str, Any]:
        """
        Get schema information, with caching.

        Returns:
            Dictionary with schema information
        """
        current_time = time.time()
        # Cache expires after 5 minutes
        if not self._schema_cache or (current_time - self._schema_cache_timestamp) > 300:
            self._schema_cache = await get_table_schema_info(settings.DEFAULT_SCHEMA)
            self._schema_cache_timestamp = current_time

        return self._schema_cache

    async def get_explanation(
            self,
            query_id: uuid.UUID,
            db: AsyncSession
    ) -> str:
        """
        Get explanation for a previously executed query.

        Args:
            query_id: The ID of the query to explain
            db: Database session

        Returns:
            The explanation as a string
        """
        try:
            # First try to get from PostgreSQL cache
            query = text("""
                SELECT 
                    natural_query, 
                    generated_sql, 
                    explanation
                FROM 
                    eligibility.query_cache
                WHERE 
                    query_id = :query_id
            """)

            result = await db.execute(query, {"query_id": str(query_id)})
            cache_hit = result.mappings().first()

            if cache_hit and cache_hit["explanation"]:
                # Explanation already exists
                return cache_hit["explanation"]

            elif cache_hit:
                # We have the query but no explanation - generate one
                natural_query = cache_hit["natural_query"]
                sql = cache_hit["generated_sql"]

                # Execute the query to get results
                result = await db.execute(text(sql))
                rows = result.mappings().all()
                results = [sanitize_for_json(dict(row)) for row in rows]

                # Get schema information for context
                schema_info = await self._get_schema_info()

                # Generate a more educational explanation
                explanation = await self._generate_educational_explanation(
                    natural_query,
                    sql,
                    results,
                    schema_info
                )

                # Store the explanation for future use
                try:
                    update_query = text("""
                        UPDATE eligibility.query_cache
                        SET explanation = :explanation
                        WHERE query_id = :query_id
                    """)

                    await db.execute(
                        update_query,
                        {
                            "explanation": explanation,
                            "query_id": str(query_id)
                        }
                    )
                    await db.commit()
                except Exception as e:
                    logger.warning(f"Failed to store explanation: {str(e)}")

                return explanation

            # Try Chroma if not in PostgreSQL
            try:
                query_data = await self._chroma_service.get_query_by_id(str(query_id))

                if query_data and query_data.get("explanation"):
                    return query_data["explanation"]

                elif query_data:
                    # We have query data but no explanation - generate one
                    natural_query = query_data["natural_query"]
                    sql = query_data["generated_sql"]

                    # Execute the query to get results
                    result = await db.execute(text(sql))
                    rows = result.mappings().all()
                    results = [sanitize_for_json(dict(row)) for row in rows]

                    # Get schema information for context
                    schema_info = await self._get_schema_info()

                    # Generate a more educational explanation
                    explanation = await self._generate_educational_explanation(
                        natural_query,
                        sql,
                        results,
                        schema_info
                    )

                    # Store the explanation in Chroma
                    await self._chroma_service.update_explanation(str(query_id), explanation)

                    return explanation
            except Exception as e:
                logger.warning(f"Failed to get query from Chroma: {str(e)}")

            # If we reach here, we couldn't find the query
            return "Could not generate explanation. The query may have expired or been removed."

        except Exception as e:
            logger.error(f"Error generating explanation: {str(e)}")
            return "An error occurred while generating the explanation."

    async def _generate_educational_explanation(
            self,
            query: str,
            sql: str,
            results: List[Dict[str, Any]],
            schema_info: Dict[str, Any]
    ) -> str:
        """
        Generate an educational explanation of the query results.

        Args:
            query: Original natural language query
            sql: Generated SQL
            results: Query results
            schema_info: Database schema information

        Returns:
            Educational explanation
        """
        # Extract tables used in the query
        tables_used = self._extract_tables_from_sql(sql)

        # Check for business rules
        business_rules = []
        if "effective_range @> CURRENT_DATE" in sql:
            business_rules.append("active member status")
        if "COUNT(DISTINCT organization_id) > 1" in sql or "COUNT(DISTINCT m.organization_id) > 1" in sql:
            business_rules.append("overeligibility")

        if not results:
            # For empty results, provide a more helpful explanation
            return (
                "Your query did not return any results. This means no data matches your search criteria. "
                f"The query looked for data in the following tables: {', '.join(tables_used)}. "
                f"{'The query also applied business rules for: ' + ', '.join(business_rules) + '.' if business_rules else ''} "
                "You might want to try broadening your search criteria or check if you're using the correct names and identifiers."
            )

        # For non-empty results, use the LLM to generate a rich explanation
        return await self._llm_service.explain_results(
            query,
            sql,
            results,
            tables_used=tables_used,
            business_rules=business_rules,
            schema_info=schema_info
        )

    def _extract_tables_from_sql(self, sql: str) -> List[str]:
        """Extract table names from SQL query."""
        # Simple regex-based extraction
        # This is a simplified approach - a proper SQL parser would be more robust
        from_pattern = r'FROM\s+([a-zA-Z0-9_.]+)'
        join_pattern = r'JOIN\s+([a-zA-Z0-9_.]+)'

        tables = []

        # Find tables in FROM clauses
        from_matches = re.finditer(from_pattern, sql, re.IGNORECASE)
        for match in from_matches:
            tables.append(match.group(1).strip())

        # Find tables in JOIN clauses
        join_matches = re.finditer(join_pattern, sql, re.IGNORECASE)
        for match in join_matches:
            tables.append(match.group(1).strip())

        return list(set(tables))  # Remove duplicates


# Create a singleton instance of the query service
query_service = QueryService()