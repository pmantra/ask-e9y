"""Service for generating and managing text embeddings."""

import logging
import time
from typing import List, Optional

from openai import AsyncOpenAI
from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating and managing text embeddings."""

    def __init__(self):
        """Initialize the embedding service."""
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.embedding_model = "text-embedding-3-small"  # Faster, cheaper model

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding vector for a text string."""
        start_time = time.time()
        try:
            response = await self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            embedding = response.data[0].embedding

            logger.debug(f"Generated embedding in {time.time() - start_time:.2f}s")
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            return None

    def normalize_query(self, query: str) -> str:
        """Normalize query text for better matching."""
        # Simple normalization - lowercase, remove excess whitespace
        normalized = " ".join(query.lower().split())
        return normalized