import logging

logger = logging.getLogger(__name__)


class SQLValidationStage:
    """Stage for validating generated SQL."""

    def __init__(self, llm_service, schema_service):
        self.llm_service = llm_service
        self.schema_service = schema_service

    async def execute(self, context, db_session):
        """Execute the SQL validation stage."""
        # Skip if SQL came from cache (assuming cached SQL is valid)
        if context.metadata.get("cache_status", "miss") != "miss":
            return {"is_valid": True, "skipped": True}

        context.start_stage("sql_validation")

        # Get schema information for validation
        schema_info = await self.schema_service.get_schema_info()

        # Validate SQL
        is_valid, errors = await self.llm_service.validate_sql(context.sql, schema_info)

        result = {
            "is_valid": is_valid,
            "errors": errors if not is_valid else []
        }

        context.metadata["validation_result"] = result
        context.complete_stage("sql_validation", result)

        return result