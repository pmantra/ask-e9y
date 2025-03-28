from app.services.embedding_service import EmbeddingService
from app.services.chroma_service import ChromaService
from app.services.example_retrieval_service import ExampleRetrievalService
from app.services.metrics_service import MetricsService
from app.services.openai_llm import OpenAILLMService
from app.services.cache_service import CacheService
from app.services.schema_embedding_service import SchemaEmbeddingService
from app.services.sql_executor import SQLExecutor
from app.services.schema_service import SchemaService

from app.services.stages.cache_lookup_stage import CacheLookupStage
from app.services.stages.sql_generation_stage import SQLGenerationStage
from app.services.stages.sql_validation_stage import SQLValidationStage
from app.services.stages.sql_execution_stage import SQLExecutionStage
from app.services.stages.explanation_generation_stage import ExplanationGenerationStage
from app.services.stages.cache_storage_stage import CacheStorageStage
from app.services.prompt_builder import PromptBuilder
from app.services.stages.prompt_analysis_stage import PromptAnalysisStage
from app.services.orchestration.orchestrator import QueryOrchestrator


# Create a singleton instance of the orchestrator
def create_query_orchestrator():
    """Create and return a configured query orchestrator."""
    # Create base services
    embedding_service = EmbeddingService()
    chroma_service = ChromaService(persist_directory="./chroma_db")    
    prompt_builder = PromptBuilder()
    llm_service = OpenAILLMService(prompt_builder=prompt_builder)
    schema_embedding_service = SchemaEmbeddingService(
        embedding_service=embedding_service,
        chroma_service=chroma_service
    )
    example_retrieval_service = ExampleRetrievalService(
        embedding_service=embedding_service,
        chroma_service=chroma_service
    )
    cache_service = CacheService(embedding_service, chroma_service)
    sql_executor = SQLExecutor()
    schema_service = SchemaService()
    metrics_service = MetricsService()    
    prompt_analysis_stage = PromptAnalysisStage(
        prompt_builder, embedding_service, chroma_service
    )

    # Create stage services
    cache_lookup_stage = CacheLookupStage(cache_service)
    sql_generation_stage = SQLGenerationStage(
        llm_service, 
        schema_service, 
        schema_embedding_service=schema_embedding_service,
        example_retrieval_service=example_retrieval_service,
        prompt_analysis_stage=prompt_analysis_stage  # Pass the reference
    )
    sql_validation_stage = SQLValidationStage(llm_service, schema_service)
    sql_execution_stage = SQLExecutionStage(sql_executor)
    explanation_stage = ExplanationGenerationStage(llm_service, schema_service)
    cache_storage_stage = CacheStorageStage(cache_service, embedding_service)

    # Create and return orchestrator
    return QueryOrchestrator(
    cache_lookup_stage=cache_lookup_stage,
    sql_generation_stage=sql_generation_stage,
    sql_validation_stage=sql_validation_stage,
    sql_execution_stage=sql_execution_stage,
    explanation_stage=explanation_stage,
    cache_storage_stage=cache_storage_stage,
    prompt_analysis_stage=prompt_analysis_stage,  # New stage
    metrics_service=metrics_service
)

# Create a singleton instance
query_orchestrator = create_query_orchestrator()
