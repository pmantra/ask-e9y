import logging

logger = logging.getLogger(__name__)


class SQLGenerationStage:
    """Stage for generating SQL from natural language."""

    def __init__(self, llm_service, schema_service):
        self.llm_service = llm_service
        self.schema_service = schema_service

    # In app/services/stages/sql_generation_stage.py
    async def execute(self, context, db_session):
        """Execute the SQL generation stage."""
        # Skip if we already have SQL from cache
        if context.sql:
            return {"sql": context.sql, "skipped": True}

        context.start_stage("sql_generation")

        # Get schema information
        schema_info = await self.schema_service.get_schema_info()

        # Store schema size in context
        context.metadata["full_schema_size"] = len(schema_info)

        # Generate SQL
        sql, explanation, token_usage, prompts = await self.llm_service.translate_to_sql(
            context.enhanced_query or context.original_query,
            schema_info,
            context.conversation_id
        )

        # Update context
        context.sql = sql
        context.metadata["sql_explanation"] = explanation
        context.metadata["token_usage"] = token_usage

        # Store prompts in context metadata
        context.metadata["prompt_system"] = prompts["system"]
        context.metadata["prompt_user"] = prompts["user"]

        logger.debug(
            f"Stored prompts in context: system={len(prompts['system'])} chars, user={len(prompts['user'])} chars")

        logger.info(f"Generated SQL: {sql}")

        context.complete_stage("sql_generation", {
            "sql": sql,
            "explanation": explanation
        })

        return {"sql": sql, "explanation": explanation}