import logging
import time
from typing import Dict, Any, List
from sqlalchemy import text

from app.utils.db_utils import sanitize_for_json

logger = logging.getLogger(__name__)


class SQLExecutor:
    """Service for executing SQL queries."""

    async def execute_query(self, sql: str, db_session, max_results: int = 100):
        """Execute a SQL query and return results."""
        start_time = time.time()

        try:
            # Execute query against database
            result = await db_session.execute(text(sql))
            rows = result.mappings().all()
            results = [sanitize_for_json(dict(row)) for row in rows]

            execution_time_ms = (time.time() - start_time) * 1000

            return {
                "results": results[:max_results],
                "row_count": len(results),
                "execution_time_ms": execution_time_ms,
                "success": True,
                "has_results": len(results) > 0
            }
        except Exception as e:
            logger.error(f"SQL execution error: {str(e)}")
            return {
                "results": [],
                "row_count": 0,
                "execution_time_ms": (time.time() - start_time) * 1000,
                "success": False,
                "error": str(e),
                "has_results": False
            }