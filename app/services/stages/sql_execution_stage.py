import logging

logger = logging.getLogger(__name__)


class SQLExecutionStage:
    """Stage for executing SQL queries."""

    def __init__(self, sql_executor):
        self.sql_executor = sql_executor

    async def execute(self, context, db_session):
        """Execute the SQL execution stage."""
        context.start_stage("sql_execution")

        # Execute the SQL
        max_results = context.metadata.get("max_results", 100)
        execution_result = await self.sql_executor.execute_query(
            context.sql,
            db_session,
            max_results
        )

        # Update context with results
        context.results = execution_result["results"]
        context.metadata["execution_time_ms"] = execution_result["execution_time_ms"]
        context.metadata["row_count"] = execution_result["row_count"]
        context.metadata["has_results"] = execution_result["has_results"]

        context.complete_stage("sql_execution", execution_result)
        return execution_result