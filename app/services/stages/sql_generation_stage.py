import logging

logger = logging.getLogger(__name__)


class SQLGenerationStage:
    """Stage for generating SQL from natural language."""

    def __init__(self, llm_service, schema_service, schema_embedding_service=None, example_retrieval_service=None):
        self.llm_service = llm_service
        self.schema_service = schema_service
        self.schema_embedding_service = schema_embedding_service
        self.example_retrieval_service = example_retrieval_service

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
        full_schema_size = len(str(schema_info))
        context.metadata["full_schema_size"] = full_schema_size

        # Use schema embedding service if available to get selective schema
        tables_used = []
        if self.schema_embedding_service:
            # Store the original query for selection
            query_for_selection = context.enhanced_query or context.original_query

            # Get selective schema
            selective_schema = await self.schema_embedding_service.get_selective_schema(
                query=query_for_selection,
                schema_info=schema_info,
                threshold=0.5,  # Set appropriate threshold
                max_tables=5
            )

            # If selective schema is empty or too small, fall back to full schema
            if not selective_schema or len(selective_schema) < 2:
                logger.warning("Selective schema too small, falling back to full schema")
                selective_schema = schema_info

            # Track schema reduction metrics
            selective_schema_size = len(str(selective_schema))
            context.metadata["selective_schema_size"] = selective_schema_size
            context.metadata["schema_reduction_percent"] = round(
                (1 - (selective_schema_size / full_schema_size)) * 100
            )

            # Use selective schema for LLM
            schema_for_llm = selective_schema
            tables_used = list(selective_schema.keys())
            context.metadata["tables_used"] = tables_used
            logger.info(f"Using selective schema with tables: {', '.join(tables_used)}")
        else:
            # Use full schema if embedding service not available
            schema_for_llm = schema_info

        # Find similar examples if available
        examples = []
        if self.example_retrieval_service:
            examples = await self.example_retrieval_service.find_similar_examples(
                query=context.original_query,
                tables=tables_used if tables_used else None,
                top_k=2
            )
            context.metadata["examples_used"] = len(examples)
            if examples:
                logger.info(f"Found {len(examples)} similar examples")

        # Generate SQL with examples
        sql, explanation, token_usage, prompts = await self.llm_service.translate_to_sql(
            context.enhanced_query or context.original_query,
            schema_for_llm,
            context.conversation_id,
            similar_examples=examples
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