# app/services/prompt_builder.py
from typing import Dict, List, Any, Optional
import re


class PromptBuilder:
    """Service for dynamically building context-aware prompts."""

    def __init__(self):
        # Define instruction modules that can be conditionally included
        self.instruction_modules = {
            "active_status": """
Active members: A member is considered active when the current date is within their effective_range.
Always use the PostgreSQL operator '@>' to check this: WHERE effective_range @> CURRENT_DATE
""",

            "overeligibility": """
Overeligibility: A person is considered "overeligible" if they have active member records in 
more than one organization with the same first name, last name, and date of birth.
To check for overeligibility, use: 
SELECT COUNT(DISTINCT organization_id) > 1 FROM eligibility.member 
WHERE first_name = 'John' AND last_name = 'Smith' AND date_of_birth = '1980-01-01'
AND effective_range @> CURRENT_DATE
""",

            "verification_status": """
Verification Status: Users are considered "verified" or "enrolled" when:
1. They have a record in the verification table with verified_at IS NOT NULL
2. AND deactivated_at IS NULL (or deactivated_at > CURRENT_DATE)
3. AND they are linked via member_verification table to a member record

Example verification join pattern:
JOIN eligibility.member_verification mv ON m.id = mv.member_id
JOIN eligibility.verification v ON mv.verification_id = v.id
WHERE v.verified_at IS NOT NULL 
AND (v.deactivated_at IS NULL OR v.deactivated_at > CURRENT_DATE)
""",

            "organization_matching": """
Important for organization name matching:
1. When searching for an organization, use only the key distinctive part of the name
2. Extract just the company name without suffixes like "Corp", "Inc", "LLC", etc.
3. For a name like "Stark Corp" or "Stark Industries", search using just "Stark": name ILIKE '%stark%'
4. Always broaden the search terms to avoid missing results by using just the distinctive name part
5. Examples:
   - For "ACME Corporation" search with name ILIKE '%acme%'
   - For "Wayne Enterprises" search with name ILIKE '%wayne%'
   - For "Stark Industries" search with name ILIKE '%stark%'
""",

            "text_matching": """
Important patterns for matching text:
1. Always use wildcards with ILIKE for name matching: ILIKE '%name%' not ILIKE 'name'
2. For first/last names, use: first_name ILIKE '%james%' to match any name containing 'james'
3. For organization names, use: name ILIKE '%acme%' to match any name containing 'acme'
""",
"eligibility_records": """
Important: In this system, the term "eligibility records" always refers to member records.
When querying for eligibility records, use the member table and check effective_range for active status:
member.effective_range @> CURRENT_DATE
Do not use verification records to represent eligibility unless the query specifically asks for verification.
""",
        }

    def analyze_query(self, query: str) -> Dict[str, Any]:
        """Analyze query to determine intent and required modules."""
        query_lower = query.lower()

        # Detect intent
        intent = self._detect_intent(query_lower)

        # Determine required instruction modules
        modules = self._determine_required_modules(query_lower)

        # Always include text matching patterns
        if "text_matching" not in modules:
            modules.append("text_matching")

        return {
            "intent": intent,
            "required_modules": modules
        }

    def build_system_prompt(self,
                            query: str,
                            schema_str: str,
                            examples_str: str = "",
                            analysis: Optional[Dict[str, Any]] = None) -> str:
        """
        Build a dynamic system prompt incorporating schema and examples.

        Args:
            query: The user query
            schema_str: Formatted schema information (already processed)
            examples_str: Formatted examples (already processed)
            analysis: Analysis results or None to perform analysis
        """
        if not analysis:
            analysis = self.analyze_query(query)

        # Start with base prompt
        prompt_parts = [
            "You are an expert SQL assistant that generates PostgreSQL SQL queries.",
            "You are given a database schema and a natural language query.",
            "Your task is to convert the natural language into a valid SQL query."
        ]

        # Add schema information (already formatted)
        prompt_parts.append(f"Here's the database schema you're working with:\n{schema_str}")

        # Add examples if provided
        if examples_str:
            prompt_parts.append(examples_str)

        # Add intent-specific instructions
        if analysis["intent"]:
            prompt_parts.append(self._get_intent_instructions(analysis["intent"]))

        # Add relevant instruction modules
        for module in analysis["required_modules"]:
            if module in self.instruction_modules:
                prompt_parts.append(self.instruction_modules[module])

        # Add standard closing instructions
        prompt_parts.append("""
Generate ONLY SQL queries that query data, specifically SELECT statements.
Do not generate queries that modify data.
Ensure your SQL is valid PostgreSQL syntax.
All table names should be prefixed with the schema name, e.g., 'eligibility.member'.
Return only the SQL query as plain text, with no markdown formatting or explanations.
""")

        return "\n\n".join(prompt_parts)

    def _detect_intent(self, query: str) -> str:
        """Detect the primary intent of the query."""
        if any(x in query for x in ["how many", "count", "total", "number of"]):
            return "counting"
        elif any(x in query for x in ["list", "show", "get", "find", "display"]):
            return "listing"
        elif any(x in query for x in ["compare", "versus", "vs", "difference"]):
            return "comparing"
        elif any(x in query for x in ["is", "check if", "verify", "has", "have"]):
            return "verifying"
        return "general"

    def _determine_required_modules(self, query: str) -> List[str]:
        """Determine which instruction modules are relevant to the query."""
        modules = []

        # Check for active status references
        if any(term in query for term in ["active", "current", "eligible", "eligibility"]):
            modules.append("active_status")

        # Check for overeligibility references
        if any(term in query for term in ["overeligible", "multiple", "duplicate"]):
            modules.append("overeligibility")

        # Check for verification/enrollment concepts
        verification_terms = ["verify", "verified", "verification", "enrolled", "enrollment",
                              "validated", "users have", "people have", "members have"]
        if any(term in query for term in verification_terms):
            modules.append("verification_status")

        # Add organization matching when company-related terms appear
        company_suffixes = ["corp", "inc", "llc", "ltd", "corporation", "company",
                            "enterprises", "industries"]
        org_terms = ["from", "at", "in", "with", "organization", "company", "business"]

        # Check for organization-related queries
        if (any(suffix in query for suffix in company_suffixes) or
                any(term in query for term in org_terms)):
            modules.append("organization_matching")

        # Also try to detect organization names using NER patterns
        potential_org_pattern = r'(?:from|at|in|with)\s+([A-Z][a-z]+(?:\s+(?:Corp|Inc|LLC|Ltd|Corporation|Company|Enterprises|Industries))?)'
        org_matches = re.findall(potential_org_pattern, query)
        if org_matches:
            modules.append("organization_matching")

        return modules

    def _get_intent_instructions(self, intent: str) -> str:
        """Get intent-specific instructions."""
        instructions = {
            "counting": "This appears to be a counting query. Use COUNT() and consider grouping if needed.",
            "listing": "This appears to be a listing query. Consider what fields to include and use WHERE clauses to filter appropriately.",
            "comparing": "This appears to be a comparison query. Consider using GROUP BY with multiple metrics or conditional expressions.",
            "verifying": "This appears to be a verification query. Consider returning a boolean result or using EXISTS."
        }
        return instructions.get(intent, "")

    def format_examples_str(self, examples: List[Dict[str, Any]]) -> str:
        """Format examples for inclusion in the prompt."""
        if not examples or len(examples) == 0:
            return ""

        examples_str = "Here are examples of similar queries:\n\n"
        for i, example in enumerate(examples):
            examples_str += f"Example {i + 1}:\n"
            examples_str += f"Query: {example['natural_query']}\n"
            examples_str += f"SQL: {example['generated_sql']}\n\n"

        return examples_str