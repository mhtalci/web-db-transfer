"""
Maintenance mode manager for controlling system maintenance states.

This module provides the MaintenanceManager class for activating and
deactivating maintenance mode on destination systems during migrations.
"""

import asyncio
import logging
import os
import tempfile
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

from migration_assistant.models.config import SystemConfig, SystemType
from migration_assistant.core.exceptions import MigrationAssistantError
from migration_assistant.models.session import LogEntry, LogLevel

logger = logging.getLogger(__name__)


class MaintenanceManager:
    """
    Manager for controlling maintenance mode on destination systems.
    
    This class provides methods to activate and deactivate maintenance mode
    for different system types including web servers, applications, and
    cloud services.
    """
    
    def __init__(self):
        """Initialize the maintenance manager."""
        self._active_maintenance: Dict[str, Dict[str, Any]] = {}
        self._maintenance_logs: List[LogEntry] = []
    
    def _log(self, level: LogLevel, message: str, system_id: Optional[str] = None, **kwargs):
        """Add a log entry."""
        log_entry = LogEntry(
            level=level,
            message=message,
            component="MaintenanceManager",
            details={"system_id": system_id, **kwargs}
        )
        self._maintenance_logs.append(log_entry)
    
    async def enable_maintenance_mode(
        self,
        system_config: SystemConfig,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Enable maintenance mode on a system.
        
        Args:
            system_config: System configuration
            options: Maintenance mode options
            
        Returns:
            Dictionary with maintenance mode details
            
        Raises:
            MigrationAssistantError: If maintenance mode activation fails
        """
        options = options or {}
        system_id = f"{system_config.host}:{system_config.port or 80}"
        
        try:
            self._log(LogLevel.INFO, f"Enabling maintenance mode for {system_config.type.value}", system_id)
            
            # Check if maintenance mode is already active
            if system_id in self._active_maintenance:
                self._log(LogLevel.WARNING, "Maintenance mode already active", system_id)
                return self._active_maintenance[system_id]
            
            # Enable maintenance mode based on system type
            maintenance_info = await self._enable_maintenance_by_type(
                system_config,
                options
            )
            
            # Store maintenance information
            self._active_maintenance[system_id] = {
                "system_config": system_config,
                "enabled_at": datetime.now(UTC),
                "options": options,
                "maintenance_info": maintenance_info,
                "status": "active"
            }
            
            self._log(LogLevel.INFO, "Maintenance mode enabled successfully", system_id)
            
            return maintenance_info
            
        except Exception as e:
            self._log(LogLevel.ERROR, f"Failed to enable maintenance mode: {str(e)}", system_id)
            raise MigrationAssistantError(f"Failed to enable maintenance mode: {str(e)}")
    
    async def disable_maintenance_mode(
        self,
        system_config: SystemConfig,
        options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Disable maintenance mode on a system.
        
        Args:
            system_config: System configuration
            options: Maintenance mode options
            
        Returns:
            True if maintenance mode was disabled successfully
            
        Raises:
            MigrationAssistantError: If maintenance mode deactivation fails
        """
        options = options or {}
        system_id = f"{system_config.host}:{system_config.port or 80}"
        
        try:
            self._log(LogLevel.INFO, f"Disabling maintenance mode for {system_config.type.value}", system_id)
            
            # Check if maintenance mode is active
            if system_id not in self._active_maintenance:
                self._log(LogLevel.WARNING, "Maintenance mode not active", system_id)
                return True
            
            maintenance_data = self._active_maintenance[system_id]
            
            # Disable maintenance mode based on system type
            success = await self._disable_maintenance_by_type(
                system_config,
                maintenance_data["maintenance_info"],
                options
            )
            
            if success:
                # Remove from active maintenance
                del self._active_maintenance[system_id]
                self._log(LogLevel.INFO, "Maintenance mode disabled successfully", system_id)
            else:
                self._log(LogLevel.ERROR, "Failed to disable maintenance mode", system_id)
            
            return success
            
        except Exception as e:
            self._log(LogLevel.ERROR, f"Failed to disable maintenance mode: {str(e)}", system_id)
            raise MigrationAssistantError(f"Failed to disable maintenance mode: {str(e)}")
    
    async def _enable_maintenance_by_type(
        self,
        system_config: SystemConfig,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enable maintenance mode based on system type."""
        system_type = system_config.type
        
        if system_type in [SystemType.WORDPRESS, SystemType.DRUPAL, SystemType.JOOMLA]:
            return await self._enable_cms_maintenance(system_config, options)
        
        elif system_type in [SystemType.DJANGO, SystemType.FLASK, SystemType.FASTAPI]:
            return await self._enable_python_app_maintenance(system_config, options)
        
        elif system_type == SystemType.LARAVEL:
            return await self._enable_laravel_maintenance(system_config, options)
        
        elif system_type == SystemType.RAILS:
            return await self._enable_rails_maintenance(system_config, options)
        
        elif system_type == SystemType.NEXTJS:
            return await self._enable_nextjs_maintenance(system_config, options)
        
        elif system_type == SystemType.STATIC_SITE:
            return await self._enable_static_site_maintenance(system_config, options)
        
        elif system_type in [SystemType.AWS_S3, SystemType.GOOGLE_CLOUD_STORAGE, SystemType.AZURE_BLOB]:
            return await self._enable_cloud_storage_maintenance(system_config, options)
        
        elif system_type in [SystemType.DOCKER_CONTAINER, SystemType.KUBERNETES_POD]:
            return await self._enable_container_maintenance(system_config, options)
        
        else:
            return await self._enable_generic_maintenance(system_config, options)
    
    async def _disable_maintenance_by_type(
        self,
        system_config: SystemConfig,
        maintenance_info: Dict[str, Any],
        options: Dict[str, Any]
    ) -> bool:
        """Disable maintenance mode based on system type."""
        system_type = system_config.type
        
        if system_type in [SystemType.WORDPRESS, SystemType.DRUPAL, SystemType.JOOMLA]:
            return await self._disable_cms_maintenance(system_config, maintenance_info, options)
        
        elif system_type in [SystemType.DJANGO, SystemType.FLASK, SystemType.FASTAPI]:
            return await self._disable_python_app_maintenance(system_config, maintenance_info, options)
        
        elif system_type == SystemType.LARAVEL:
            return await self._disable_laravel_maintenance(system_config, maintenance_info, options)
        
        elif system_type == SystemType.RAILS:
            return await self._disable_rails_maintenance(system_config, maintenance_info, options)
        
        elif system_type == SystemType.NEXTJS:
            return await self._disable_nextjs_maintenance(system_config, maintenance_info, options)
        
        elif system_type == SystemType.STATIC_SITE:
            return await self._disable_static_site_maintenance(system_config, maintenance_info, options)
        
        elif system_type in [SystemType.AWS_S3, SystemType.GOOGLE_CLOUD_STORAGE, SystemType.AZURE_BLOB]:
            return await self._disable_cloud_storage_maintenance(system_config, maintenance_info, options)
        
        elif system_type in [SystemType.DOCKER_CONTAINER, SystemType.KUBERNETES_POD]:
            return await self._disable_container_maintenance(system_config, maintenance_info, options)
        
        else:
            return await self._disable_generic_maintenance(system_config, maintenance_info, options)
    
    async def _enable_cms_maintenance(
        self,
        system_config: SystemConfig,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enable maintenance mode for CMS systems (WordPress, Drupal, Joomla)."""
        maintenance_file = options.get("maintenance_file", ".maintenance")
        maintenance_message = options.get("message", "Site is temporarily under maintenance. Please check back soon.")
        
        # Create maintenance file content
        if system_config.type == SystemType.WORDPRESS:
            maintenance_content = self._create_wordpress_maintenance_content(maintenance_message)
        elif system_config.type == SystemType.DRUPAL:
            maintenance_content = self._create_drupal_maintenance_content(maintenance_message)
        elif system_config.type == SystemType.JOOMLA:
            maintenance_content = self._create_joomla_maintenance_content(maintenance_message)
        else:
            maintenance_content = maintenance_message
        
        # In a real implementation, this would upload the maintenance file to the server
        # For now, we'll simulate the process
        await asyncio.sleep(1)
        
        return {
            "method": "maintenance_file",
            "file_path": maintenance_file,
            "content": maintenance_content,
            "backup_required": True
        }
    
    async def _disable_cms_maintenance(
        self,
        system_config: SystemConfig,
        maintenance_info: Dict[str, Any],
        options: Dict[str, Any]
    ) -> bool:
        """Disable maintenance mode for CMS systems."""
        # In a real implementation, this would remove the maintenance file
        await asyncio.sleep(1)
        return True
    
    async def _enable_python_app_maintenance(
        self,
        system_config: SystemConfig,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enable maintenance mode for Python applications."""
        maintenance_method = options.get("method", "environment_variable")
        
        if maintenance_method == "environment_variable":
            # Set maintenance mode environment variable
            env_var = options.get("env_var", "MAINTENANCE_MODE")
            return {
                "method": "environment_variable",
                "env_var": env_var,
                "value": "true"
            }
        
        elif maintenance_method == "config_file":
            # Create maintenance configuration file
            config_file = options.get("config_file", "maintenance.json")
            return {
                "method": "config_file",
                "file_path": config_file,
                "content": {"maintenance_mode": True, "message": options.get("message", "Under maintenance")}
            }
        
        else:
            # Default to file-based maintenance
            return await self._enable_generic_maintenance(system_config, options)
    
    async def _disable_python_app_maintenance(
        self,
        system_config: SystemConfig,
        maintenance_info: Dict[str, Any],
        options: Dict[str, Any]
    ) -> bool:
        """Disable maintenance mode for Python applications."""
        method = maintenance_info.get("method", "file")
        
        if method == "environment_variable":
            # Unset maintenance mode environment variable
            pass
        elif method == "config_file":
            # Remove or update maintenance configuration file
            pass
        
        await asyncio.sleep(1)
        return True
    
    async def _enable_laravel_maintenance(
        self,
        system_config: SystemConfig,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enable maintenance mode for Laravel applications."""
        # Laravel has built-in maintenance mode via 'php artisan down'
        return {
            "method": "artisan_command",
            "command": "php artisan down",
            "message": options.get("message", "Application is under maintenance"),
            "retry_after": options.get("retry_after", 60)
        }
    
    async def _disable_laravel_maintenance(
        self,
        system_config: SystemConfig,
        maintenance_info: Dict[str, Any],
        options: Dict[str, Any]
    ) -> bool:
        """Disable maintenance mode for Laravel applications."""
        # Laravel maintenance mode disabled via 'php artisan up'
        await asyncio.sleep(1)
        return True
    
    async def _enable_rails_maintenance(
        self,
        system_config: SystemConfig,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enable maintenance mode for Rails applications."""
        # Rails maintenance mode typically uses a maintenance page
        return {
            "method": "maintenance_page",
            "page_path": "public/maintenance.html",
            "message": options.get("message", "Application is under maintenance")
        }
    
    async def _disable_rails_maintenance(
        self,
        system_config: SystemConfig,
        maintenance_info: Dict[str, Any],
        options: Dict[str, Any]
    ) -> bool:
        """Disable maintenance mode for Rails applications."""
        await asyncio.sleep(1)
        return True
    
    async def _enable_nextjs_maintenance(
        self,
        system_config: SystemConfig,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enable maintenance mode for Next.js applications."""
        return {
            "method": "maintenance_page",
            "page_path": "pages/maintenance.js",
            "redirect_rule": True,
            "message": options.get("message", "Site is under maintenance")
        }
    
    async def _disable_nextjs_maintenance(
        self,
        system_config: SystemConfig,
        maintenance_info: Dict[str, Any],
        options: Dict[str, Any]
    ) -> bool:
        """Disable maintenance mode for Next.js applications."""
        await asyncio.sleep(1)
        return True
    
    async def _enable_static_site_maintenance(
        self,
        system_config: SystemConfig,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enable maintenance mode for static sites."""
        # For static sites, we typically replace index.html with a maintenance page
        return {
            "method": "index_replacement",
            "backup_file": "index.html.backup",
            "maintenance_file": "maintenance.html",
            "message": options.get("message", "Site is temporarily under maintenance")
        }
    
    async def _disable_static_site_maintenance(
        self,
        system_config: SystemConfig,
        maintenance_info: Dict[str, Any],
        options: Dict[str, Any]
    ) -> bool:
        """Disable maintenance mode for static sites."""
        await asyncio.sleep(1)
        return True
    
    async def _enable_cloud_storage_maintenance(
        self,
        system_config: SystemConfig,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enable maintenance mode for cloud storage hosted sites."""
        return {
            "method": "object_replacement",
            "maintenance_object": "maintenance.html",
            "original_index": "index.html",
            "message": options.get("message", "Site is under maintenance")
        }
    
    async def _disable_cloud_storage_maintenance(
        self,
        system_config: SystemConfig,
        maintenance_info: Dict[str, Any],
        options: Dict[str, Any]
    ) -> bool:
        """Disable maintenance mode for cloud storage hosted sites."""
        await asyncio.sleep(1)
        return True
    
    async def _enable_container_maintenance(
        self,
        system_config: SystemConfig,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enable maintenance mode for containerized applications."""
        return {
            "method": "container_scaling",
            "maintenance_container": options.get("maintenance_container", "maintenance:latest"),
            "original_replicas": options.get("replicas", 1)
        }
    
    async def _disable_container_maintenance(
        self,
        system_config: SystemConfig,
        maintenance_info: Dict[str, Any],
        options: Dict[str, Any]
    ) -> bool:
        """Disable maintenance mode for containerized applications."""
        await asyncio.sleep(1)
        return True
    
    async def _enable_generic_maintenance(
        self,
        system_config: SystemConfig,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enable generic maintenance mode using a maintenance file."""
        maintenance_file = options.get("maintenance_file", "maintenance.html")
        maintenance_message = options.get("message", "System is under maintenance. Please check back soon.")
        
        # Create generic maintenance HTML content
        maintenance_content = self._create_generic_maintenance_content(maintenance_message)
        
        return {
            "method": "maintenance_file",
            "file_path": maintenance_file,
            "content": maintenance_content,
            "backup_required": False
        }
    
    async def _disable_generic_maintenance(
        self,
        system_config: SystemConfig,
        maintenance_info: Dict[str, Any],
        options: Dict[str, Any]
    ) -> bool:
        """Disable generic maintenance mode."""
        await asyncio.sleep(1)
        return True
    
    def _create_wordpress_maintenance_content(self, message: str) -> str:
        """Create WordPress maintenance mode content."""
        return f"""<?php
$upgrading = time();
// Maintenance mode enabled at {datetime.now(UTC).isoformat()}
// Message: {message}
?>"""
    
    def _create_drupal_maintenance_content(self, message: str) -> str:
        """Create Drupal maintenance mode content."""
        return f"""<?php
// Drupal maintenance mode
// Enabled at {datetime.now(UTC).isoformat()}
// Message: {message}
$conf['maintenance_mode'] = 1;
$conf['maintenance_mode_message'] = '{message}';
?>"""
    
    def _create_joomla_maintenance_content(self, message: str) -> str:
        """Create Joomla maintenance mode content."""
        return f"""<?php
// Joomla maintenance mode
// Enabled at {datetime.now(UTC).isoformat()}
class JConfig {{
    public $offline = '1';
    public $offline_message = '{message}';
}}
?>"""
    
    def _create_generic_maintenance_content(self, message: str) -> str:
        """Create generic maintenance HTML content."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Under Maintenance</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            text-align: center;
            padding: 50px;
            background-color: #f5f5f5;
        }}
        .maintenance-container {{
            max-width: 600px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            margin-bottom: 20px;
        }}
        p {{
            color: #666;
            line-height: 1.6;
        }}
        .timestamp {{
            font-size: 12px;
            color: #999;
            margin-top: 30px;
        }}
    </style>
</head>
<body>
    <div class="maintenance-container">
        <h1>🔧 Under Maintenance</h1>
        <p>{message}</p>
        <p>We apologize for any inconvenience and appreciate your patience.</p>
        <div class="timestamp">
            Maintenance started: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}
        </div>
    </div>
</body>
</html>"""
    
    def is_maintenance_active(self, system_config: SystemConfig) -> bool:
        """Check if maintenance mode is active for a system."""
        system_id = f"{system_config.host}:{system_config.port or 80}"
        return system_id in self._active_maintenance
    
    def get_maintenance_info(self, system_config: SystemConfig) -> Optional[Dict[str, Any]]:
        """Get maintenance mode information for a system."""
        system_id = f"{system_config.host}:{system_config.port or 80}"
        return self._active_maintenance.get(system_id)
    
    def list_active_maintenance(self) -> List[Dict[str, Any]]:
        """List all systems with active maintenance mode."""
        return [
            {
                "system_id": system_id,
                "system_type": data["system_config"].type.value,
                "host": data["system_config"].host,
                "enabled_at": data["enabled_at"].isoformat(),
                "method": data["maintenance_info"].get("method", "unknown")
            }
            for system_id, data in self._active_maintenance.items()
        ]
    
    async def cleanup_stale_maintenance(self, max_age_hours: int = 24) -> List[str]:
        """Clean up stale maintenance mode entries."""
        current_time = datetime.now(UTC)
        stale_systems = []
        
        for system_id, data in list(self._active_maintenance.items()):
            enabled_at = data["enabled_at"]
            age_hours = (current_time - enabled_at).total_seconds() / 3600
            
            if age_hours > max_age_hours:
                try:
                    # Attempt to disable maintenance mode
                    await self.disable_maintenance_mode(
                        data["system_config"],
                        {"force": True}
                    )
                    stale_systems.append(system_id)
                    self._log(LogLevel.INFO, f"Cleaned up stale maintenance mode", system_id)
                except Exception as e:
                    self._log(LogLevel.ERROR, f"Failed to cleanup stale maintenance: {str(e)}", system_id)
        
        return stale_systems
    
    def get_logs(self, system_id: Optional[str] = None) -> List[LogEntry]:
        """Get maintenance operation logs."""
        if system_id:
            return [
                log for log in self._maintenance_logs
                if log.details.get("system_id") == system_id
            ]
        return self._maintenance_logs.copy()
    
    def clear_logs(self):
        """Clear maintenance operation logs."""
        self._maintenance_logs.clear()