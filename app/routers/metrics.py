from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_async_db
from typing import List, Dict, Any, Optional
from datetime import date
from pydantic import BaseModel, Field

router = APIRouter(
    prefix="/api/metrics",
    tags=["Metrics"]
)


# Create Pydantic models for the response
class DailyMetric(BaseModel):
    day: date
    query_count: int
    avg_response_time: float
    cache_hit_rate: float
    avg_tokens: Optional[float] = None
    avg_schema_size: Optional[float] = None


class OverallMetrics(BaseModel):
    total_queries: int
    avg_response_time: float
    cache_hit_rate: float
    avg_tokens: Optional[float] = None
    avg_schema_size: Optional[float] = None


class MetricsSummaryResponse(BaseModel):
    daily_metrics: List[DailyMetric]
    overall: OverallMetrics


@router.get("/summary", response_model=MetricsSummaryResponse)
async def get_metrics_summary(
        days: int = 7,
        db: AsyncSession = Depends(get_async_db)
):
    """
    Get summary metrics for the API over the specified number of days.

    - **days**: Number of days to include in the summary (default: 7)
    """
    try:
        # First query for daily metrics
        query = text("""
            WITH metrics AS (
                SELECT
                    DATE(timestamp) as day,
                    COUNT(*) as query_count,
                    AVG(total_time_ms) as avg_response_time,
                    AVG(CASE WHEN cache_status != 'miss' THEN 1 ELSE 0 END) * 100 as cache_hit_rate,
                    AVG((token_usage->>'total_tokens')::float) as avg_tokens,
                    AVG(schema_size) as avg_schema_size
                FROM
                    eligibility.api_metrics
                WHERE
                    timestamp > CURRENT_DATE - MAKE_INTERVAL(days => :days)
                GROUP BY
                    DATE(timestamp)
                ORDER BY
                    day
            )
            SELECT
                day,
                query_count,
                avg_response_time,
                cache_hit_rate,
                avg_tokens,
                avg_schema_size
            FROM metrics
        """)

        result = await db.execute(query, {"days": days})
        daily_metrics = result.mappings().all()

        # Second query for overall averages
        query = text("""
            SELECT
                COUNT(*) as total_queries,
                AVG(total_time_ms) as avg_response_time,
                AVG(CASE WHEN cache_status != 'miss' THEN 1 ELSE 0 END) * 100 as cache_hit_rate,
                AVG((token_usage->>'total_tokens')::float) as avg_tokens,
                AVG(schema_size) as avg_schema_size
            FROM
                eligibility.api_metrics
            WHERE
                timestamp > CURRENT_DATE - MAKE_INTERVAL(days => :days)
        """)

        result = await db.execute(query, {"days": days})
        overall_data = result.mappings().first()

        # Convert to dictionary and sanitize NULL values
        if overall_data:
            overall_dict = dict(overall_data)
            # Replace any None values with appropriate defaults
            overall_dict = {k: (0 if v is None else v) for k, v in overall_dict.items()}
        else:
            # Create default dictionary if no data
            overall_dict = {
                "total_queries": 0,
                "avg_response_time": 0.0,
                "cache_hit_rate": 0.0,
                "avg_tokens": 0.0,
                "avg_schema_size": 0.0
            }

        # Handle empty results with default values
        daily_metrics_list = []
        if daily_metrics:
            for day_data in daily_metrics:
                day_dict = dict(day_data)
                # Replace any None values with appropriate defaults
                day_dict = {k: (0 if v is None and k != 'day' else v) for k, v in day_dict.items()}
                daily_metrics_list.append(DailyMetric(**day_dict))

        # Create the response
        return MetricsSummaryResponse(
            daily_metrics=daily_metrics_list,
            overall=OverallMetrics(**overall_dict)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching metrics: {str(e)}")