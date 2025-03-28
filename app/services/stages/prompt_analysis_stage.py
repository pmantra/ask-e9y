import logging
import hashlib
import json
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class PromptAnalysisStage:
    """Stage for analyzing queries and generating context-aware prompts."""

    def __init__(self, prompt_builder, embedding_service, chroma_service):
        self.prompt_builder = prompt_builder
        self.embedding_service = embedding_service
        self.chroma_service = chroma_service
        self.collection_name = "prompt_cache"
    
    async def execute(self, context, db_session):
        """Execute the prompt analysis stage."""
        # Skip if we already have SQL from cache
        if context.sql:
            logger.info("SQL already in context, skipping prompt analysis")
            return {"skipped": True}
            
        context.start_stage("prompt_analysis")
        
        query = context.original_query
        
        # Note: We don't fetch schema_info here, as SQLGenerationStage already does this
        # We'll simply analyze the query and prepare to enhance the prompt later
        
        # Create a placeholder for schema fingerprint
        # This will be filled in later when we have schema_info
        context.metadata["schema_fingerprint"] = "(pending)"
        
        # Perform query analysis
        query_analysis = self.prompt_builder.analyze_query(query)
        
        # Store analysis in context for use by SQLGenerationStage
        context.metadata["query_analysis"] = query_analysis
        
        # For now, mark as pending prompt generation
        # The actual prompt will be generated in SQLGenerationStage after schema selection
        context.metadata["prompt_status"] = "pending"
        
        context.complete_stage("prompt_analysis", {"analysis": query_analysis})
        return {"analysis": query_analysis}
    
    async def lookup_cached_prompt(self, query: str, schema_fingerprint: str, 
                                  context) -> Dict[str, Any]:
        """Look up a prompt in the cache - called by SQLGenerationStage."""
        try:
            # Skip cache if not enabled
            if not context.metadata.get("enable_prompt_cache", True):
                return {"cache_hit": False}
                
            normalized_query = self._normalize_query(query)
                
            # Generate embedding for semantic search
            embedding = await self.embedding_service.get_embedding(normalized_query)
            
            if not embedding:
                return {"cache_hit": False}
            
            try:
                # Get or create collection
                collection = self.chroma_service.client.get_or_create_collection(
                    name=self.collection_name
                )
                
                # Add schema fingerprint filter
                filter_criteria = {"schema_fingerprint": schema_fingerprint}
                
                # Search for similar prompts
                results = collection.query(
                    query_embeddings=[embedding],
                    n_results=1,
                    where=filter_criteria,
                    include=["metadatas", "distances"]
                )
                
                # Check if we have valid results with proper structure
                if (results and 
                    "metadatas" in results and 
                    "distances" in results and
                    results["metadatas"] and 
                    len(results["metadatas"]) > 0 and
                    results["distances"] and 
                    len(results["distances"]) > 0 and
                    len(results["distances"][0]) > 0):
                    
                    distance = results["distances"][0][0]
                    similarity = 1 - distance
                    
                    # Use a threshold for semantic matching
                    if similarity >= 0.85:
                        metadata = results["metadatas"][0][0]
                        logger.info(f"Prompt cache hit with similarity {similarity:.3f}")
                        return {
                            "cache_hit": True,
                            "prompt": metadata["prompt"],
                            "cache_type": "semantic",
                            "token_count": metadata.get("token_count", 0),
                            "embedding": embedding  # Return embedding for possible storage
                        }
                else:
                    logger.debug("No matching prompts found in cache")
            except Exception as e:
                logger.warning(f"Error in semantic prompt lookup: {str(e)}")
            
            # No cache hit
            logger.info("Prompt cache miss")
            return {
                "cache_hit": False,
                "embedding": embedding  # Return embedding for storage
            }
        except Exception as e:
            logger.error(f"Error in prompt cache lookup: {str(e)}")
            context.add_error("prompt_cache_lookup", e)
            return {"cache_hit": False}
    
    async def store_prompt_in_cache(self, query: str, prompt: str, 
                                  schema_fingerprint: str, token_count: int,
                                  embedding=None):
        """Store a prompt in the cache."""
        try:
            # Get or generate embedding
            if not embedding:
                normalized_query = self._normalize_query(query)
                embedding = await self.embedding_service.get_embedding(normalized_query)
            
            if embedding:
                # Store in vector cache
                try:
                    collection = self.chroma_service.client.get_or_create_collection(
                        name=self.collection_name
                    )
                    
                    # Create a unique ID
                    cache_key = f"prompt:{self._hash_text(query)}:{schema_fingerprint}"
                    
                    collection.upsert(
                        ids=[cache_key],
                        embeddings=[embedding],
                        metadatas=[{
                            "query": query,
                            "prompt": prompt,
                            "schema_fingerprint": schema_fingerprint,
                            "token_count": token_count,
                            "timestamp": self._get_current_timestamp()
                        }]
                    )
                    
                    logger.info(f"Stored prompt in cache with key {cache_key[:15]}...")
                    return True
                except Exception as e:
                    logger.warning(f"Error storing prompt in vector cache: {str(e)}")
            
            return False
        except Exception as e:
            logger.error(f"Error storing prompt in cache: {str(e)}")
            return False
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query for caching purposes."""
        return " ".join(query.lower().split())
    
    def _hash_text(self, text: str) -> str:
        """Create a hash of the text."""
        return hashlib.md5(text.encode()).hexdigest()
    
    def _get_current_timestamp(self) -> int:
        """Get current timestamp in seconds."""
        import time
        return int(time.time())