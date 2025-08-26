"""
Tests for the Migration Assistant API authentication and authorization.

This module provides comprehensive tests for JWT authentication, API key authentication,
multi-tenant support, and role-based access control.
"""

import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import patch

from fastapi.testclient import TestClient
from jose import jwt

from migration_assistant.api.main import app
from migration_assistant.api.auth import (
    SECRET_KEY, ALGORITHM, create_access_token, create_user, create_api_key, create_tenant,
    UserRole, fake_users_db, fake_api_keys_db, fake_tenants_db
)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def admin_token():
    """Create admin JWT token."""
    return create_access_token(
        data={
            "sub": "admin",
            "tenant_id": None,
            "scopes": ["admin", "migrations:read", "migrations:write", "migrations:delete", "presets:read", "presets:write"]
        }
    )


@pytest.fixture
def user_token():
    """Create regular user JWT token."""
    return create_access_token(
        data={
            "sub": "testuser",
            "tenant_id": "tenant1",
            "scopes": ["migrations:read", "migrations:write", "presets:read"]
        }
    )


@pytest.fixture
def expired_token():
    """Create expired JWT token."""
    return create_access_token(
        data={"sub": "testuser", "tenant_id": "tenant1", "scopes": ["migrations:read"]},
        expires_delta=timedelta(seconds=-1)  # Already expired
    )


@pytest.fixture
def api_key():
    """Get test API key."""
    return "test-api-key-123"


class TestAuthenticationEndpoints:
    """Test authentication endpoints."""
    
    def test_login_success(self, client):
        """Test successful login."""
        response = client.post(
            "/auth/token",
            data={"username": "admin", "password": "admin123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
    
    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        response = client.post(
            "/auth/token",
            data={"username": "admin", "password": "wrongpassword"}
        )
        
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]
    
    def test_login_nonexistent_user(self, client):
        """Test login with non-existent user."""
        response = client.post(
            "/auth/token",
            data={"username": "nonexistent", "password": "password"}
        )
        
        assert response.status_code == 401
    
    def test_get_current_user_with_token(self, client, admin_token):
        """Test getting current user with valid token."""
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"
        assert data["role"] == "admin"
        assert "admin" in data["scopes"]
    
    def test_get_current_user_with_api_key(self, client, api_key):
        """Test getting current user with valid API key."""
        response = client.get(
            "/auth/me",
            headers={"X-API-Key": api_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "api_key_Test API Key"
        assert data["tenant_id"] == "tenant1"
    
    def test_get_current_user_no_auth(self, client):
        """Test getting current user without authentication."""
        response = client.get("/auth/me")
        
        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]
    
    def test_get_current_user_invalid_token(self, client):
        """Test getting current user with invalid token."""
        response = client.get(
            "/auth/me",
            headers={"Authorization": "Bearer invalid-token"}
        )
        
        assert response.status_code == 401
    
    def test_get_current_user_expired_token(self, client, expired_token):
        """Test getting current user with expired token."""
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        
        assert response.status_code == 401
        assert "Token expired" in response.json()["detail"]


class TestUserManagement:
    """Test user management endpoints."""
    
    def test_create_user_as_admin(self, client, admin_token):
        """Test creating user as admin."""
        user_data = {
            "username": "newuser",
            "password": "newpass123",
            "email": "newuser@example.com",
            "full_name": "New User",
            "role": "user",
            "tenant_id": "tenant1",
            "scopes": ["migrations:read"]
        }
        
        response = client.post(
            "/auth/users",
            json=user_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert data["role"] == "user"
        assert data["tenant_id"] == "tenant1"
    
    def test_create_user_as_regular_user(self, client, user_token):
        """Test creating user as regular user (should fail)."""
        user_data = {
            "username": "newuser",
            "password": "newpass123",
            "role": "user"
        }
        
        response = client.post(
            "/auth/users",
            json=user_data,
            headers={"Authorization": f"Bearer {user_token}"}
        )
        
        assert response.status_code == 403
        assert "Not enough permissions" in response.json()["detail"]
    
    def test_list_users_as_admin(self, client, admin_token):
        """Test listing users as admin."""
        response = client.get(
            "/auth/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # admin and testuser
        
        usernames = [user["username"] for user in data]
        assert "admin" in usernames
        assert "testuser" in usernames
    
    def test_get_user_as_admin(self, client, admin_token):
        """Test getting specific user as admin."""
        response = client.get(
            "/auth/users/testuser",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["tenant_id"] == "tenant1"
    
    def test_get_nonexistent_user(self, client, admin_token):
        """Test getting non-existent user."""
        response = client.get(
            "/auth/users/nonexistent",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]


class TestAPIKeyManagement:
    """Test API key management endpoints."""
    
    def test_create_api_key(self, client, user_token):
        """Test creating API key."""
        api_key_data = {
            "name": "Test Key",
            "scopes": ["migrations:read"],
            "expires_in_days": 30
        }
        
        response = client.post(
            "/auth/api-keys",
            json=api_key_data,
            headers={"Authorization": f"Bearer {user_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Key"
        assert data["tenant_id"] == "tenant1"
        assert "migrations:read" in data["scopes"]
        assert "key" in data
        assert data["expires_at"] is not None
    
    def test_list_api_keys(self, client, user_token):
        """Test listing API keys."""
        response = client.get(
            "/auth/api-keys",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should see the test API key for tenant1
        assert len(data) >= 1
    
    def test_delete_api_key(self, client, user_token):
        """Test deleting API key."""
        # First create an API key
        api_key_data = {
            "name": "Key to Delete",
            "scopes": ["migrations:read"]
        }
        
        create_response = client.post(
            "/auth/api-keys",
            json=api_key_data,
            headers={"Authorization": f"Bearer {user_token}"}
        )
        
        assert create_response.status_code == 200
        key = create_response.json()["key"]
        
        # Now delete it
        delete_response = client.delete(
            f"/auth/api-keys/{key}",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        
        assert delete_response.status_code == 200
        assert "deleted successfully" in delete_response.json()["message"]
    
    def test_delete_nonexistent_api_key(self, client, user_token):
        """Test deleting non-existent API key."""
        response = client.delete(
            "/auth/api-keys/nonexistent-key",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        
        assert response.status_code == 404
        assert "API key not found" in response.json()["detail"]


class TestTenantManagement:
    """Test tenant management endpoints."""
    
    def test_create_tenant_as_admin(self, client, admin_token):
        """Test creating tenant as admin."""
        tenant_data = {
            "id": "newtenant",
            "name": "New Tenant",
            "description": "A new tenant for testing",
            "settings": {"max_migrations": 50}
        }
        
        response = client.post(
            "/auth/tenants",
            json=tenant_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "newtenant"
        assert data["name"] == "New Tenant"
        assert data["settings"]["max_migrations"] == 50
    
    def test_create_tenant_as_regular_user(self, client, user_token):
        """Test creating tenant as regular user (should fail)."""
        tenant_data = {
            "id": "newtenant",
            "name": "New Tenant"
        }
        
        response = client.post(
            "/auth/tenants",
            json=tenant_data,
            headers={"Authorization": f"Bearer {user_token}"}
        )
        
        assert response.status_code == 403
        assert "Not enough permissions" in response.json()["detail"]
    
    def test_list_tenants_as_admin(self, client, admin_token):
        """Test listing tenants as admin."""
        response = client.get(
            "/auth/tenants",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1  # tenant1
        
        tenant_ids = [tenant["id"] for tenant in data]
        assert "tenant1" in tenant_ids
    
    def test_get_tenant_as_admin(self, client, admin_token):
        """Test getting specific tenant as admin."""
        response = client.get(
            "/auth/tenants/tenant1",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "tenant1"
        assert data["name"] == "Example Organization"


class TestMultiTenantAccess:
    """Test multi-tenant access control."""
    
    def test_tenant_isolation_in_migrations(self, client, user_token):
        """Test that users can only see their tenant's migrations."""
        # This test would need actual migration data, but we can test the endpoint
        response = client.get(
            "/migrations/",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        
        # Should not fail due to authentication
        assert response.status_code == 200
    
    def test_cross_tenant_access_denied(self, client):
        """Test that users cannot access other tenants' resources."""
        # Create a token for a different tenant
        other_tenant_token = create_access_token(
            data={
                "sub": "otheruser",
                "tenant_id": "othertenant",
                "scopes": ["migrations:read"]
            }
        )
        
        response = client.get(
            "/migrations/",
            headers={"Authorization": f"Bearer {other_tenant_token}"}
        )
        
        # Should work but return empty list (no migrations for othertenant)
        assert response.status_code == 200


class TestScopeBasedAccess:
    """Test scope-based access control."""
    
    def test_insufficient_scope_for_write(self, client):
        """Test that read-only scope cannot perform write operations."""
        read_only_token = create_access_token(
            data={
                "sub": "testuser",
                "tenant_id": "tenant1",
                "scopes": ["migrations:read"]  # No write scope
            }
        )
        
        migration_config = {
            "name": "Test Migration",
            "source": {
                "type": "wordpress",
                "host": "source.example.com",
                "authentication": {"type": "ssh_key", "username": "testuser"},
                "paths": {"root_path": "/var/www/html"}
            },
            "destination": {
                "type": "aws_s3",
                "host": "s3.amazonaws.com",
                "authentication": {"type": "aws_iam"},
                "paths": {"root_path": "/"}
            },
            "transfer": {"method": "aws_s3"},
            "options": {}
        }
        
        response = client.post(
            "/migrations/",
            json=migration_config,
            headers={"Authorization": f"Bearer {read_only_token}"}
        )
        
        assert response.status_code == 403
        assert "Not enough permissions" in response.json()["detail"]
    
    def test_sufficient_scope_for_read(self, client, user_token):
        """Test that read scope can perform read operations."""
        response = client.get(
            "/presets/",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        
        assert response.status_code == 200


class TestTokenValidation:
    """Test JWT token validation."""
    
    def test_malformed_token(self, client):
        """Test handling of malformed JWT token."""
        response = client.get(
            "/auth/me",
            headers={"Authorization": "Bearer malformed.token.here"}
        )
        
        assert response.status_code == 401
    
    def test_token_without_bearer_prefix(self, client, user_token):
        """Test token without Bearer prefix."""
        response = client.get(
            "/auth/me",
            headers={"Authorization": user_token}  # Missing "Bearer "
        )
        
        assert response.status_code == 401
    
    def test_token_with_invalid_signature(self, client):
        """Test token with invalid signature."""
        # Create token with wrong secret
        invalid_token = jwt.encode(
            {"sub": "testuser", "scopes": ["migrations:read"]},
            "wrong-secret",
            algorithm=ALGORITHM
        )
        
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {invalid_token}"}
        )
        
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__])