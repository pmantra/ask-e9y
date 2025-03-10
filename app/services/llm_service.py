"""Abstract LLM service interface for natural language to SQL conversion."""

import abc
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID

from app.models.requests import QueryRequest


class LLMService(abc.ABC):
    """Abstract base class for LLM services."""

    @abc.abstractmethod
    async def translate_to_sql(
        self,
        query: str,
        schema_info: Dict[str, Any],
        conversation_id: Optional[UUID] = None,
    ) -> Tuple[str, str]:
        """
        Translate a natural language query to SQL.

        Args:
            query: The natural language query
            schema_info: Database schema information
            conversation_id: Optional conversation context ID

        Returns:
            Tuple containing:
            - The generated SQL query
            - A natural language explanation of what the query does
        """
        pass

    @abc.abstractmethod
    async def validate_sql(
        self,
        sql: str,
        schema_info: Dict[str, Any],
    ) -> Tuple[bool, Optional[List[Dict[str, str]]]]:
        """
        Validate the generated SQL against the schema.

        Args:
            sql: The SQL query to validate
            schema_info: Database schema information

        Returns:
            Tuple containing:
            - Boolean indicating if the SQL is valid
            - List of validation errors if any
        """
        pass

    @abc.abstractmethod
    async def explain_results(
        self,
        query: str,
        sql: str,
        results: List[Dict[str, Any]],
    ) -> str:
        """
        Generate a natural language explanation of query results.

        Args:
            query: The original natural language query
            sql: The executed SQL query
            results: The query results

        Returns:
            A natural language explanation of the results
        """
        pass

    @abc.abstractmethod
    async def handle_error(
        self,
        query: str,
        error: str,
        schema_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate a helpful error message and suggestions.

        Args:
            query: The original natural language query
            error: The error message from the database
            schema_info: Database schema information

        Returns:
            Dictionary with error details and suggestions
        """
        pass