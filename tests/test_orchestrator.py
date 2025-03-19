import pytest
from uuid import UUID
from unittest.mock import AsyncMock, patch

from app.services.orchestration.orchestrator import QueryOrchestrator
from app.services.orchestration.context import ProcessingContext
from app.models.requests import QueryRequest
from app.models.responses import QueryResponse, ErrorResponse


class TestQueryOrchestrator:
    @pytest.fixture
    def mock_cache_lookup_stage(self):
        """Create a mock cache lookup stage."""
        stage = AsyncMock()
        stage.execute.return_value = {"cache_hit": False, "cache_status": "miss"}
        return stage

    @pytest.fixture
    def mock_sql_generation_stage(self):
        """Create a mock SQL generation stage."""
        stage = AsyncMock()
        stage.execute.return_value = {"sql": "SELECT * FROM test"}
        return stage

    @pytest.fixture
    def mock_sql_validation_stage(self):
        """Create a mock SQL validation stage."""
        stage = AsyncMock()
        stage.execute.return_value = {"is_valid": True}
        return stage

    @pytest.fixture
    def mock_sql_execution_stage(self):
        """Create a mock SQL execution stage."""
        stage = AsyncMock()
        stage.execute.return_value = {
            "success": True,
            "results": [],
            "row_count": 0,
            "execution_time_ms": 100,
            "has_results": False
        }
        return stage

    @pytest.fixture
    def mock_explanation_stage(self):
        """Create a mock explanation stage."""
        stage = AsyncMock()
        stage.execute.return_value = {"explanation": "Test explanation"}
        return stage

    @pytest.fixture
    def mock_cache_storage_stage(self):
        """Create a mock cache storage stage."""
        stage = AsyncMock()
        stage.execute.return_value = {"stored": True}
        return stage

    @pytest.fixture
    def orchestrator(self, mock_cache_lookup_stage, mock_sql_generation_stage,
                     mock_sql_validation_stage, mock_sql_execution_stage,
                     mock_explanation_stage, mock_cache_storage_stage):
        """Create orchestrator with mock stages."""
        return QueryOrchestrator(
            cache_lookup_stage=mock_cache_lookup_stage,
            sql_generation_stage=mock_sql_generation_stage,
            sql_validation_stage=mock_sql_validation_stage,
            sql_execution_stage=mock_sql_execution_stage,
            explanation_stage=mock_explanation_stage,
            cache_storage_stage=mock_cache_storage_stage
        )

    async def test_process_query_returns_response(self, orchestrator):
        """Test that the orchestrator returns a QueryResponse for successful processing."""
        # Arrange
        request = QueryRequest(query="test query")
        db_session = AsyncMock()

        # Act
        response = await orchestrator.process_query(request, db_session)

        # Assert
        assert isinstance(response, QueryResponse)
        assert response.results == []
        assert response.has_results is False
        assert response.query_id is not None

    async def test_handles_validation_errors(self, orchestrator, mock_sql_validation_stage):
        """Test that the orchestrator handles validation errors."""
        # Arrange
        request = QueryRequest(query="test query")
        db_session = AsyncMock()

        # Mock validation failure
        mock_sql_validation_stage.execute.return_value = {
            "is_valid": False,
            "errors": [{"code": "TEST_ERROR", "message": "Test error"}]
        }

        # Act
        response = await orchestrator.process_query(request, db_session)

        # Assert
        assert isinstance(response, ErrorResponse)
        assert "validation failed" in response.error.lower()
        assert len(response.details) > 0
        assert "Test error" in response.details[0].message

    async def test_handles_execution_errors(self, orchestrator, mock_sql_execution_stage):
        """Test that the orchestrator handles execution errors."""
        # Arrange
        request = QueryRequest(query="test query")
        db_session = AsyncMock()

        # Mock execution failure
        mock_sql_execution_stage.execute.return_value = {
            "success": False,
            "error": "Execution test error"
        }

        # Act
        response = await orchestrator.process_query(request, db_session)

        # Assert
        assert isinstance(response, ErrorResponse)
        assert "execution failed" in response.error.lower()
        assert "Execution test error" in response.details[0].message

    async def test_handles_unhandled_exceptions(self, orchestrator, mock_sql_generation_stage):
        """Test that the orchestrator handles unhandled exceptions."""
        # Arrange
        request = QueryRequest(query="test query")
        db_session = AsyncMock()

        # Mock an exception during processing
        mock_sql_generation_stage.execute.side_effect = Exception("Unexpected error")

        # Act
        response = await orchestrator.process_query(request, db_session)

        # Assert
        assert isinstance(response, ErrorResponse)
        assert "failed" in response.error.lower()
        assert response.query_id is not None