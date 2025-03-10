"""Service for processing natural language queries and executing SQL."""

import logging
import time
import uuid
from typing import Dict, Any, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_table_schema_info
from app.models.requests import QueryRequest
from app.models.responses import QueryResponse, QueryDetails, ErrorResponse, ErrorDetail
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
                "schema_info_time": 0,
                "translation_time": 0,
                "validation_time": 0,
                "execution_time": 0,
                "explanation_time": 0,
                "total_time": 0
            }

            # Get schema information (caching for 5 minutes)
            schema_start = time.time()
            schema_info = await self._get_schema_info()
            timing_stats["schema_info_time"] = time.time() - schema_start

            # Generate SQL from natural language
            translation_start = time.time()
            sql, explanation = await self._llm_service.translate_to_sql(
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
                logger.info(f"Query timing stats (error): {timing_stats}")

                return None, ErrorResponse(
                    error="SQL validation failed",
                    details=error_details,
                    query_id=uuid.uuid4()
                )

            # Execute the SQL
            execution_start = time.time()
            try:
                result = await db.execute(text(sql))
                # Convert results to dict for JSON serialization and sanitize all values
                rows = result.mappings().all()
                results = [sanitize_for_json(dict(row)) for row in rows]
                timing_stats["execution_time"] = time.time() - execution_start

            except Exception as e:
                logger.error(f"SQL execution error: {str(e)}")
                error_help = await self._llm_service.handle_error(request.query, str(e), schema_info)

                # Calculate total time
                timing_stats["total_time"] = time.time() - timing_stats["start_time"]
                logger.info(f"Query timing stats (execution error): {timing_stats}")

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
                    query_id=uuid.uuid4()
                )

            # Generate explanation for the results
            explanation_start = time.time()
            results_explanation = await self._llm_service.explain_results(
                request.query,
                sql,
                results
            )
            timing_stats["explanation_time"] = time.time() - explanation_start

            # Calculate total time
            timing_stats["total_time"] = time.time() - timing_stats["start_time"]

            # Create the response
            query_id = uuid.uuid4()
            query_details = QueryDetails(
                generated_sql=sql,
                execution_time_ms=timing_stats["execution_time"] * 1000,  # Convert to ms
                row_count=len(results)
            )

            if not request.include_sql:
                query_details = None

            response = QueryResponse(
                query_id=query_id,
                results=results[:request.max_results],
                query_details=query_details,
                conversation_id=request.conversation_id,
                message=results_explanation,
                timing_stats={k: round(v * 1000, 2) for k, v in timing_stats.items() if k != "start_time"}
                # Convert to ms
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


# Create a singleton instance of the query service
query_service = QueryService()