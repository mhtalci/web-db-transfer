"""
Main FastAPI application for the Migration Assistant API.

This module provides the REST API endpoints for programmatic
access to migration functionality with async support for long-running migrations.
"""

import sys
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any
from datetime import datetime

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from migration_assistant import __version__
from migration_assistant.models.config import MigrationConfig, SystemType, TransferMethod, DatabaseType
from migration_assistant.models.session import MigrationSession, MigrationStatus, StepStatus, LogLevel
from migration_assistant.orchestrator.orchestrator import MigrationOrchestrator
from migration_assistant.cli.preset_manager import PresetManager
from migration_assistant.validation.engine import ValidationEngine
from migration_assistant.backup.manager import BackupManager
from migration_assistant.backup.rollback import RollbackManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
orchestrator: Optional[MigrationOrchestrator] = None
preset_manager: Optional[PresetManager] = None
validation_engine: Optional[ValidationEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global orchestrator, preset_manager, validation_engine
    
    # Startup
    logger.info(f"Starting Migration Assistant API v{__version__}")
    
    # Initialize components
    try:
        backup_manager = BackupManager()
        rollback_manager = RollbackManager()
        orchestrator = MigrationOrchestrator(
            backup_manager=backup_manager,
            rollback_manager=rollback_manager
        )
        preset_manager = PresetManager()
        validation_engine = ValidationEngine()
        
        logger.info("API components initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize API components: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Migration Assistant API")


# Create FastAPI application
app = FastAPI(
    title="Web & Database Migration Assistant API",
    description="A comprehensive REST API for migrating web applications and databases between different systems, platforms, and environments",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    contact={
        "name": "Migration Assistant Support",
        "url": "https://github.com/migration-assistant/support",
        "email": "support@migration-assistant.com"
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    }
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include authentication routes (import here to avoid circular imports)
try:
    from .auth_routes import router as auth_router
    app.include_router(auth_router)
except ImportError as e:
    logger.warning(f"Could not import auth routes: {e}")


# Response models
class MigrationCreateResponse(BaseModel):
    """Response model for migration creation."""
    session_id: str
    status: str
    message: str
    created_at: datetime


class MigrationStatusResponse(BaseModel):
    """Response model for migration status."""
    session_id: str
    status: MigrationStatus
    progress: float
    current_step: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    error: Optional[str] = None
    steps_completed: int
    steps_total: int


class MigrationListResponse(BaseModel):
    """Response model for migration listing."""
    session_id: str
    name: str
    status: MigrationStatus
    created_at: datetime
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    source_type: str
    destination_type: str
    progress: float


class PresetResponse(BaseModel):
    """Response model for preset information."""
    id: str
    name: str
    description: str
    source_types: List[str]
    destination_types: List[str]


class ValidationResponse(BaseModel):
    """Response model for configuration validation."""
    valid: bool
    checks_performed: int
    checks_passed: int
    checks_failed: int
    warnings: List[str]
    errors: List[str]
    can_proceed: bool
    estimated_duration: Optional[str] = None


# Import authentication dependencies
from .auth import get_current_active_user, get_current_tenant, require_scope, User, Tenant


# Dependency to get orchestrator instance
async def get_orchestrator() -> MigrationOrchestrator:
    """Get the migration orchestrator instance."""
    if orchestrator is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Migration orchestrator not initialized"
        )
    return orchestrator


# Dependency to get preset manager instance
async def get_preset_manager() -> PresetManager:
    """Get the preset manager instance."""
    if preset_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Preset manager not initialized"
        )
    return preset_manager


# Dependency to get validation engine instance
async def get_validation_engine() -> ValidationEngine:
    """Get the validation engine instance."""
    if validation_engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Validation engine not initialized"
        )
    return validation_engine


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": __version__,
        "service": "Migration Assistant API",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "orchestrator": orchestrator is not None,
            "preset_manager": preset_manager is not None,
            "validation_engine": validation_engine is not None
        }
    }


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Web & Database Migration Assistant API",
        "version": __version__,
        "description": "A comprehensive REST API for migrating web applications and databases between different systems, platforms, and environments",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "health_url": "/health",
        "features": [
            "Async migration execution",
            "Real-time progress tracking",
            "Multiple transfer methods",
            "Database migration support",
            "Backup and rollback capabilities",
            "Platform-specific adapters",
            "Comprehensive validation"
        ]
    }


# Migration endpoints
@app.post("/migrations/", 
          response_model=MigrationCreateResponse, 
          status_code=status.HTTP_201_CREATED,
          tags=["Migrations"])
async def create_migration(
    config: MigrationConfig,
    current_user: User = Depends(require_scope("migrations:write")),
    current_tenant: Optional[Tenant] = Depends(get_current_tenant),
    orch: MigrationOrchestrator = Depends(get_orchestrator)
):
    """
    Create a new migration session.
    
    This endpoint creates a new migration session with the provided configuration.
    The migration will be queued for execution and a session ID will be returned.
    
    - **config**: Complete migration configuration including source, destination, transfer settings, and options
    - **Returns**: Session ID and creation details for tracking the migration
    """
    try:
        # Set tenant ID from current user
        if current_tenant:
            config.tenant_id = current_tenant.id
        elif current_user.tenant_id:
            config.tenant_id = current_user.tenant_id
        
        # Set created_by
        config.created_by = current_user.username
        
        # Create migration session
        session = await orch.create_migration_session(config)
        
        logger.info(f"Created migration session {session.id} for config {config.name} by user {current_user.username}")
        
        return MigrationCreateResponse(
            session_id=session.id,
            status="created",
            message="Migration session created successfully",
            created_at=session.created_at
        )
    except Exception as e:
        logger.error(f"Failed to create migration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create migration: {str(e)}"
        )


@app.get("/migrations/{session_id}/status", 
         response_model=MigrationStatusResponse,
         tags=["Migrations"])
async def get_migration_status(
    session_id: str,
    current_user: User = Depends(require_scope("migrations:read")),
    orch: MigrationOrchestrator = Depends(get_orchestrator)
):
    """
    Get migration status by session ID.
    
    Returns detailed status information including progress, current step,
    and any errors that may have occurred.
    
    - **session_id**: Unique identifier for the migration session
    - **Returns**: Detailed status including progress, current step, and timing information
    """
    try:
        # Get session from orchestrator
        session = orch._active_sessions.get(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Migration session not found: {session_id}"
            )
        
        # Check tenant access
        if current_user.role.value != "admin" and session.tenant_id != current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this migration session"
            )
        
        # Calculate progress
        completed_steps = sum(1 for step in session.steps if step.status == StepStatus.COMPLETED)
        total_steps = len(session.steps)
        progress = (completed_steps / total_steps * 100) if total_steps > 0 else 0
        
        # Get error message if failed
        error_message = None
        if session.error:
            error_message = session.error.message
        
        return MigrationStatusResponse(
            session_id=session.id,
            status=session.status,
            progress=progress,
            current_step=session.current_step,
            start_time=session.start_time,
            end_time=session.end_time,
            duration=session.duration,
            error=error_message,
            steps_completed=completed_steps,
            steps_total=total_steps
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get migration status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get migration status: {str(e)}"
        )


@app.get("/migrations/", 
         response_model=List[MigrationListResponse],
         tags=["Migrations"])
async def list_migrations(
    status_filter: Optional[MigrationStatus] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(require_scope("migrations:read")),
    orch: MigrationOrchestrator = Depends(get_orchestrator)
):
    """
    List all migration sessions.
    
    Optionally filter by status. Returns a list of migration sessions
    with basic information.
    
    - **status_filter**: Optional status filter (pending, running, completed, failed, etc.)
    - **limit**: Maximum number of results to return (default: 100)
    - **offset**: Number of results to skip (default: 0)
    - **Returns**: List of migration sessions with basic information
    """
    try:
        sessions = list(orch._active_sessions.values())
        
        # Filter by tenant access
        if current_user.role.value != "admin":
            sessions = [s for s in sessions if s.tenant_id == current_user.tenant_id]
        
        # Filter by status if provided
        if status_filter:
            sessions = [s for s in sessions if s.status == status_filter]
        
        # Sort by creation time (newest first)
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        
        # Apply pagination
        sessions = sessions[offset:offset + limit]
        
        # Convert to response format
        result = []
        for session in sessions:
            completed_steps = sum(1 for step in session.steps if step.status == StepStatus.COMPLETED)
            total_steps = len(session.steps)
            progress = (completed_steps / total_steps * 100) if total_steps > 0 else 0
            
            result.append(MigrationListResponse(
                session_id=session.id,
                name=session.config.name,
                status=session.status,
                created_at=session.created_at,
                start_time=session.start_time,
                end_time=session.end_time,
                source_type=session.config.source.type.value,
                destination_type=session.config.destination.type.value,
                progress=progress
            ))
        
        return result
    except Exception as e:
        logger.error(f"Failed to list migrations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list migrations: {str(e)}"
        )


@app.post("/migrations/{session_id}/start", 
          response_model=Dict[str, str],
          tags=["Migrations"])
async def start_migration(
    session_id: str,
    background_tasks: BackgroundTasks,
    auto_rollback: bool = True,
    current_user: User = Depends(require_scope("migrations:write")),
    orch: MigrationOrchestrator = Depends(get_orchestrator)
):
    """
    Start a migration session.
    
    Begins execution of a previously created migration session.
    The migration runs asynchronously in the background.
    
    - **session_id**: Unique identifier for the migration session
    - **auto_rollback**: Whether to automatically rollback on failure (default: true)
    - **Returns**: Confirmation that migration has started
    """
    try:
        # Check if session exists
        session = orch._active_sessions.get(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Migration session not found: {session_id}"
            )
        
        # Check tenant access
        if current_user.role.value != "admin" and session.tenant_id != current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this migration session"
            )
        
        # Check if session is in a startable state
        if session.status not in [MigrationStatus.PENDING]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Migration session cannot be started. Current status: {session.status.value}"
            )
        
        # Start migration in background
        background_tasks.add_task(
            _execute_migration_background,
            orch,
            session_id,
            auto_rollback
        )
        
        logger.info(f"Started migration session {session_id}")
        
        return {
            "session_id": session_id,
            "status": "started",
            "message": "Migration execution started in background"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start migration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start migration: {str(e)}"
        )


async def _execute_migration_background(
    orch: MigrationOrchestrator,
    session_id: str,
    auto_rollback: bool
):
    """Execute migration in background task."""
    try:
        await orch.execute_migration(
            session_id=session_id,
            show_progress=False,  # No console output in API mode
            auto_rollback=auto_rollback
        )
        logger.info(f"Migration {session_id} completed successfully")
    except Exception as e:
        logger.error(f"Migration {session_id} failed: {str(e)}")


@app.post("/migrations/{session_id}/cancel", 
          response_model=Dict[str, str],
          tags=["Migrations"])
async def cancel_migration(
    session_id: str,
    current_user: User = Depends(require_scope("migrations:write")),
    orch: MigrationOrchestrator = Depends(get_orchestrator)
):
    """
    Cancel a running migration session.
    
    Attempts to gracefully cancel a running migration and perform cleanup.
    
    - **session_id**: Unique identifier for the migration session
    - **Returns**: Confirmation that migration cancellation was initiated
    """
    try:
        # Check if session exists
        session = orch._active_sessions.get(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Migration session not found: {session_id}"
            )
        
        # Check if session can be cancelled
        if session.status not in [MigrationStatus.RUNNING, MigrationStatus.PENDING, MigrationStatus.VALIDATING]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Migration session cannot be cancelled. Current status: {session.status.value}"
            )
        
        # Cancel the session
        session.cancel()
        session.add_log(LogLevel.INFO, "Migration cancelled via API request")
        
        logger.info(f"Cancelled migration session {session_id}")
        
        return {
            "session_id": session_id,
            "status": "cancelled",
            "message": "Migration cancellation initiated"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel migration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel migration: {str(e)}"
        )


@app.post("/migrations/{session_id}/rollback", 
          response_model=Dict[str, str],
          tags=["Migrations"])
async def rollback_migration(
    session_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_scope("migrations:write")),
    orch: MigrationOrchestrator = Depends(get_orchestrator)
):
    """
    Rollback a migration session.
    
    Attempts to rollback a completed or failed migration using available backups.
    The rollback process runs asynchronously in the background.
    
    - **session_id**: Unique identifier for the migration session
    - **Returns**: Confirmation that rollback has started
    """
    try:
        # Check if session exists
        session = orch._active_sessions.get(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Migration session not found: {session_id}"
            )
        
        # Check if session can be rolled back
        if session.status not in [MigrationStatus.COMPLETED, MigrationStatus.FAILED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Migration session cannot be rolled back. Current status: {session.status.value}"
            )
        
        # Check if backups are available
        if not session.backups:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No backups available for rollback"
            )
        
        # Start rollback in background
        background_tasks.add_task(
            _execute_rollback_background,
            orch,
            session_id
        )
        
        logger.info(f"Started rollback for migration session {session_id}")
        
        return {
            "session_id": session_id,
            "status": "rollback_started",
            "message": "Migration rollback started in background"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start rollback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start rollback: {str(e)}"
        )


async def _execute_rollback_background(
    orch: MigrationOrchestrator,
    session_id: str
):
    """Execute rollback in background task."""
    try:
        session = orch._active_sessions.get(session_id)
        if session and orch.rollback_manager:
            await orch._rollback_migration(session)
            session.rollback()
            logger.info(f"Rollback for migration {session_id} completed successfully")
        else:
            logger.error(f"Cannot rollback migration {session_id}: session or rollback manager not found")
    except Exception as e:
        logger.error(f"Rollback for migration {session_id} failed: {str(e)}")


# Configuration and preset endpoints
@app.get("/presets/", 
         response_model=List[PresetResponse],
         tags=["Configuration"])
async def list_presets(
    current_user: User = Depends(require_scope("presets:read")),
    preset_mgr: PresetManager = Depends(get_preset_manager)
):
    """
    List available migration presets.
    
    Returns a list of predefined migration configurations for common scenarios
    like WordPress/MySQL, Django/PostgreSQL, static sites, etc.
    
    - **Returns**: List of available presets with their supported source and destination types
    """
    try:
        presets = preset_mgr.get_available_presets()
        
        result = []
        for preset_key, name, description in presets:
            preset_config = preset_mgr.get_preset_config(preset_key)
            if preset_config:
                # Extract source and destination types from preset
                source_types = [preset_config["source"]["type"]]
                destination_types = [preset_config["destination"]["type"]]
                
                result.append(PresetResponse(
                    id=preset_key,
                    name=name,
                    description=description,
                    source_types=source_types,
                    destination_types=destination_types
                ))
        
        return result
    except Exception as e:
        logger.error(f"Failed to list presets: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list presets: {str(e)}"
        )


@app.get("/presets/{preset_id}", 
         tags=["Configuration"])
async def get_preset(
    preset_id: str,
    current_user: User = Depends(require_scope("presets:read")),
    preset_mgr: PresetManager = Depends(get_preset_manager)
):
    """
    Get a specific migration preset by ID.
    
    Returns the complete configuration template for the specified preset.
    
    - **preset_id**: Unique identifier for the preset
    - **Returns**: Complete preset configuration template
    """
    try:
        preset_config = preset_mgr.get_preset_config(preset_id)
        if not preset_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Preset not found: {preset_id}"
            )
        
        return {
            "id": preset_id,
            "name": preset_config.get("name", preset_id),
            "description": preset_config.get("description", ""),
            "config_template": preset_config,
            "custom": preset_config.get("custom", False)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get preset: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get preset: {str(e)}"
        )


@app.post("/presets/{preset_id}/create-migration",
          response_model=MigrationCreateResponse,
          status_code=status.HTTP_201_CREATED,
          tags=["Configuration"])
async def create_migration_from_preset(
    preset_id: str,
    overrides: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(require_scope("migrations:write")),
    current_tenant: Optional[Tenant] = Depends(get_current_tenant),
    preset_mgr: PresetManager = Depends(get_preset_manager),
    orch: MigrationOrchestrator = Depends(get_orchestrator)
):
    """
    Create a migration session from a preset.
    
    Creates a new migration session using a predefined preset configuration
    with optional parameter overrides.
    
    - **preset_id**: Unique identifier for the preset
    - **overrides**: Optional dictionary of configuration values to override
    - **Returns**: Session ID and creation details for the new migration
    """
    try:
        # Create migration config from preset
        config = preset_mgr.create_migration_config_from_preset(preset_id, overrides)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Preset not found: {preset_id}"
            )
        
        # Set tenant ID from current user
        if current_tenant:
            config.tenant_id = current_tenant.id
        elif current_user.tenant_id:
            config.tenant_id = current_user.tenant_id
        
        # Set created_by
        config.created_by = current_user.username
        
        # Create migration session
        session = await orch.create_migration_session(config)
        
        logger.info(f"Created migration session {session.id} from preset {preset_id}")
        
        return MigrationCreateResponse(
            session_id=session.id,
            status="created",
            message=f"Migration session created from preset {preset_id}",
            created_at=session.created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create migration from preset: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create migration from preset: {str(e)}"
        )


@app.post("/validate/", 
          response_model=ValidationResponse,
          tags=["Validation"])
async def validate_configuration(
    config: MigrationConfig,
    current_user: User = Depends(require_scope("migrations:read")),
    validation_engine: ValidationEngine = Depends(get_validation_engine)
):
    """
    Validate a migration configuration.
    
    Performs comprehensive validation of the migration configuration
    including connectivity tests, compatibility checks, and dependency verification.
    
    - **config**: Complete migration configuration to validate
    - **Returns**: Detailed validation results with errors, warnings, and recommendations
    """
    try:
        # Run validation
        validation_summary = await validation_engine.validate_migration(
            config,
            show_progress=False,
            detailed_output=False
        )
        
        # Convert validation summary to response format
        return ValidationResponse(
            valid=validation_summary.can_proceed,
            checks_performed=validation_summary.total_checks,
            checks_passed=validation_summary.passed_checks,
            checks_failed=validation_summary.failed_checks,
            warnings=[issue.message for issue in validation_summary.warning_issues_list],
            errors=[issue.message for issue in validation_summary.critical_issues_list],
            can_proceed=validation_summary.can_proceed,
            estimated_duration=validation_summary.estimated_fix_time
        )
    except Exception as e:
        logger.error(f"Configuration validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation failed: {str(e)}"
        )


# System information endpoints
@app.get("/system/types",
         tags=["System"])
async def get_system_types():
    """
    Get available system types.
    
    Returns lists of supported source and destination system types.
    
    - **Returns**: Available system types, transfer methods, and database types
    """
    return {
        "system_types": [t.value for t in SystemType],
        "transfer_methods": [t.value for t in TransferMethod],
        "database_types": [t.value for t in DatabaseType]
    }


@app.get("/system/modules",
         tags=["System"])
async def get_available_modules():
    """
    Get available migration modules.
    
    Returns information about available platform adapters, transfer methods,
    and database migrators.
    
    - **Returns**: Available modules and their capabilities
    """
    return {
        "platform_adapters": {
            "cms": ["wordpress", "drupal", "joomla"],
            "frameworks": ["django", "flask", "fastapi", "laravel", "rails", "spring_boot", "nextjs"],
            "cloud": ["aws_s3", "google_cloud_storage", "azure_blob"],
            "containers": ["docker_container", "kubernetes_pod"],
            "control_panels": ["cpanel", "directadmin", "plesk"]
        },
        "transfer_methods": {
            "secure": ["ssh_scp", "ssh_sftp", "rsync"],
            "traditional": ["ftp", "ftps"],
            "cloud": ["aws_s3", "google_cloud_storage", "azure_blob"],
            "containers": ["docker_volume", "kubernetes_volume"],
            "high_performance": ["hybrid_sync"]
        },
        "database_migrators": {
            "relational": ["mysql", "postgresql", "sqlite", "sqlserver", "oracle"],
            "nosql": ["mongodb", "redis", "cassandra"],
            "cloud": ["aws_rds", "google_cloud_sql", "azure_sql"]
        }
    }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions with consistent error format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "type": "http_error"
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions with consistent error format."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error",
                "type": "server_error",
                "details": str(exc) if app.debug else None
            }
        }
    )


def start_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Start the FastAPI server."""
    try:
        uvicorn.run(
            "migration_assistant.api.main:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info"
        )
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    start_server()