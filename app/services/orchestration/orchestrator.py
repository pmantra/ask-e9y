import logging
import time
import uuid
from typing import Tuple, Optional, Dict, Any, Union

from app.models.requests import QueryRequest
from app.models.responses import QueryResponse, QueryDetails, ErrorResponse, ErrorDetail
from app.services.orchestration.context import ProcessingContext

logger = logging.getLogger(__name__)


class QueryOrchestrator:
    """Orchestrates the processing of natural language queries."""

    def __init__(
            self,
            cache_lookup_stage,
            sql_generation_stage,
            sql_validation_stage,
            sql_execution_stage,
            explanation_stage,
            cache_storage_stage,
            explanation_service=None  # Optional service for explanation endpoint
    ):
        self.cache_lookup_stage = cache_lookup_stage
        self.sql_generation_stage = sql_generation_stage
        self.sql_validation_stage = sql_validation_stage
        self.sql_execution_stage = sql_execution_stage
        self.explanation_stage = explanation_stage
        self.cache_storage_stage = cache_storage_stage
        self.explanation_service = explanation_service  # Store for get_explanation method

    async def process_query(
            self,
            request: QueryRequest,
            db_session,
            request_id: str = None
    ) -> Union[QueryResponse, ErrorResponse]:
        """Process a natural language query through all stages."""
        # Initialize context
        context = ProcessingContext(
            query_id=uuid.uuid4(),
            conversation_id=request.conversation_id or uuid.uuid4(),
            original_query=request.query,
            enhanced_query=request.query,
            request_id=request_id or str(uuid.uuid4()),
            metadata={
                "include_explanation": request.include_explanation,
                "max_results": request.max_results,
                "include_sql": request.include_sql
            }
        )

        logger.info(
            f"Processing query via orchestrator. Request ID: {context.request_id}, "
            f"Query ID: {context.query_id}, Conversation: {context.conversation_id}"
        )

        try:
            # Process the query through all stages
            result = await self._execute_query_pipeline(context, db_session)

            # Log summary before returning
            summary = context.get_summary()
            logger.info(f"Query processing summary: {summary}")

            return result

        except Exception as e:
            logger.exception(f"Unhandled error in query orchestration: {str(e)}")
            context.add_error("orchestration", e)

            # Log summary before returning
            summary = context.get_summary()
            logger.info(f"Query processing summary: {summary}")

            return self._create_general_error_response(context)

    async def _execute_query_pipeline(
            self,
            context: ProcessingContext,
            db_session
    ) -> Union[QueryResponse, ErrorResponse]:
        """Execute the query processing pipeline."""
        try:
            # Stage 1: Cache Lookup
            await self.cache_lookup_stage.execute(context, db_session)
            logger.debug(f"Cache lookup completed with status: {context.metadata.get('cache_status', 'unknown')}")

            # If no cache hit, generate and validate SQL
            if context.metadata.get("cache_status", "miss") == "miss":
                # Stage 2: Generate SQL
                await self.sql_generation_stage.execute(context, db_session)
                logger.debug(f"SQL generation completed: {len(context.sql or '') > 0}")

                # Stage 3: Validate SQL
                validation_result = await self.sql_validation_stage.execute(context, db_session)
                if not validation_result.get("is_valid", True):
                    logger.warning(f"SQL validation failed for query {context.query_id}")
                    return self._create_validation_error_response(context, validation_result)
                logger.debug("SQL validation passed")

            # Stage 4: Execute SQL
            execution_result = await self.sql_execution_stage.execute(context, db_session)
            if not execution_result.get("success", False):
                logger.warning(
                    f"SQL execution failed for query {context.query_id}: {execution_result.get('error', 'Unknown error')}")
                return self._create_execution_error_response(context, execution_result)
            logger.debug(f"SQL execution completed with {context.metadata.get('row_count', 0)} results")

            # Stage 5: Generate explanation if needed
            needs_explanation = context.metadata.get("include_explanation", False) or not context.results
            if needs_explanation:
                await self.explanation_stage.execute(context, db_session)
                logger.debug("Explanation generated")
            else:
                context.results_explanation = "Results found. Request an explanation to learn more about this data."
                logger.debug("Skipped explanation generation")

            # Stage 6: Store in cache if new query
            if context.metadata.get("cache_status", "miss") == "miss":
                storage_result = await self.cache_storage_stage.execute(context, db_session)
                logger.debug(f"Query cached: {storage_result.get('stored', False)}")

            # Create response
            logger.info(f"Query processing successful for {context.query_id}")
            return self._create_successful_response(context)

        except Exception as e:
            # This catches exceptions in the pipeline itself, separate from the outer try/except
            logger.error(f"Error in query pipeline execution: {str(e)}")
            context.add_error("pipeline_execution", e)
            return self._create_general_error_response(context)

    async def get_explanation(self, query_id: uuid.UUID, db_session) -> str:
        """Get explanation for a previously executed query."""
        if not self.explanation_service:
            return "Explanation service not configured"

        # Create a simple tracking context
        context = ProcessingContext(
            query_id=uuid.uuid4(),
            metadata={"original_query_id": str(query_id)}
        )

        try:
            logger.info(f"Retrieving explanation for query {query_id} via orchestrator")
            context.start_stage("explanation_retrieval")

            # Delegate to the explanation service
            explanation = await self.explanation_service.get_explanation(query_id, db_session)

            context.complete_stage("explanation_retrieval")
            return explanation
        except Exception as e:
            logger.error(f"Error retrieving explanation: {str(e)}")
            context.add_error("explanation_retrieval", e)
            return f"An error occurred while retrieving the explanation: {str(e)}"
        finally:
            # Log the operation
            logger.info(f"Explanation retrieval summary: {context.get_summary()}")

    def _create_successful_response(self, context) -> QueryResponse:
        """Create successful response from context."""
        # Prepare query details if requested
        query_details = None
        if context.metadata.get("include_sql", True):
            query_details = QueryDetails(
                generated_sql=context.sql,
                execution_time_ms=context.metadata.get("execution_time_ms", 0),
                row_count=context.metadata.get("row_count", 0)
            )

        # Prepare timing stats
        timing_stats = {
            "start_time": context.start_time,
            "cache_status": context.metadata.get("cache_status", "miss"),
        }

        # Add all stage timings
        for stage, duration in context.stage_timings.items():
            if not stage.endswith("_start"):  # Skip start markers
                timing_stats[stage] = duration * 1000  # Convert to ms

        # Calculate total time
        timing_stats["total_time"] = (time.time() - context.start_time) * 1000

        # Create response
        return QueryResponse(
            query_id=context.query_id,
            request_id=context.request_id,
            results=context.results,
            query_details=query_details,
            conversation_id=context.conversation_id,
            message=context.results_explanation,
            timing_stats=timing_stats,
            has_results=context.metadata.get("has_results", False)
        )

    def _create_validation_error_response(self, context, validation_result) -> ErrorResponse:
        """Create error response for SQL validation failures."""
        error_details = [
            ErrorDetail(
                code=error.get("code", "VALIDATION_ERROR"),
                message=error.get("message", "Unknown validation error"),
                location=error.get("location"),
                suggestion=error.get("suggestion")
            )
            for error in validation_result.get("errors", [])
        ]

        return ErrorResponse(
            error="SQL validation failed",
            details=error_details,
            query_id=context.query_id,
            request_id=context.request_id
        )

    def _create_execution_error_response(self, context, execution_result) -> ErrorResponse:
        """Create error response for SQL execution failures."""
        return ErrorResponse(
            error="SQL execution failed",
            details=[
                ErrorDetail(
                    code="EXECUTION_ERROR",
                    message=execution_result.get("error", "Unknown execution error"),
                    location=None,
                    suggestion="Please try a different query"
                )
            ],
            query_id=context.query_id,
            request_id=context.request_id
        )

    def _create_general_error_response(self, context) -> ErrorResponse:
        """Create error response for general failures."""
        # Get the most relevant error
        error_message = "Unknown error"
        if context.errors:
            error_message = context.errors[-1].get("message", error_message)

        return ErrorResponse(
            error="Query processing failed",
            details=[
                ErrorDetail(
                    code="PROCESSING_ERROR",
                    message=error_message,
                    location=None,
                    suggestion="Please try again with a different query"
                )
            ],
            query_id=context.query_id,
            request_id=context.request_id
        )