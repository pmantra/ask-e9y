"""Service for retrieving similar query examples."""

import json
import logging
from typing import List, Dict, Any, Optional

from app.services.embedding_service import EmbeddingService
from app.services.chroma_service import ChromaService

logger = logging.getLogger(__name__)


class ExampleRetrievalService:
    """Service for retrieving similar query examples."""

    def __init__(self, embedding_service: EmbeddingService, chroma_service: ChromaService):
        self.embedding_service = embedding_service
        self.chroma_service = chroma_service
        self.collection_name = "query_examples"

    async def find_similar_examples(
            self,
            query: str,
            tables: Optional[List[str]] = None,
            top_k: int = 2,
            similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Find examples similar to the given query.

        Args:
            query: The user query
            tables: Optional list of tables the query is about
            top_k: Number of examples to retrieve
            similarity_threshold: Minimum similarity threshold

        Returns:
            List of example objects
        """
        try:
            # Get collection
            collection = self.chroma_service.client.get_or_create_collection(
                name=self.collection_name
            )

            # Generate embedding for query
            query_embedding = await self.embedding_service.get_embedding(query)

            if not query_embedding:
                logger.warning("Could not generate embedding for query")
                return []

            # Prepare filter for tables if provided
            where_filter = {}
            if tables:
                # Find examples involving any of these tables
                where_filter = {
                    "is_example": {"$eq": True}  # Only match examples
                }

            # Query for similar examples
            n_results = top_k * 3 if tables else top_k  # Get 3x more results when filtering by tables
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter if where_filter else None,
                include=["metadatas", "distances"]
            )

            # Process results with improved logging
            examples = []
            similarity_scores = []

            # First, collect all similarity scores for logging
            if results["metadatas"] and len(results["metadatas"]) > 0:
                for i, metadata in enumerate(results["metadatas"][0]):
                    distance = results["distances"][0][i] if i < len(results["distances"][0]) else 1.0
                    similarity = 1.0 - distance
                    query_text = metadata.get("natural_query", "")
                    similarity_scores.append((query_text, similarity))

            # Sort and log the top similarity scores
            sorted_scores = sorted(similarity_scores, key=lambda x: x[1], reverse=True)
            top_scores = sorted_scores[:min(5, len(sorted_scores))]
            score_str = ", ".join([f'"{q[:30]}...": {s:.3f}' for q, s in top_scores])
            logger.debug(f"Top example similarities: {score_str}")

            # Infer query type to boost relevant examples
            query_type = self._infer_query_type(query)
            logger.debug(f"Inferred query type: {query_type}")

            # Process results to find matching examples
            if results["metadatas"] and len(results["metadatas"]) > 0:
                matched_count = 0
                for i, metadata in enumerate(results["metadatas"][0]):
                    # Calculate base similarity
                    distance = results["distances"][0][i] if i < len(results["distances"][0]) else 1.0
                    similarity = 1.0 - distance

                    # Apply boost for matching query type
                    metadata_query_type = metadata.get("query_type", "")
                    if metadata_query_type == query_type:
                        boost = 0.1
                        similarity += boost
                        logger.debug(f"Boosting example similarity by {boost} for matching query type: {query_type}")

                    if similarity >= similarity_threshold:
                        # Parse JSON fields
                        table_list = json.loads(metadata.get("tables", "[]"))
                        business_concepts = json.loads(metadata.get("business_concepts", "[]"))

                        # Skip if tables filter is provided and there's no match
                        if tables and not any(table in table_list for table in tables):
                            continue

                        examples.append({
                            "natural_query": metadata.get("natural_query", ""),
                            "generated_sql": metadata.get("generated_sql", ""),
                            "explanation": metadata.get("explanation", ""),
                            "tables": table_list,
                            "business_concepts": business_concepts,
                            "query_type": metadata.get("query_type", ""),
                            "similarity": similarity
                        })
                        matched_count += 1

                        # Stop once we have enough examples
                        if matched_count >= top_k:
                            break

            # Log the final selection results
            if examples:
                example_str = ", ".join([f'"{e["natural_query"][:30]}...": {e["similarity"]:.3f}' for e in examples])
                logger.info(f"Selected examples with similarities: {example_str}")
            else:
                logger.info(f"No examples found above threshold {similarity_threshold}")

            # Consider adding adaptive threshold similar to schema selection
            if not examples and similarity_scores:
                best_score = sorted_scores[0][1]
                adaptive_threshold = max(0.5, best_score * 0.8)  # Higher minimum for examples

                if adaptive_threshold < similarity_threshold:
                    logger.info(f"Using adaptive threshold {adaptive_threshold:.3f} for example selection")

                    # Try again with adaptive threshold
                    for query_text, similarity in sorted_scores:
                        if similarity >= adaptive_threshold:
                            for i, metadata in enumerate(results["metadatas"][0]):
                                if metadata.get("natural_query", "") == query_text:
                                    # Get the metadata and add the example
                                    # (Similar code as above, but with the adaptive threshold)
                                    # You may want to refactor this into a function to avoid duplication
                                    table_list = json.loads(metadata.get("tables", "[]"))
                                    business_concepts = json.loads(metadata.get("business_concepts", "[]"))

                                    # Skip if tables filter is provided and there's no match
                                    if tables and not any(table in table_list for table in tables):
                                        continue

                                    examples.append({
                                        "natural_query": query_text,
                                        "generated_sql": metadata.get("generated_sql", ""),
                                        "explanation": metadata.get("explanation", ""),
                                        "tables": table_list,
                                        "business_concepts": business_concepts,
                                        "query_type": metadata.get("query_type", ""),
                                        "similarity": similarity
                                    })
                                    break

                        if len(examples) >= top_k:
                            break

                    if examples:
                        example_str = ", ".join(
                            [f'"{e["natural_query"][:30]}...": {e["similarity"]:.3f}' for e in examples])
                        logger.info(f"Selected examples using adaptive threshold: {example_str}")

            return examples
        except Exception as e:
            logger.error(f"Error finding similar examples: {str(e)}")
            return []

    def _infer_query_type(self, query: str) -> str:
        """Infer the type of query from text patterns."""
        query_lower = query.lower()

        # Eligibility/active status queries
        if ("active" in query_lower and "eligibility" in query_lower) or "effective_range" in query_lower:
            if any(x in query_lower for x in ["how many", "count", "number"]):
                return "count_aggregate"
            return "boolean_check"

        # Verification/enrollment queries
        if any(term in query_lower for term in ["enrolled", "verified", "verification"]):
            if any(x in query_lower for x in ["how many", "count", "number"]):
                return "count_aggregate"
            return "verification_check"

        # Check for count/aggregate patterns
        if any(x in query_lower for x in ["how many", "count", "total", "number of"]):
            return "count_aggregate"

        # Check for comparison patterns
        elif any(x in query_lower for x in ["compare", "versus", "vs", "difference between", "percentage"]):
            if "rate" in query_lower:
                return "analytical_percentage"
            return "comparative_count"

        # Check for list/retrieval patterns
        elif any(x in query_lower for x in ["list", "show", "display", "all", "find"]):
            if "overeligible" in query_lower:
                return "complex_aggregate"
            return "retrieval"

        # Check for boolean/check patterns
        elif any(x in query_lower for x in ["is", "has", "does", "check if"]):
            return "boolean_check"

        # Check for specific business concepts
        elif "overeligible" in query_lower:
            if "list" in query_lower or "show" in query_lower:
                return "complex_aggregate"
            return "boolean_check"

        # Default case
        return "general"