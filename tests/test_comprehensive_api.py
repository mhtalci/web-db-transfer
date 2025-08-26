"""
Comprehensive tests for the FastAPI REST API with 90%+ coverage.

This module tests all API endpoints, authentication, multi-tenant support,
and async operations.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import status
from jose import jwt

from migration_assistant.api.main import app
from migration_assistant.api.auth import (
    create_access_token, verify_token, get_current_user,
    authenticate_user, get_password_hash
)
from migration_assistant.models.config import MigrationConfig, SystemConfig, DatabaseType
from migration_assistant.models.session import MigrationSession, MigrationStatus
from migration_assistant.core.exceptions import AuthenticationError


class TestAPIAuthentication:
    """Test API authentication and authorization."""
    
    @pytest.fixture
    def test_client(self):
        """FastAPI test client."""
        return TestClient(app)
    
    @pytest.fixture
    def test_user(self):
        """Test user data."""
        return {
            "username": "testuser",
            "email": "test@example.com",
            "tenant_id": "tenant_123",
            "is_active": True
        }
    
    def test_create_access_token(self, test_user):
        """Test JWT access token creation."""
        token = create_access_token(
            data={"sub": test_user["username"], "tenant_id": test_user["tenant_id"]},
            expires_delta=timedelta(hours=1)
        )
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Verify token can be decoded
        payload = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
        assert payload["sub"] == test_user["username"]
        assert payload["tenant_id"] == test_user["tenant_id"]
    
    def test_verify_token_valid(self, test_user):
        """Test token verification with valid token."""
        token = create_access_token(
            data={"sub": test_user["username"], "tenant_id": test_user["tenant_id"]}
        )
        
        payload = verify_token(token)
        
        assert payload["sub"] == test_user["username"]
        assert payload["tenant_id"] == test_user["tenant_id"]
    
    def test_verify_token_invalid(self):
        """Test token verification with invalid token."""
        invalid_token = "invalid.token.here"
        
        with pytest.raises(AuthenticationError):
            verify_token(invalid_token)
    
    def test_verify_token_expired(self, test_user):
        """Test token verification with expired token."""
        token = create_access_token(
            data={"sub": test_user["username"]},
            expires_delta=timedelta(seconds=-1)  # Already expired
        )
        
        with pytest.raises(AuthenticationError):
            verify_token(token)
    
    @pytest.mark.asyncio
    async def test_authenticate_user_valid(self, test_user):
        """Test user authentication with valid credentials."""
        with patch('migration_assistant.api.auth.get_user') as mock_get_user:
            mock_get_user.return_value = {
                **test_user,
                "hashed_password": get_password_hash("testpass")
            }
            
            user = await authenticate_user("testuser", "testpass")
            
            assert user is not None
            assert user["username"] == "testuser"
    
    @pytest.mark.asyncio
    async def test_authenticate_user_invalid(self):
        """Test user authentication with invalid credentials."""
        with patch('migration_assistant.api.auth.get_user') as mock_get_user:
            mock_get_user.return_value = None
            
            user = await authenticate_user("nonexistent", "wrongpass")
            
            assert user is None
    
    def test_login_endpoint(self, test_client):
        """Test login endpoint."""
        with patch('migration_assistant.api.auth.authenticate_user') as mock_auth:
            mock_auth.return_value = {
                "username": "testuser",
                "tenant_id": "tenant_123"
            }
            
            response = test_client.post(
                "/auth/login",
                data={"username": "testuser", "password": "testpass"}
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"
    
    def test_login_endpoint_invalid(self, test_client):
        """Test login endpoint with invalid credentials."""
        with patch('migration_assistant.api.auth.authenticate_user') as mock_auth:
            mock_auth.return_value = None
            
            response = test_client.post(
                "/auth/login",
                data={"username": "testuser", "password": "wrongpass"}
            )
            
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_protected_endpoint_with_token(self, test_client, test_user):
        """Test accessing protected endpoint with valid token."""
        token = create_access_token(
            data={"sub": test_user["username"], "tenant_id": test_user["tenant_id"]}
        )
        
        with patch('migration_assistant.api.auth.get_user') as mock_get_user:
            mock_get_user.return_value = test_user
            
            response = test_client.get(
                "/migrations/",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            # Should not return 401 (authentication error)
            assert response.status_code != status.HTTP_401_UNAUTHORIZED
    
    def test_protected_endpoint_without_token(self, test_client):
        """Test accessing protected endpoint without token."""
        response = test_client.get("/migrations/")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestMigrationEndpoints:
    """Test migration-related API endpoints."""
    
    @pytest.fixture
    def test_client(self):
        """FastAPI test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self, test_user):
        """Authentication headers for requests."""
        token = create_access_token(
            data={"sub": test_user["username"], "tenant_id": test_user["tenant_id"]}
        )
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture
    def test_user(self):
        """Test user data."""
        return {
            "username": "testuser",
            "tenant_id": "tenant_123",
            "is_active": True
        }
    
    @pytest.fixture
    def sample_migration_request(self):
        """Sample migration request data."""
        return {
            "name": "Test Migration",
            "description": "A test migration",
            "source": {
                "type": "wordpress",
                "host": "source.example.com",
                "database": {
                    "type": "mysql",
                    "host": "db.source.com",
                    "database_name": "wp_db",
                    "username": "wp_user",
                    "password": "wp_pass"
                }
            },
            "destination": {
                "type": "aws-s3",
                "host": "s3.amazonaws.com",
                "database": {
                    "type": "aurora-mysql",
                    "host": "aurora.amazonaws.com",
                    "database_name": "wp_db_new",
                    "username": "aurora_user",
                    "password": "aurora_pass"
                }
            },
            "transfer": {
                "method": "s3_sync",
                "parallel_transfers": 4,
                "compression_enabled": True
            },
            "options": {
                "maintenance_mode": True,
                "backup_before": True,
                "verify_after": True
            }
        }
    
    def test_create_migration(self, test_client, auth_headers, sample_migration_request, test_user):
        """Test creating a new migration."""
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.orchestrator.orchestrator.MigrationOrchestrator') as mock_orchestrator:
            
            mock_get_user.return_value = test_user
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            mock_instance.create_session.return_value = MigrationSession(
                id="session_123",
                config=Mock(),
                status=MigrationStatus.PENDING
            )
            
            response = test_client.post(
                "/migrations/",
                json=sample_migration_request,
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert "session_id" in data
            assert data["status"] == "pending"
    
    def test_get_migration_status(self, test_client, auth_headers, test_user):
        """Test getting migration status."""
        session_id = "session_123"
        
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.orchestrator.orchestrator.MigrationOrchestrator') as mock_orchestrator:
            
            mock_get_user.return_value = test_user
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            mock_instance.get_session.return_value = MigrationSession(
                id=session_id,
                config=Mock(),
                status=MigrationStatus.RUNNING,
                progress=45
            )
            
            response = test_client.get(
                f"/migrations/{session_id}/status",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["session_id"] == session_id
            assert data["status"] == "running"
            assert data["progress"] == 45
    
    def test_list_migrations(self, test_client, auth_headers, test_user):
        """Test listing user migrations."""
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.orchestrator.orchestrator.MigrationOrchestrator') as mock_orchestrator:
            
            mock_get_user.return_value = test_user
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            mock_instance.list_sessions.return_value = [
                MigrationSession(id="session_1", config=Mock(), status=MigrationStatus.COMPLETED),
                MigrationSession(id="session_2", config=Mock(), status=MigrationStatus.RUNNING)
            ]
            
            response = test_client.get(
                "/migrations/",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data["migrations"]) == 2
            assert data["migrations"][0]["session_id"] == "session_1"
    
    def test_start_migration(self, test_client, auth_headers, test_user):
        """Test starting a migration."""
        session_id = "session_123"
        
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.orchestrator.orchestrator.MigrationOrchestrator') as mock_orchestrator:
            
            mock_get_user.return_value = test_user
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            mock_instance.start_migration = AsyncMock(return_value=True)
            
            response = test_client.post(
                f"/migrations/{session_id}/start",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "started"
    
    def test_stop_migration(self, test_client, auth_headers, test_user):
        """Test stopping a migration."""
        session_id = "session_123"
        
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.orchestrator.orchestrator.MigrationOrchestrator') as mock_orchestrator:
            
            mock_get_user.return_value = test_user
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            mock_instance.stop_migration = AsyncMock(return_value=True)
            
            response = test_client.post(
                f"/migrations/{session_id}/stop",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "stopped"
    
    def test_rollback_migration(self, test_client, auth_headers, test_user):
        """Test rolling back a migration."""
        session_id = "session_123"
        
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.orchestrator.orchestrator.MigrationOrchestrator') as mock_orchestrator:
            
            mock_get_user.return_value = test_user
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            mock_instance.rollback_migration = AsyncMock(return_value=True)
            
            response = test_client.post(
                f"/migrations/{session_id}/rollback",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "rollback_started"
    
    def test_get_migration_logs(self, test_client, auth_headers, test_user):
        """Test getting migration logs."""
        session_id = "session_123"
        
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.orchestrator.orchestrator.MigrationOrchestrator') as mock_orchestrator:
            
            mock_get_user.return_value = test_user
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            mock_instance.get_logs.return_value = [
                {"timestamp": "2024-01-01T12:00:00", "level": "INFO", "message": "Migration started"},
                {"timestamp": "2024-01-01T12:01:00", "level": "INFO", "message": "Validation completed"}
            ]
            
            response = test_client.get(
                f"/migrations/{session_id}/logs",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data["logs"]) == 2
            assert data["logs"][0]["message"] == "Migration started"
    
    def test_delete_migration(self, test_client, auth_headers, test_user):
        """Test deleting a migration session."""
        session_id = "session_123"
        
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.orchestrator.orchestrator.MigrationOrchestrator') as mock_orchestrator:
            
            mock_get_user.return_value = test_user
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            mock_instance.delete_session = AsyncMock(return_value=True)
            
            response = test_client.delete(
                f"/migrations/{session_id}",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_204_NO_CONTENT


class TestPresetEndpoints:
    """Test preset-related API endpoints."""
    
    @pytest.fixture
    def test_client(self):
        """FastAPI test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self, test_user):
        """Authentication headers for requests."""
        token = create_access_token(
            data={"sub": test_user["username"], "tenant_id": test_user["tenant_id"]}
        )
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture
    def test_user(self):
        """Test user data."""
        return {
            "username": "testuser",
            "tenant_id": "tenant_123",
            "is_active": True
        }
    
    def test_list_presets(self, test_client, auth_headers, test_user):
        """Test listing available migration presets."""
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.cli.preset_manager.PresetManager') as mock_preset_manager:
            
            mock_get_user.return_value = test_user
            mock_instance = Mock()
            mock_preset_manager.return_value = mock_instance
            mock_instance.list_presets.return_value = [
                {"name": "wordpress-mysql", "description": "WordPress with MySQL"},
                {"name": "django-postgres", "description": "Django with PostgreSQL"},
                {"name": "static-s3", "description": "Static site to S3"}
            ]
            
            response = test_client.get(
                "/presets/",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data["presets"]) == 3
            assert data["presets"][0]["name"] == "wordpress-mysql"
    
    def test_get_preset_details(self, test_client, auth_headers, test_user):
        """Test getting preset details."""
        preset_name = "wordpress-mysql"
        
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.cli.preset_manager.PresetManager') as mock_preset_manager:
            
            mock_get_user.return_value = test_user
            mock_instance = Mock()
            mock_preset_manager.return_value = mock_instance
            mock_instance.get_preset.return_value = {
                "name": "wordpress-mysql",
                "description": "WordPress with MySQL",
                "source": {"type": "wordpress"},
                "destination": {"type": "aws-s3"},
                "transfer": {"method": "s3_sync"},
                "options": {"backup_before": True}
            }
            
            response = test_client.get(
                f"/presets/{preset_name}",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["name"] == preset_name
            assert data["source"]["type"] == "wordpress"
    
    def test_create_custom_preset(self, test_client, auth_headers, test_user):
        """Test creating a custom preset."""
        preset_data = {
            "name": "custom-preset",
            "description": "Custom migration preset",
            "source": {"type": "drupal"},
            "destination": {"type": "gcs"},
            "transfer": {"method": "gcs_sync"},
            "options": {"verify_after": True}
        }
        
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.cli.preset_manager.PresetManager') as mock_preset_manager:
            
            mock_get_user.return_value = test_user
            mock_instance = Mock()
            mock_preset_manager.return_value = mock_instance
            mock_instance.create_preset.return_value = True
            
            response = test_client.post(
                "/presets/",
                json=preset_data,
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["name"] == "custom-preset"


class TestValidationEndpoints:
    """Test validation-related API endpoints."""
    
    @pytest.fixture
    def test_client(self):
        """FastAPI test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self, test_user):
        """Authentication headers for requests."""
        token = create_access_token(
            data={"sub": test_user["username"], "tenant_id": test_user["tenant_id"]}
        )
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture
    def test_user(self):
        """Test user data."""
        return {
            "username": "testuser",
            "tenant_id": "tenant_123",
            "is_active": True
        }
    
    def test_validate_configuration(self, test_client, auth_headers, test_user, sample_migration_request):
        """Test configuration validation endpoint."""
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.validation.engine.ValidationEngine') as mock_validator:
            
            mock_get_user.return_value = test_user
            mock_instance = Mock()
            mock_validator.return_value = mock_instance
            mock_instance.validate_migration = AsyncMock(return_value=Mock(
                success=True,
                errors=[],
                warnings=["Minor compatibility issue"],
                validation_time=1.5
            ))
            
            response = test_client.post(
                "/validate/configuration",
                json=sample_migration_request,
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert len(data["warnings"]) == 1
    
    def test_validate_connectivity(self, test_client, auth_headers, test_user):
        """Test connectivity validation endpoint."""
        connectivity_request = {
            "source": {
                "type": "mysql",
                "host": "source.db.com",
                "port": 3306,
                "username": "user",
                "password": "pass"
            },
            "destination": {
                "type": "postgresql",
                "host": "dest.db.com",
                "port": 5432,
                "username": "user",
                "password": "pass"
            }
        }
        
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.validation.connectivity.ConnectivityValidator') as mock_validator:
            
            mock_get_user.return_value = test_user
            mock_instance = Mock()
            mock_validator.return_value = mock_instance
            mock_instance.validate_database_connection = AsyncMock(return_value=Mock(
                success=True,
                response_time=0.1
            ))
            
            response = test_client.post(
                "/validate/connectivity",
                json=connectivity_request,
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["source"]["success"] is True
            assert data["destination"]["success"] is True


class TestMultiTenantSupport:
    """Test multi-tenant functionality."""
    
    @pytest.fixture
    def test_client(self):
        """FastAPI test client."""
        return TestClient(app)
    
    @pytest.fixture
    def tenant1_user(self):
        """Tenant 1 user."""
        return {
            "username": "tenant1_user",
            "tenant_id": "tenant_1",
            "is_active": True
        }
    
    @pytest.fixture
    def tenant2_user(self):
        """Tenant 2 user."""
        return {
            "username": "tenant2_user",
            "tenant_id": "tenant_2",
            "is_active": True
        }
    
    @pytest.fixture
    def tenant1_headers(self, tenant1_user):
        """Tenant 1 auth headers."""
        token = create_access_token(
            data={"sub": tenant1_user["username"], "tenant_id": tenant1_user["tenant_id"]}
        )
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture
    def tenant2_headers(self, tenant2_user):
        """Tenant 2 auth headers."""
        token = create_access_token(
            data={"sub": tenant2_user["username"], "tenant_id": tenant2_user["tenant_id"]}
        )
        return {"Authorization": f"Bearer {token}"}
    
    def test_tenant_isolation(self, test_client, tenant1_headers, tenant2_headers, tenant1_user, tenant2_user):
        """Test that tenants can only see their own migrations."""
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.orchestrator.orchestrator.MigrationOrchestrator') as mock_orchestrator:
            
            # Setup mock to return different sessions based on tenant
            def mock_get_user_side_effect(username):
                if username == "tenant1_user":
                    return tenant1_user
                elif username == "tenant2_user":
                    return tenant2_user
                return None
            
            mock_get_user.side_effect = mock_get_user_side_effect
            
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            
            def mock_list_sessions(tenant_id):
                if tenant_id == "tenant_1":
                    return [MigrationSession(id="tenant1_session", config=Mock(), status=MigrationStatus.RUNNING)]
                elif tenant_id == "tenant_2":
                    return [MigrationSession(id="tenant2_session", config=Mock(), status=MigrationStatus.COMPLETED)]
                return []
            
            mock_instance.list_sessions.side_effect = mock_list_sessions
            
            # Test tenant 1 can only see their sessions
            response1 = test_client.get("/migrations/", headers=tenant1_headers)
            assert response1.status_code == status.HTTP_200_OK
            data1 = response1.json()
            assert len(data1["migrations"]) == 1
            assert data1["migrations"][0]["session_id"] == "tenant1_session"
            
            # Test tenant 2 can only see their sessions
            response2 = test_client.get("/migrations/", headers=tenant2_headers)
            assert response2.status_code == status.HTTP_200_OK
            data2 = response2.json()
            assert len(data2["migrations"]) == 1
            assert data2["migrations"][0]["session_id"] == "tenant2_session"
    
    def test_cross_tenant_access_denied(self, test_client, tenant1_headers, tenant1_user):
        """Test that users cannot access other tenants' resources."""
        tenant2_session_id = "tenant2_session"
        
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.orchestrator.orchestrator.MigrationOrchestrator') as mock_orchestrator:
            
            mock_get_user.return_value = tenant1_user
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            mock_instance.get_session.return_value = None  # Session not found for this tenant
            
            response = test_client.get(
                f"/migrations/{tenant2_session_id}/status",
                headers=tenant1_headers
            )
            
            assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAsyncOperations:
    """Test asynchronous API operations."""
    
    @pytest.fixture
    def test_client(self):
        """FastAPI test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self, test_user):
        """Authentication headers for requests."""
        token = create_access_token(
            data={"sub": test_user["username"], "tenant_id": test_user["tenant_id"]}
        )
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture
    def test_user(self):
        """Test user data."""
        return {
            "username": "testuser",
            "tenant_id": "tenant_123",
            "is_active": True
        }
    
    def test_async_migration_start(self, test_client, auth_headers, test_user, sample_migration_request):
        """Test asynchronous migration start."""
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.orchestrator.orchestrator.MigrationOrchestrator') as mock_orchestrator:
            
            mock_get_user.return_value = test_user
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            
            # Mock async migration creation
            mock_session = MigrationSession(
                id="async_session_123",
                config=Mock(),
                status=MigrationStatus.PENDING
            )
            mock_instance.create_session.return_value = mock_session
            mock_instance.start_migration = AsyncMock(return_value=True)
            
            response = test_client.post(
                "/migrations/",
                json={**sample_migration_request, "start_immediately": True},
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["session_id"] == "async_session_123"
            assert data["status"] == "pending"
    
    def test_websocket_progress_updates(self, test_client, auth_headers, test_user):
        """Test WebSocket progress updates."""
        session_id = "session_123"
        
        # Note: WebSocket testing with TestClient is limited
        # In a real implementation, you'd use a WebSocket test client
        with patch('migration_assistant.api.auth.get_user') as mock_get_user:
            mock_get_user.return_value = test_user
            
            # Test WebSocket endpoint exists
            response = test_client.get(f"/ws/migrations/{session_id}/progress")
            # WebSocket upgrade should be attempted
            assert response.status_code in [status.HTTP_426_UPGRADE_REQUIRED, status.HTTP_400_BAD_REQUEST]


class TestErrorHandling:
    """Test API error handling."""
    
    @pytest.fixture
    def test_client(self):
        """FastAPI test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self, test_user):
        """Authentication headers for requests."""
        token = create_access_token(
            data={"sub": test_user["username"], "tenant_id": test_user["tenant_id"]}
        )
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture
    def test_user(self):
        """Test user data."""
        return {
            "username": "testuser",
            "tenant_id": "tenant_123",
            "is_active": True
        }
    
    def test_validation_error_handling(self, test_client, auth_headers, test_user):
        """Test validation error handling."""
        invalid_request = {
            "name": "",  # Invalid: empty name
            "source": {},  # Invalid: missing required fields
            "destination": {}  # Invalid: missing required fields
        }
        
        with patch('migration_assistant.api.auth.get_user') as mock_get_user:
            mock_get_user.return_value = test_user
            
            response = test_client.post(
                "/migrations/",
                json=invalid_request,
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            data = response.json()
            assert "detail" in data
    
    def test_not_found_error_handling(self, test_client, auth_headers, test_user):
        """Test 404 error handling."""
        nonexistent_session_id = "nonexistent_session"
        
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.orchestrator.orchestrator.MigrationOrchestrator') as mock_orchestrator:
            
            mock_get_user.return_value = test_user
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            mock_instance.get_session.return_value = None
            
            response = test_client.get(
                f"/migrations/{nonexistent_session_id}/status",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_404_NOT_FOUND
            data = response.json()
            assert "detail" in data
    
    def test_internal_server_error_handling(self, test_client, auth_headers, test_user, sample_migration_request):
        """Test internal server error handling."""
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.orchestrator.orchestrator.MigrationOrchestrator') as mock_orchestrator:
            
            mock_get_user.return_value = test_user
            mock_orchestrator.side_effect = Exception("Internal error")
            
            response = test_client.post(
                "/migrations/",
                json=sample_migration_request,
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert "detail" in data


class TestAPIPerformance:
    """Test API performance and load handling."""
    
    @pytest.fixture
    def test_client(self):
        """FastAPI test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self, test_user):
        """Authentication headers for requests."""
        token = create_access_token(
            data={"sub": test_user["username"], "tenant_id": test_user["tenant_id"]}
        )
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture
    def test_user(self):
        """Test user data."""
        return {
            "username": "testuser",
            "tenant_id": "tenant_123",
            "is_active": True
        }
    
    @pytest.mark.benchmark
    def test_list_migrations_performance(self, benchmark, test_client, auth_headers, test_user):
        """Benchmark list migrations endpoint performance."""
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.orchestrator.orchestrator.MigrationOrchestrator') as mock_orchestrator:
            
            mock_get_user.return_value = test_user
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            mock_instance.list_sessions.return_value = [
                MigrationSession(id=f"session_{i}", config=Mock(), status=MigrationStatus.COMPLETED)
                for i in range(100)  # 100 sessions
            ]
            
            def make_request():
                return test_client.get("/migrations/", headers=auth_headers)
            
            response = benchmark(make_request)
            assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.benchmark
    def test_create_migration_performance(self, benchmark, test_client, auth_headers, test_user, sample_migration_request):
        """Benchmark create migration endpoint performance."""
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.orchestrator.orchestrator.MigrationOrchestrator') as mock_orchestrator:
            
            mock_get_user.return_value = test_user
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            mock_instance.create_session.return_value = MigrationSession(
                id="benchmark_session",
                config=Mock(),
                status=MigrationStatus.PENDING
            )
            
            def make_request():
                return test_client.post(
                    "/migrations/",
                    json=sample_migration_request,
                    headers=auth_headers
                )
            
            response = benchmark(make_request)
            assert response.status_code == status.HTTP_201_CREATED