"""
File Organizer

Handles safe file moving and directory cleanup operations.
"""

import ast
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set, Any
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict

from migration_assistant.checkup.models import (
    CheckupConfig, FileMove, FileRemoval, StructureIssue
)


@dataclass
class DependencyGraph:
    """Represents dependencies between files."""
    dependencies: Dict[Path, Set[Path]]  # file -> set of files it depends on
    dependents: Dict[Path, Set[Path]]    # file -> set of files that depend on it
    
    def get_move_order(self, files_to_move: List[Path]) -> List[Path]:
        """Get optimal order for moving files to minimize import breaks."""
        # Use topological sort to order moves
        # Files with fewer dependencies should be moved first
        remaining = set(files_to_move)
        ordered = []
        
        while remaining:
            # Find files with no dependencies in remaining set
            no_deps = []
            for file_path in remaining:
                file_deps = self.dependencies.get(file_path, set())
                if not (file_deps & remaining):  # No dependencies in remaining files
                    no_deps.append(file_path)
            
            if not no_deps:
                # Circular dependency or isolated group - just pick one
                no_deps = [next(iter(remaining))]
            
            # Add to ordered list and remove from remaining
            ordered.extend(no_deps)
            remaining -= set(no_deps)
        
        return ordered
    
    def analyze_move_impact(self, source: Path, destination: Path) -> Dict[str, Any]:
        """Analyze the impact of moving a file."""
        impact = {
            "broken_imports": [],
            "affected_files": [],
            "risk_level": "low",
            "suggested_fixes": []
        }
        
        # Find files that import this file
        affected_files = self.dependents.get(source, set())
        impact["affected_files"] = list(affected_files)
        
        if affected_files:
            impact["risk_level"] = "medium" if len(affected_files) <= 5 else "high"
            impact["suggested_fixes"].append(
                f"Update {len(affected_files)} import statements after moving {source.name}"
            )
        
        return impact


@dataclass
class RollbackPlan:
    """Plan for rolling back file organization changes."""
    file_moves: List[Tuple[Path, Path]]  # (current_location, original_location)
    directory_restorations: List[Path]   # Directories to recreate
    backup_path: Optional[Path]          # Path to backup for full restoration
    timestamp: datetime
    
    def can_rollback(self) -> bool:
        """Check if rollback is possible."""
        if self.backup_path and self.backup_path.exists():
            return True
        
        # Check if individual moves can be reversed
        for current, original in self.file_moves:
            if not current.exists():
                return False
        
        return True


@dataclass
class ReorganizationPlan:
    """Plan for reorganizing files and directories."""
    file_moves: List[Tuple[Path, Path, str]]  # (source, destination, reason)
    directory_removals: List[Path]  # Empty directories to remove
    directory_creations: List[Path]  # New directories to create
    impact_assessment: str
    estimated_duration: float  # in seconds
    risk_level: str  # "low", "medium", "high"
    
    @property
    def total_operations(self) -> int:
        """Total number of operations in the plan."""
        return len(self.file_moves) + len(self.directory_removals) + len(self.directory_creations)


class FileOrganizer:
    """Handles file organization and directory cleanup operations."""
    
    def __init__(self, config: CheckupConfig):
        """Initialize the file organizer."""
        self.config = config
        self.target_directory = config.target_directory
        self.backup_dir = config.backup_dir
        self._backup_created = False
        self._backup_path: Optional[Path] = None
    
    async def reorganize_directory_structure(self, plan: ReorganizationPlan) -> Dict[str, List]:
        """
        Execute a reorganization plan with safety checks.
        
        Args:
            plan: The reorganization plan to execute
            
        Returns:
            Dictionary with results of the reorganization
        """
        results = {
            "file_moves": [],
            "directory_removals": [],
            "directory_creations": [],
            "errors": [],
            "backup_path": None
        }
        
        # Create backup if enabled
        if self.config.create_backup and not self.config.dry_run:
            backup_path = await self._create_backup()
            results["backup_path"] = backup_path
        
        # Validate plan before execution
        validation_errors = self._validate_reorganization_plan(plan)
        if validation_errors:
            results["errors"].extend(validation_errors)
            return results
        
        # Execute plan if not in dry run mode
        if not self.config.dry_run:
            # Create new directories first
            for directory in plan.directory_creations:
                try:
                    directory.mkdir(parents=True, exist_ok=True)
                    results["directory_creations"].append({
                        "path": directory,
                        "success": True,
                        "timestamp": datetime.now()
                    })
                except Exception as e:
                    results["errors"].append(f"Failed to create directory {directory}: {e}")
            
            # Move files
            for source, destination, reason in plan.file_moves:
                move_result = await self._safe_move_file(source, destination, reason)
                results["file_moves"].append(move_result)
            
            # Remove empty directories last
            for directory in plan.directory_removals:
                removal_result = await self._safe_remove_directory(directory)
                results["directory_removals"].append(removal_result)
        else:
            # Dry run - just log what would be done
            for source, destination, reason in plan.file_moves:
                results["file_moves"].append({
                    "source": source,
                    "destination": destination,
                    "reason": reason,
                    "success": True,
                    "dry_run": True,
                    "timestamp": datetime.now()
                })
        
        return results
    
    async def remove_empty_directories(self, directories: List[Path]) -> List[FileRemoval]:
        """
        Remove empty directories safely.
        
        Args:
            directories: List of directories to remove
            
        Returns:
            List of removal results
        """
        results = []
        
        # Sort directories by depth (deepest first) to avoid removing parent before child
        sorted_dirs = sorted(directories, key=lambda d: len(d.parts), reverse=True)
        
        for directory in sorted_dirs:
            if self._is_safe_to_remove(directory):
                removal_result = await self._safe_remove_directory(directory)
                results.append(removal_result)
            else:
                results.append(FileRemoval(
                    file_path=directory,
                    reason="Directory not safe to remove",
                    success=False
                ))
        
        return results
    
    async def move_misplaced_files(self, misplaced_files: List[StructureIssue]) -> List[FileMove]:
        """
        Move misplaced files to their suggested locations.
        
        Args:
            misplaced_files: List of structure issues with suggested locations
            
        Returns:
            List of file move results
        """
        results = []
        
        # Filter issues that have suggested locations
        moveable_files = [
            issue for issue in misplaced_files 
            if issue.suggested_location and issue.suggested_location != issue.file_path
        ]
        
        # Limit number of moves based on configuration
        if len(moveable_files) > self.config.max_file_moves:
            moveable_files = moveable_files[:self.config.max_file_moves]
        
        for issue in moveable_files:
            move_result = await self._safe_move_file(
                issue.file_path,
                issue.suggested_location,
                issue.message
            )
            results.append(move_result)
        
        return results
    
    def generate_reorganization_plan(
        self, 
        structure_issues: List[StructureIssue]
    ) -> ReorganizationPlan:
        """
        Generate a reorganization plan based on structure issues.
        
        Args:
            structure_issues: List of structure issues to address
            
        Returns:
            Reorganization plan
        """
        file_moves = []
        directory_removals = []
        directory_creations = set()
        seen_destinations = set()
        
        # Process misplaced files, avoiding duplicate destinations
        for issue in structure_issues:
            if (issue.suggested_location and 
                issue.file_path.is_file() and 
                issue.suggested_location not in seen_destinations):
                
                file_moves.append((
                    issue.file_path,
                    issue.suggested_location,
                    issue.message
                ))
                seen_destinations.add(issue.suggested_location)
                # Track directories that need to be created
                directory_creations.add(issue.suggested_location.parent)
        
        # Process empty directories
        for issue in structure_issues:
            if "Empty directory" in issue.message and issue.file_path.is_dir():
                directory_removals.append(issue.file_path)
        
        # Filter out directories that already exist
        directory_creations = [
            d for d in directory_creations 
            if not d.exists() and d != self.target_directory
        ]
        
        # Assess impact and risk
        impact_assessment = self._assess_reorganization_impact(
            len(file_moves), len(directory_removals), len(directory_creations)
        )
        
        risk_level = self._assess_risk_level(file_moves, directory_removals)
        estimated_duration = self._estimate_duration(file_moves, directory_removals, directory_creations)
        
        return ReorganizationPlan(
            file_moves=file_moves,
            directory_removals=directory_removals,
            directory_creations=directory_creations,
            impact_assessment=impact_assessment,
            estimated_duration=estimated_duration,
            risk_level=risk_level
        )
    
    async def _create_backup(self) -> Path:
        """Create a backup of the target directory."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}"
        backup_path = self.backup_dir / backup_name
        
        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Create backup
        shutil.copytree(
            self.target_directory,
            backup_path,
            ignore=shutil.ignore_patterns(*self.config.exclude_patterns)
        )
        
        self._backup_created = True
        self._backup_path = backup_path
        
        return backup_path
    
    async def _safe_move_file(self, source: Path, destination: Path, reason: str) -> FileMove:
        """
        Safely move a file with validation and error handling.
        
        Args:
            source: Source file path
            destination: Destination file path
            reason: Reason for the move
            
        Returns:
            FileMove result
        """
        try:
            # Validate move operation
            if not source.exists():
                return FileMove(
                    source_path=source,
                    destination_path=destination,
                    reason=reason,
                    success=False
                )
            
            if destination.exists():
                return FileMove(
                    source_path=source,
                    destination_path=destination,
                    reason=f"{reason} (destination exists)",
                    success=False
                )
            
            # Create destination directory if needed
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            # Move the file
            shutil.move(str(source), str(destination))
            
            return FileMove(
                source_path=source,
                destination_path=destination,
                reason=reason,
                success=True
            )
            
        except Exception as e:
            return FileMove(
                source_path=source,
                destination_path=destination,
                reason=f"{reason} (error: {e})",
                success=False
            )
    
    async def _safe_remove_directory(self, directory: Path) -> FileRemoval:
        """
        Safely remove a directory with validation.
        
        Args:
            directory: Directory to remove
            
        Returns:
            FileRemoval result
        """
        try:
            if not directory.exists():
                return FileRemoval(
                    file_path=directory,
                    reason="Directory does not exist",
                    success=False
                )
            
            if not self._is_directory_empty(directory):
                return FileRemoval(
                    file_path=directory,
                    reason="Directory is not empty",
                    success=False
                )
            
            # Remove the directory
            directory.rmdir()
            
            return FileRemoval(
                file_path=directory,
                reason="Empty directory removed",
                success=True
            )
            
        except Exception as e:
            return FileRemoval(
                file_path=directory,
                reason=f"Error removing directory: {e}",
                success=False
            )
    
    def _validate_reorganization_plan(self, plan: ReorganizationPlan) -> List[str]:
        """Validate a reorganization plan for safety."""
        errors = []
        
        # Check if too many operations
        if plan.total_operations > 100:
            errors.append(f"Plan contains too many operations ({plan.total_operations}). Consider breaking it down.")
        
        # Check for conflicting moves
        destinations = set()
        for source, destination, _ in plan.file_moves:
            if destination in destinations:
                errors.append(f"Multiple files would be moved to {destination}")
            destinations.add(destination)
        
        # Check if source files exist
        for source, destination, _ in plan.file_moves:
            if not source.exists():
                errors.append(f"Source file does not exist: {source}")
        
        # Check if we're not moving files outside the target directory
        for source, destination, _ in plan.file_moves:
            try:
                destination.relative_to(self.target_directory)
            except ValueError:
                errors.append(f"Destination outside target directory: {destination}")
        
        return errors
    
    def _is_safe_to_remove(self, directory: Path) -> bool:
        """Check if directory is safe to remove."""
        # Don't remove if it's the target directory or a parent
        if directory == self.target_directory:
            return False
        
        try:
            directory.relative_to(self.target_directory)
        except ValueError:
            # Directory is not under target directory
            return False
        
        # Don't remove important directories
        important_dirs = {'.git', '.github', '.vscode', 'node_modules', '__pycache__'}
        if directory.name in important_dirs:
            return False
        
        # Check if truly empty
        return self._is_directory_empty(directory)
    
    def _is_directory_empty(self, directory: Path) -> bool:
        """Check if directory is completely empty."""
        try:
            return not any(directory.iterdir())
        except (PermissionError, OSError):
            return False
    
    def _assess_reorganization_impact(
        self, 
        file_moves: int, 
        directory_removals: int, 
        directory_creations: int
    ) -> str:
        """Assess the impact of a reorganization plan."""
        total_ops = file_moves + directory_removals + directory_creations
        
        if total_ops == 0:
            return "No changes needed"
        elif total_ops <= 5:
            return f"Low impact: {total_ops} operations (minimal disruption expected)"
        elif total_ops <= 20:
            return f"Medium impact: {total_ops} operations (some import paths may need updating)"
        else:
            return f"High impact: {total_ops} operations (significant restructuring, thorough testing recommended)"
    
    def _assess_risk_level(
        self, 
        file_moves: List[Tuple[Path, Path, str]], 
        directory_removals: List[Path]
    ) -> str:
        """Assess the risk level of reorganization operations."""
        # Check for risky moves
        risky_moves = 0
        for source, destination, _ in file_moves:
            # Moving Python files is riskier due to import impacts
            if source.suffix == '.py':
                risky_moves += 1
            # Moving from/to important directories
            important_parts = {'src', 'lib', 'tests', 'docs'}
            if (any(part in important_parts for part in source.parts) or
                any(part in important_parts for part in destination.parts)):
                risky_moves += 1
        
        risk_score = risky_moves + len(directory_removals)
        
        if risk_score == 0:
            return "low"
        elif risk_score <= 3:
            return "low"
        elif risk_score <= 10:
            return "medium"
        else:
            return "high"
    
    def _estimate_duration(
        self, 
        file_moves: List[Tuple[Path, Path, str]], 
        directory_removals: List[Path], 
        directory_creations: List[Path]
    ) -> float:
        """Estimate duration of reorganization operations in seconds."""
        # Base time estimates per operation
        move_time = 0.1  # seconds per file move
        removal_time = 0.05  # seconds per directory removal
        creation_time = 0.05  # seconds per directory creation
        
        total_time = (
            len(file_moves) * move_time +
            len(directory_removals) * removal_time +
            len(directory_creations) * creation_time
        )
        
        # Add overhead for backup creation if enabled
        if self.config.create_backup:
            total_time += 5.0  # 5 seconds for backup
        
        return total_time
    
    def analyze_dependencies(self, files: List[Path]) -> DependencyGraph:
        """
        Analyze import dependencies between Python files.
        
        Args:
            files: List of Python files to analyze
            
        Returns:
            Dependency graph
        """
        dependencies = {}
        dependents = defaultdict(set)
        
        for file_path in files:
            if file_path.suffix != '.py':
                continue
            
            try:
                file_deps = self._extract_file_dependencies(file_path)
                dependencies[file_path] = file_deps
                
                # Build reverse dependency map
                for dep in file_deps:
                    dependents[dep].add(file_path)
                    
            except Exception:
                # If we can't parse the file, assume no dependencies
                dependencies[file_path] = set()
        
        return DependencyGraph(dependencies=dependencies, dependents=dict(dependents))
    
    def _extract_file_dependencies(self, file_path: Path) -> Set[Path]:
        """Extract dependencies from a Python file."""
        dependencies = set()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse AST to find imports
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        dep_path = self._resolve_import_path(alias.name, file_path)
                        if dep_path:
                            dependencies.add(dep_path)
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        dep_path = self._resolve_import_path(node.module, file_path)
                        if dep_path:
                            dependencies.add(dep_path)
        
        except (SyntaxError, UnicodeDecodeError, OSError):
            # If we can't parse the file, return empty dependencies
            pass
        
        return dependencies
    
    def _resolve_import_path(self, import_name: str, current_file: Path) -> Optional[Path]:
        """Resolve an import name to a file path."""
        # Handle relative imports
        if import_name.startswith('.'):
            # Relative import - resolve relative to current file's directory
            parts = import_name.lstrip('.').split('.')
            current_dir = current_file.parent
            
            # Go up directories for each leading dot
            dots = len(import_name) - len(import_name.lstrip('.'))
            for _ in range(dots - 1):
                current_dir = current_dir.parent
            
            # Build path
            for part in parts:
                if part:
                    current_dir = current_dir / part
            
            # Check for .py file or __init__.py in directory
            if (current_dir.with_suffix('.py')).exists():
                return current_dir.with_suffix('.py')
            elif (current_dir / '__init__.py').exists():
                return current_dir / '__init__.py'
        
        else:
            # Absolute import - search in target directory
            parts = import_name.split('.')
            
            # Try to find the module in the project
            search_paths = [self.target_directory]
            
            # Add src/ if it exists
            if (self.target_directory / 'src').exists():
                search_paths.append(self.target_directory / 'src')
            
            for search_path in search_paths:
                module_path = search_path
                for part in parts:
                    module_path = module_path / part
                
                # Check for .py file
                if module_path.with_suffix('.py').exists():
                    return module_path.with_suffix('.py')
                
                # Check for package directory with __init__.py
                if (module_path / '__init__.py').exists():
                    return module_path / '__init__.py'
        
        return None
    
    async def create_rollback_plan(self, executed_moves: List[FileMove]) -> RollbackPlan:
        """
        Create a rollback plan for executed file moves.
        
        Args:
            executed_moves: List of successfully executed file moves
            
        Returns:
            Rollback plan
        """
        file_moves = []
        directory_restorations = set()
        
        for move in executed_moves:
            if move.success:
                # Reverse the move
                file_moves.append((move.destination_path, move.source_path))
                
                # Track directories that might need restoration
                if move.source_path.parent != move.destination_path.parent:
                    directory_restorations.add(move.source_path.parent)
        
        return RollbackPlan(
            file_moves=file_moves,
            directory_restorations=list(directory_restorations),
            backup_path=self._backup_path,
            timestamp=datetime.now()
        )
    
    async def execute_rollback(self, rollback_plan: RollbackPlan) -> Dict[str, Any]:
        """
        Execute a rollback plan to undo file organization changes.
        
        Args:
            rollback_plan: The rollback plan to execute
            
        Returns:
            Results of the rollback operation
        """
        results = {
            "file_moves": [],
            "directory_restorations": [],
            "errors": [],
            "success": True
        }
        
        if not rollback_plan.can_rollback():
            results["errors"].append("Rollback not possible - backup or files missing")
            results["success"] = False
            return results
        
        # If we have a backup, use full restoration
        if rollback_plan.backup_path and rollback_plan.backup_path.exists():
            try:
                # Remove current directory contents (except backup)
                for item in self.target_directory.iterdir():
                    if item != self.backup_dir:
                        if item.is_dir():
                            shutil.rmtree(item)
                        else:
                            item.unlink()
                
                # Restore from backup
                for item in rollback_plan.backup_path.iterdir():
                    dest = self.target_directory / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)
                
                results["success"] = True
                return results
                
            except Exception as e:
                results["errors"].append(f"Full restoration failed: {e}")
                results["success"] = False
        
        # Otherwise, reverse individual moves
        for current_path, original_path in rollback_plan.file_moves:
            try:
                # Create original directory if needed
                original_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Move file back
                shutil.move(str(current_path), str(original_path))
                
                results["file_moves"].append({
                    "source": current_path,
                    "destination": original_path,
                    "success": True
                })
                
            except Exception as e:
                results["file_moves"].append({
                    "source": current_path,
                    "destination": original_path,
                    "success": False,
                    "error": str(e)
                })
                results["errors"].append(f"Failed to rollback {current_path}: {e}")
        
        # Restore directories
        for directory in rollback_plan.directory_restorations:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                results["directory_restorations"].append({
                    "directory": directory,
                    "success": True
                })
            except Exception as e:
                results["directory_restorations"].append({
                    "directory": directory,
                    "success": False,
                    "error": str(e)
                })
                results["errors"].append(f"Failed to restore directory {directory}: {e}")
        
        results["success"] = len(results["errors"]) == 0
        return results
    
    def analyze_reorganization_impact(self, plan: ReorganizationPlan) -> Dict[str, Any]:
        """
        Analyze the impact of a reorganization plan on imports and dependencies.
        
        Args:
            plan: The reorganization plan to analyze
            
        Returns:
            Impact analysis results
        """
        impact = {
            "dependency_analysis": {},
            "import_breaks": [],
            "affected_files": set(),
            "risk_assessment": "low",
            "mitigation_suggestions": []
        }
        
        # Get all Python files that will be moved
        python_moves = [
            (source, dest) for source, dest, _ in plan.file_moves 
            if source.suffix == '.py'
        ]
        
        if not python_moves:
            return impact
        
        # Analyze dependencies
        all_python_files = list(self.target_directory.rglob("*.py"))
        dependency_graph = self.analyze_dependencies(all_python_files)
        
        # Analyze impact of each move
        for source, destination in python_moves:
            move_impact = dependency_graph.analyze_move_impact(source, destination)
            impact["dependency_analysis"][str(source)] = move_impact
            
            if move_impact["affected_files"]:
                impact["affected_files"].update(move_impact["affected_files"])
                impact["import_breaks"].extend(move_impact.get("broken_imports", []))
        
        # Assess overall risk
        total_affected = len(impact["affected_files"])
        if total_affected == 0:
            impact["risk_assessment"] = "low"
        elif total_affected <= 5:
            impact["risk_assessment"] = "medium"
        else:
            impact["risk_assessment"] = "high"
        
        # Generate mitigation suggestions
        if total_affected > 0:
            impact["mitigation_suggestions"].extend([
                f"Review and update {total_affected} files with import statements",
                "Run tests after reorganization to catch import errors",
                "Consider using IDE refactoring tools for automatic import updates"
            ])
        
        if impact["risk_assessment"] == "high":
            impact["mitigation_suggestions"].append(
                "Consider breaking reorganization into smaller phases"
            )
        
        return impact