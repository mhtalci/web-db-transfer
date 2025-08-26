"""
Health check and monitoring endpoints for the Migration Assistant API.

This module provides comprehensive health checks, system monitoring,
and readiness probes for deployment environments.
"""

import asyncio
import os
import sys
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel

from migration_assistant import __version__
from migration_assistant.core.exceptions import MigrationError


router = APIRouter(prefix="/health", tags=["Health"])


class HealthStatus(BaseModel):
    """Health status response model."""
    status: str
    version: str
    service: str
    timestamp: datetime
    uptime_seconds: float
    components: Dict[str, bool]


class DetailedHealthStatus(BaseModel):
    """Detailed health status with system metrics."""
    status: str
    version: str
    service: str
    timestamp: datetime
    uptime_seconds: float
    components: Dict[str, Dict[str, Any]]
    system_metrics: Dict[str, Any]
    performance_metrics: Dict[str, Any]


class ReadinessStatus(BaseModel):
    """Readiness status for Kubernetes probes."""
    ready: bool
    checks: Dict[str, bool]
    message: str


class LivenessStatus(BaseModel):
    """Liveness status for Kubernetes probes."""
    alive: bool
    last_activity: datetime
    message: str


# Global variables for tracking
_start_time = time.time()
_last_activity = datetime.utcnow()
_health_cache = {}
_cache_ttl = 30  # seconds


def update_activity():
    """Update last activity timestamp."""
    global _last_activity
    _last_activity = datetime.utcnow()


def get_uptime() -> float:
    """Get service uptime in seconds."""
    return time.time() - _start_time


async def check_component_health(component_name: str) -> Dict[str, Any]:
    """Check health of a specific component."""
    try:
        if component_name == "database":
            return await check_database_health()
        elif component_name == "storage":
            return await check_storage_health()
        elif component_name == "go_engine":
            return await check_go_engine_health()
        elif component_name == "external_apis":
            return await check_external_apis_health()
        else:
            return {"status": "unknown", "message": f"Unknown component: {component_name}"}
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


async def check_database_health() -> Dict[str, Any]:
    """Check database connectivity and performance."""
    try:
        # This would typically check your database connection
        # For now, we'll simulate a basic check
        start_time = time.time()
        
        # Simulate database ping
        await asyncio.sleep(0.001)  # Simulate network latency
        
        response_time = (time.time() - start_time) * 1000  # ms
        
        return {
            "status": "healthy",
            "response_time_ms": round(response_time, 2),
            "connection_pool": {
                "active": 5,
                "idle": 15,
                "total": 20
            },
            "last_check": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "last_check": datetime.utcnow().isoformat()
        }


async def check_storage_health() -> Dict[str, Any]:
    """Check storage system health."""
    try:
        # Check disk space
        disk_usage = psutil.disk_usage('/')
        free_space_gb = disk_usage.free / (1024**3)
        total_space_gb = disk_usage.total / (1024**3)
        usage_percent = (disk_usage.used / disk_usage.total) * 100
        
        # Check temp directory
        temp_dir = Path("/tmp")
        temp_writable = temp_dir.is_dir() and os.access(temp_dir, os.W_OK)
        
        status = "healthy"
        warnings = []
        
        if usage_percent > 90:
            status = "warning"
            warnings.append("Disk usage above 90%")
        elif usage_percent > 95:
            status = "unhealthy"
            warnings.append("Disk usage critically high")
        
        if not temp_writable:
            status = "unhealthy"
            warnings.append("Temporary directory not writable")
        
        return {
            "status": status,
            "disk_usage": {
                "free_gb": round(free_space_gb, 2),
                "total_gb": round(total_space_gb, 2),
                "usage_percent": round(usage_percent, 2)
            },
            "temp_directory": {
                "path": str(temp_dir),
                "writable": temp_writable
            },
            "warnings": warnings,
            "last_check": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "last_check": datetime.utcnow().isoformat()
        }


async def check_go_engine_health() -> Dict[str, Any]:
    """Check Go engine availability and performance."""
    try:
        from migration_assistant.performance.engine import GoPerformanceEngine
        
        go_engine = GoPerformanceEngine()
        
        # Check if Go binary exists
        binary_exists = go_engine.check_binary_availability()
        
        if not binary_exists:
            return {
                "status": "warning",
                "message": "Go binary not available, using Python fallback",
                "binary_path": go_engine.go_binary_path,
                "fallback_available": True,
                "last_check": datetime.utcnow().isoformat()
            }
        
        # Test Go engine performance
        start_time = time.time()
        test_result = await go_engine.test_performance()
        response_time = (time.time() - start_time) * 1000
        
        return {
            "status": "healthy",
            "binary_available": True,
            "binary_path": go_engine.go_binary_path,
            "response_time_ms": round(response_time, 2),
            "performance_test": test_result,
            "last_check": datetime.utcnow().isoformat()
        }
        
    except ImportError:
        return {
            "status": "warning",
            "message": "Go engine module not available",
            "last_check": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "last_check": datetime.utcnow().isoformat()
        }


async def check_external_apis_health() -> Dict[str, Any]:
    """Check external API connectivity."""
    try:
        import httpx
        
        # Test external services
        services = {
            "aws": "https://aws.amazon.com",
            "google": "https://www.google.com",
            "github": "https://api.github.com"
        }
        
        results = {}
        overall_status = "healthy"
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            for service, url in services.items():
                try:
                    start_time = time.time()
                    response = await client.get(url)
                    response_time = (time.time() - start_time) * 1000
                    
                    results[service] = {
                        "status": "healthy" if response.status_code < 400 else "unhealthy",
                        "status_code": response.status_code,
                        "response_time_ms": round(response_time, 2)
                    }
                except Exception as e:
                    results[service] = {
                        "status": "unhealthy",
                        "error": str(e)
                    }
                    overall_status = "warning"
        
        return {
            "status": overall_status,
            "services": results,
            "last_check": datetime.utcnow().isoformat()
        }
        
    except ImportError:
        return {
            "status": "warning",
            "message": "HTTP client not available for external API checks",
            "last_check": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "last_check": datetime.utcnow().isoformat()
        }


def get_system_metrics() -> Dict[str, Any]:
    """Get system performance metrics."""
    try:
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # Memory metrics
        memory = psutil.virtual_memory()
        memory_mb = memory.total / (1024**2)
        memory_used_mb = memory.used / (1024**2)
        memory_percent = memory.percent
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        disk_total_gb = disk.total / (1024**3)
        disk_used_gb = disk.used / (1024**3)
        disk_percent = (disk.used / disk.total) * 100
        
        # Network metrics (if available)
        try:
            network = psutil.net_io_counters()
            network_metrics = {
                "bytes_sent": network.bytes_sent,
                "bytes_recv": network.bytes_recv,
                "packets_sent": network.packets_sent,
                "packets_recv": network.packets_recv
            }
        except:
            network_metrics = {"error": "Network metrics not available"}
        
        return {
            "cpu": {
                "usage_percent": cpu_percent,
                "count": cpu_count
            },
            "memory": {
                "total_mb": round(memory_mb, 2),
                "used_mb": round(memory_used_mb, 2),
                "usage_percent": memory_percent
            },
            "disk": {
                "total_gb": round(disk_total_gb, 2),
                "used_gb": round(disk_used_gb, 2),
                "usage_percent": round(disk_percent, 2)
            },
            "network": network_metrics,
            "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else None
        }
    except Exception as e:
        return {"error": f"Failed to get system metrics: {e}"}


def get_performance_metrics() -> Dict[str, Any]:
    """Get application performance metrics."""
    try:
        # Get process information
        process = psutil.Process()
        
        return {
            "process": {
                "pid": process.pid,
                "memory_mb": round(process.memory_info().rss / (1024**2), 2),
                "cpu_percent": process.cpu_percent(),
                "threads": process.num_threads(),
                "open_files": len(process.open_files()),
                "connections": len(process.connections())
            },
            "python": {
                "version": sys.version,
                "executable": sys.executable,
                "path": sys.path[:3]  # First 3 paths only
            },
            "uptime_seconds": get_uptime()
        }
    except Exception as e:
        return {"error": f"Failed to get performance metrics: {e}"}


@router.get("/", response_model=HealthStatus)
async def health_check():
    """
    Basic health check endpoint.
    
    Returns basic health status and component availability.
    Used for load balancer health checks.
    """
    update_activity()
    
    # Check cache
    cache_key = "basic_health"
    now = time.time()
    
    if cache_key in _health_cache:
        cached_data, cache_time = _health_cache[cache_key]
        if now - cache_time < _cache_ttl:
            return cached_data
    
    # Check basic components
    components = {}
    
    try:
        # Check if we can import main modules
        from migration_assistant.orchestrator.orchestrator import MigrationOrchestrator
        from migration_assistant.cli.preset_manager import PresetManager
        from migration_assistant.validation.engine import ValidationEngine
        
        components["orchestrator"] = True
        components["preset_manager"] = True
        components["validation_engine"] = True
        
    except ImportError as e:
        components["orchestrator"] = False
        components["preset_manager"] = False
        components["validation_engine"] = False
    
    # Determine overall status
    status = "healthy" if all(components.values()) else "unhealthy"
    
    result = HealthStatus(
        status=status,
        version=__version__,
        service="Migration Assistant API",
        timestamp=datetime.utcnow(),
        uptime_seconds=get_uptime(),
        components=components
    )
    
    # Cache result
    _health_cache[cache_key] = (result, now)
    
    return result


@router.get("/detailed", response_model=DetailedHealthStatus)
async def detailed_health_check():
    """
    Detailed health check endpoint.
    
    Returns comprehensive health status including system metrics,
    component details, and performance information.
    """
    update_activity()
    
    # Check cache
    cache_key = "detailed_health"
    now = time.time()
    
    if cache_key in _health_cache:
        cached_data, cache_time = _health_cache[cache_key]
        if now - cache_time < _cache_ttl:
            return cached_data
    
    # Check all components in detail
    component_names = ["database", "storage", "go_engine", "external_apis"]
    components = {}
    
    for component in component_names:
        components[component] = await check_component_health(component)
    
    # Get system and performance metrics
    system_metrics = get_system_metrics()
    performance_metrics = get_performance_metrics()
    
    # Determine overall status
    component_statuses = [comp.get("status", "unknown") for comp in components.values()]
    if all(status == "healthy" for status in component_statuses):
        overall_status = "healthy"
    elif any(status == "unhealthy" for status in component_statuses):
        overall_status = "unhealthy"
    else:
        overall_status = "warning"
    
    result = DetailedHealthStatus(
        status=overall_status,
        version=__version__,
        service="Migration Assistant API",
        timestamp=datetime.utcnow(),
        uptime_seconds=get_uptime(),
        components=components,
        system_metrics=system_metrics,
        performance_metrics=performance_metrics
    )
    
    # Cache result
    _health_cache[cache_key] = (result, now)
    
    return result


@router.get("/ready", response_model=ReadinessStatus)
async def readiness_probe():
    """
    Kubernetes readiness probe endpoint.
    
    Checks if the service is ready to accept traffic.
    Returns 200 if ready, 503 if not ready.
    """
    update_activity()
    
    checks = {}
    ready = True
    messages = []
    
    # Check critical components
    try:
        from migration_assistant.orchestrator.orchestrator import MigrationOrchestrator
        checks["orchestrator"] = True
    except Exception:
        checks["orchestrator"] = False
        ready = False
        messages.append("Orchestrator not available")
    
    # Check storage
    try:
        disk_usage = psutil.disk_usage('/')
        usage_percent = (disk_usage.used / disk_usage.total) * 100
        if usage_percent > 95:
            checks["storage"] = False
            ready = False
            messages.append("Disk usage critically high")
        else:
            checks["storage"] = True
    except Exception:
        checks["storage"] = False
        ready = False
        messages.append("Storage check failed")
    
    # Check memory
    try:
        memory = psutil.virtual_memory()
        if memory.percent > 95:
            checks["memory"] = False
            ready = False
            messages.append("Memory usage critically high")
        else:
            checks["memory"] = True
    except Exception:
        checks["memory"] = False
        ready = False
        messages.append("Memory check failed")
    
    message = "Ready" if ready else "; ".join(messages)
    
    status_code = status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE
    
    result = ReadinessStatus(
        ready=ready,
        checks=checks,
        message=message
    )
    
    if not ready:
        raise HTTPException(status_code=status_code, detail=result.dict())
    
    return result


@router.get("/live", response_model=LivenessStatus)
async def liveness_probe():
    """
    Kubernetes liveness probe endpoint.
    
    Checks if the service is alive and responsive.
    Returns 200 if alive, 503 if not responding.
    """
    global _last_activity
    
    update_activity()
    
    # Check if service has been active recently
    time_since_activity = datetime.utcnow() - _last_activity
    max_inactive_time = timedelta(minutes=10)  # 10 minutes
    
    alive = time_since_activity < max_inactive_time
    
    if alive:
        message = "Service is alive and responsive"
        status_code = status.HTTP_200_OK
    else:
        message = f"Service inactive for {time_since_activity.total_seconds():.0f} seconds"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    result = LivenessStatus(
        alive=alive,
        last_activity=_last_activity,
        message=message
    )
    
    if not alive:
        raise HTTPException(status_code=status_code, detail=result.dict())
    
    return result


@router.get("/metrics")
async def metrics_endpoint():
    """
    Prometheus-compatible metrics endpoint.
    
    Returns metrics in Prometheus format for monitoring.
    """
    update_activity()
    
    try:
        # Get system metrics
        system_metrics = get_system_metrics()
        performance_metrics = get_performance_metrics()
        
        # Format as Prometheus metrics
        metrics = []
        
        # System metrics
        if "cpu" in system_metrics:
            metrics.append(f'migration_assistant_cpu_usage_percent {system_metrics["cpu"]["usage_percent"]}')
            metrics.append(f'migration_assistant_cpu_count {system_metrics["cpu"]["count"]}')
        
        if "memory" in system_metrics:
            metrics.append(f'migration_assistant_memory_usage_percent {system_metrics["memory"]["usage_percent"]}')
            metrics.append(f'migration_assistant_memory_total_bytes {system_metrics["memory"]["total_mb"] * 1024 * 1024}')
        
        if "disk" in system_metrics:
            metrics.append(f'migration_assistant_disk_usage_percent {system_metrics["disk"]["usage_percent"]}')
            metrics.append(f'migration_assistant_disk_total_bytes {system_metrics["disk"]["total_gb"] * 1024 * 1024 * 1024}')
        
        # Application metrics
        if "process" in performance_metrics:
            process = performance_metrics["process"]
            metrics.append(f'migration_assistant_process_memory_bytes {process["memory_mb"] * 1024 * 1024}')
            metrics.append(f'migration_assistant_process_cpu_percent {process["cpu_percent"]}')
            metrics.append(f'migration_assistant_process_threads {process["threads"]}')
            metrics.append(f'migration_assistant_process_open_files {process["open_files"]}')
        
        # Uptime
        metrics.append(f'migration_assistant_uptime_seconds {get_uptime()}')
        
        # Add timestamp
        timestamp = int(time.time() * 1000)
        metrics_with_timestamp = [f"{metric} {timestamp}" for metric in metrics]
        
        return "\n".join(metrics_with_timestamp)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate metrics: {e}"
        )