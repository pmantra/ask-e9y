import time
from typing import Dict, Any

from app.config import settings
from app.database import get_table_schema_info


class SchemaService:
    """Service for managing database schema information."""

    def __init__(self):
        self._schema_cache = {}
        self._schema_cache_timestamp = 0

    async def get_schema_info(self) -> Dict[str, Any]:
        """Get schema information with caching."""
        current_time = time.time()
        # Cache expires after 5 minutes
        if not self._schema_cache or (current_time - self._schema_cache_timestamp) > 300:
            self._schema_cache = await get_table_schema_info(settings.DEFAULT_SCHEMA)
            self._schema_cache_timestamp = current_time

        return self._schema_cache