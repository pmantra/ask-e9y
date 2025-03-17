"""OpenAI implementation of the LLM service."""

import json
import logging
import re
import time
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID

from openai import AsyncOpenAI

from app.config import settings
from app.services.llm_service import LLMService
from app.utils.sql_patterns import SQL_PATTERNS

logger = logging.getLogger(__name__)


class OpenAILLMService(LLMService):
    """OpenAI implementation of the LLM service."""

    def __init__(self):
        """Initialize the OpenAI client."""
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL

    async def translate_to_sql(
            self,
            query: str,
            schema_info: Dict[str, Any],
            conversation_id: Optional[UUID] = None,
    ) -> Tuple[str, str]:
        """
        Translate a natural language query to SQL using OpenAI.
        """
        # Prepare schema information as a string for the prompt
        schema_str = self._format_schema_for_prompt(schema_info)

        # Create the system prompt
        system_prompt = f"""You are an expert SQL assistant that generates PostgreSQL SQL queries.
    You are given a database schema and a natural language query. Your task is to convert the natural language into a valid SQL query.

    Here's the database schema you're working with:
    {schema_str}

    Important concepts to understand about this schema:
    1. A member is considered "active" if the current date is contained within their effective_range. Use the PostgreSQL operator '@>' to check this: WHERE effective_range @> CURRENT_DATE
    2. Organizations are identified by the organization table, with a name column that can be searched using ILIKE.
    3. All tables are in the 'eligibility' schema, so always prefix table names with 'eligibility.'
    4. Never use a 'status' column for members as it doesn't exist. Always use the effective_range to determine if a member is active.
    5. For date operations, use PostgreSQL date functions like CURRENT_DATE.
    6. A person is considered "overeligible" if they have active member records in more than one organization with the same first name, last name, and date of birth. To check for overeligibility, look for members with identical first_name, last_name, and date_of_birth values that exist in multiple organizations.

    Generate ONLY SQL queries that query data, specifically SELECT statements. Do not generate queries that modify data.
    Ensure your SQL is valid PostgreSQL syntax.
    All table names should be prefixed with the schema name, e.g., 'eligibility.member'.
    Return only the SQL query as plain text, with no markdown formatting or explanations.
    """

        start_time = time.time()
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Generate a SQL query for: {query}"}
                ],
                temperature=0.1,  # Low temperature for more deterministic responses
                max_tokens=1000,
            )

            api_duration = time.time() - start_time
            logger.info(f"OpenAI API call for SQL translation took {api_duration:.2f} seconds")

            sql = response.choices[0].message.content.strip()

            # Clean up the SQL (remove markdown formatting if present)
            sql = self._clean_sql(sql)

            # Generate explanation of the SQL
            explanation = await self._generate_explanation(query, sql)

            return sql, explanation

        except Exception as e:
            api_duration = time.time() - start_time
            logger.error(f"Error in OpenAI SQL translation (after {api_duration:.2f} seconds): {str(e)}")
            raise

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
        # Check for disallowed SQL operations
        for operation in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"]:
            pattern = rf"\b{operation}\b"
            if re.search(pattern, sql, re.IGNORECASE):
                return False, [{
                    "code": "DISALLOWED_OPERATION",
                    "message": f"SQL operation '{operation}' is not allowed",
                    "location": None,
                    "suggestion": "Use only SELECT statements for data retrieval"
                }]

        # Use the LLM to validate the SQL
        schema_str = self._format_schema_for_prompt(schema_info)

        system_prompt = f"""You are an expert SQL validator that checks if SQL queries are valid for a given schema.

Here's the database schema:
{schema_str}

Your task is to validate if the SQL query follows these rules:
1. It must be valid PostgreSQL syntax
2. It must only reference tables and columns that exist in the schema
3. It must use the correct data types for comparisons and operations
4. It must include all required schema prefixes (e.g., 'eligibility.member')

Output your response in JSON format with the following structure:
{{
  "is_valid": boolean,
  "errors": [
    {{
      "code": "ERROR_CODE",
      "message": "Error description",
      "location": "Part of the query with the error",
      "suggestion": "How to fix the error"
    }}
  ]
}}
If the query is valid, return an empty errors array.
"""

        start_time = time.time()
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Validate this SQL query: {sql}"}
                ],
                temperature=0.1,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )

            api_duration = time.time() - start_time
            logger.info(f"OpenAI API call for SQL validation took {api_duration:.2f} seconds")

            validation_result = json.loads(response.choices[0].message.content)
            return validation_result["is_valid"], validation_result.get("errors", [])

        except Exception as e:
            api_duration = time.time() - start_time
            logger.error(f"Error in SQL validation (after {api_duration:.2f} seconds): {str(e)}")
            return False, [{
                "code": "VALIDATION_ERROR",
                "message": f"Error validating SQL: {str(e)}",
                "location": None,
                "suggestion": "Please try a different query"
            }]

    async def explain_results(
            self,
            query: str,
            sql: str,
            results: List[Dict[str, Any]],
            tables_used: Optional[List[str]] = None,
            business_rules: Optional[List[str]] = None,
            schema_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate an educational natural language explanation of query results.

        Args:
            query: The original natural language query
            sql: The executed SQL query
            results: The query results
            tables_used: List of tables used in the query (optional)
            business_rules: List of business rules applied (optional)
            schema_info: Database schema information (optional)

        Returns:
            A natural language explanation of the results
        """
        # Format a sample of the results for the prompt
        results_sample = results[:5] if results else []
        results_str = json.dumps(results_sample, default=str, indent=2)
        total_rows = len(results)

        # If no tables_used provided, try to extract them
        if not tables_used:
            tables_used = self._extract_tables_from_sql(sql)

        # Format tables info if schema_info is provided
        tables_info = ""
        if schema_info and tables_used:
            tables_info = "Tables used in this query:\n"
            for table_name in tables_used:
                # Remove schema prefix if present
                clean_table = table_name.replace("eligibility.", "")
                if clean_table in schema_info:
                    table_info = schema_info[clean_table]
                    tables_info += f"- {table_name}: Contains "
                    tables_info += ", ".join([col["name"] for col in table_info.get("columns", [])[:5]])
                    tables_info += " and other fields\n"

        # Create an educational system prompt
        system_prompt = """You are an expert data educator who helps users understand database queries.
Your goal is to help users who may not understand the database structure or business rules.

For each query, explain:
1. The data organization (which tables were used and why)
2. The business rules and domain concepts applied (like what makes a member "active" or "overeligible")
3. How the natural language was interpreted and translated to SQL

Specific business rules to explain when relevant:
- Active members: A member is considered active when the current date is within their effective_range.
- Overeligibility: A person is overeligible if they have active member records in more than one organization with the same identity details.
- Verification status: Members can be verified through various methods, stored in the verification table.

Focus on being educational rather than just describing results. Help users understand the "why" behind the data.
"""

        start_time = time.time()
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"""
Original question: {query}
SQL query: {sql}
Total results: {total_rows}
{tables_info}
Business concepts applied: {', '.join(business_rules) if business_rules else 'None specifically detected'}
Sample results: {results_str}

Please provide an educational explanation that helps the user understand:
1. What data was queried and from where
2. What the results mean in business terms
3. Any business rules that were applied
4. How their natural language query was interpreted

Make your explanation helpful for someone who doesn't understand the database structure.
"""}
                ],
                temperature=0.7,
                max_tokens=500,  # Allow longer explanations for educational content
            )

            api_duration = time.time() - start_time
            logger.info(f"OpenAI API call for results explanation took {api_duration:.2f} seconds")

            return response.choices[0].message.content.strip()

        except Exception as e:
            api_duration = time.time() - start_time
            logger.error(f"Error generating results explanation (after {api_duration:.2f} seconds): {str(e)}")

            # Fallback explanation
            if not results:
                return f"Your query did not return any results. This might be because no data matches your search criteria. The query searched in the following tables: {', '.join(tables_used) if tables_used else 'the database'}."
            else:
                return f"Query returned {len(results)} results. This data comes from {', '.join(tables_used) if tables_used else 'the database'}."

    def _extract_tables_from_sql(self, sql: str) -> List[str]:
        """Extract table names from SQL query."""
        # Simple regex-based extraction
        # This is a simplified approach - a proper SQL parser would be more robust
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
        schema_str = self._format_schema_for_prompt(schema_info)

        system_prompt = f"""You are an expert SQL assistant that helps debug errors.

Here's the database schema:
{schema_str}

A user tried to run a query and encountered an error. Your task is to:
1. Explain the error in simple terms
2. Suggest how to fix the issue
3. Provide an example of a correct query if possible

Output your response in JSON format with the following structure:
{{
  "explanation": "Simple explanation of the error",
  "suggestion": "How to fix the error",
  "example_query": "Example of a corrected natural language query"
}}
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"""
Natural language query: {query}
Error message: {error}

Please help debug this error.
"""}
                ],
                temperature=0.3,
                max_tokens=800,
                response_format={"type": "json_object"}
            )

            error_help = json.loads(response.choices[0].message.content)

            return {
                "code": "QUERY_ERROR",
                "message": error,
                "explanation": error_help.get("explanation", "An error occurred when processing your query."),
                "suggestion": error_help.get("suggestion", "Please try a different query."),
                "example_query": error_help.get("example_query", None)
            }

        except Exception as e:
            logger.error(f"Error generating error explanation: {str(e)}")
            return {
                "code": "QUERY_ERROR",
                "message": error,
                "explanation": "An error occurred when processing your query.",
                "suggestion": "Please try simplifying your query or being more specific.",
                "example_query": None
            }

    def _format_schema_for_prompt(self, schema_info: Dict[str, Any]) -> str:
        """Format schema information for inclusion in a prompt."""
        schema_str = "Tables in the database:\n\n"

        for table_name, table_info in schema_info.items():
            schema_str += f"Table: eligibility.{table_name}\n"
            schema_str += "Columns:\n"

            for column in table_info["columns"]:
                nullable = "NULL" if column["nullable"] else "NOT NULL"
                schema_str += f"  - {column['name']} ({column['type']}, {nullable})\n"

                # Add special notes for important columns
                if table_name == "member" and column["name"] == "effective_range":
                    schema_str += "    NOTE: This column defines if a member is active. A member is active when CURRENT_DATE is within this range.\n"
                elif table_name == "organization" and column["name"] == "name":
                    schema_str += "    NOTE: This column contains the organization name, such as 'ACME Corporation' or 'Wayne Enterprises'.\n"

            if "foreign_keys" in table_info and table_info["foreign_keys"]:
                schema_str += "Foreign Keys:\n"
                for fk in table_info["foreign_keys"]:
                    schema_str += f"  - {fk['column']} references eligibility.{fk['foreign_table']}({fk['foreign_column']})\n"

            schema_str += "\n"

        # Add common SQL patterns section
        schema_str += "Common SQL Patterns:\n"
        schema_str += "1. Check if a member is active: member.effective_range @> CURRENT_DATE\n"
        schema_str += "2. Find members by organization name: member.organization_id = (SELECT id FROM eligibility.organization WHERE name ILIKE '%Organization Name%')\n"
        schema_str += "3. Count active members: COUNT(*) FROM eligibility.member WHERE effective_range @> CURRENT_DATE\n"
        schema_str += "4. Check for overeligibility: SELECT COUNT(DISTINCT organization_id) > 1 FROM eligibility.member WHERE first_name = 'John' AND last_name = 'Smith' AND date_of_birth = '1980-01-01' AND effective_range @> CURRENT_DATE\n"

        return schema_str

    def _clean_sql(self, sql: str) -> str:
        """Clean up SQL by removing markdown and code block formatting."""
        # Remove markdown code blocks if present
        sql = re.sub(r'^```sql\s+', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'^```postgres\s+', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'^```postgresql\s+', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'^```\s+', '', sql)
        sql = re.sub(r'\s+```$', '', sql)

        return sql.strip()

    async def _generate_explanation(self, query: str, sql: str) -> str:
        """Generate a natural language explanation of what the SQL query does."""
        system_prompt = """You are an expert SQL educator who explains SQL queries in simple terms.
Provide a brief explanation of what the given SQL query does in relation to the original question.
Keep your explanation concise and focus on the main purpose of the query.
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"""
Original question: {query}
SQL query: {sql}

Briefly explain what this SQL query does.
"""}
                ],
                temperature=0.7,
                max_tokens=150,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error generating SQL explanation: {str(e)}")
            return "This query attempts to answer your question by retrieving data from the database."