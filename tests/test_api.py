"""
Tests for Migration Assistant API.

This module contains unit tests for the FastAPI endpoints
and API functionality.
"""

import pytest
from fastapi.testclient import TestClient

from migration_assistant.api.main import app
from migration_assistant.models.config import (
    MigrationConfig,
    SystemConfig,
    AuthConfig,
    PathConfig,
    TransferConfig,
    MigrationOptions,
    AuthType,
    SystemType,
    TransferMethod,
)


class TestAPI:
    """Test API functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(app)

    def test_health_check(self):
        """Test health check endpoint."""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert data["service"] == "Migration Assistant API"

    def test_root_endpoint(self):
        """Test root endpoint returns API information."""
        response = self.client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "Web & Database Migration Assistant API" in data["name"]
        assert "version" in data
        assert "docs_url" in data

    def test_create_migration(self, sample_migration_config):
        """Test creating a migration session."""
        response = self.client.post(
            "/migrations/",
            json=sample_migration_config.dict()
        )
        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        assert data["status"] == "created"

    def test_get_migration_status(self):
        """Test getting migration status."""
        session_id = "test_session_123"
        response = self.client.get(f"/migrations/{session_id}/status")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert "status" in data
        assert "progress" in data

    def test_list_migrations(self):
        """Test listing migrations."""
        response = self.client.get("/migrations/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_migrations_with_filter(self):
        """Test listing migrations with status filter."""
        response = self.client.get("/migrations/?status_filter=running")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_start_migration(self):
        """Test starting a migration session."""
        session_id = "test_session_123"
        response = self.client.post(f"/migrations/{session_id}/start")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert "status" in data

    def test_cancel_migration(self):
        """Test cancelling a migration session."""
        session_id = "test_session_123"
        response = self.client.post(f"/migrations/{session_id}/cancel")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id

    def test_rollback_migration(self):
        """Test rolling back a migration session."""
        session_id = "test_session_123"
        response = self.client.post(f"/migrations/{session_id}/rollback")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id

    def test_list_presets(self):
        """Test listing migration presets."""
        response = self.client.get("/presets/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have at least the example presets
        assert len(data) >= 2

    def test_get_preset(self):
        """Test getting a specific preset."""
        preset_id = "wordpress-mysql"
        response = self.client.get(f"/presets/{preset_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == preset_id
        assert "name" in data
        assert "description" in data

    def test_validate_configuration(self, sample_migration_config):
        """Test validating a migration configuration."""
        response = self.client.post(
            "/validate/",
            json=sample_migration_config.dict()
        )
        assert response.status_code == 200
        data = response.json()
        assert "valid" in data
        assert "checks_performed" in data

    def test_invalid_migration_config(self):
        """Test creating migration with invalid configuration."""
        invalid_config = {
            "name": "",  # Empty name should fail validation
            "source": {},
            "destination": {},
            "transfer": {},
            "options": {}
        }
        response = self.client.post("/migrations/", json=invalid_config)
        assert response.status_code == 422  # Validation error

    def test_nonexistent_session_status(self):
        """Test getting status for non-existent session."""
        response = self.client.get("/migrations/nonexistent/status")
        assert response.status_code == 200  # Currently returns placeholder data
        # This will change when actual implementation is added

    def test_openapi_docs(self):
        """Test OpenAPI documentation endpoint."""
        response = self.client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert data["info"]["title"] == "Web & Database Migration Assistant API"

    def test_docs_endpoint(self):
        """Test Swagger UI docs endpoint."""
        response = self.client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_redoc_endpoint(self):
        """Test ReDoc documentation endpoint."""
        response = self.client.get("/redoc")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]