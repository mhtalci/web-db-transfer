"""
Advanced CMS migration orchestrator with intelligent workflow management.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

from ..core.cms_exceptions import CMSMigrationError
from ..validators.cms_validator import CMSHealthChecker, CMSCompatibilityChecker
from ..utils.cms_utils import CMSMigrationPlanner, CMSFileAnalyzer


class MigrationStage(Enum):
    """Migration stages."""
    PREPARATION = "preparation"
    VALIDATION = "validation"
    BACKUP = "backup"
    EXPORT = "export"
    TRANSFORM = "transform"
    IMPORT = "import"
    CONFIGURATION = "configuration"
    VERIFICATION = "verification"
    CLEANUP = "cleanup"
    COMPLETION = "completion"


class MigrationStatus(Enum):
    """Migration status."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class MigrationStep:
    """Represents a single migration step."""
    id: str
    name: str
    stage: MigrationStage
    description: str
    estimated_duration: int  # seconds
    dependencies: List[str] = field(default_factory=list)
    status: MigrationStatus = MigrationStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    progress: float = 0.0
    error_message: Optional[str] = None
    result_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MigrationPlan:
    """Complete migration plan."""
    id: str
    source_platform: str
    destination_platform: str
    source_path: Path
    destination_path: Path
    steps: List[MigrationStep]
    total_estimated_duration: int
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class CMSMigrationOrchestrator:
    """Advanced CMS migration orchestrator."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.active_migrations: Dict[str, MigrationPlan] = {}
        self.step_handlers: Dict[str, Callable] = {}
        self.progress_callbacks: List[Callable] = []
        self.max_concurrent_steps = self.config.get('max_concurrent_steps', 3)
        self.retry_attempts = self.config.get('retry_attempts', 3)
        self.retry_delay = self.config.get('retry_delay', 30)  # seconds
        
        # Register default step handlers
        self._register_default_handlers()
    
    def register_step_handler(self, step_id: str, handler: Callable):
        """Register a custom step handler."""
        self.step_handlers[step_id] = handler
    
    def add_progress_callback(self, callback: Callable):
        """Add a progress callback function."""
        self.progress_callbacks.append(callback)
    
    async def create_migration_plan(
        self,
        source_platform: str,
        destination_platform: str,
        source_path: Path,
        destination_path: Path,
        options: Dict[str, Any] = None
    ) -> MigrationPlan:
        """Create a comprehensive migration plan."""
        
        options = options or {}
        migration_id = f"migration_{int(time.time())}"
        
        # Analyze source platform
        source_stats = CMSFileAnalyzer.analyze_directory_structure(source_path)
        
        # Estimate migration time
        time_estimate = CMSMigrationPlanner.estimate_migration_time(
            source_stats, source_platform, destination_platform
        )
        
        # Generate migration steps
        steps = await self._generate_migration_steps(
            source_platform, destination_platform, source_path, destination_path, options
        )
        
        # Create migration plan
        plan = MigrationPlan(
            id=migration_id,
            source_platform=source_platform,
            destination_platform=destination_platform,
            source_path=source_path,
            destination_path=destination_path,
            steps=steps,
            total_estimated_duration=time_estimate['estimated_seconds'],
            metadata={
                'source_stats': source_stats,
                'time_estimate': time_estimate,
                'options': options
            }
        )
        
        self.active_migrations[migration_id] = plan
        return plan
    
    async def execute_migration(self, migration_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute migration plan with real-time progress updates."""
        
        if migration_id not in self.active_migrations:
            raise CMSMigrationError("", "", "execute", f"Migration {migration_id} not found")
        
        plan = self.active_migrations[migration_id]
        
        try:
            # Pre-migration validation
            yield await self._emit_progress(plan, "Starting migration validation...")
            
            validation_result = await self._validate_migration_prerequisites(plan)
            if not validation_result['valid']:
                raise CMSMigrationError(
                    plan.source_platform, 
                    plan.destination_platform,
                    "validation",
                    f"Validation failed: {'; '.join(validation_result['errors'])}"
                )
            
            # Execute migration steps
            completed_steps = 0
            total_steps = len(plan.steps)
            
            for step in plan.steps:
                yield await self._emit_progress(
                    plan, 
                    f"Executing step: {step.name}",
                    completed_steps / total_steps * 100
                )
                
                await self._execute_step(plan, step)
                completed_steps += 1
                
                # Emit step completion
                yield await self._emit_progress(
                    plan,
                    f"Completed step: {step.name}",
                    completed_steps / total_steps * 100
                )
            
            # Final validation
            yield await self._emit_progress(plan, "Running final validation...")
            await self._run_post_migration_validation(plan)
            
            yield await self._emit_progress(plan, "Migration completed successfully!", 100)
            
        except Exception as e:
            yield await self._emit_progress(plan, f"Migration failed: {str(e)}", error=True)
            raise
    
    async def pause_migration(self, migration_id: str):
        """Pause an active migration."""
        if migration_id in self.active_migrations:
            plan = self.active_migrations[migration_id]
            # Mark current running steps as paused
            for step in plan.steps:
                if step.status == MigrationStatus.RUNNING:
                    step.status = MigrationStatus.PAUSED
    
    async def resume_migration(self, migration_id: str):
        """Resume a paused migration."""
        if migration_id in self.active_migrations:
            plan = self.active_migrations[migration_id]
            # Resume paused steps
            for step in plan.steps:
                if step.status == MigrationStatus.PAUSED:
                    step.status = MigrationStatus.PENDING
    
    async def cancel_migration(self, migration_id: str):
        """Cancel an active migration."""
        if migration_id in self.active_migrations:
            plan = self.active_migrations[migration_id]
            # Mark all pending/running steps as cancelled
            for step in plan.steps:
                if step.status in [MigrationStatus.PENDING, MigrationStatus.RUNNING, MigrationStatus.PAUSED]:
                    step.status = MigrationStatus.CANCELLED
    
    async def get_migration_status(self, migration_id: str) -> Dict[str, Any]:
        """Get detailed migration status."""
        if migration_id not in self.active_migrations:
            return {'error': 'Migration not found'}
        
        plan = self.active_migrations[migration_id]
        
        # Calculate overall progress
        completed_steps = sum(1 for step in plan.steps if step.status == MigrationStatus.COMPLETED)
        failed_steps = sum(1 for step in plan.steps if step.status == MigrationStatus.FAILED)
        total_steps = len(plan.steps)
        
        overall_progress = (completed_steps / total_steps * 100) if total_steps > 0 else 0
        
        # Calculate time estimates
        elapsed_time = 0
        remaining_time = plan.total_estimated_duration
        
        if plan.steps:
            started_steps = [s for s in plan.steps if s.start_time]
            if started_steps:
                earliest_start = min(s.start_time for s in started_steps)
                elapsed_time = (datetime.now() - earliest_start).total_seconds()
                
                if overall_progress > 0:
                    estimated_total = elapsed_time / (overall_progress / 100)
                    remaining_time = max(0, estimated_total - elapsed_time)
        
        return {
            'migration_id': migration_id,
            'source_platform': plan.source_platform,
            'destination_platform': plan.destination_platform,
            'overall_progress': overall_progress,
            'completed_steps': completed_steps,
            'failed_steps': failed_steps,
            'total_steps': total_steps,
            'elapsed_time': elapsed_time,
            'estimated_remaining_time': remaining_time,
            'current_stage': self._get_current_stage(plan),
            'steps': [
                {
                    'id': step.id,
                    'name': step.name,
                    'stage': step.stage.value,
                    'status': step.status.value,
                    'progress': step.progress,
                    'error_message': step.error_message
                }
                for step in plan.steps
            ]
        }
    
    async def _generate_migration_steps(
        self,
        source_platform: str,
        destination_platform: str,
        source_path: Path,
        destination_path: Path,
        options: Dict[str, Any]
    ) -> List[MigrationStep]:
        """Generate detailed migration steps."""
        
        steps = []
        
        # Preparation steps
        steps.extend([
            MigrationStep(
                id="health_check_source",
                name="Source Health Check",
                stage=MigrationStage.PREPARATION,
                description="Analyze source platform health and readiness",
                estimated_duration=120
            ),
            MigrationStep(
                id="prepare_destination",
                name="Prepare Destination",
                stage=MigrationStage.PREPARATION,
                description="Prepare destination environment",
                estimated_duration=180,
                dependencies=["health_check_source"]
            )
        ])
        
        # Validation steps
        steps.extend([
            MigrationStep(
                id="compatibility_check",
                name="Compatibility Check",
                stage=MigrationStage.VALIDATION,
                description="Verify migration compatibility",
                estimated_duration=60,
                dependencies=["prepare_destination"]
            ),
            MigrationStep(
                id="dependency_check",
                name="Dependency Check",
                stage=MigrationStage.VALIDATION,
                description="Verify all dependencies are available",
                estimated_duration=90,
                dependencies=["compatibility_check"]
            )
        ])
        
        # Backup steps
        if options.get('create_backup', True):
            steps.append(
                MigrationStep(
                    id="create_backup",
                    name="Create Backup",
                    stage=MigrationStage.BACKUP,
                    description="Create full backup of source platform",
                    estimated_duration=600,
                    dependencies=["dependency_check"]
                )
            )
        
        # Export steps
        steps.extend([
            MigrationStep(
                id="export_database",
                name="Export Database",
                stage=MigrationStage.EXPORT,
                description="Export source database",
                estimated_duration=300,
                dependencies=["create_backup"] if options.get('create_backup', True) else ["dependency_check"]
            ),
            MigrationStep(
                id="export_files",
                name="Export Files",
                stage=MigrationStage.EXPORT,
                description="Export source files and media",
                estimated_duration=400,
                dependencies=["export_database"]
            )
        ])
        
        # Transform steps (for cross-platform migrations)
        if source_platform != destination_platform:
            steps.extend([
                MigrationStep(
                    id="transform_database",
                    name="Transform Database",
                    stage=MigrationStage.TRANSFORM,
                    description="Transform database schema and data",
                    estimated_duration=450,
                    dependencies=["export_files"]
                ),
                MigrationStep(
                    id="transform_content",
                    name="Transform Content",
                    stage=MigrationStage.TRANSFORM,
                    description="Transform content format and structure",
                    estimated_duration=300,
                    dependencies=["transform_database"]
                )
            ])
        
        # Import steps
        import_deps = ["transform_content"] if source_platform != destination_platform else ["export_files"]
        steps.extend([
            MigrationStep(
                id="import_database",
                name="Import Database",
                stage=MigrationStage.IMPORT,
                description="Import database to destination",
                estimated_duration=250,
                dependencies=import_deps
            ),
            MigrationStep(
                id="import_files",
                name="Import Files",
                stage=MigrationStage.IMPORT,
                description="Import files to destination",
                estimated_duration=350,
                dependencies=["import_database"]
            )
        ])
        
        # Configuration steps
        steps.extend([
            MigrationStep(
                id="update_configuration",
                name="Update Configuration",
                stage=MigrationStage.CONFIGURATION,
                description="Update platform configuration",
                estimated_duration=120,
                dependencies=["import_files"]
            ),
            MigrationStep(
                id="update_urls",
                name="Update URLs",
                stage=MigrationStage.CONFIGURATION,
                description="Update internal URLs and links",
                estimated_duration=180,
                dependencies=["update_configuration"]
            ),
            MigrationStep(
                id="set_permissions",
                name="Set Permissions",
                stage=MigrationStage.CONFIGURATION,
                description="Set proper file and directory permissions",
                estimated_duration=60,
                dependencies=["update_urls"]
            )
        ])
        
        # Verification steps
        steps.extend([
            MigrationStep(
                id="verify_functionality",
                name="Verify Functionality",
                stage=MigrationStage.VERIFICATION,
                description="Verify platform functionality",
                estimated_duration=240,
                dependencies=["set_permissions"]
            ),
            MigrationStep(
                id="performance_check",
                name="Performance Check",
                stage=MigrationStage.VERIFICATION,
                description="Check platform performance",
                estimated_duration=120,
                dependencies=["verify_functionality"]
            )
        ])
        
        # Cleanup steps
        if options.get('cleanup_temp_files', True):
            steps.append(
                MigrationStep(
                    id="cleanup_temp_files",
                    name="Cleanup Temporary Files",
                    stage=MigrationStage.CLEANUP,
                    description="Remove temporary migration files",
                    estimated_duration=60,
                    dependencies=["performance_check"]
                )
            )
        
        # Completion step
        steps.append(
            MigrationStep(
                id="finalize_migration",
                name="Finalize Migration",
                stage=MigrationStage.COMPLETION,
                description="Finalize migration and generate report",
                estimated_duration=30,
                dependencies=["cleanup_temp_files"] if options.get('cleanup_temp_files', True) else ["performance_check"]
            )
        )
        
        return steps
    
    async def _execute_step(self, plan: MigrationPlan, step: MigrationStep):
        """Execute a single migration step."""
        step.status = MigrationStatus.RUNNING
        step.start_time = datetime.now()
        
        try:
            # Check dependencies
            for dep_id in step.dependencies:
                dep_step = next((s for s in plan.steps if s.id == dep_id), None)
                if not dep_step or dep_step.status != MigrationStatus.COMPLETED:
                    raise CMSMigrationError(
                        plan.source_platform,
                        plan.destination_platform,
                        step.id,
                        f"Dependency {dep_id} not completed"
                    )
            
            # Execute step with retry logic
            for attempt in range(self.retry_attempts):
                try:
                    if step.id in self.step_handlers:
                        result = await self.step_handlers[step.id](plan, step)
                        step.result_data = result or {}
                    else:
                        # Default step execution
                        await self._execute_default_step(plan, step)
                    
                    step.status = MigrationStatus.COMPLETED
                    step.progress = 100.0
                    break
                    
                except Exception as e:
                    if attempt < self.retry_attempts - 1:
                        await asyncio.sleep(self.retry_delay)
                        continue
                    else:
                        raise e
        
        except Exception as e:
            step.status = MigrationStatus.FAILED
            step.error_message = str(e)
            raise CMSMigrationError(
                plan.source_platform,
                plan.destination_platform,
                step.id,
                str(e)
            )
        
        finally:
            step.end_time = datetime.now()
    
    async def _execute_default_step(self, plan: MigrationPlan, step: MigrationStep):
        """Execute default step implementation."""
        # This would contain default implementations for common steps
        # For now, we'll simulate step execution
        await asyncio.sleep(1)  # Simulate work
        
        if step.id == "health_check_source":
            checker = CMSHealthChecker(plan.source_platform, plan.source_path)
            health_result = await checker.run_health_check()
            step.result_data = health_result
        
        elif step.id == "compatibility_check":
            # Simulate compatibility check
            step.result_data = {'compatible': True}
        
        # Add more default implementations as needed
    
    async def _validate_migration_prerequisites(self, plan: MigrationPlan) -> Dict[str, Any]:
        """Validate migration prerequisites."""
        errors = []
        warnings = []
        
        # Check source path exists
        if not plan.source_path.exists():
            errors.append(f"Source path does not exist: {plan.source_path}")
        
        # Check destination path is writable
        try:
            plan.destination_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"Cannot create destination path: {e}")
        
        # Run compatibility check
        try:
            compatibility = await CMSCompatibilityChecker.check_migration_compatibility(
                plan.source_platform, "unknown",
                plan.destination_platform, "unknown"
            )
            if not compatibility['compatible']:
                errors.extend(compatibility['issues'])
            warnings.extend(compatibility.get('warnings', []))
        except Exception as e:
            warnings.append(f"Could not run compatibility check: {e}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    async def _run_post_migration_validation(self, plan: MigrationPlan):
        """Run post-migration validation."""
        # Check destination platform health
        checker = CMSHealthChecker(plan.destination_platform, plan.destination_path)
        health_result = await checker.run_health_check()
        
        if health_result['health_score'] < 70:
            raise CMSMigrationError(
                plan.source_platform,
                plan.destination_platform,
                "post_validation",
                f"Destination health score too low: {health_result['health_score']}"
            )
    
    async def _emit_progress(self, plan: MigrationPlan, message: str, progress: float = None, error: bool = False) -> Dict[str, Any]:
        """Emit progress update."""
        progress_data = {
            'migration_id': plan.id,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'error': error
        }
        
        if progress is not None:
            progress_data['progress'] = progress
        
        # Call progress callbacks
        for callback in self.progress_callbacks:
            try:
                await callback(progress_data)
            except Exception:
                pass  # Don't let callback errors stop migration
        
        return progress_data
    
    def _get_current_stage(self, plan: MigrationPlan) -> str:
        """Get current migration stage."""
        running_steps = [s for s in plan.steps if s.status == MigrationStatus.RUNNING]
        if running_steps:
            return running_steps[0].stage.value
        
        # Find the last completed step's stage
        completed_steps = [s for s in plan.steps if s.status == MigrationStatus.COMPLETED]
        if completed_steps:
            return completed_steps[-1].stage.value
        
        return MigrationStage.PREPARATION.value
    
    def _register_default_handlers(self):
        """Register default step handlers."""
        # This would register default handlers for common steps
        pass