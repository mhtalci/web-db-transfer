"""
REST API endpoints for CMS platform operations.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from pathlib import Path
import asyncio
import json
from datetime import datetime

from ..platforms.factory import PlatformAdapterFactory
from ..validators.cms_validator import CMSHealthChecker, CMSCompatibilityChecker
from ..orchestrators.cms_migration_orchestrator import CMSMigrationOrchestrator
from ..monitoring.cms_metrics import CMSPerformanceMonitor
from ..models.config import SystemConfig, DatabaseConfig


router = APIRouter(prefix="/api/v1/cms", tags=["CMS Platforms"])


# Request/Response Models
class PlatformDetectionRequest(BaseModel):
    path: str = Field(..., description="Path to analyze for CMS platforms")


class PlatformDetectionResponse(BaseModel):
    detected_platforms: List[Dict[str, Any]]
    analysis_time: float
    path: str


class HealthCheckRequest(BaseModel):
    platform_type: str = Field(..., description="CMS platform type")
    path: str = Field(..., description="Path to CMS installation")


class HealthCheckResponse(BaseModel):
    platform: str
    health_score: int
    total_issues: int
    severity_breakdown: Dict[str, int]
    issues: List[Dict[str, Any]]
    recommendations: List[str]


class CompatibilityCheckRequest(BaseModel):
    source_platform: str
    source_version: Optional[str] = None
    destination_platform: str
    destination_version: Optional[str] = None


class CompatibilityCheckResponse(BaseModel):
    compatible: bool
    migration_complexity: str
    estimated_success_rate: int
    issues: List[str]
    warnings: List[str]


class MigrationPlanRequest(BaseModel):
    source_platform: str
    destination_platform: str
    source_path: str
    destination_path: str
    options: Dict[str, Any] = Field(default_factory=dict)


class MigrationPlanResponse(BaseModel):
    migration_id: str
    total_steps: int
    estimated_duration: int
    steps: List[Dict[str, Any]]


class MigrationExecutionRequest(BaseModel):
    migration_id: str


# Global instances
orchestrator = CMSMigrationOrchestrator()
active_monitors: Dict[str, CMSPerformanceMonitor] = {}


@router.get("/platforms", summary="Get supported CMS platforms")
async def get_supported_platforms():
    """Get list of all supported CMS platforms with their information."""
    try:
        platforms = PlatformAdapterFactory.get_available_platforms()
        platform_info = {}
        
        for platform in platforms:
            try:
                info = PlatformAdapterFactory.get_adapter_info(platform)
                platform_info[platform] = info
            except Exception:
                continue
        
        # Filter CMS platforms
        cms_platforms = {
            k: v for k, v in platform_info.items() 
            if k in ["wordpress", "drupal", "joomla", "magento", "shopware", 
                    "prestashop", "opencart", "ghost", "craftcms", "typo3", 
                    "concrete5", "umbraco"]
        }
        
        return {
            "total_platforms": len(cms_platforms),
            "platforms": cms_platforms,
            "categories": {
                "content_management": ["wordpress", "drupal", "joomla", "typo3", "concrete5", "ghost", "craftcms", "umbraco"],
                "ecommerce": ["magento", "shopware", "prestashop", "opencart"]
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get platforms: {str(e)}")


@router.post("/detect", response_model=PlatformDetectionResponse, summary="Detect CMS platforms")
async def detect_cms_platforms(request: PlatformDetectionRequest):
    """Detect CMS platforms at the specified path."""
    try:
        start_time = datetime.now()
        path = Path(request.path)
        
        if not path.exists():
            raise HTTPException(status_code=404, detail="Path does not exist")
        
        # Create basic config for detection
        config = SystemConfig(
            type="detection",
            host="localhost",
            database=DatabaseConfig(
                db_type="mysql",
                host="localhost",
                port=3306,
                name="temp_db",
                user="temp_user",
                password="temp_pass"
            )
        )
        
        # Detect all platforms
        detected_platforms = await PlatformAdapterFactory.analyze_directory(path, config)
        
        platform_results = []
        for adapter in detected_platforms:
            try:
                platform_info = await adapter.analyze_platform(path)
                dependencies = await adapter.get_dependencies()
                
                platform_results.append({
                    "platform_type": adapter.platform_type,
                    "version": platform_info.version,
                    "framework": platform_info.framework,
                    "database_type": platform_info.database_type,
                    "config_files": platform_info.config_files,
                    "dependencies": [
                        {
                            "name": dep.name,
                            "version": dep.version,
                            "required": dep.required
                        }
                        for dep in dependencies
                    ]
                })
            except Exception as e:
                platform_results.append({
                    "platform_type": adapter.platform_type,
                    "error": str(e)
                })
        
        analysis_time = (datetime.now() - start_time).total_seconds()
        
        return PlatformDetectionResponse(
            detected_platforms=platform_results,
            analysis_time=analysis_time,
            path=request.path
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")


@router.post("/health-check", response_model=HealthCheckResponse, summary="Perform CMS health check")
async def perform_health_check(request: HealthCheckRequest):
    """Perform comprehensive health check on CMS installation."""
    try:
        path = Path(request.path)
        
        if not path.exists():
            raise HTTPException(status_code=404, detail="Path does not exist")
        
        # Create health checker
        checker = CMSHealthChecker(request.platform_type, path)
        
        # Run health check
        health_result = await checker.run_health_check()
        
        return HealthCheckResponse(**health_result)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.post("/compatibility-check", response_model=CompatibilityCheckResponse, summary="Check migration compatibility")
async def check_migration_compatibility(request: CompatibilityCheckRequest):
    """Check compatibility between source and destination platforms."""
    try:
        compatibility_result = await CMSCompatibilityChecker.check_migration_compatibility(
            request.source_platform,
            request.source_version or "unknown",
            request.destination_platform,
            request.destination_version or "unknown"
        )
        
        return CompatibilityCheckResponse(**compatibility_result)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compatibility check failed: {str(e)}")


@router.post("/migration/plan", response_model=MigrationPlanResponse, summary="Create migration plan")
async def create_migration_plan(request: MigrationPlanRequest):
    """Create a detailed migration plan."""
    try:
        source_path = Path(request.source_path)
        destination_path = Path(request.destination_path)
        
        if not source_path.exists():
            raise HTTPException(status_code=404, detail="Source path does not exist")
        
        # Create migration plan
        plan = await orchestrator.create_migration_plan(
            request.source_platform,
            request.destination_platform,
            source_path,
            destination_path,
            request.options
        )
        
        # Format steps for response
        steps = [
            {
                "id": step.id,
                "name": step.name,
                "stage": step.stage.value,
                "description": step.description,
                "estimated_duration": step.estimated_duration,
                "dependencies": step.dependencies
            }
            for step in plan.steps
        ]
        
        return MigrationPlanResponse(
            migration_id=plan.id,
            total_steps=len(plan.steps),
            estimated_duration=plan.total_estimated_duration,
            steps=steps
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create migration plan: {str(e)}")


@router.post("/migration/execute", summary="Execute migration plan")
async def execute_migration_plan(request: MigrationExecutionRequest, background_tasks: BackgroundTasks):
    """Execute migration plan with real-time progress updates."""
    try:
        migration_id = request.migration_id
        
        # Start performance monitoring
        monitor = CMSPerformanceMonitor(migration_id)
        active_monitors[migration_id] = monitor
        await monitor.start_monitoring()
        
        # Execute migration in background
        async def run_migration():
            try:
                async for progress in orchestrator.execute_migration(migration_id):
                    # Progress updates are handled by the streaming endpoint
                    pass
            finally:
                await monitor.stop_monitoring()
        
        background_tasks.add_task(run_migration)
        
        return {
            "migration_id": migration_id,
            "status": "started",
            "message": "Migration execution started. Use /migration/{migration_id}/status for updates."
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start migration: {str(e)}")


@router.get("/migration/{migration_id}/status", summary="Get migration status")
async def get_migration_status(migration_id: str):
    """Get current migration status and progress."""
    try:
        status = await orchestrator.get_migration_status(migration_id)
        
        if 'error' in status:
            raise HTTPException(status_code=404, detail=status['error'])
        
        # Add performance metrics if available
        if migration_id in active_monitors:
            monitor = active_monitors[migration_id]
            performance_metrics = monitor.get_current_metrics()
            status['performance'] = performance_metrics
        
        return status
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get migration status: {str(e)}")


@router.get("/migration/{migration_id}/stream", summary="Stream migration progress")
async def stream_migration_progress(migration_id: str):
    """Stream real-time migration progress updates."""
    
    async def generate_progress():
        """Generate Server-Sent Events for migration progress."""
        try:
            # Check if migration exists
            status = await orchestrator.get_migration_status(migration_id)
            if 'error' in status:
                yield f"data: {json.dumps({'error': status['error']})}\n\n"
                return
            
            # Stream progress updates
            while True:
                current_status = await orchestrator.get_migration_status(migration_id)
                
                # Add performance metrics
                if migration_id in active_monitors:
                    monitor = active_monitors[migration_id]
                    current_status['performance'] = monitor.get_current_metrics()
                
                yield f"data: {json.dumps(current_status)}\n\n"
                
                # Check if migration is complete
                if current_status.get('overall_progress', 0) >= 100:
                    break
                
                await asyncio.sleep(2)  # Update every 2 seconds
                
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/migration/{migration_id}/pause", summary="Pause migration")
async def pause_migration(migration_id: str):
    """Pause an active migration."""
    try:
        await orchestrator.pause_migration(migration_id)
        return {"migration_id": migration_id, "status": "paused"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pause migration: {str(e)}")


@router.post("/migration/{migration_id}/resume", summary="Resume migration")
async def resume_migration(migration_id: str):
    """Resume a paused migration."""
    try:
        await orchestrator.resume_migration(migration_id)
        return {"migration_id": migration_id, "status": "resumed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume migration: {str(e)}")


@router.post("/migration/{migration_id}/cancel", summary="Cancel migration")
async def cancel_migration(migration_id: str):
    """Cancel an active migration."""
    try:
        await orchestrator.cancel_migration(migration_id)
        
        # Stop monitoring if active
        if migration_id in active_monitors:
            await active_monitors[migration_id].stop_monitoring()
            del active_monitors[migration_id]
        
        return {"migration_id": migration_id, "status": "cancelled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel migration: {str(e)}")


@router.get("/migration/{migration_id}/report", summary="Get migration report")
async def get_migration_report(migration_id: str):
    """Get comprehensive migration performance report."""
    try:
        if migration_id not in active_monitors:
            raise HTTPException(status_code=404, detail="Migration monitoring data not found")
        
        monitor = active_monitors[migration_id]
        report = monitor.generate_performance_report()
        
        return report
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.get("/statistics", summary="Get global CMS migration statistics")
async def get_migration_statistics():
    """Get global migration statistics and platform performance data."""
    try:
        # This would normally come from a persistent metrics collector
        # For now, return sample statistics
        
        return {
            "total_migrations": 1247,
            "successful_migrations": 1189,
            "success_rate_percent": 95.3,
            "total_platforms_supported": 12,
            "most_popular_platforms": [
                {"platform": "wordpress", "migrations": 456, "success_rate": 97.8},
                {"platform": "drupal", "migrations": 234, "success_rate": 94.2},
                {"platform": "magento", "migrations": 189, "success_rate": 91.5},
                {"platform": "joomla", "migrations": 156, "success_rate": 96.1}
            ],
            "average_migration_time_minutes": 42,
            "total_data_migrated_gb": 15847.3,
            "platform_compatibility_matrix": {
                "wordpress": ["wordpress", "drupal", "ghost"],
                "drupal": ["drupal", "wordpress", "ghost"],
                "magento": ["magento", "shopware", "prestashop", "opencart"],
                "shopware": ["shopware", "magento", "prestashop", "opencart"]
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


# Health check endpoint
@router.get("/health", summary="API health check")
async def health_check():
    """Check API health and service status."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "features": {
            "platform_detection": True,
            "health_checking": True,
            "migration_orchestration": True,
            "real_time_monitoring": True,
            "performance_analytics": True
        },
        "supported_platforms": 12
    }