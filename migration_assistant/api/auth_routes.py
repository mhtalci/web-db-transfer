"""
Authentication routes for the Migration Assistant API.

This module provides endpoints for user authentication, token management,
and user/tenant administration.
"""

from datetime import timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from .auth import (
    Token, User, UserInDB, APIKey, Tenant, UserRole,
    authenticate_user, create_access_token, create_user, create_api_key, create_tenant,
    get_current_active_user, get_current_tenant, require_role, require_scope,
    fake_users_db, fake_api_keys_db, fake_tenants_db,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# Request/Response models
class UserCreate(BaseModel):
    """User creation request model."""
    username: str
    password: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: UserRole = UserRole.USER
    tenant_id: Optional[str] = None
    scopes: List[str] = []


class UserResponse(BaseModel):
    """User response model."""
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: bool
    role: UserRole
    tenant_id: Optional[str] = None
    scopes: List[str]


class APIKeyCreate(BaseModel):
    """API key creation request model."""
    name: str
    tenant_id: Optional[str] = None
    scopes: List[str] = []
    expires_in_days: Optional[int] = None


class APIKeyResponse(BaseModel):
    """API key response model."""
    key: str
    name: str
    tenant_id: Optional[str] = None
    scopes: List[str]
    created_at: str
    expires_at: Optional[str] = None
    disabled: bool


class TenantCreate(BaseModel):
    """Tenant creation request model."""
    id: str
    name: str
    description: Optional[str] = None
    settings: Dict[str, Any] = {}


class TenantResponse(BaseModel):
    """Tenant response model."""
    id: str
    name: str
    description: Optional[str] = None
    created_at: str
    disabled: bool
    settings: Dict[str, Any]


# Authentication endpoints
@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 compatible token login endpoint.
    
    Authenticate user with username and password, return JWT access token.
    
    - **username**: User's username
    - **password**: User's password
    - **scope**: Optional space-separated scopes
    - **Returns**: JWT access token with expiration info
    """
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Parse requested scopes
    requested_scopes = form_data.scopes if hasattr(form_data, 'scopes') else []
    
    # Filter scopes to only include those the user actually has
    allowed_scopes = [scope for scope in requested_scopes if scope in user.scopes or "admin" in user.scopes]
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.username,
            "tenant_id": user.tenant_id,
            "scopes": allowed_scopes
        },
        expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        scope=" ".join(allowed_scopes) if allowed_scopes else None
    )


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """
    Get current user information.
    
    Returns the authenticated user's profile information.
    
    - **Returns**: Current user's profile data
    """
    return UserResponse(
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        disabled=current_user.disabled,
        role=current_user.role,
        tenant_id=current_user.tenant_id,
        scopes=current_user.scopes
    )


@router.get("/me/tenant", response_model=Optional[TenantResponse])
async def read_users_tenant(current_tenant: Optional[Tenant] = Depends(get_current_tenant)):
    """
    Get current user's tenant information.
    
    Returns the tenant information for the authenticated user.
    
    - **Returns**: Current user's tenant data or null if no tenant
    """
    if not current_tenant:
        return None
    
    return TenantResponse(
        id=current_tenant.id,
        name=current_tenant.name,
        description=current_tenant.description,
        created_at=current_tenant.created_at.isoformat(),
        disabled=current_tenant.disabled,
        settings=current_tenant.settings
    )


# User management endpoints (admin only)
@router.post("/users", response_model=UserResponse)
async def create_new_user(
    user_data: UserCreate,
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """
    Create a new user (admin only).
    
    Creates a new user account with the specified details.
    
    - **user_data**: User creation data
    - **Returns**: Created user information
    """
    try:
        new_user = create_user(
            username=user_data.username,
            password=user_data.password,
            email=user_data.email,
            full_name=user_data.full_name,
            role=user_data.role,
            tenant_id=user_data.tenant_id,
            scopes=user_data.scopes
        )
        
        return UserResponse(
            username=new_user.username,
            email=new_user.email,
            full_name=new_user.full_name,
            disabled=new_user.disabled,
            role=new_user.role,
            tenant_id=new_user.tenant_id,
            scopes=new_user.scopes
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    tenant_id: Optional[str] = None,
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """
    List all users (admin only).
    
    Returns a list of all users, optionally filtered by tenant.
    
    - **tenant_id**: Optional tenant ID filter
    - **Returns**: List of users
    """
    users = []
    for user in fake_users_db.values():
        if tenant_id and user.tenant_id != tenant_id:
            continue
        
        users.append(UserResponse(
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            disabled=user.disabled,
            role=user.role,
            tenant_id=user.tenant_id,
            scopes=user.scopes
        ))
    
    return users


@router.get("/users/{username}", response_model=UserResponse)
async def get_user(
    username: str,
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """
    Get user by username (admin only).
    
    Returns detailed information about a specific user.
    
    - **username**: Username to retrieve
    - **Returns**: User information
    """
    user = fake_users_db.get(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        disabled=user.disabled,
        role=user.role,
        tenant_id=user.tenant_id,
        scopes=user.scopes
    )


# API key management endpoints
@router.post("/api-keys", response_model=APIKeyResponse)
async def create_new_api_key(
    api_key_data: APIKeyCreate,
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new API key.
    
    Creates a new API key for the current user or tenant.
    
    - **api_key_data**: API key creation data
    - **Returns**: Created API key information
    """
    # Non-admin users can only create API keys for their own tenant
    if current_user.role != UserRole.ADMIN:
        if api_key_data.tenant_id and api_key_data.tenant_id != current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create API key for different tenant"
            )
        api_key_data.tenant_id = current_user.tenant_id
    
    # Limit scopes to what the user has
    if current_user.role != UserRole.ADMIN:
        allowed_scopes = [scope for scope in api_key_data.scopes if scope in current_user.scopes]
        api_key_data.scopes = allowed_scopes
    
    api_key = create_api_key(
        name=api_key_data.name,
        tenant_id=api_key_data.tenant_id,
        scopes=api_key_data.scopes,
        expires_in_days=api_key_data.expires_in_days
    )
    
    return APIKeyResponse(
        key=api_key.key,
        name=api_key.name,
        tenant_id=api_key.tenant_id,
        scopes=api_key.scopes,
        created_at=api_key.created_at.isoformat(),
        expires_at=api_key.expires_at.isoformat() if api_key.expires_at else None,
        disabled=api_key.disabled
    )


@router.get("/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_active_user)
):
    """
    List API keys.
    
    Returns API keys accessible to the current user.
    
    - **Returns**: List of API keys
    """
    api_keys = []
    for api_key in fake_api_keys_db.values():
        # Admin can see all API keys, others only their tenant's
        if current_user.role == UserRole.ADMIN or api_key.tenant_id == current_user.tenant_id:
            api_keys.append(APIKeyResponse(
                key=api_key.key,
                name=api_key.name,
                tenant_id=api_key.tenant_id,
                scopes=api_key.scopes,
                created_at=api_key.created_at.isoformat(),
                expires_at=api_key.expires_at.isoformat() if api_key.expires_at else None,
                disabled=api_key.disabled
            ))
    
    return api_keys


@router.delete("/api-keys/{key}")
async def delete_api_key(
    key: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete an API key.
    
    Removes an API key from the system.
    
    - **key**: API key to delete
    - **Returns**: Success confirmation
    """
    api_key = fake_api_keys_db.get(key)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Check permissions
    if current_user.role != UserRole.ADMIN and api_key.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete API key from different tenant"
        )
    
    del fake_api_keys_db[key]
    return {"message": "API key deleted successfully"}


# Tenant management endpoints (admin only)
@router.post("/tenants", response_model=TenantResponse)
async def create_new_tenant(
    tenant_data: TenantCreate,
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """
    Create a new tenant (admin only).
    
    Creates a new tenant for multi-tenant isolation.
    
    - **tenant_data**: Tenant creation data
    - **Returns**: Created tenant information
    """
    try:
        tenant = create_tenant(
            tenant_id=tenant_data.id,
            name=tenant_data.name,
            description=tenant_data.description,
            settings=tenant_data.settings
        )
        
        return TenantResponse(
            id=tenant.id,
            name=tenant.name,
            description=tenant.description,
            created_at=tenant.created_at.isoformat(),
            disabled=tenant.disabled,
            settings=tenant.settings
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/tenants", response_model=List[TenantResponse])
async def list_tenants(
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """
    List all tenants (admin only).
    
    Returns a list of all tenants in the system.
    
    - **Returns**: List of tenants
    """
    tenants = []
    for tenant in fake_tenants_db.values():
        tenants.append(TenantResponse(
            id=tenant.id,
            name=tenant.name,
            description=tenant.description,
            created_at=tenant.created_at.isoformat(),
            disabled=tenant.disabled,
            settings=tenant.settings
        ))
    
    return tenants


@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """
    Get tenant by ID (admin only).
    
    Returns detailed information about a specific tenant.
    
    - **tenant_id**: Tenant ID to retrieve
    - **Returns**: Tenant information
    """
    tenant = fake_tenants_db.get(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        description=tenant.description,
        created_at=tenant.created_at.isoformat(),
        disabled=tenant.disabled,
        settings=tenant.settings
    )