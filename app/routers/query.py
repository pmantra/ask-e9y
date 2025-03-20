# app/routers/query.py
import logging
import json
import uuid
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.models.requests import QueryRequest, FeedbackRequest, SchemaRequest
from app.models.responses import ErrorResponse, FeedbackResponse, SchemaInfo, QueryResponse
from app.services.explanation_service import ExplanationService
from app.services.feedback_service import FeedbackService
from app.services.orchestration.factory import query_orchestrator
from app.services.schema_info_service import SchemaInfoService
from app.utils.db_utils import sanitize_for_json

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["Query"]
)

feedback_service = FeedbackService()
schema_info_service = SchemaInfoService()
explanation_service = ExplanationService(
    llm_service=query_orchestrator.sql_generation_stage.llm_service,
    schema_service=query_orchestrator.sql_generation_stage.schema_service,
    chroma_service=query_orchestrator.cache_lookup_stage.cache_service.chroma_service
)


@router.post("/query",
    response_model=None,  # Use custom response handling
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)
async def process_query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """Process a natural language query and return the results."""
    request_id = str(uuid.uuid4())
    logger.info(f"Processing query [ID: {request_id}]: {request.query}")

    # Process the query through the orchestrator
    response = await query_orchestrator.process_query(request, db, request_id)

    # Handle the response based on its type using pattern matching
    match response:
        case ErrorResponse():
            # Sanitize error response to handle special types
            error_dict = sanitize_for_json(response.dict())

            # Determine appropriate status code
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            if "validation" in response.error.lower():
                status_code = status.HTTP_400_BAD_REQUEST

            # Log completion with error
            logger.info(f"Query processing completed [ID: {request_id}] with error: {response.error}")

            # Return error response
            return Response(
                content=json.dumps({"detail": error_dict}),
                status_code=status_code,
                media_type="application/json"
            )

        case QueryResponse():
            # Sanitize successful response
            response_dict = sanitize_for_json(response.dict())

            # Log successful completion
            logger.info(
                f"Query processing completed [ID: {request_id}] successfully, returning {len(response.results)} results")

            # Return success response
            return Response(
                content=json.dumps(response_dict),
                media_type="application/json"
            )

        case _:
            # Unexpected response type (shouldn't happen but good defensive programming)
            logger.error(f"Query processing returned unexpected type: {type(response)}")
            return Response(
                content=json.dumps({"detail": "Internal server error: unexpected response type"}),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                media_type="application/json"
            )


@router.post("/feedback", response_model=None)
async def submit_feedback(
        request: FeedbackRequest,
        db: AsyncSession = Depends(get_async_db)
):
    """Submit feedback on a query result."""
    request_id = str(uuid.uuid4())
    logger.info(f"Received feedback [ID: {request_id}] for query {request.query_id}: {request.is_accurate}")

    # Process feedback through the service
    result = await feedback_service.submit_feedback(
        query_id=request.query_id,
        is_accurate=request.is_accurate,
        comments=request.comments,
        corrected_sql=request.corrected_sql,
        db_session=db
    )

    # Create response
    response = FeedbackResponse(
        status=result["status"],
        message=result["message"],
        query_id=request.query_id
    )

    # Sanitize and return
    response_dict = sanitize_for_json(response.dict())

    logger.info(f"Feedback processing completed [ID: {request_id}]")

    return Response(
        content=json.dumps(response_dict),
        media_type="application/json"
    )


@router.post("/schema", response_model=None)
async def get_schema(
        request: SchemaRequest,
        db: AsyncSession = Depends(get_async_db)
):
    """Get database schema information."""
    request_id = str(uuid.uuid4())
    logger.info(f"Getting schema information [ID: {request_id}] for {request.schema_name}")

    # Get schema through the service
    schema_result = await schema_info_service.get_schema_info(
        schema_name=request.schema_name,
        tables=request.tables,
        include_metadata=request.include_metadata
    )

    # Create response
    response = SchemaInfo(
        tables=schema_result["tables"],
        metadata=schema_result["metadata"]
    )

    # Sanitize and return
    response_dict = sanitize_for_json(response.dict())

    logger.info(f"Schema retrieval completed [ID: {request_id}]")

    return Response(
        content=json.dumps(response_dict),
        media_type="application/json"
    )


@router.post("/explain",
             response_model=None,
             responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}
             )
async def get_explanation(
        request: Dict[str, Any],
        db: AsyncSession = Depends(get_async_db)
):
    """Get explanation for a previously executed query."""
    request_id = str(uuid.uuid4())

    # Validate request
    if "query_id" not in request:
        logger.warning(f"Explanation request [ID: {request_id}] missing query_id")
        return Response(
            content=json.dumps({
                "detail": {
                    "error": "Missing query_id",
                    "message": "The query_id is required to retrieve an explanation"
                }
            }),
            status_code=status.HTTP_400_BAD_REQUEST,
            media_type="application/json"
        )

    try:
        query_id = uuid.UUID(request["query_id"])
    except (ValueError, TypeError):
        logger.warning(f"Explanation request [ID: {request_id}] had invalid query_id format")
        return Response(
            content=json.dumps({
                "detail": {
                    "error": "Invalid query_id format",
                    "message": "The query_id must be a valid UUID"
                }
            }),
            status_code=status.HTTP_400_BAD_REQUEST,
            media_type="application/json"
        )

    logger.info(f"Generating explanation [ID: {request_id}] for query {query_id}")

    # Get explanation through service
    explanation = await explanation_service.get_explanation(query_id, db)
    logger.debug(f"Raw explanation content: '{explanation}'")

    if not explanation or explanation.startswith("Could not generate explanation"):
        logger.warning(f"Explanation not found [ID: {request_id}] for query {query_id}")
        return Response(
            content=json.dumps({
                "detail": {
                    "error": "Explanation not found",
                    "message": "No query found with the provided ID, or the explanation could not be generated"
                }
            }),
            status_code=status.HTTP_404_NOT_FOUND,
            media_type="application/json"
        )

    # Create response
    response_dict = {
        "query_id": str(query_id),
        "explanation": explanation,
        "timestamp": datetime.now().isoformat(),
        "request_id": request_id
    }

    logger.info(f"Explanation generation completed [ID: {request_id}] for query {query_id}")

    return Response(
        content=json.dumps(response_dict),
        media_type="application/json"
    )