import logging
from uuid import UUID
from sqlalchemy import text

logger = logging.getLogger(__name__)


class FeedbackService:
    """Service for handling query feedback."""

    async def submit_feedback(self, query_id: UUID, is_accurate: bool, comments: str = None,
                              corrected_sql: str = None, db_session=None):
        """Submit feedback for a query."""
        logger.info(f"Processing feedback for query {query_id}: accurate={is_accurate}")

        try:
            if db_session:
                # Store feedback in database
                await self._store_feedback(
                    query_id, is_accurate, comments, corrected_sql, db_session
                )

            return {
                "status": "success",
                "message": "Thank you for your feedback"
            }
        except Exception as e:
            logger.error(f"Error processing feedback: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to process feedback: {str(e)}"
            }

    async def _store_feedback(self, query_id: UUID, is_accurate: bool,
                              comments: str, corrected_sql: str, db_session):
        """Store feedback in the database."""
        try:
            # Check if we have a query history table to store feedback
            query = text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'eligibility' 
                    AND table_name = 'query_history'
                )
            """)

            result = await db_session.execute(query)
            has_history_table = result.scalar()

            if has_history_table:
                # Store in query_history
                query = text("""
                    UPDATE eligibility.query_history
                    SET user_feedback = :feedback,
                        corrected_sql = :corrected_sql
                    WHERE query_id = :query_id
                """)

                await db_session.execute(query, {
                    "feedback": comments,
                    "corrected_sql": corrected_sql,
                    "query_id": str(query_id)
                })

                await db_session.commit()
                logger.info(f"Feedback stored for query {query_id}")
            else:
                logger.warning("query_history table not found, feedback not stored")

        except Exception as e:
            logger.error(f"Database error storing feedback: {str(e)}")
            # Don't rethrow, we want to return a success response even if storage fails