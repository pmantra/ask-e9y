# app/services/metrics_service.py
import time
import logging
from datetime import datetime
import json
import os
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)


class MetricsService:
    """Service for collecting and storing performance metrics."""

    def __init__(self, metrics_directory="./metrics"):
        self.metrics_directory = metrics_directory
        os.makedirs(metrics_directory, exist_ok=True)
        self.current_metrics = {}

    async def record_query_metrics(self, context, db_session=None):
        """Record metrics for a query execution."""
        metrics = {
            "query_id": str(context.query_id),
            "timestamp": datetime.now(),
            "original_query": context.original_query,
            "cache_status": context.metadata.get("cache_status", "miss"),
            "execution_time_ms": context.metadata.get("execution_time_ms", 0),
            "total_time_ms": (time.time() - context.start_time) * 1000,
            "row_count": context.metadata.get("row_count", 0),
            "schema_size": self._get_schema_size(context),
            "token_usage": self._get_token_usage(context),
            "stage_timings": context.get_timing_metrics(),
            "success": len(context.errors) == 0,
        }

        # Store in database if session provided
        if db_session:
            await self._store_metrics_in_db(metrics, db_session)

        # Also store in local file for backup
        self._store_metrics_in_file(metrics)

        return metrics

    def _get_schema_size(self, context):
        """Get the size of the schema used for this query."""
        if "focused_schema" in context.metadata:
            return len(context.metadata["focused_schema"])
        elif "tables_used" in context.metadata:
            return len(context.metadata["tables_used"])
        elif "full_schema_size" in context.metadata:
            return context.metadata["full_schema_size"]
        return None  # Unknown schema size

    def _get_token_usage(self, context):
        """Extract token usage from context if available."""
        # This assumes the LLM service adds token usage to the context
        return context.metadata.get("token_usage", {})

    def _store_metrics_in_file(self, metrics):
        """Store metrics in a local JSON file."""
        try:
            filename = f"{self.metrics_directory}/metrics_{datetime.now().strftime('%Y%m%d')}.jsonl"
            with open(filename, "a") as f:
                f.write(json.dumps(metrics) + "\n")
        except Exception as e:
            logger.error(f"Error storing metrics in file: {str(e)}")

    async def _store_metrics_in_db(self, metrics, db_session):
        """Store metrics in the database."""
        try:
            # Create the metrics table if it doesn't exist
            await self._ensure_metrics_table(db_session)

            # Insert metrics record
            query = text("""
                INSERT INTO eligibility.api_metrics (
                    query_id, timestamp, original_query, cache_status,
                    execution_time_ms, total_time_ms, row_count, 
                    schema_size, token_usage, stage_timings, success
                ) VALUES (
                    :query_id, :timestamp, :original_query, :cache_status,
                    :execution_time_ms, :total_time_ms, :row_count,
                    :schema_size, :token_usage, :stage_timings, :success
                )
            """)

            # Convert complex objects to JSON strings
            metrics_db = metrics.copy()
            metrics_db["token_usage"] = json.dumps(metrics.get("token_usage", {}))
            metrics_db["stage_timings"] = json.dumps(metrics.get("stage_timings", {}))

            await db_session.execute(query, metrics_db)
            await db_session.commit()
        except Exception as e:
            logger.error(f"Error storing metrics in database: {str(e)}")

    async def _ensure_metrics_table(self, db_session):
        """Ensure the metrics table exists."""
        try:
            create_table_query = text("""
                CREATE TABLE IF NOT EXISTS eligibility.api_metrics (
                    id SERIAL PRIMARY KEY,
                    query_id TEXT NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                    original_query TEXT NOT NULL,
                    cache_status TEXT,
                    execution_time_ms FLOAT,
                    total_time_ms FLOAT,
                    row_count INTEGER,
                    schema_size INTEGER,
                    token_usage JSONB,
                    stage_timings JSONB,
                    success BOOLEAN,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db_session.execute(create_table_query)
            await db_session.commit()

            # Create index for query_id
            index_query = text("""
                CREATE INDEX IF NOT EXISTS idx_api_metrics_query_id
                ON eligibility.api_metrics (query_id)
            """)

            await db_session.execute(index_query)
            await db_session.commit()
        except Exception as e:
            logger.error(f"Error creating metrics table: {str(e)}")