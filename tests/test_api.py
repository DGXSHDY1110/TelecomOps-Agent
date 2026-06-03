"""Tests for the FastAPI health check endpoint and package imports."""

import pytest
from fastapi.testclient import TestClient


class TestHealthCheck:
    """Tests for the GET /health endpoint."""

    def test_health_check_returns_ok(self, client: TestClient):
        """The health check should return status ok and version."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"

    def test_health_check_content_type(self, client: TestClient):
        """The health check should return JSON content-type."""
        response = client.get("/health")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]


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
