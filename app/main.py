"""Main FastAPI application for the Chatbot Query System."""

import logging
import json
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import debug_endpoints
from app.config import settings
from app.database import get_async_db, test_connection, AsyncSession
from app.routers import query, metrics
from app.utils.json_encoder import CustomJSONEncoder

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app with custom JSON handling
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="A chatbot system that leverages LLMs to translate natural language to SQL queries",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Custom exception handler for HTTPExceptions
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request, exc):
    """
    Custom exception handler that ensures UUID objects in the response are properly serialized.
    """
    if hasattr(exc, "detail") and isinstance(exc.detail, dict):
        # Convert any UUIDs to strings in the detail dictionary
        for key, value in exc.detail.items():
            if isinstance(value, UUID):
                exc.detail[key] = str(value)

    # Use our custom JSON encoder for the response
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )

# Configure custom JSON encoder for FastAPI responses
def custom_json_serializer(*args, **kwargs):
    """Custom JSON serializer using our encoder."""
    return json.dumps(*args, cls=CustomJSONEncoder, **kwargs)

JSONResponse.json_dumps = custom_json_serializer

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ask-e9y-o3of4kox2-prashanth-mantravadis-projects.vercel.app",
        "http://localhost:3000",  # Local development
        "*"  # Temporarily allow all origins for testing (remove in production)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(query.router)
app.include_router(debug_endpoints.router)  # Add debug endpoints
# Add the metrics router
app.include_router(metrics.router)



@app.get("/", tags=["Health"])
async def root():
    """Root endpoint for health check."""
    return {
        "message": "Welcome to the Chatbot Query System API",
        "version": settings.APP_VERSION,
        "status": "healthy",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    # Check database connection
    try:
        db_connected = test_connection()
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        db_connected = False

    if not db_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )

    return {
        "status": "healthy",
        "database": "connected",
        "environment": settings.ENV
    }


@app.get("/debug", tags=["Debug"])
async def debug_info(db: AsyncSession = Depends(get_async_db)):
    """Return debug information (only in development mode)."""
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debug mode is disabled",
        )

    # Return debug information
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENV,
        "debug_mode": settings.DEBUG,
        "llm_provider": settings.LLM_PROVIDER,
        "database_connected": test_connection(),
    }