"""Service for managing schema embeddings and schema selection based on query relevance."""

import logging
import time
import re
from typing import Dict, List, Any, Optional, Tuple

from app.services.embedding_service import EmbeddingService
from app.services.chroma_service import ChromaService

logger = logging.getLogger(__name__)


class SchemaEmbeddingService:
    """Service for managing schema embeddings and selection."""

    def __init__(self, embedding_service: EmbeddingService, chroma_service: ChromaService):
        self.embedding_service = embedding_service
        self.chroma_service = chroma_service
        self._embedding_cache = {}  # In-memory cache
        self._last_refresh = 0
        self.cache_ttl = 3600  # 1 hour cache lifetime
        self.collection_name = "schema_embeddings"
        self._query_table_cache = {}  # Cache for recent query->tables mappings
        self._query_cache_size = 100  # Limit cache size
        self._query_cache_ttl = 300  # 5 minutes TTL for query cache

    async def generate_schema_embeddings(self, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate embeddings for all tables and columns in the schema.

        Args:
            schema_info: The database schema information

        Returns:
            Dictionary mapping table names to their embeddings
        """
        schema_embeddings = {}

        for table_name, table_info in schema_info.items():
            # Create a descriptive text for the table
            table_text = f"Table: {table_name}. "

            # Add column information
            column_descriptions = []
            for column in table_info.get("columns", []):
                column_desc = f"Column: {column['name']} ({column['type']})"
                column_descriptions.append(column_desc)

            table_text += " ".join(column_descriptions)

            # Add foreign key information
            for fk in table_info.get("foreign_keys", []):
                table_text += f" Foreign key: {fk['column']} references {fk['foreign_table']}.{fk['foreign_column']}."

            # Add any schema metadata if available
            if "description" in table_info:
                table_text += f" Description: {table_info['description']}"

            # Generate embedding for this table
            table_embedding = await self.embedding_service.get_embedding(table_text)

            if table_embedding:
                schema_embeddings[table_name] = {
                    "embedding": table_embedding,
                    "text": table_text
                }

        return schema_embeddings

    async def store_schema_embeddings(self, schema_embeddings: Dict[str, Any]) -> bool:
        """
        Store schema embeddings in Chroma.

        Args:
            schema_embeddings: Dict mapping table names to embeddings

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create or get the collection for schema embeddings
            collection = self.chroma_service.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )

            # Prepare data for batch insertion
            ids = []
            embeddings = []
            metadatas = []

            for table_name, data in schema_embeddings.items():
                ids.append(f"table_{table_name}")
                embeddings.append(data["embedding"])
                metadatas.append({
                    "table_name": table_name,
                    "description": data["text"],
                    "type": "table"
                })

            # Upsert into Chroma
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas
            )

            # Update cache
            self._embedding_cache = {table_name: data["embedding"] for table_name, data in schema_embeddings.items()}
            self._last_refresh = time.time()

            return True
        except Exception as e:
            logger.error(f"Error storing schema embeddings: {str(e)}")
            return False

    async def build_schema_embeddings(self, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build and store embeddings for the database schema.

        Args:
            schema_info: Schema information dictionary

        Returns:
            Dictionary with operation results
        """
        # Generate embeddings
        schema_embeddings = await self.generate_schema_embeddings(schema_info)

        # Store in Chroma
        store_result = await self.store_schema_embeddings(schema_embeddings)

        return {
            "tables_processed": len(schema_embeddings),
            "storage_success": store_result
        }

    # Update the check in load_all_embeddings method
    async def load_all_embeddings(self):
        """Load all table embeddings into the cache."""
        try:
            # Get the schema embeddings collection
            collection = self.chroma_service.client.get_or_create_collection(
                name=self.collection_name
            )

            # Get all embeddings
            results = collection.get(
                include=["embeddings", "metadatas"]
            )

            # Update cache - Fix the condition that's causing the numpy array boolean context issue
            if (results["ids"] is not None and len(results["ids"]) > 0 and
                    results["embeddings"] is not None and len(results["embeddings"]) > 0 and
                    results["metadatas"] is not None and len(results["metadatas"]) > 0):

                self._embedding_cache = {}
                for i, table_id in enumerate(results["ids"]):
                    # Extract table name from ID (remove 'table_' prefix)
                    table_name = results["metadatas"][i]["table_name"]
                    self._embedding_cache[table_name] = results["embeddings"][i]

                self._last_refresh = time.time()
                logger.info(f"Loaded {len(self._embedding_cache)} table embeddings into cache")
                return True

            return False
        except Exception as e:
            logger.error(f"Error loading schema embeddings: {str(e)}")
            return False

    def _calculate_similarity(self, vec1, vec2):
        """Calculate cosine similarity between two vectors."""
        import numpy as np

        # Convert to numpy arrays if they aren't already
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)

        # Calculate dot product
        dot_product = np.dot(vec1, vec2)

        # Calculate norms
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        # Avoid division by zero
        if norm1 == 0 or norm2 == 0:
            return 0

        # Calculate cosine similarity
        return float(dot_product / (norm1 * norm2))

    async def find_relevant_tables(self, query: str, threshold: float = 0.7, max_tables: int = 5) -> List[
        Tuple[str, float]]:
        """
        Find tables relevant to the given query.

        Args:
            query: The user query
            threshold: Minimum similarity threshold
            max_tables: Maximum number of tables to return

        Returns:
            List of (table_name, similarity_score) tuples
        """
        # Try cache first
        normalized_query = self._normalize_query_for_cache(query)

        # Check if we have a cached result that's still valid
        if normalized_query in self._query_table_cache:
            cache_entry = self._query_table_cache[normalized_query]
            cache_time, cache_result = cache_entry

            # Check if cache is still valid
            if (time.time() - cache_time) < self._query_cache_ttl:
                logger.debug(f"Using cached table selection for similar query")
                return cache_result
            else:
                # Cache expired, remove it
                del self._query_table_cache[normalized_query]

        # Ensure cache is fresh
        if not self._embedding_cache or (time.time() - self._last_refresh > self.cache_ttl):
            cache_loaded = await self.load_all_embeddings()
            if not cache_loaded:
                logger.warning("Could not load embeddings, falling back to empty result")
                return []

        # Direct pattern matching pre-check
        direct_matches = self._direct_pattern_match(query)
        if direct_matches:
            logger.info(f"Found direct pattern matches: {', '.join(table for table, _ in direct_matches)}")
            return direct_matches
        
        # Generate embedding for the query
        query_embedding = await self.embedding_service.get_embedding(query)
        if not query_embedding:
            logger.warning("Could not generate embedding for query")
            return []

        # Calculate similarity with each table, with keyword boosting
        all_similarities = []
        query_lower = query.lower()

        # List of common business terms and their relevant tables
        business_terms = {
            # File-related terms
            "file": ["file"],
            "files": ["file"],
            "upload": ["file"],
            "process": ["file"],

            # Member-related terms
            "member": ["member"],
            "members": ["member"],
             "email": ["member"],  
            "emails": ["member"],
            "eligibility": ["member"],  # Eligibility records are in member table
            "eligible": ["member"],
            "records": ["member"],  # Often refers to member records

            # Verification-related terms
            "verification": ["verification", "verification_attempt", "member_verification"],
            "verify": ["verification", "verification_attempt", "member_verification"],
            "enrolled": ["verification", "member_verification"],  # Enrollment implies verification
            "users": ["verification", "member"],  # "Users" can refer to verified members

            # Organization-related terms
            "organization": ["organization"],
            "company": ["organization"],
            "corp": ["organization"],

            # Status-related terms
            "active": ["member"],  # Active status refers to effective_range in member
            "effective": ["member"],
            "status": ["member", "verification"]
        }

        # Identify business terms in query
        matched_terms = set()
        for term, tables in business_terms.items():
            if term in query_lower:
                matched_terms.update(tables)

        logger.debug(f"Detected business terms: {matched_terms}")

        for table_name, table_embedding in self._embedding_cache.items():
            # Base similarity from embeddings
            similarity = self._calculate_similarity(query_embedding, table_embedding)

            # Apply keyword boosting for exact table mentions
            if table_name.lower() in query_lower:
                boost = 0.3
                logger.debug(f"Boosting {table_name} by {boost} due to exact mention")
                similarity += boost

            # Apply boosting for business terms
            elif table_name in matched_terms:
                boost = 0.2
                logger.debug(f"Boosting {table_name} by {boost} due to business term match")
                similarity += boost

            all_similarities.append((table_name, similarity))

        # Sort all similarities (for debugging and adaptive threshold)
        sorted_similarities = sorted(all_similarities, key=lambda x: x[1], reverse=True)

        # Log all similarities for debugging
        similarity_str = ", ".join([f"{t}:{s:.3f}" for t, s in sorted_similarities[:10]])
        logger.debug(f"Top 10 table similarities: {similarity_str}")

        # Filter by threshold and get top tables
        filtered_similarities = [(t, s) for t, s in sorted_similarities if s >= threshold]

        # If no tables meet the threshold, use adaptive threshold to get at least the most relevant ones
        if not filtered_similarities and sorted_similarities:
            # Use top tables with 80% of max similarity
            adaptive_threshold = max(0.4, sorted_similarities[0][1] * 0.8)
            filtered_similarities = [(t, s) for t, s in sorted_similarities if s >= adaptive_threshold]
            logger.info(f"Using adaptive threshold {adaptive_threshold:.3f} for table selection")

            # Ensure we get at least one table
            if not filtered_similarities:
                top_tables = sorted_similarities[:max(2, max_tables // 2)]
                logger.info(f"Falling back to top {len(top_tables)} tables regardless of threshold")
                filtered_similarities = top_tables

        # Apply max_tables limit
        result = filtered_similarities[:max_tables]

        # Log the selected tables
        if result:
            selected_tables = ", ".join([f"{t}:{s:.3f}" for t, s in result])
            logger.info(f"Selected tables with similarities: {selected_tables}")
        else:
            logger.warning("No tables selected after all fallback strategies")

        if len(self._query_table_cache) >= self._query_cache_size:
            # Find oldest entry to remove (LRU-like behavior)
            oldest_key = min(self._query_table_cache.keys(),
                             key=lambda k: self._query_table_cache[k][0])
            del self._query_table_cache[oldest_key]

        # Store with current timestamp
        self._query_table_cache[normalized_query] = (time.time(), result)

        return result

    async def get_selective_schema(self, query: str, schema_info: Dict[str, Any],
                                   threshold: float = 0.7, max_tables: int = 5,
                                   include_related: bool = True) -> Dict[str, Any]:
        """
        Get a subset of the schema based on query relevance.

        Args:
            query: The user query
            schema_info: Complete schema information
            threshold: Similarity threshold
            max_tables: Maximum number of direct matches to include
            include_related: Whether to include related tables

        Returns:
            Filtered schema with only relevant tables
        """
        relevant_tables = await self.find_relevant_tables(query, threshold, max_tables)

        if not relevant_tables:
            logger.info("No relevant tables found, returning full schema")
            return schema_info

        # Extract table names
        table_names = [table for table, _ in relevant_tables]
        logger.info(f"Found relevant tables: {', '.join(table_names)}")

        # Create filtered schema
        filtered_schema = {}
        for table_name, similarity in relevant_tables:
            if table_name in schema_info:
                filtered_schema[table_name] = schema_info[table_name]

        # Add special handling for business concepts
        query_lower = query.lower()

        # Special handling for overeligibility queries
        if "overeligible" in query_lower or "overeligibility" in query_lower:
            critical_tables = ["member", "organization"]
            for table in critical_tables:
                if table not in filtered_schema and table in schema_info:
                    filtered_schema[table] = schema_info[table]
                    logger.info(f"Added {table} table due to overeligibility concept detection")

        # Special handling for eligibility/active status queries
        if any(term in query_lower for term in ["active", "eligibility", "eligible", "effective"]):
            critical_tables = ["member"]
            if any(org_term in query_lower for org_term in ["corp", "organization", "company", "acme"]):
                critical_tables.append("organization")

            for table in critical_tables:
                if table not in filtered_schema and table in schema_info:
                    filtered_schema[table] = schema_info[table]
                    logger.info(f"Added {table} table due to eligibility concept detection")

        # Special handling for verification/enrollment queries
        if any(term in query_lower for term in ["enrolled", "verified", "verification", "users"]):
            critical_tables = ["member", "verification", "member_verification"]
            if any(org_term in query_lower for org_term in ["corp", "organization", "company", "acme"]):
                critical_tables.append("organization")

            for table in critical_tables:
                if table not in filtered_schema and table in schema_info:
                    filtered_schema[table] = schema_info[table]
                    logger.info(f"Added {table} table due to enrollment/verification concept detection")

        # Special handling for file processing queries
        if any(term in query_lower for term in ["file", "files", "processed", "upload"]):
            critical_tables = ["file"]
            for table in critical_tables:
                if table not in filtered_schema and table in schema_info:
                    filtered_schema[table] = schema_info[table]
                    logger.info(f"Added {table} table due to file processing concept detection")

        # Add related tables if requested
        if include_related:
            # Create a copy to avoid modifying while iterating
            original_tables = list(filtered_schema.keys())
            for table_name in original_tables:
                # Add tables referenced by foreign keys
                for fk in schema_info.get(table_name, {}).get("foreign_keys", []):
                    foreign_table = fk["foreign_table"]
                    if foreign_table not in filtered_schema and foreign_table in schema_info:
                        filtered_schema[foreign_table] = schema_info[foreign_table]
                        logger.debug(f"Added {foreign_table} as it's referenced by {table_name}")

                # Add tables that reference this table
                for potential_referencing_table, table_info in schema_info.items():
                    if potential_referencing_table not in filtered_schema:
                        for fk in table_info.get("foreign_keys", []):
                            if fk["foreign_table"] == table_name:
                                filtered_schema[potential_referencing_table] = table_info
                                logger.debug(f"Added {potential_referencing_table} as it references {table_name}")
                                break

        # Log the final table selection
        logger.info(f"Final schema includes {len(filtered_schema)} tables: {', '.join(filtered_schema.keys())}")
        return filtered_schema

    def _normalize_query_for_cache(self, query: str) -> str:
        """Normalize a query for caching purposes."""
        # Remove extra whitespace, lowercase
        normalized = " ".join(query.lower().split())
        return normalized

    def _direct_pattern_match(self, query: str) -> List[Tuple[str, float]]:
        """Use direct pattern matching to find relevant tables."""
        query_lower = query.lower()
        matches = []
        
        # Define direct mapping patterns
        patterns = {
            # Table-specific patterns with high confidence scores
            "member": [
                (r"\bemail", 0.95),               # Any mention of email
                (r"\bname", 0.85),                # Any mention of name
                (r"\bmember", 0.95),              # Direct mention
                (r"find .{0,20}\bpeople", 0.85),  # Finding people
                (r"show .{0,20}\buser", 0.85),    # Showing users
            ],
            "organization": [
                (r"\bcompany", 0.95),             # Company mentions
                (r"\bcorp", 0.95),                # Corp mentions
                (r"\borganization", 0.95),        # Direct mention
                (r"\bindustries", 0.90),          # Industries suffix
                (r"\benterprise", 0.90),          # Enterprise mentions
            ],
            "verification": [
                (r"\bverif", 0.95),               # verification/verified
                (r"\benroll", 0.95),              # enrollment/enrolled
                (r"\bvalid", 0.90),               # validation/validated
            ],
        }
        
        # Check each pattern for matches
        for table, table_patterns in patterns.items():
            for pattern, confidence in table_patterns:
                if re.search(pattern, query_lower):
                    matches.append((table, confidence))
                    # Don't break, collect all matches
        
        # Add common combinations
        if any(table == "organization" for table, _ in matches) and "email" in query_lower:
            if not any(table == "member" for table, _ in matches):
                matches.append(("member", 0.9))  # If asking about org + email, include member
        
        # Return unique tables with highest confidence
        unique_matches = {}
        for table, confidence in matches:
            if table not in unique_matches or confidence > unique_matches[table]:
                unique_matches[table] = confidence
        
        return [(table, conf) for table, conf in unique_matches.items()]
