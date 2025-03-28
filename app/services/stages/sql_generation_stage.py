import logging

logger = logging.getLogger(__name__)


class SQLGenerationStage:
    """Stage for generating SQL from natural language."""

    def __init__(self, llm_service, schema_service, schema_embedding_service=None, example_retrieval_service=None, prompt_analysis_stage=None):
        self.llm_service = llm_service
        self.schema_service = schema_service
        self.schema_embedding_service = schema_embedding_service
        self.example_retrieval_service = example_retrieval_service
        self.prompt_analysis_stage = prompt_analysis_stage

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

         # Generate schema fingerprint for caching
        schema_fingerprint = self._create_schema_fingerprint(schema_for_llm)
        context.metadata["schema_fingerprint"] = schema_fingerprint

        # Find similar examples (existing logic)
        examples = []
        if self.example_retrieval_service:
            examples = await self.example_retrieval_service.find_similar_examples(
                query=context.original_query,
                tables=tables_used if tables_used else None,
                top_k=2
            )
            context.metadata["examples_used"] = len(examples)

        # Format examples string
        examples_str = self._format_examples(examples)
        
        # Format schema string
        schema_str = self.llm_service._format_schema_for_prompt(schema_for_llm)
        
        # Try to get cached prompt if prompt_analysis_stage is available
        if self.prompt_analysis_stage:
            cache_result = await self.prompt_analysis_stage.lookup_cached_prompt(
                context.original_query, 
                schema_fingerprint,
                context
            )
            
            if cache_result.get("cache_hit", False):
                # Use cached prompt
                system_prompt = cache_result["prompt"]
                context.metadata["prompt_cache"] = "hit"
                context.metadata["prompt_cache_type"] = cache_result["cache_type"]
                context.metadata["prompt_token_count"] = cache_result["token_count"]
            else:
                # Generate new dynamic prompt using PromptBuilder
                query_analysis = context.metadata.get("query_analysis", {})
                if not query_analysis:
                    # If no analysis available (shouldn't happen), create it now
                    query_analysis = self.prompt_analysis_stage.prompt_builder.analyze_query(
                        context.original_query
                    )
                
                # Build dynamic prompt
                system_prompt = self.prompt_analysis_stage.prompt_builder.build_system_prompt(
                    context.original_query,
                    schema_str,
                    examples_str,
                    query_analysis
                )
                
                # Estimate token count
                token_count = len(system_prompt.split()) // 0.75
                context.metadata["prompt_token_count"] = token_count
                context.metadata["prompt_cache"] = "miss"
                
                # Store in cache for future use
                if cache_result.get("embedding"):
                    await self.prompt_analysis_stage.store_prompt_in_cache(
                        context.original_query,
                        system_prompt,
                        schema_fingerprint,
                        token_count,
                        cache_result["embedding"]
                    )
        else:
            # Use standard prompt generation from llm_service
            # This is a fallback for backward compatibility
            system_prompt = self._build_standard_prompt(schema_str, examples_str)
            
        # Use the user prompt format from the LLM service
        user_prompt = f"Generate a SQL query for: {context.original_query}"
        
        # Store prompts in context metadata
        context.metadata["prompt_system"] = system_prompt
        context.metadata["prompt_user"] = user_prompt

        # Generate SQL using the LLM
        sql, explanation, token_usage, _ = await self.llm_service.translate_to_sql_with_prompt(
            context.original_query,
            system_prompt,
            user_prompt,
            context.conversation_id
        )

        # Update context
        context.sql = sql
        context.metadata["sql_explanation"] = explanation
        context.metadata["token_usage"] = token_usage

        logger.debug(
            f"Stored prompts in context: system={len(system_prompt)} chars, user={len(user_prompt)} chars")

        logger.info(f"Generated SQL: {sql}")

        context.complete_stage("sql_generation", {
            "sql": sql,
            "explanation": explanation
        })

        return {"sql": sql, "explanation": explanation}

    def _format_examples(self, examples):
        """Format examples for inclusion in the prompt."""
        if not examples or len(examples) == 0:
            return ""
            
        examples_str = "Here are examples of similar queries:\n\n"
        for i, example in enumerate(examples):
            examples_str += f"Example {i + 1}:\n"
            examples_str += f"Query: {example['natural_query']}\n"
            examples_str += f"SQL: {example['generated_sql']}\n\n"
            
        return examples_str
        
    def _create_schema_fingerprint(self, schema_info):
        """Create a fingerprint for the schema structure."""
        import hashlib
        import json
        
        # Create a simplified representation of schema structure
        schema_repr = {
            table: sorted([col["name"] for col in info.get("columns", [])])
            for table, info in schema_info.items()
        }
        
        # Create a stable string representation
        schema_str = json.dumps(schema_repr, sort_keys=True)
        
        # Return a hash of the schema
        return hashlib.md5(schema_str.encode()).hexdigest()
        
    def _build_standard_prompt(self, schema_str, examples_str):
        """Build a standard prompt (fallback when PromptBuilder is unavailable)."""
        return f"""You are an expert SQL assistant that generates PostgreSQL SQL queries.
        You are given a database schema and a natural language query. Your task is to convert the natural language into a valid SQL query.

        Here's the database schema you're working with:
        {schema_str}

        {examples_str}  

        Important concepts to understand about this schema:
        1. A member is considered "active" if the current date is contained within their effective_range. Use the PostgreSQL operator '@>' to check this: WHERE effective_range @> CURRENT_DATE
        2. Organizations are identified by the organization table, with a name column that can be searched using ILIKE.
        3. All tables are in the 'eligibility' schema, so always prefix table names with 'eligibility.'
        4. Never use a 'status' column for members as it doesn't exist. Always use the effective_range to determine if a member is active.
        5. For date operations, use PostgreSQL date functions like CURRENT_DATE.
        6. A person is considered "overeligible" if they have active member records in more than one organization with the same first name, last name, and date of birth. To check for overeligibility, look for members with identical first_name, last_name, and date_of_birth values that exist in multiple organizations.
        
        Important patterns for matching text:
        1. Always use wildcards with ILIKE for name matching: ILIKE '%name%' not ILIKE 'name'
        2. For first/last names, use: first_name ILIKE '%james%' to match any name containing 'james'
        3. For organization names, use: name ILIKE '%acme%' to match any name containing 'acme'

        Generate ONLY SQL queries that query data, specifically SELECT statements. Do not generate queries that modify data.
        Ensure your SQL is valid PostgreSQL syntax.
        All table names should be prefixed with the schema name, e.g., 'eligibility.member'.
        Return only the SQL query as plain text, with no markdown formatting or explanations.
        """