import logging
import re
from typing import List

logger = logging.getLogger(__name__)


class ExplanationGenerationStage:
    """Stage for generating explanations of query results."""

    def __init__(self, llm_service, schema_service):
        self.llm_service = llm_service
        self.schema_service = schema_service

    async def execute(self, context, db_session):
        """Execute the explanation generation stage."""
        # Skip if we already have an explanation from cache
        if context.metadata.get("explanation"):
            return {"explanation": context.metadata["explanation"], "skipped": True}

        context.start_stage("explanation_generation")

        # Check if results are empty
        if not context.metadata.get("has_results", False):
            explanation = self._generate_empty_results_explanation(context)
        else:
            # Generate explanation using LLM
            explanation = await self._generate_results_explanation(context)

        # Update context
        context.results_explanation = explanation

        context.complete_stage("explanation_generation", {
            "explanation": explanation
        })

        return {"explanation": explanation}

    async def _generate_results_explanation(self, context):
        """Generate explanation for non-empty result set."""
        # Extract tables used in the query
        tables_used = self._extract_tables_from_sql(context.sql)

        # Get schema information
        schema_info = await self.schema_service.get_schema_info()

        # Check for business rules
        business_rules = self._detect_business_rules(context.sql)

        # Generate explanation
        return await self.llm_service.explain_results(
            context.original_query,
            context.sql,
            context.results,
            tables_used=tables_used,
            business_rules=business_rules,
            schema_info=schema_info
        )

    def _generate_empty_results_explanation(self, context):
        """Generate explanation for empty result set."""
        tables_used = self._extract_tables_from_sql(context.sql)
        business_rules = self._detect_business_rules(context.sql)

        return (
            "Your query did not return any results. This means no data matches your search criteria. "
            f"The query looked for data in the following tables: {', '.join(tables_used)}. "
            f"{'The query also applied business rules for: ' + ', '.join(business_rules) + '.' if business_rules else ''} "
            "You might want to try broadening your search criteria or check if you're using the correct names and identifiers."
        )

    def _extract_tables_from_sql(self, sql: str) -> List[str]:
        """Extract table names from SQL query."""
        from_pattern = r'FROM\s+([a-zA-Z0-9_.]+)'
        join_pattern = r'JOIN\s+([a-zA-Z0-9_.]+)'

        tables = []

        # Find tables in FROM clauses
        from_matches = re.finditer(from_pattern, sql, re.IGNORECASE)
        for match in from_matches:
            tables.append(match.group(1).strip())

        # Find tables in JOIN clauses
        join_matches = re.finditer(join_pattern, sql, re.IGNORECASE)
        for match in join_matches:
            tables.append(match.group(1).strip())

        return list(set(tables))  # Remove duplicates

    def _detect_business_rules(self, sql: str) -> List[str]:
        """Detect business rules applied in SQL query."""
        business_rules = []

        if "effective_range @> CURRENT_DATE" in sql:
            business_rules.append("active member status")
        if "COUNT(DISTINCT organization_id) > 1" in sql or "COUNT(DISTINCT m.organization_id) > 1" in sql:
            business_rules.append("overeligibility")

        return business_rules