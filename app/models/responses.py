"""Response models for the API."""

from typing import Optional, List, Dict, Any, Union
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime


class RangeModel(BaseModel):
    """Model for representing PostgreSQL range types."""
    lower: Optional[Any] = None
    upper: Optional[Any] = None


class QueryDetails(BaseModel):
    """Details about the executed query."""

    generated_sql: str = Field(
        ...,
        description="The SQL query generated from the natural language query"
    )
    execution_time_ms: float = Field(
        ...,
        description="Query execution time in milliseconds"
    )
    row_count: int = Field(
        ...,
        description="Number of rows returned by the query"
    )


class QueryResponse(BaseModel):
    """Response model for a natural language query."""

    query_id: UUID = Field(
        ...,
        description="Unique identifier for this query"
    )
    results: List[Dict[str, Any]] = Field(
        ...,
        description="Query results as a list of dictionaries"
    )
    query_details: Optional[QueryDetails] = Field(
        default=None,
        description="Details about the executed query"
    )
    conversation_id: UUID = Field(
        ...,
        description="Conversation context ID"
    )
    message: Optional[str] = Field(
        default=None,
        description="Natural language explanation of the results"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp of the response"
    )
    timing_stats: Optional[Dict[str, Union[float, str]]] = Field(
        default=None,
        description="Timing statistics for different parts of the query processing (in milliseconds)"
    )
    has_results: bool = Field(
        ...,
        description="Whether the query returned any results"
    )
    request_id: Optional[str] = None

class ErrorDetail(BaseModel):
    """Detailed error information."""

    code: str = Field(
        ...,
        description="Error code"
    )
    message: str = Field(
        ...,
        description="Error message"
    )
    location: Optional[str] = Field(
        default=None,
        description="Location where the error occurred (e.g., query part, specific token)"
    )
    suggestion: Optional[str] = Field(
        default=None,
        description="Suggestion for fixing the error"
    )


class ErrorResponse(BaseModel):
    """Response model for errors."""

    error: str = Field(
        ...,
        description="General error description"
    )
    details: Optional[List[ErrorDetail]] = Field(
        default=None,
        description="Detailed error information"
    )
    query_id: Optional[UUID] = Field(
        default=None,
        description="ID of the failed query, if applicable"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp of the error"
    )


class FeedbackResponse(BaseModel):
    """Response model for feedback submission."""

    status: str = Field(
        default="success",
        description="Status of the feedback submission"
    )
    message: str = Field(
        default="Thank you for your feedback",
        description="Response message"
    )
    query_id: UUID = Field(
        ...,
        description="ID of the query that received feedback"
    )


class SchemaInfo(BaseModel):
    """Information about a database schema."""

    tables: Dict[str, Dict[str, Any]] = Field(
        ...,
        description="Tables in the schema with their columns and relations"
    )
    metadata: Optional[Dict[str, Dict[str, Dict[str, str]]]] = Field(
        default=None,
        description="Additional metadata about tables and columns"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="When the schema information was last updated"
    )


class ColumnInfo(BaseModel):
    """Information about a database column."""

    name: str = Field(..., description="Column name")
    type: str = Field(..., description="Data type")
    nullable: bool = Field(..., description="Whether the column can be null")
    default: Optional[str] = Field(None, description="Default value")
    description: Optional[str] = Field(None, description="Column description")
    example: Optional[str] = Field(None, description="Example value")


class ForeignKeyInfo(BaseModel):
    """Information about a foreign key."""

    column: str = Field(..., description="Column name")
    foreign_table: str = Field(..., description="Referenced table")
    foreign_column: str = Field(..., description="Referenced column")


class TableInfo(BaseModel):
    """Information about a database table."""

    columns: List[ColumnInfo] = Field(..., description="Table columns")
    foreign_keys: List[ForeignKeyInfo] = Field(default_factory=list, description="Foreign keys")
    description: Optional[str] = Field(None, description="Table description")