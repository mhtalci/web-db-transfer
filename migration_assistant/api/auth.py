"""
Authentication and authorization module for the Migration Assistant API.

This module provides JWT-based authentication, API key authentication,
and multi-tenant support with proper user management and authorization.
Enhanced with security features including rate limiting, secure headers,
and audit logging.
"""

import os
import secrets
import hashlib
import hmac
import time
from datetime import datetime, timedelta, UTC
from typing import Optional, List, Dict, Any, Union
from enum import Enum
import logging

from fastapi import HTTPException, status, Depends, Request
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field

from ..security.credential_manager import CredentialManager
from ..security.encryption import EncryptionManager

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
API_KEY_HEADER_NAME = "X-API-Key"
RATE_LIMIT_REQUESTS = 100  # requests per minute
RATE_LIMIT_WINDOW = 60  # seconds

# Security logging
security_logger = logging.getLogger("migration_assistant.security")

# Password hashing with enhanced security
pwd_context = CryptContext(
    schemes=["bcrypt"], 
    deprecated="auto",
    bcrypt__rounds=12  # Increased rounds for better security
)

# Initialize security managers
credential_manager = CredentialManager("migration_assistant_api")
encryption_manager = EncryptionManager()

# Security schemes
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


class UserRole(str, Enum):
    """User roles for authorization."""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class AuthMethod(str, Enum):
    """Authentication methods."""
    JWT = "jwt"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"


# Pydantic models
class Token(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str
    expires_in: int
    scope: Optional[str] = None


class TokenData(BaseModel):
    """Token data model for JWT payload."""
    username: Optional[str] = None
    tenant_id: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)
    exp: Optional[datetime] = None


class User(BaseModel):
    """User model."""
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: bool = False
    role: UserRole = UserRole.USER
    tenant_id: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)


class UserInDB(User):
    """User model with hashed password."""
    hashed_password: str


class APIKey(BaseModel):
    """API key model."""
    key: str
    name: str
    tenant_id: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: Optional[datetime] = None
    disabled: bool = False


class Tenant(BaseModel):
    """Tenant model for multi-tenancy."""
    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    disabled: bool = False
    settings: Dict[str, Any] = Field(default_factory=dict)


# In-memory storage (replace with database in production)
fake_users_db: Dict[str, UserInDB] = {
    "admin": UserInDB(
        username="admin",
        email="admin@migration-assistant.com",
        full_name="System Administrator",
        disabled=False,
        role=UserRole.ADMIN,
        tenant_id=None,  # Super admin
        scopes=["admin", "migrations:read", "migrations:write", "migrations:delete", "presets:read", "presets:write"],
        hashed_password=pwd_context.hash("admin123")
    ),
    "testuser": UserInDB(
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        disabled=False,
        role=UserRole.USER,
        tenant_id="tenant1",
        scopes=["migrations:read", "migrations:write", "presets:read"],
        hashed_password=pwd_context.hash("testpass")
    )
}

fake_api_keys_db: Dict[str, APIKey] = {
    "test-api-key-123": APIKey(
        key="test-api-key-123",
        name="Test API Key",
        tenant_id="tenant1",
        scopes=["migrations:read", "migrations:write"],
        disabled=False
    )
}

fake_tenants_db: Dict[str, Tenant] = {
    "tenant1": Tenant(
        id="tenant1",
        name="Example Organization",
        description="Example tenant for testing",
        disabled=False,
        settings={"max_migrations": 100, "retention_days": 30}
    )
}

# Rate limiting storage (in production, use Redis or similar)
rate_limit_storage: Dict[str, List[float]] = {}

# Security audit log storage (in production, use proper logging backend)
security_audit_log: List[Dict[str, Any]] = []


# Utility functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def generate_api_key() -> str:
    """Generate a secure API key."""
    return secrets.token_urlsafe(32)


def log_security_event(event_type: str, user_id: Optional[str], 
                      request: Optional[Request], details: Dict[str, Any] = None):
    """Log security-related events for audit purposes."""
    event = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event_type": event_type,
        "user_id": user_id,
        "ip_address": request.client.host if request else None,
        "user_agent": request.headers.get("user-agent") if request else None,
        "details": details or {}
    }
    
    security_audit_log.append(event)
    security_logger.info(f"Security event: {event_type}", extra=event)


def check_rate_limit(client_id: str, limit: int = RATE_LIMIT_REQUESTS, 
                    window: int = RATE_LIMIT_WINDOW) -> bool:
    """Check if client has exceeded rate limit."""
    now = time.time()
    
    # Clean old entries
    if client_id in rate_limit_storage:
        rate_limit_storage[client_id] = [
            timestamp for timestamp in rate_limit_storage[client_id]
            if now - timestamp < window
        ]
    else:
        rate_limit_storage[client_id] = []
    
    # Check current rate
    if len(rate_limit_storage[client_id]) >= limit:
        return False
    
    # Add current request
    rate_limit_storage[client_id].append(now)
    return True


def get_client_identifier(request: Request, user: Optional[User] = None) -> str:
    """Get unique client identifier for rate limiting."""
    if user:
        return f"user:{user.username}"
    return f"ip:{request.client.host}"


def verify_request_signature(request: Request, signature: str, secret: str) -> bool:
    """Verify HMAC signature for webhook requests."""
    try:
        body = request.body()
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    except Exception:
        return False


def create_secure_session_token(user: User, request: Request) -> str:
    """Create a secure session token with additional security context."""
    session_data = {
        "sub": user.username,
        "tenant_id": user.tenant_id,
        "scopes": user.scopes,
        "role": user.role.value,
        "ip_address": request.client.host,
        "user_agent_hash": hashlib.sha256(
            request.headers.get("user-agent", "").encode()
        ).hexdigest()[:16],
        "iat": datetime.now(UTC),
        "jti": secrets.token_urlsafe(16)  # JWT ID for token revocation
    }
    
    return create_access_token(session_data)


async def validate_session_context(request: Request, token_data: TokenData) -> bool:
    """Validate session context for additional security."""
    try:
        # Check IP address consistency (optional, can be disabled for mobile users)
        stored_ip = token_data.get("ip_address")
        current_ip = request.client.host
        
        # For now, we'll log IP changes but not block them
        if stored_ip and stored_ip != current_ip:
            security_logger.warning(
                f"IP address changed for user {token_data.username}: {stored_ip} -> {current_ip}"
            )
        
        # Check User-Agent consistency
        stored_ua_hash = token_data.get("user_agent_hash")
        current_ua_hash = hashlib.sha256(
            request.headers.get("user-agent", "").encode()
        ).hexdigest()[:16]
        
        if stored_ua_hash and stored_ua_hash != current_ua_hash:
            security_logger.warning(
                f"User-Agent changed for user {token_data.username}"
            )
        
        return True
        
    except Exception as e:
        security_logger.error(f"Session context validation failed: {e}")
        return False


# Authentication functions
def get_user(username: str) -> Optional[UserInDB]:
    """Get user by username."""
    return fake_users_db.get(username)


def get_api_key(key: str) -> Optional[APIKey]:
    """Get API key by key value."""
    return fake_api_keys_db.get(key)


def get_tenant(tenant_id: str) -> Optional[Tenant]:
    """Get tenant by ID."""
    return fake_tenants_db.get(tenant_id)


def authenticate_user(username: str, password: str) -> Union[UserInDB, bool]:
    """Authenticate user with username and password."""
    user = get_user(username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


async def get_current_user_from_token(
    token: Optional[str] = Depends(oauth2_scheme),
    request: Request = None
) -> Optional[User]:
    """Get current user from JWT token with enhanced security validation."""
    if not token:
        return None
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        
        token_data = TokenData(
            username=username,
            tenant_id=payload.get("tenant_id"),
            scopes=payload.get("scopes", []),
            exp=datetime.fromtimestamp(payload.get("exp", 0), UTC) if payload.get("exp") else None
        )
        
        # Additional token validation
        jti = payload.get("jti")  # JWT ID for revocation checking
        if jti:
            # In production, check against revoked tokens list
            pass
            
    except JWTError as e:
        log_security_event("jwt_validation_failed", None, request, {"error": str(e)})
        raise credentials_exception
    
    user = get_user(username=token_data.username)
    if user is None:
        log_security_event("user_not_found", token_data.username, request)
        raise credentials_exception
    
    # Check if user is disabled
    if user.disabled:
        log_security_event("disabled_user_access_attempt", user.username, request)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Check token expiration
    if token_data.exp and datetime.now(UTC) > token_data.exp:
        log_security_event("expired_token_used", user.username, request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Validate session context if request is available
    if request:
        # Store additional context in token_data for validation
        token_data_dict = payload
        if not await validate_session_context(request, token_data_dict):
            log_security_event("session_context_validation_failed", user.username, request)
            # For now, just log - in production you might want to reject
    
    return User(**user.model_dump())


async def get_current_user_from_api_key(api_key: Optional[str] = Depends(api_key_header)) -> Optional[User]:
    """Get current user from API key."""
    if not api_key:
        return None
    
    key_data = get_api_key(api_key)
    if not key_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    # Check if API key is disabled
    if key_data.disabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key disabled"
        )
    
    # Check API key expiration
    if key_data.expires_at and datetime.now(UTC) > key_data.expires_at:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key expired"
        )
    
    # Create a user object from API key
    return User(
        username=f"api_key_{key_data.name}",
        email=None,
        full_name=f"API Key: {key_data.name}",
        disabled=False,
        role=UserRole.USER,
        tenant_id=key_data.tenant_id,
        scopes=key_data.scopes
    )


async def check_rate_limit_dependency(request: Request):
    """Dependency to check rate limiting."""
    client_id = get_client_identifier(request)
    
    if not check_rate_limit(client_id):
        log_security_event("rate_limit_exceeded", None, request, {"client_id": client_id})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(RATE_LIMIT_WINDOW)}
        )


async def get_current_user(
    request: Request,
    _: None = Depends(check_rate_limit_dependency),
    token_user: Optional[User] = Depends(get_current_user_from_token),
    api_key_user: Optional[User] = Depends(get_current_user_from_api_key)
) -> User:
    """Get current user from either JWT token or API key with rate limiting."""
    user = token_user or api_key_user
    
    if not user:
        log_security_event("unauthenticated_access_attempt", None, request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Log successful authentication
    log_security_event("successful_authentication", user.username, request, {
        "auth_method": "jwt" if token_user else "api_key"
    })
    
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user."""
    if current_user.disabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


async def get_current_tenant(current_user: User = Depends(get_current_active_user)) -> Optional[Tenant]:
    """Get current user's tenant."""
    if not current_user.tenant_id:
        return None
    
    tenant = get_tenant(current_user.tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    if tenant.disabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant disabled"
        )
    
    return tenant


def require_scope(required_scope: str):
    """Dependency factory for requiring specific scopes."""
    def scope_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if required_scope not in current_user.scopes and "admin" not in current_user.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not enough permissions. Required scope: {required_scope}"
            )
        return current_user
    return scope_checker


def require_role(required_role: UserRole):
    """Dependency factory for requiring specific roles."""
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role != required_role and current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not enough permissions. Required role: {required_role.value}"
            )
        return current_user
    return role_checker


def require_tenant_access(tenant_id: str):
    """Dependency factory for requiring access to specific tenant."""
    def tenant_checker(current_user: User = Depends(get_current_active_user)) -> User:
        # Admin users can access any tenant
        if current_user.role == UserRole.ADMIN:
            return current_user
        
        # Regular users can only access their own tenant
        if current_user.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this tenant"
            )
        return current_user
    return tenant_checker


# User management functions
def create_user(
    username: str,
    password: str,
    email: Optional[str] = None,
    full_name: Optional[str] = None,
    role: UserRole = UserRole.USER,
    tenant_id: Optional[str] = None,
    scopes: Optional[List[str]] = None
) -> UserInDB:
    """Create a new user."""
    if username in fake_users_db:
        raise ValueError("User already exists")
    
    user = UserInDB(
        username=username,
        email=email,
        full_name=full_name,
        disabled=False,
        role=role,
        tenant_id=tenant_id,
        scopes=scopes or [],
        hashed_password=get_password_hash(password)
    )
    
    fake_users_db[username] = user
    return user


def create_api_key(
    name: str,
    tenant_id: Optional[str] = None,
    scopes: Optional[List[str]] = None,
    expires_in_days: Optional[int] = None
) -> APIKey:
    """Create a new API key."""
    key = generate_api_key()
    expires_at = None
    if expires_in_days:
        expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)
    
    api_key = APIKey(
        key=key,
        name=name,
        tenant_id=tenant_id,
        scopes=scopes or [],
        expires_at=expires_at,
        disabled=False
    )
    
    fake_api_keys_db[key] = api_key
    return api_key


def create_tenant(
    tenant_id: str,
    name: str,
    description: Optional[str] = None,
    settings: Optional[Dict[str, Any]] = None
) -> Tenant:
    """Create a new tenant."""
    if tenant_id in fake_tenants_db:
        raise ValueError("Tenant already exists")
    
    tenant = Tenant(
        id=tenant_id,
        name=name,
        description=description,
        disabled=False,
        settings=settings or {}
    )
    
    fake_tenants_db[tenant_id] = tenant
    return tenant