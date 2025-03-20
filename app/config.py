# Add to app/config.py
import os
from enum import Enum
from typing import Optional

from pydantic_settings import BaseSettings

class Environment(str, Enum):
    """Application environment."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"

class LLMProvider(str, Enum):
    """LLM provider options."""
    OPENAI = "openai"
    GEMINI = "gemini"

class Settings(BaseSettings):
    """Application settings."""

    # Application Settings
    APP_NAME: str = "Chatbot Query System"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    ENV: Environment = os.getenv("ENV", Environment.DEVELOPMENT)
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/ask_e9y_db")
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))

    # LLM Settings
    LLM_PROVIDER: LLMProvider = os.getenv("LLM_PROVIDER", LLMProvider.OPENAI)
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4-1106-preview")
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")

    # Security Settings
    ALLOWED_SQL_OPERATIONS: list[str] = ["SELECT"]
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "4096"))

    # Chatbot Settings
    MAX_CONVERSATION_HISTORY: int = int(os.getenv("MAX_CONVERSATION_HISTORY", "10"))
    DEFAULT_SCHEMA: str = os.getenv("DEFAULT_SCHEMA", "eligibility")

    # ChromaDB Settings
    CHROMA_PERSIST_DIRECTORY: str = os.getenv("CHROMA_PERSIST_DIRECTORY", "./chroma_db")

settings = Settings()