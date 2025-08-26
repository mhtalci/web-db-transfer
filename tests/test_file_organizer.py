"""
Tests for File Organizer

Tests file reorganization system and directory cleanup operations.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime

from migration_assistant.checkup.cleaners.files import FileOrganizer, ReorganizationPlan
from migration_assistant.checkup.analyzers.structure import StructureAnalyzer
from migration_assistant.checkup.models import (
    CheckupConfig, StructureIssue, IssueType, IssueSeverity, FileMove, FileRemoval
)


class TestFileOrganizer:
    """Test cases for FileOrganizer."""
    
    @pytest.fixture
    def temp_project(self):
        """Create a temporary project structure for testing."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create a sample project structure with issues
        project_structure = {
            'README.md': '# Test Project',
            'pyproject.toml': '[tool.black]\nline-length = 88',
            'src/mypackage/__init__.py': '',
            'src/mypackage/main.py': 'def main(): pass',
            'tests/test_main.py': 'def test_main(): pass',
            'test_outside.py': 'def test_something(): pass',  # Misplaced
            'script_outside.py': 'if __name__ == "__main__": pass',  # Misplaced
            'wrongplace/README.md': '# Misplaced readme',  # Misplaced
            'empty_dir1/.gitkeep': '',  # Will be empty after removing .gitkeep
            'empty_dir2/nested_empty/.gitkeep': '',  # Nested empty
            'config_outside.yaml': 'key: value',  # Misplaced config
        }
        
        # Create files and directories
        for file_path, content in project_structure.items():
            full_path = temp_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
        
        # Remove .gitkeep files to create truly empty directories
        (temp_dir / 'empty_dir1' / '.gitkeep').unlink()
        (temp_dir / 'empty_dir2' / 'nested_empty' / '.gitkeep').unlink()
        
        yield temp_dir
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def config(self, temp_project):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=temp_project,
            create_backup=True,
            backup_dir=temp_project / 'backups',
            max_file_moves=10,
            dry_run=False
        )
    
    @pytest.fixture
    def organizer(self, config):
        """Create file organizer instance."""
        return FileOrganizer(config)
    
    @pytest.fixture
    def sample_structure_issues(self, temp_project):
        """Create sample structure issues for testing."""
        return [
            StructureIssue(
                file_path=temp_project / 'test_outside.py',
                line_number=None,
                severity=IssueSeverity.MEDIUM,
                issue_type=IssueType.STRUCTURE_ISSUE,
                message="Test file not in tests directory",
                description="Test file should be in tests directory",
                suggested_location=temp_project / 'tests' / 'test_outside.py'
            ),
            StructureIssue(
                file_path=temp_project / 'script_outside.py',
                line_number=None,
                severity=IssueSeverity.LOW,
                issue_type=IssueType.STRUCTURE_ISSUE,
                message="Script file not in scripts directory",
                description="Script file should be in scripts directory",
                suggested_location=temp_project / 'scripts' / 'script_outside.py'
            ),
            StructureIssue(
                file_path=temp_project / 'empty_dir1',
                line_number=None,
                severity=IssueSeverity.LOW,
                issue_type=IssueType.STRUCTURE_ISSUE,
                message="Empty directory: empty_dir1",
                description="Directory is empty and can be removed",
                suggestion="Remove empty directory"
            ),
            StructureIssue(
                file_path=temp_project / 'empty_dir2' / 'nested_empty',
                line_number=None,
                severity=IssueSeverity.LOW,
                issue_type=IssueType.STRUCTURE_ISSUE,
                message="Empty directory: empty_dir2/nested_empty",
                description="Directory is empty and can be removed",
                suggestion="Remove empty directory"
            ),
        ]
    
    def test_generate_reorganization_plan(self, organizer, sample_structure_issues):
        """Test reorganization plan generation."""
        plan = organizer.generate_reorganization_plan(sample_structure_issues)
        
        assert isinstance(plan, ReorganizationPlan)
        assert len(plan.file_moves) == 2  # Two misplaced files
        assert len(plan.directory_removals) == 2  # Two empty directories
        assert len(plan.directory_creations) >= 1  # At least scripts directory
        
        # Check file moves
        move_sources = [move[0] for move in plan.file_moves]
        assert any('test_outside.py' in str(source) for source in move_sources)
        assert any('script_outside.py' in str(source) for source in move_sources)
        
        # Check plan properties
        assert plan.total_operations > 0
        assert plan.risk_level in ['low', 'medium', 'high']
        assert plan.estimated_duration > 0
        assert plan.impact_assessment
    
    @pytest.mark.asyncio
    async def test_safe_move_file_success(self, organizer, temp_project):
        """Test successful file move operation."""
        source = temp_project / 'test_outside.py'
        destination = temp_project / 'tests' / 'test_outside.py'
        
        # Ensure destination directory exists
        destination.parent.mkdir(exist_ok=True)
        
        result = await organizer._safe_move_file(source, destination, "Test move")
        
        assert isinstance(result, FileMove)
        assert result.success
        assert result.source_path == source
        assert result.destination_path == destination
        assert destination.exists()
        assert not source.exists()
    
    @pytest.mark.asyncio
    async def test_safe_move_file_destination_exists(self, organizer, temp_project):
        """Test file move when destination already exists."""
        source = temp_project / 'test_outside.py'
        destination = temp_project / 'tests' / 'test_main.py'  # Already exists
        
        result = await organizer._safe_move_file(source, destination, "Test move")
        
        assert isinstance(result, FileMove)
        assert not result.success
        assert "destination exists" in result.reason
        assert source.exists()  # Source should still exist
    
    @pytest.mark.asyncio
    async def test_safe_move_file_source_not_exists(self, organizer, temp_project):
        """Test file move when source doesn't exist."""
        source = temp_project / 'nonexistent.py'
        destination = temp_project / 'tests' / 'nonexistent.py'
        
        result = await organizer._safe_move_file(source, destination, "Test move")
        
        assert isinstance(result, FileMove)
        assert not result.success
        assert not destination.exists()
    
    @pytest.mark.asyncio
    async def test_safe_remove_directory_success(self, organizer, temp_project):
        """Test successful directory removal."""
        empty_dir = temp_project / 'empty_dir1'
        
        result = await organizer._safe_remove_directory(empty_dir)
        
        assert isinstance(result, FileRemoval)
        assert result.success
        assert not empty_dir.exists()
    
    @pytest.mark.asyncio
    async def test_safe_remove_directory_not_empty(self, organizer, temp_project):
        """Test directory removal when directory is not empty."""
        non_empty_dir = temp_project / 'src'
        
        result = await organizer._safe_remove_directory(non_empty_dir)
        
        assert isinstance(result, FileRemoval)
        assert not result.success
        assert "not empty" in result.reason
        assert non_empty_dir.exists()
    
    @pytest.mark.asyncio
    async def test_remove_empty_directories(self, organizer, temp_project):
        """Test removal of multiple empty directories."""
        empty_dirs = [
            temp_project / 'empty_dir1',
            temp_project / 'empty_dir2' / 'nested_empty'
        ]
        
        results = await organizer.remove_empty_directories(empty_dirs)
        
        assert len(results) == 2
        assert all(isinstance(result, FileRemoval) for result in results)
        
        # Check that directories were removed (or at least attempted)
        successful_removals = [r for r in results if r.success]
        assert len(successful_removals) >= 1
    
    @pytest.mark.asyncio
    async def test_move_misplaced_files(self, organizer, sample_structure_issues):
        """Test moving misplaced files."""
        # Filter to only file issues (not directory issues)
        file_issues = [
            issue for issue in sample_structure_issues 
            if issue.file_path.is_file() and issue.suggested_location
        ]
        
        results = await organizer.move_misplaced_files(file_issues)
        
        assert len(results) == 2  # Two misplaced files
        assert all(isinstance(result, FileMove) for result in results)
        
        # Check that at least some moves were successful
        successful_moves = [r for r in results if r.success]
        assert len(successful_moves) >= 1
    
    @pytest.mark.asyncio
    async def test_reorganize_directory_structure_dry_run(self, organizer, sample_structure_issues):
        """Test reorganization in dry run mode."""
        organizer.config.dry_run = True
        plan = organizer.generate_reorganization_plan(sample_structure_issues)
        
        results = await organizer.reorganize_directory_structure(plan)
        
        assert "file_moves" in results
        assert "directory_removals" in results
        assert "directory_creations" in results
        assert "errors" in results
        
        # In dry run, all moves should be marked as dry_run
        for move in results["file_moves"]:
            assert move.get("dry_run", False)
    
    @pytest.mark.asyncio
    async def test_reorganize_directory_structure_with_backup(self, organizer, sample_structure_issues):
        """Test reorganization with backup creation."""
        organizer.config.create_backup = True
        organizer.config.dry_run = False
        plan = organizer.generate_reorganization_plan(sample_structure_issues)
        
        with patch.object(organizer, '_create_backup') as mock_backup:
            mock_backup.return_value = Path('/fake/backup/path')
            results = await organizer.reorganize_directory_structure(plan)
            
            mock_backup.assert_called_once()
            assert results["backup_path"] == Path('/fake/backup/path')
    
    def test_validate_reorganization_plan_valid(self, organizer, sample_structure_issues):
        """Test validation of a valid reorganization plan."""
        plan = organizer.generate_reorganization_plan(sample_structure_issues)
        errors = organizer._validate_reorganization_plan(plan)
        
        assert len(errors) == 0
    
    def test_validate_reorganization_plan_invalid(self, organizer, temp_project):
        """Test validation of an invalid reorganization plan."""
        # Create a plan with conflicting moves
        invalid_plan = ReorganizationPlan(
            file_moves=[
                (temp_project / 'file1.py', temp_project / 'dest.py', "reason1"),
                (temp_project / 'file2.py', temp_project / 'dest.py', "reason2"),  # Conflict
            ],
            directory_removals=[],
            directory_creations=[],
            impact_assessment="Test",
            estimated_duration=1.0,
            risk_level="low"
        )
        
        errors = organizer._validate_reorganization_plan(invalid_plan)
        assert len(errors) > 0
        assert any("Multiple files would be moved" in error for error in errors)
    
    def test_is_safe_to_remove(self, organizer, temp_project):
        """Test directory safety check."""
        # Safe to remove: empty directory
        assert organizer._is_safe_to_remove(temp_project / 'empty_dir1')
        
        # Not safe to remove: target directory
        assert not organizer._is_safe_to_remove(temp_project)
        
        # Not safe to remove: non-empty directory
        assert not organizer._is_safe_to_remove(temp_project / 'src')
        
        # Not safe to remove: important directory
        git_dir = temp_project / '.git'
        git_dir.mkdir()
        assert not organizer._is_safe_to_remove(git_dir)
    
    def test_is_directory_empty(self, organizer, temp_project):
        """Test empty directory detection."""
        # Empty directory
        assert organizer._is_directory_empty(temp_project / 'empty_dir1')
        
        # Non-empty directory
        assert not organizer._is_directory_empty(temp_project / 'src')
    
    def test_assess_reorganization_impact(self, organizer):
        """Test impact assessment."""
        # No changes
        impact = organizer._assess_reorganization_impact(0, 0, 0)
        assert "No changes needed" in impact
        
        # Low impact
        impact = organizer._assess_reorganization_impact(2, 1, 1)
        assert "Low impact" in impact
        
        # Medium impact
        impact = organizer._assess_reorganization_impact(10, 5, 3)
        assert "Medium impact" in impact
        
        # High impact
        impact = organizer._assess_reorganization_impact(30, 10, 5)
        assert "High impact" in impact
    
    def test_assess_risk_level(self, organizer, temp_project):
        """Test risk level assessment."""
        # Low risk: no Python files, no important directories
        file_moves = [(temp_project / 'file.txt', temp_project / 'dest.txt', "reason")]
        risk = organizer._assess_risk_level(file_moves, [])
        assert risk == "low"
        
        # Higher risk: Python files
        file_moves = [(temp_project / 'file.py', temp_project / 'dest.py', "reason")]
        risk = organizer._assess_risk_level(file_moves, [])
        assert risk in ["low", "medium"]
        
        # Higher risk: many operations
        file_moves = [(temp_project / f'file{i}.py', temp_project / f'dest{i}.py', "reason") 
                     for i in range(15)]
        risk = organizer._assess_risk_level(file_moves, [])
        assert risk == "high"
    
    def test_estimate_duration(self, organizer, temp_project):
        """Test duration estimation."""
        file_moves = [(temp_project / 'file1.py', temp_project / 'dest1.py', "reason")]
        directory_removals = [temp_project / 'empty_dir']
        directory_creations = [temp_project / 'new_dir']
        
        duration = organizer._estimate_duration(file_moves, directory_removals, directory_creations)
        
        assert duration > 0
        assert isinstance(duration, float)
        
        # With backup enabled, duration should be higher
        organizer.config.create_backup = True
        duration_with_backup = organizer._estimate_duration(file_moves, directory_removals, directory_creations)
        assert duration_with_backup > duration


class TestReorganizationPlan:
    """Test cases for ReorganizationPlan."""
    
    def test_reorganization_plan_creation(self):
        """Test creation of reorganization plan."""
        plan = ReorganizationPlan(
            file_moves=[(Path('src.py'), Path('dest.py'), "reason")],
            directory_removals=[Path('empty_dir')],
            directory_creations=[Path('new_dir')],
            impact_assessment="Low impact",
            estimated_duration=1.5,
            risk_level="low"
        )
        
        assert len(plan.file_moves) == 1
        assert len(plan.directory_removals) == 1
        assert len(plan.directory_creations) == 1
        assert plan.total_operations == 3
        assert plan.impact_assessment == "Low impact"
        assert plan.estimated_duration == 1.5
        assert plan.risk_level == "low"
    
    def test_total_operations_property(self):
        """Test total operations calculation."""
        plan = ReorganizationPlan(
            file_moves=[(Path('f1'), Path('d1'), "r1"), (Path('f2'), Path('d2'), "r2")],
            directory_removals=[Path('dir1'), Path('dir2'), Path('dir3')],
            directory_creations=[Path('new1')],
            impact_assessment="Test",
            estimated_duration=1.0,
            risk_level="low"
        )
        
        assert plan.total_operations == 6  # 2 + 3 + 1


class TestFileOrganizerIntegration:
    """Integration tests for file organizer with structure analyzer."""
    
    @pytest.fixture
    def integration_project(self):
        """Create a project for integration testing."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create a more complex project structure
        project_structure = {
            'README.md': '# Test Project',
            'pyproject.toml': '[tool.black]\nline-length = 88',
            'src/mypackage/__init__.py': '',
            'src/mypackage/main.py': 'def main(): pass',
            'src/mypackage/utils.py': 'def helper(): pass',
            'tests/test_main.py': 'def test_main(): pass',
            'test_outside.py': 'def test_something(): pass',
            'script_outside.py': 'if __name__ == "__main__": pass',
            'config_outside.yaml': 'key: value',
            'wrongplace/README.md': '# Misplaced readme',
            'empty1/.gitkeep': '',
            'empty2/nested_empty/.gitkeep': '',
            'package_without_init/module.py': 'def func(): pass',
        }
        
        for file_path, content in project_structure.items():
            full_path = temp_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
        
        # Remove .gitkeep files to create empty directories
        (temp_dir / 'empty1' / '.gitkeep').unlink()
        (temp_dir / 'empty2' / 'nested_empty' / '.gitkeep').unlink()
        
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.mark.asyncio
    async def test_full_integration_workflow(self, integration_project):
        """Test full integration between analyzer and organizer."""
        # Setup
        config = CheckupConfig(
            target_directory=integration_project,
            create_backup=False,  # Skip backup for test speed
            max_file_moves=20,
            dry_run=True  # Use dry run for safety
        )
        
        # Analyze structure issues
        analyzer = StructureAnalyzer(config)
        issues = await analyzer.analyze()
        
        assert len(issues) > 0
        print(f"Found {len(issues)} structure issues")
        
        # Generate reorganization plan
        organizer = FileOrganizer(config)
        plan = organizer.generate_reorganization_plan(issues)
        
        assert plan.total_operations > 0
        print(f"Generated plan with {plan.total_operations} operations")
        print(f"Risk level: {plan.risk_level}")
        print(f"Impact: {plan.impact_assessment}")
        
        # Execute plan (dry run)
        results = await organizer.reorganize_directory_structure(plan)
        
        assert "file_moves" in results
        assert "errors" in results
        assert len(results["errors"]) == 0  # Should have no errors in dry run
        
        print(f"Dry run completed with {len(results['file_moves'])} file moves")


if __name__ == '__main__':
    pytest.main([__file__])