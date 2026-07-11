"""Test authentication functionality."""

import pytest
from fastapi.testclient import TestClient

from mcprelay.config import MCPRelayConfig
from mcprelay.server import create_app


@pytest.fixture
def client():
    """Create test client.

    Context-managed so the app's startup runs (it initialises the auth manager);
    without it, ``auth_manager`` is None and every protected route 500s instead
    of authenticating.
    """
    config = MCPRelayConfig()
    config.auth.api_keys = {"test-key": "test-user"}
    app = create_app(config)
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint_no_auth(client):
    """Test health endpoint doesn't require auth."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


def test_root_endpoint_no_auth(client):
    """Test root endpoint doesn't require auth."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "MCPRelay"


def test_admin_requires_auth(client):
    """Test admin endpoint requires authentication."""
    response = client.get("/admin/")
    assert response.status_code == 401


def test_valid_api_key(client):
    """Test valid API key authentication."""
    headers = {"Authorization": "Bearer test-key"}
    response = client.get("/admin/", headers=headers)
    # Should return HTML, not 401
    assert response.status_code != 401
