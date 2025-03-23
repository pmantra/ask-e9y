# app/routers/analysis.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_async_db
from app.services.prompt_analyzer import PromptAnalyzer

router = APIRouter(
    prefix="/api/analysis",
    tags=["Analysis"]
)


@router.get("/prompts/recent")
async def get_recent_prompts(
        limit: int = 10,
        db: AsyncSession = Depends(get_async_db)
):
    """Get most recent prompts with analysis."""
    try:
        query = text("""
            SELECT 
                query_id,
                original_query,
                prompt_system,
                prompt_user,
                token_usage,
                schema_size,
                execution_time_ms
            FROM
                eligibility.api_metrics
            ORDER BY
                timestamp DESC
            LIMIT :limit
        """)

        result = await db.execute(query, {"limit": limit})
        prompts = result.mappings().all()

        # Analyze each prompt
        analyzer = PromptAnalyzer()
        analyzed_prompts = []

        for p in prompts:
            prompt_data = dict(p)
            analysis = analyzer.analyze_prompt(
                prompt_data.get("prompt_system", ""),
                prompt_data.get("prompt_user", "")
            )
            prompt_data["analysis"] = analysis
            analyzed_prompts.append(prompt_data)

        return analyzed_prompts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing prompts: {str(e)}")


@router.get("/prompts/compare")
async def compare_prompts(
        query_id1: str,
        query_id2: str,
        db: AsyncSession = Depends(get_async_db)
):
    """Compare two prompts side by side."""
    try:
        # Get first prompt
        query = text("""
            SELECT 
                query_id,
                original_query,
                prompt_system,
                prompt_user,
                token_usage,
                schema_size,
                execution_time_ms
            FROM
                eligibility.api_metrics
            WHERE
                query_id = :query_id
        """)

        result = await db.execute(query, {"query_id": query_id1})
        prompt1 = result.mappings().first()

        if not prompt1:
            raise HTTPException(status_code=404, detail="First query not found")

        # Get second prompt
        result = await db.execute(query, {"query_id": query_id2})
        prompt2 = result.mappings().first()

        if not prompt2:
            raise HTTPException(status_code=404, detail="Second query not found")

        # Compare the prompts
        analyzer = PromptAnalyzer()
        comparison = analyzer.compare_prompts(
            {"system": prompt1["prompt_system"], "user": prompt1["prompt_user"]},
            {"system": prompt2["prompt_system"], "user": prompt2["prompt_user"]}
        )

        return {
            "query1": dict(prompt1),
            "query2": dict(prompt2),
            "comparison": comparison
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error comparing prompts: {str(e)}")