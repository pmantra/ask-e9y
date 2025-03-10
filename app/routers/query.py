"""API routes for natural language queries."""

import logging
import json
from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db, get_table_schema_info
from app.models.requests import QueryRequest, FeedbackRequest, SchemaRequest
from app.models.responses import ErrorResponse, FeedbackResponse, SchemaInfo
from app.services.query_service import QueryService
from app.utils.db_utils import sanitize_for_json

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["Query"]
)

# Initialize the query service
query_service = QueryService()


@router.post("/query",
    response_model=None,  # Use custom response handling
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)
async def process_query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Process a natural language query and return the results.

    Parameters:
    - **query**: The natural language query to process
    - **conversation_id**: (Optional) Conversation context ID
    - **max_results**: (Optional) Maximum number of results to return
    - **include_sql**: (Optional) Whether to include the generated SQL in the response

    Returns:
    - **QueryResponse**: The query results
    """
    logger.info(f"Processing query: {request.query}")

    response, error = await query_service.process_query(request, db)

    if error:
        # Sanitize error response to handle special types
        error_dict = sanitize_for_json(error.dict())

        if "validation" in error.error.lower():
            status_code = status.HTTP_400_BAD_REQUEST
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

        # Return custom JSON response
        return Response(
            content=json.dumps({"detail": error_dict}),
            status_code=status_code,
            media_type="application/json"
        )

    # Sanitize successful response to handle special types
    response_dict = sanitize_for_json(response.dict())

    # Return custom JSON response
    return Response(
        content=json.dumps(response_dict),
        media_type="application/json"
    )


@router.post("/feedback", response_model=None)
async def submit_feedback(
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Submit feedback on a query result.

    Parameters:
    - **query_id**: ID of the previous query
    - **is_accurate**: Whether the query results were accurate
    - **comments**: (Optional) Feedback comments
    - **corrected_sql**: (Optional) Corrected SQL if the generated SQL was inaccurate

    Returns:
    - **FeedbackResponse**: Confirmation of feedback submission
    """
    logger.info(f"Received feedback for query {request.query_id}: {request.is_accurate}")

    # In a real implementation, this would store the feedback in a database
    # For now, we just log it and return a success response

    response = FeedbackResponse(
        status="success",
        message="Thank you for your feedback",
        query_id=request.query_id
    )

    # Sanitize response and return custom JSON
    response_dict = sanitize_for_json(response.dict())

    return Response(
        content=json.dumps(response_dict),
        media_type="application/json"
    )


@router.post("/schema", response_model=None)
async def get_schema(
    request: SchemaRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get database schema information.

    Parameters:
    - **schema_name**: (Optional) Database schema name
    - **include_metadata**: (Optional) Whether to include schema metadata
    - **tables**: (Optional) Specific tables to include

    Returns:
    - **SchemaInfo**: Schema information including tables, columns, and relationships
    """
    logger.info(f"Getting schema information for {request.schema_name}")

    schema_info = await get_table_schema_info(request.schema_name)

    # If specific tables were requested, filter the schema info
    if request.tables:
        schema_info = {
            table: info
            for table, info in schema_info.items()
            if table in request.tables
        }

    # TODO: Add metadata from the schema_metadata table if include_metadata is True

    response = SchemaInfo(
        tables=schema_info,
        metadata=None,  # For now, this is null; would be populated in a real implementation
    )

    # Sanitize response and return custom JSON
    response_dict = sanitize_for_json(response.dict())

    return Response(
        content=json.dumps(response_dict),
        media_type="application/json"
    )