import logging
from typing import Optional, Dict, Any
from sqlalchemy import text
from uuid import UUID

from app.utils.db_utils import sanitize_for_json

logger = logging.getLogger(__name__)


class ExplanationService:
    """Service for retrieving and generating explanations for queries."""

    def __init__(self, llm_service, schema_service, chroma_service):
        self.llm_service = llm_service
        self.schema_service = schema_service
        self.chroma_service = chroma_service

    async def get_explanation(self, query_id: UUID, db_session) -> str:
        """
        Retrieve or generate explanation for a query by ID.

        Args:
            query_id: The ID of the query to explain
            db_session: Database session for queries

        Returns:
            The explanation text or an error message
        """
        try:
            logger.info(f"Retrieving explanation for query {query_id}")

            # Strategy 1: Check PostgreSQL cache
            explanation = await self._get_from_postgres(query_id, db_session)
            if explanation:
                logger.info(f"Found explanation in PostgreSQL for query {query_id}")
                return explanation

            # Strategy 2: Check Chroma vector store
            explanation = self._get_from_chroma(query_id)
            if explanation:
                logger.info(f"Found explanation in Chroma for query {query_id}")
                return explanation

            # Strategy 3: Get query details and generate new explanation
            query_data = await self._get_query_details(query_id, db_session)
            if query_data:
                logger.info(f"Generating new explanation for query {query_id}")
                return await self._generate_new_explanation(
                    query_data["natural_query"],
                    query_data["sql"],
                    query_id,
                    db_session
                )

            # No query found
            logger.warning(f"No query found for ID {query_id}")
            return "Could not generate explanation. The query may have expired or been removed."

        except Exception as e:
            logger.error(f"Error retrieving explanation for query {query_id}: {str(e)}", exc_info=True)
            return f"An error occurred while retrieving the explanation: {str(e)}"

    async def _get_from_postgres(self, query_id: UUID, db_session) -> Optional[str]:
        """Get explanation directly from PostgreSQL cache."""
        try:
            query = text("""
                SELECT explanation
                FROM eligibility.query_cache
                WHERE query_id = :query_id AND explanation IS NOT NULL
            """)

            result = await db_session.execute(query, {"query_id": str(query_id)})
            row = result.mappings().first()

            if row and row["explanation"]:
                return row["explanation"]

        except Exception as e:
            logger.warning(f"Error checking PostgreSQL for explanation: {str(e)}")

        return None

    def _get_from_chroma(self, query_id: UUID) -> Optional[str]:
        """Get explanation from Chroma service."""
        try:
            # Using synchronous method from chroma_service
            query_data = self.chroma_service.get_query_by_id(str(query_id))

            if query_data and query_data.get("explanation"):
                return query_data["explanation"]

        except Exception as e:
            logger.warning(f"Error checking Chroma for explanation: {str(e)}")

        return None

    async def _get_query_details(self, query_id: UUID, db_session) -> Optional[Dict[str, Any]]:
        """Get query details from any available source."""
        # Try PostgreSQL first
        try:
            query = text("""
                SELECT natural_query, generated_sql
                FROM eligibility.query_cache
                WHERE query_id = :query_id
            """)

            result = await db_session.execute(query, {"query_id": str(query_id)})
            row = result.mappings().first()

            if row:
                return {
                    "natural_query": row["natural_query"],
                    "sql": row["generated_sql"],
                    "source": "postgres"
                }
        except Exception as e:
            logger.warning(f"Error retrieving query details from PostgreSQL: {str(e)}")

        # Try Chroma next
        try:
            query_data = self.chroma_service.get_query_by_id(str(query_id))

            if query_data:
                return {
                    "natural_query": query_data.get("natural_query"),
                    "sql": query_data.get("generated_sql"),
                    "source": "chroma"
                }
        except Exception as e:
            logger.warning(f"Error retrieving query details from Chroma: {str(e)}")

        return None

    async def _generate_new_explanation(self, query: str, sql: str, query_id: UUID, db_session) -> str:
        """Generate a new explanation for a query."""
        try:
            # Execute the query to get results
            result = await db_session.execute(text(sql))
            rows = result.mappings().all()
            results = [sanitize_for_json(dict(row)) for row in rows]

            # Get schema information for context
            schema_info = await self.schema_service.get_schema_info()

            # Generate explanation using LLM
            explanation = await self.llm_service.explain_results(
                query,
                sql,
                results,
                schema_info=schema_info
            )

            # Store the explanation in both storage systems
            await self._store_explanation(query_id, explanation, db_session)

            return explanation
        except Exception as e:
            logger.error(f"Error generating explanation: {str(e)}")
            return f"Could not generate explanation: {str(e)}"

    async def _store_explanation(self, query_id: UUID, explanation: str, db_session) -> None:
        """Store explanation in all available storage systems."""
        # Store in PostgreSQL
        try:
            update_query = text("""
                UPDATE eligibility.query_cache
                SET explanation = :explanation
                WHERE query_id = :query_id
            """)

            await db_session.execute(
                update_query,
                {
                    "explanation": explanation,
                    "query_id": str(query_id)
                }
            )
            await db_session.commit()
            logger.info(f"Stored explanation in PostgreSQL for query {query_id}")
        except Exception as e:
            logger.warning(f"Failed to store explanation in PostgreSQL: {str(e)}")

        # Store in Chroma if method exists
        try:
            if hasattr(self.chroma_service, 'update_explanation'):
                self.chroma_service.update_explanation(str(query_id), explanation)
                logger.info(f"Stored explanation in Chroma for query {query_id}")
        except Exception as e:
            logger.warning(f"Failed to store explanation in Chroma: {str(e)}")