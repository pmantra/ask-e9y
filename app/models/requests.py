"""Request models for the API."""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator


# In app/models/requests.py
class QueryRequest(BaseModel):
    """Request model for a natural language query."""

    query: str = Field(
        ...,
        description="The natural language query to process",
        examples=["Show me all members from ACME Corporation"]
    )
    conversation_id: Optional[UUID] = Field(
        default_factory=uuid4,
        description="Unique identifier for the conversation context"
    )
    max_results: Optional[int] = Field(
        default=100,
        description="Maximum number of results to return",
        ge=1,
        le=1000
    )
    include_sql: Optional[bool] = Field(
        default=True,
        description="Whether to include the generated SQL in the response"
    )
    include_explanation: Optional[bool] = Field(
        default=False,
        description="Whether to generate explanation for the results in the initial response"
    )
    include_cached_explanation: Optional[bool] = Field(
        default=False,
        description="Whether to include explanations for cached results"
    )
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional parameters to pass to the query"
    )

    @field_validator('query')
    @classmethod
    def validate_query(cls, v):
        """Validate the query string."""
        if not v or v.strip() == "":
            raise ValueError("Query cannot be empty")
        if len(v) > 1000:
            raise ValueError("Query is too long (max 1000 characters)")
        return v


class FeedbackRequest(BaseModel):
    """Request model for providing feedback on a query result."""

    query_id: UUID = Field(
        ...,
        description="ID of the previous query"
    )
    is_accurate: bool = Field(
        ...,
        description="Whether the query results were accurate"
    )
    comments: Optional[str] = Field(
        default=None,
        description="Optional feedback comments"
    )
    corrected_sql: Optional[str] = Field(
        default=None,
        description="Corrected SQL if the generated SQL was inaccurate"
    )


class SchemaRequest(BaseModel):
    """Request model for retrieving schema information."""

    schema_name: Optional[str] = Field(
        default="eligibility",
        description="Database schema name"
    )
    include_metadata: Optional[bool] = Field(
        default=True,
        description="Whether to include schema metadata in the response"
    )
    tables: Optional[List[str]] = Field(
        default=None,
        description="Specific tables to include (all if not specified)"
    )