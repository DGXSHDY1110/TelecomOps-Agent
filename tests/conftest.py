"""Test fixtures and configuration for pytest."""

import pytest
from fastapi.testclient import TestClient

from src.telecomops_agent.api.main import create_app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    app = create_app()
    return TestClient(app)
