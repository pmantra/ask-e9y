# app/services/prompt_analyzer.py
import json
import re
from typing import Dict, Any, List, Optional


class PromptAnalyzer:
    """Service for analyzing and visualizing prompts."""

    def analyze_prompt(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Analyze a prompt and extract key metrics."""
        analysis = {
            "total_length": len(system_prompt) + len(user_prompt),
            "system_length": len(system_prompt),
            "user_length": len(user_prompt),
            "estimated_tokens": self._estimate_token_count(system_prompt + user_prompt),
            "schema_tables": self._extract_tables(system_prompt),
            "schema_table_count": len(self._extract_tables(system_prompt)),
            "includes_examples": "Here are examples" in system_prompt
        }

        return analysis

    def _estimate_token_count(self, text: str) -> int:
        """Estimate token count (rough approximation)."""
        # A very rough approximation - ~4 chars per token
        return len(text) // 4

    def _extract_tables(self, system_prompt: str) -> List[str]:
        """Extract table names from the schema section of a prompt."""
        tables = []

        # Look for table definitions in the schema
        table_pattern = r"Table:\s+eligibility\.([a-zA-Z_]+)"
        tables = re.findall(table_pattern, system_prompt)

        return tables

    def compare_prompts(self, before_prompt: Dict[str, str], after_prompt: Dict[str, str]) -> Dict[str, Any]:
        """Compare two prompts and identify differences."""
        before_analysis = self.analyze_prompt(before_prompt.get("system", ""), before_prompt.get("user", ""))
        after_analysis = self.analyze_prompt(after_prompt.get("system", ""), after_prompt.get("user", ""))

        comparison = {
            "token_reduction": before_analysis["estimated_tokens"] - after_analysis["estimated_tokens"],
            "token_reduction_percent": round(
                (1 - after_analysis["estimated_tokens"] / before_analysis["estimated_tokens"]) * 100, 2) if
            before_analysis["estimated_tokens"] > 0 else 0,
            "table_reduction": before_analysis["schema_table_count"] - after_analysis["schema_table_count"],
            "before": before_analysis,
            "after": after_analysis,
        }

        return comparison