"""Service for Chroma vector database operations."""

import logging
import chromadb
import hashlib
from typing import List, Optional, Dict, Any, Union

logger = logging.getLogger(__name__)


class ChromaService:
    """Service for handling vector operations with Chroma DB."""

    def __init__(self, persist_directory="./chroma_db"):
        """Initialize the Chroma client."""
        self.client = chromadb.PersistentClient(path=persist_directory)

        # Create or get the collection for query cache
        self.collection = self.client.get_or_create_collection(
            name="query_cache",
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )
        logger.info(f"Initialized Chroma collection 'query_cache' with {self.collection.count()} entries")

    def get_query_id(self, query_text: str) -> str:
        """Generate a consistent ID for a query."""
        return hashlib.md5(query_text.encode()).hexdigest()

    # In app/services/chroma_service.py

    async def find_similar_query(
            self,
            embedding: List[float],
            similarity_threshold: float = 0.85
    ) -> Optional[Dict[str, Any]]:
        """Find a similar query using vector similarity."""
        try:
            logger.debug(f"Searching for similar queries with threshold: {similarity_threshold}")
            # Query the collection
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=1,
                include=["metadatas", "distances"]
            )

            # Log detailed results
            logger.debug(f"Chroma search results: {results}")

            # Check if we have results and if the similarity is high enough
            if (results["metadatas"] and
                    len(results["metadatas"]) > 0 and
                    len(results["metadatas"][0]) > 0 and
                    results["distances"] and
                    len(results["distances"]) > 0 and
                    len(results["distances"][0]) > 0):

                # Convert distance to similarity (Chroma returns distance, not similarity)
                distance = results["distances"][0][0]
                similarity = 1 - distance
                logger.debug(f"Best match similarity: {similarity} (distance: {distance})")

                if similarity >= similarity_threshold:
                    metadata = results["metadatas"][0][0]
                    if "query_id" not in metadata and results["ids"] and len(results["ids"]) > 0:
                        metadata["original_query_id"] = results["ids"][0][0]
                    logger.info(f"Found similar query with similarity: {similarity}")
                    return metadata
                else:
                    logger.debug(f"Best match similarity {similarity} below threshold {similarity_threshold}")

            return None
        except Exception as e:
            logger.error(f"Error in Chroma similarity search: {str(e)}", exc_info=True)
            return None

    async def store_query(
            self,
            query_text: str,
            embedding: List[float],
            sql: str,
            explanation: Optional[str],
            execution_time_ms: float,
            query_id: Optional[str] = None
    ) -> bool:
        """Store a query in the vector database."""
        try:
            # Generate query ID if not provided
            if not query_id:
                query_id = self.get_query_id(query_text)

            # Store metadata with the embedding
            metadata = {
                "natural_query": query_text,
                "generated_sql": sql,
                "explanation": explanation or "",  # Convert None to empty string
                "execution_time_ms": execution_time_ms,
                "usage_count": 1,
                "last_used_timestamp": self._get_current_timestamp(),
                "query_id": query_id  # Store the query ID in metadata
            }

            # Upsert the document
            self.collection.upsert(
                ids=[query_id],
                embeddings=[embedding],
                metadatas=[metadata]
            )

            return True
        except Exception as e:
            logger.error(f"Error storing query in Chroma: {str(e)}")
            return False

    async def update_usage(self, query_text: str) -> bool:
        """Update usage statistics for a query."""
        try:
            query_id = self.get_query_id(query_text)

            # Get current metadata
            results = self.collection.get(
                ids=[query_id],
                include=["metadatas"]
            )

            if results["metadatas"] and len(results["metadatas"]) > 0:
                metadata = results["metadatas"][0]

                # Update usage count and timestamp
                metadata["usage_count"] = metadata.get("usage_count", 0) + 1
                metadata["last_used_timestamp"] = self._get_current_timestamp()

                # Update metadata
                self.collection.update(
                    ids=[query_id],
                    metadatas=[metadata]
                )

                return True

            return False
        except Exception as e:
            logger.error(f"Error updating usage in Chroma: {str(e)}")
            return False

    def get_query_by_id(self, query_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a query by its ID."""
        try:
            # Query collection by ID
            results = self.collection.get(
                ids=[query_id],
                include=["metadatas"]
            )

            if results["metadatas"] and len(results["metadatas"]) > 0:
                return results["metadatas"][0]

            # If not found by direct ID, try searching through metadata
            all_entries = self.collection.get(
                include=["metadatas", "documents", "embeddings"]
            )

            for i, metadata in enumerate(all_entries["metadatas"]):
                if metadata.get("query_id") == query_id:
                    return metadata

            return None
        except Exception as e:
            logger.error(f"Error retrieving query by ID: {str(e)}")
            return None

    async def update_explanation(self, query_id: str, explanation: str) -> bool:
        """Update the explanation for a query."""
        try:
            # Get current metadata
            results = self.collection.get(
                ids=[query_id],
                include=["metadatas"]
            )

            if results["metadatas"] and len(results["metadatas"]) > 0:
                metadata = results["metadatas"][0]

                # Update explanation
                metadata["explanation"] = explanation

                # Update metadata
                self.collection.update(
                    ids=[query_id],
                    metadatas=[metadata]
                )

                return True

            # If not found by direct ID, try searching through metadata
            all_entries = self.collection.get(
                include=["metadatas", "documents", "embeddings"]
            )

            for i, metadata in enumerate(all_entries["metadatas"]):
                if metadata.get("query_id") == query_id:
                    doc_id = all_entries["ids"][i]
                    metadata["explanation"] = explanation

                    self.collection.update(
                        ids=[doc_id],
                        metadatas=[metadata]
                    )

                    return True

            return False
        except Exception as e:
            logger.error(f"Error updating explanation: {str(e)}")
            return False

    def _get_current_timestamp(self) -> int:
        """Get current timestamp in seconds."""
        import time
        return int(time.time())