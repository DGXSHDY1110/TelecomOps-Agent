"""Tests for the FastAPI endpoints: health, diagnose, feedback, and package imports."""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    """Tests for the GET /health endpoint."""

    def test_health_check_returns_200(self, client: TestClient):
        """The health check should return 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_status_ok(self, client: TestClient):
        """The health check should report status ok."""
        data = client.get("/health").json()
        assert data["status"] == "ok"

    def test_health_check_service_name(self, client: TestClient):
        """The health check should include the service name."""
        data = client.get("/health").json()
        assert data["service"] == "telecomops-agent"

    def test_health_check_content_type(self, client: TestClient):
        """The response should be JSON."""
        response = client.get("/health")
        assert "application/json" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# Diagnosis (mock)
# ---------------------------------------------------------------------------


class TestDiagnose:
    """Tests for POST /api/v1/diagnose (mock implementation)."""

    DIAGNOSE_URL = "/api/v1/diagnose"

    def _diagnose(self, client: TestClient, **overrides):
        """Helper to call diagnose with sensible defaults."""
        payload = {
            "query": "Cell SZ-NS-023-2 RSRP drop, call drop rate increase, please diagnose.",
            "cell_id": "SZ-NS-023-2",
            "debug": False,
        }
        payload.update(overrides)
        return client.post(self.DIAGNOSE_URL, json=payload)

    # ---- basic response structure ----

    def test_diagnose_returns_200(self, client: TestClient):
        """A valid diagnose request should return 200."""
        response = self._diagnose(client)
        assert response.status_code == 200

    def test_diagnose_has_query_id(self, client: TestClient):
        """Response must contain a non-empty query_id."""
        data = self._diagnose(client).json()
        assert "query_id" in data
        assert len(data["query_id"]) > 0

    def test_diagnose_has_answer(self, client: TestClient):
        """Response must contain an answer string."""
        data = self._diagnose(client).json()
        assert "answer" in data
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 0

    def test_diagnose_has_result(self, client: TestClient):
        """Response must contain a structured result object."""
        data = self._diagnose(client).json()
        assert "result" in data

    def test_diagnose_has_evidence(self, client: TestClient):
        """Response must contain evidence list."""
        data = self._diagnose(client).json()
        assert "evidence" in data
        assert isinstance(data["evidence"], list)

    def test_diagnose_has_tool_traces(self, client: TestClient):
        """Response must contain tool_traces list."""
        data = self._diagnose(client).json()
        assert "tool_traces" in data
        assert isinstance(data["tool_traces"], list)

    def test_diagnose_has_needs_human_review(self, client: TestClient):
        """Response must contain needs_human_review flag."""
        data = self._diagnose(client).json()
        assert "needs_human_review" in data
        assert isinstance(data["needs_human_review"], bool)

    # ---- result.confidence ----

    def test_confidence_is_valid(self, client: TestClient):
        """result.confidence must be one of low/medium/high."""
        data = self._diagnose(client).json()
        confidence = data["result"]["confidence"]
        assert confidence in ("low", "medium", "high")

    # ---- debug mode ----

    def test_debug_true_tool_traces_nonempty(self, client: TestClient):
        """When debug=True, tool_traces must be non-empty."""
        data = self._diagnose(client, debug=True).json()
        assert len(data["tool_traces"]) > 0

    def test_debug_false_tool_traces_empty(self, client: TestClient):
        """When debug=False, tool_traces must be empty."""
        data = self._diagnose(client, debug=False).json()
        assert data["tool_traces"] == []

    # ---- evidence content ----

    def test_evidence_contains_sql_and_graph(self, client: TestClient):
        """Mock evidence should include at least one SQL and one graph item."""
        data = self._diagnose(client).json()
        sources = {e["source"] for e in data["evidence"]}
        assert "sql" in sources
        assert "graph" in sources

    # ---- query missing required field ----

    def test_missing_query_field_returns_422(self, client: TestClient):
        """Omitting the required 'query' field should return 422."""
        response = client.post(self.DIAGNOSE_URL, json={})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Feedback (mock)
# ---------------------------------------------------------------------------


class TestFeedback:
    """Tests for POST /api/v1/feedback (mock implementation)."""

    FEEDBACK_URL = "/api/v1/feedback"

    def test_feedback_valid_rating_returns_200(self, client: TestClient):
        """rating=5 should be accepted and return 200."""
        response = client.post(
            self.FEEDBACK_URL,
            json={"query_id": "test-123", "rating": 5},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "saved"
        assert data["query_id"] == "test-123"

    def test_feedback_rating_out_of_range_returns_422(self, client: TestClient):
        """rating=6 should be rejected with 422."""
        response = client.post(
            self.FEEDBACK_URL,
            json={"query_id": "test-123", "rating": 6},
        )
        assert response.status_code == 422

    def test_feedback_rating_below_1_returns_422(self, client: TestClient):
        """rating=0 should be rejected with 422."""
        response = client.post(
            self.FEEDBACK_URL,
            json={"query_id": "test-123", "rating": 0},
        )
        assert response.status_code == 422

    def test_feedback_rating_1_returns_200(self, client: TestClient):
        """rating=1 is the lower bound and should be accepted."""
        response = client.post(
            self.FEEDBACK_URL,
            json={"query_id": "test-123", "rating": 1},
        )
        assert response.status_code == 200

    def test_feedback_with_comment_returns_200(self, client: TestClient):
        """Feedback with an optional comment should be accepted."""
        response = client.post(
            self.FEEDBACK_URL,
            json={
                "query_id": "test-456",
                "rating": 4,
                "is_correct": True,
                "comment": "诊断准确，步骤清晰。",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "saved"


# ---------------------------------------------------------------------------
# Package imports
# ---------------------------------------------------------------------------


class TestPackageImports:
    """Tests that all subpackages can be imported successfully."""

    def test_import_telecomops_agent(self):
        """The main package should be importable."""
        import src.telecomops_agent

        assert src.telecomops_agent.__version__ == "0.1.0"

    def test_import_api(self):
        """The api subpackage should be importable."""
        from src.telecomops_agent.api import main, routes, schemas, errors

        assert main is not None
        assert routes is not None
        assert schemas is not None
        assert errors is not None

    def test_import_agent(self):
        """The agent subpackage should be importable."""
        import src.telecomops_agent.agent

        assert src.telecomops_agent.agent is not None

    def test_import_tools(self):
        """The tools subpackage should be importable."""
        import src.telecomops_agent.tools

        assert src.telecomops_agent.tools is not None

    def test_import_db(self):
        """The db subpackage should be importable."""
        import src.telecomops_agent.db

        assert src.telecomops_agent.db is not None

    def test_import_retrievers(self):
        """The retrievers subpackage should be importable."""
        import src.telecomops_agent.retrievers

        assert src.telecomops_agent.retrievers is not None

    def test_import_evaluation(self):
        """The evaluation subpackage should be importable."""
        import src.telecomops_agent.evaluation

        assert src.telecomops_agent.evaluation is not None

    def test_import_utils(self):
        """The utils subpackage should be importable."""
        import src.telecomops_agent.utils

        assert src.telecomops_agent.utils is not None
