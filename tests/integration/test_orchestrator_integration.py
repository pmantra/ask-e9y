import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app
from app.models.responses import QueryResponse

client = TestClient(app)


class TestOrchestratorIntegration:
    def test_query_endpoint_uses_orchestrator(self):
        """Test that the query endpoint uses the orchestrator."""
        # This would patch the orchestrator used in the endpoint
        with patch("app.services.orchestration.factory.query_orchestrator.process_query") as mock_process:
            # Setup mock return - now returning a single QueryResponse object
            mock_response = QueryResponse(
                query_id="test-id",
                conversation_id="test-conversation",
                results=[],
                has_results=False,
                message="No results found",
                timing_stats={"total_time": 100}
            )
            mock_process.return_value = mock_response

            # Make request
            response = client.post(
                "/api/query",
                json={"query": "test query"}
            )

            # Verify
            assert response.status_code == 200
            mock_process.assert_called_once()