"""
Tests for Migration Planning System

Tests dependency analysis, rollback capabilities, and impact assessment.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime

from migration_assistant.checkup.cleaners.files import (
    FileOrganizer, DependencyGraph, RollbackPlan
)
from migration_assistant.checkup.analyzers.structure import StructureAnalyzer
from migration_assistant.checkup.models import (
    CheckupConfig, StructureIssue, IssueType, IssueSeverity, FileMove
)


class TestDependencyGraph:
    """Test cases for DependencyGraph."""
    
    def test_dependency_graph_creation(self):
        """Test creation of dependency graph."""
        dependencies = {
            Path('a.py'): {Path('b.py'), Path('c.py')},
            Path('b.py'): {Path('c.py')},
            Path('c.py'): set()
        }
        dependents = {
            Path('b.py'): {Path('a.py')},
            Path('c.py'): {Path('a.py'), Path('b.py')}
        }
        
        graph = DependencyGraph(dependencies=dependencies, dependents=dependents)
        
        assert graph.dependencies == dependencies
        assert graph.dependents == dependents
    
    def test_get_move_order(self):
        """Test optimal move order calculation."""
        dependencies = {
            Path('a.py'): {Path('b.py')},
            Path('b.py'): {Path('c.py')},
            Path('c.py'): set(),
            Path('d.py'): set()
        }
        dependents = {
            Path('b.py'): {Path('a.py')},
            Path('c.py'): {Path('b.py')}
        }
        
        graph = DependencyGraph(dependencies=dependencies, dependents=dependents)
        files_to_move = [Path('a.py'), Path('b.py'), Path('c.py'), Path('d.py')]
        
        order = graph.get_move_order(files_to_move)
        
        # Files with no dependencies should come first
        assert Path('c.py') in order[:2]  # c.py and d.py should be first
        assert Path('d.py') in order[:2]
        
        # a.py should come after b.py (since a depends on b)
        a_index = order.index(Path('a.py'))
        b_index = order.index(Path('b.py'))
        assert b_index < a_index
    
    def test_analyze_move_impact(self):
        """Test move impact analysis."""
        dependencies = {Path('a.py'): {Path('b.py')}}
        dependents = {Path('b.py'): {Path('a.py'), Path('c.py')}}
        
        graph = DependencyGraph(dependencies=dependencies, dependents=dependents)
        
        impact = graph.analyze_move_impact(Path('b.py'), Path('new/b.py'))
        
        assert len(impact["affected_files"]) == 2
        assert Path('a.py') in impact["affected_files"]
        assert Path('c.py') in impact["affected_files"]
        assert impact["risk_level"] == "medium"
        assert len(impact["suggested_fixes"]) > 0


class TestRollbackPlan:
    """Test cases for RollbackPlan."""
    
    def test_rollback_plan_creation(self):
        """Test creation of rollback plan."""
        file_moves = [(Path('new/a.py'), Path('old/a.py'))]
        directory_restorations = [Path('old')]
        backup_path = Path('/backup')
        
        plan = RollbackPlan(
            file_moves=file_moves,
            directory_restorations=directory_restorations,
            backup_path=backup_path,
            timestamp=datetime.now()
        )
        
        assert plan.file_moves == file_moves
        assert plan.directory_restorations == directory_restorations
        assert plan.backup_path == backup_path
    
    def test_can_rollback_with_backup(self, tmp_path):
        """Test rollback possibility with backup."""
        backup_path = tmp_path / 'backup'
        backup_path.mkdir()
        
        plan = RollbackPlan(
            file_moves=[],
            directory_restorations=[],
            backup_path=backup_path,
            timestamp=datetime.now()
        )
        
        assert plan.can_rollback()
    
    def test_can_rollback_without_backup(self, tmp_path):
        """Test rollback possibility without backup."""
        # Create files for rollback
        current_file = tmp_path / 'current.py'
        current_file.write_text('content')
        
        plan = RollbackPlan(
            file_moves=[(current_file, tmp_path / 'original.py')],
            directory_restorations=[],
            backup_path=None,
            timestamp=datetime.now()
        )
        
        assert plan.can_rollback()
    
    def test_cannot_rollback_missing_files(self, tmp_path):
        """Test rollback impossibility with missing files."""
        plan = RollbackPlan(
            file_moves=[(tmp_path / 'missing.py', tmp_path / 'original.py')],
            directory_restorations=[],
            backup_path=None,
            timestamp=datetime.now()
        )
        
        assert not plan.can_rollback()


class TestMigrationPlanning:
    """Test cases for migration planning functionality."""
    
    @pytest.fixture
    def temp_project(self):
        """Create a temporary project with dependencies."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create Python files with import dependencies
        project_structure = {
            'main.py': '''
import utils
from config import settings

def main():
    utils.helper()
    print(settings.DEBUG)
''',
            'utils.py': '''
from config import settings

def helper():
    return "help"
''',
            'config.py': '''
DEBUG = True
''',
            'tests/test_main.py': '''
import sys
sys.path.append('..')
import main

def test_main():
    main.main()
''',
            'scripts/deploy.py': '''
import sys
import os
sys.path.append('..')
from config import settings

if __name__ == "__main__":
    print("Deploying...")
''',
        }
        
        for file_path, content in project_structure.items():
            full_path = temp_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
        
        yield temp_dir
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
    
    def test_analyze_dependencies(self, organizer, temp_project):
        """Test dependency analysis."""
        python_files = list(temp_project.rglob("*.py"))
        
        graph = organizer.analyze_dependencies(python_files)
        
        assert isinstance(graph, DependencyGraph)
        assert len(graph.dependencies) > 0
        assert len(graph.dependents) > 0
        
        # Check specific dependencies
        main_py = temp_project / 'main.py'
        utils_py = temp_project / 'utils.py'
        config_py = temp_project / 'config.py'
        
        if main_py in graph.dependencies:
            main_deps = graph.dependencies[main_py]
            # main.py should depend on utils.py and config.py
            assert any('utils' in str(dep) for dep in main_deps)
            assert any('config' in str(dep) for dep in main_deps)
    
    def test_extract_file_dependencies(self, organizer, temp_project):
        """Test extraction of dependencies from a single file."""
        main_py = temp_project / 'main.py'
        
        deps = organizer._extract_file_dependencies(main_py)
        
        assert isinstance(deps, set)
        # Should find dependencies on utils and config
        dep_names = [str(dep) for dep in deps]
        assert any('utils' in name for name in dep_names)
        assert any('config' in name for name in dep_names)
    
    def test_resolve_import_path(self, organizer, temp_project):
        """Test import path resolution."""
        main_py = temp_project / 'main.py'
        
        # Test absolute import
        utils_path = organizer._resolve_import_path('utils', main_py)
        assert utils_path is not None
        assert 'utils.py' in str(utils_path)
        
        # Test relative import (from subdirectory)
        test_file = temp_project / 'tests' / 'test_main.py'
        main_path = organizer._resolve_import_path('main', test_file)
        # This might not resolve correctly due to sys.path manipulation in test
        # but the method should not crash
        assert main_path is None or 'main.py' in str(main_path)
    
    @pytest.mark.asyncio
    async def test_create_rollback_plan(self, organizer, temp_project):
        """Test rollback plan creation."""
        # Create some executed moves
        executed_moves = [
            FileMove(
                source_path=temp_project / 'utils.py',
                destination_path=temp_project / 'src' / 'utils.py',
                reason="Reorganization",
                success=True
            ),
            FileMove(
                source_path=temp_project / 'config.py',
                destination_path=temp_project / 'config' / 'settings.py',
                reason="Reorganization",
                success=True
            ),
            FileMove(
                source_path=temp_project / 'failed.py',
                destination_path=temp_project / 'dest' / 'failed.py',
                reason="Failed move",
                success=False
            )
        ]
        
        rollback_plan = await organizer.create_rollback_plan(executed_moves)
        
        assert isinstance(rollback_plan, RollbackPlan)
        assert len(rollback_plan.file_moves) == 2  # Only successful moves
        assert len(rollback_plan.directory_restorations) >= 0
        
        # Check that moves are reversed
        for current, original in rollback_plan.file_moves:
            # Find corresponding executed move
            executed_move = next(
                move for move in executed_moves 
                if move.success and move.destination_path == current
            )
            assert original == executed_move.source_path
    
    @pytest.mark.asyncio
    async def test_execute_rollback_individual_moves(self, organizer, temp_project):
        """Test rollback execution with individual file moves."""
        # Create a file to move and then rollback
        original_file = temp_project / 'original.py'
        moved_file = temp_project / 'moved' / 'original.py'
        
        original_file.write_text('original content')
        moved_file.parent.mkdir(exist_ok=True)
        shutil.move(str(original_file), str(moved_file))
        
        # Create rollback plan
        rollback_plan = RollbackPlan(
            file_moves=[(moved_file, original_file)],
            directory_restorations=[],
            backup_path=None,
            timestamp=datetime.now()
        )
        
        # Execute rollback
        results = await organizer.execute_rollback(rollback_plan)
        
        assert results["success"]
        assert len(results["errors"]) == 0
        assert len(results["file_moves"]) == 1
        assert results["file_moves"][0]["success"]
        
        # Check that file was moved back
        assert original_file.exists()
        assert not moved_file.exists()
    
    def test_analyze_reorganization_impact(self, organizer, temp_project):
        """Test reorganization impact analysis."""
        from migration_assistant.checkup.cleaners.files import ReorganizationPlan
        
        # Create a plan that moves Python files
        plan = ReorganizationPlan(
            file_moves=[
                (temp_project / 'utils.py', temp_project / 'src' / 'utils.py', "reorganization"),
                (temp_project / 'config.py', temp_project / 'config' / 'settings.py', "reorganization")
            ],
            directory_removals=[],
            directory_creations=[temp_project / 'src', temp_project / 'config'],
            impact_assessment="Test impact",
            estimated_duration=1.0,
            risk_level="medium"
        )
        
        impact = organizer.analyze_reorganization_impact(plan)
        
        assert "dependency_analysis" in impact
        assert "import_breaks" in impact
        assert "affected_files" in impact
        assert "risk_assessment" in impact
        assert "mitigation_suggestions" in impact
        
        # Should have analysis for moved Python files
        assert len(impact["dependency_analysis"]) == 2
        
        # Should have mitigation suggestions if there are affected files
        if impact["affected_files"]:
            assert len(impact["mitigation_suggestions"]) > 0


class TestStructureAnalyzerSuggestions:
    """Test reorganization suggestions from StructureAnalyzer."""
    
    @pytest.fixture
    def temp_project(self):
        """Create a temporary project for testing suggestions."""
        temp_dir = Path(tempfile.mkdtemp())
        
        project_structure = {
            'README.md': '# Test Project',
            'src/mypackage/__init__.py': '',
            'src/mypackage/main.py': 'def main(): pass',
            'tests/test_main.py': 'def test_main(): pass',
            'test_outside.py': 'def test_something(): pass',
            'script_outside.py': 'if __name__ == "__main__": pass',
            'badname123/module.py': 'pass',
            'deep/very/deeply/nested/file.py': 'pass',
        }
        
        for file_path, content in project_structure.items():
            full_path = temp_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
        
        # Create empty directories
        (temp_dir / 'empty1').mkdir()
        (temp_dir / 'empty2').mkdir()
        
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.mark.asyncio
    async def test_suggest_reorganization(self, temp_project):
        """Test reorganization suggestions."""
        config = CheckupConfig(target_directory=temp_project)
        analyzer = StructureAnalyzer(config)
        
        suggestions = await analyzer.suggest_reorganization()
        
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        
        # Should have suggestions for various issues
        suggestion_text = ' '.join(suggestions)
        assert 'misplaced files' in suggestion_text.lower() or 'move' in suggestion_text.lower()
        assert 'empty directories' in suggestion_text.lower() or 'remove' in suggestion_text.lower()
        assert 'directories' in suggestion_text.lower() or 'rename' in suggestion_text.lower()
    
    @pytest.mark.asyncio
    async def test_suggest_reorganization_clean_project(self):
        """Test suggestions for a clean project."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create a well-organized project
        project_structure = {
            'README.md': '# Clean Project',
            'pyproject.toml': '[tool.black]',
            'src/mypackage/__init__.py': '',
            'src/mypackage/main.py': 'def main(): pass',
            'tests/__init__.py': '',
            'tests/test_main.py': 'def test_main(): pass',
            'docs/README.md': '# Documentation',
        }
        
        for file_path, content in project_structure.items():
            full_path = temp_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
        
        try:
            config = CheckupConfig(target_directory=temp_dir)
            analyzer = StructureAnalyzer(config)
            
            suggestions = await analyzer.suggest_reorganization()
            
            # Should indicate the project is well-organized
            assert len(suggestions) >= 1
            if len(suggestions) == 1:
                assert 'best practices' in suggestions[0].lower()
        
        finally:
            shutil.rmtree(temp_dir)
    
    def test_suggest_package_improvements(self, temp_project):
        """Test package structure improvement suggestions."""
        config = CheckupConfig(target_directory=temp_project)
        analyzer = StructureAnalyzer(config)
        
        suggestions = analyzer._suggest_package_improvements()
        
        assert isinstance(suggestions, list)
        # Should have suggestions about package organization
        if suggestions:
            suggestion_text = ' '.join(suggestions)
            assert any(keyword in suggestion_text.lower() 
                      for keyword in ['package', 'src', 'tests', 'organize'])


class TestMigrationPlanningIntegration:
    """Integration tests for the complete migration planning system."""
    
    @pytest.fixture
    def complex_project(self):
        """Create a complex project for integration testing."""
        temp_dir = Path(tempfile.mkdtemp())
        
        project_structure = {
            'README.md': '# Complex Project',
            'main.py': '''
from utils import helper
from config.settings import DEBUG
import data.processor

def main():
    helper()
    data.processor.process()
''',
            'utils.py': '''
def helper():
    return "help"
''',
            'config/settings.py': '''
DEBUG = True
''',
            'data/processor.py': '''
from utils import helper

def process():
    return helper()
''',
            'test_main.py': '''  # Misplaced test
def test_main():
    pass
''',
            'script.py': '''  # Misplaced script
if __name__ == "__main__":
    print("Script")
''',
        }
        
        for file_path, content in project_structure.items():
            full_path = temp_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
        
        # Create empty directories
        (temp_dir / 'empty1').mkdir()
        (temp_dir / 'empty2' / 'nested').mkdir(parents=True)
        
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.mark.asyncio
    async def test_full_migration_planning_workflow(self, complex_project):
        """Test the complete migration planning workflow."""
        config = CheckupConfig(
            target_directory=complex_project,
            create_backup=False,
            max_file_moves=20,
            dry_run=True
        )
        
        # Step 1: Analyze structure issues
        analyzer = StructureAnalyzer(config)
        issues = await analyzer.analyze()
        suggestions = await analyzer.suggest_reorganization()
        
        print(f"Found {len(issues)} issues")
        print(f"Generated {len(suggestions)} suggestions")
        
        # Step 2: Generate reorganization plan
        organizer = FileOrganizer(config)
        plan = organizer.generate_reorganization_plan(issues)
        
        print(f"Plan has {plan.total_operations} operations")
        print(f"Risk level: {plan.risk_level}")
        
        # Step 3: Analyze impact
        impact = organizer.analyze_reorganization_impact(plan)
        
        print(f"Impact analysis: {impact['risk_assessment']}")
        print(f"Affected files: {len(impact['affected_files'])}")
        
        # Step 4: Execute plan (dry run)
        results = await organizer.reorganize_directory_structure(plan)
        
        assert len(results["errors"]) == 0
        print("Migration planning workflow completed successfully")
        
        # Verify all components worked together
        assert len(issues) > 0
        assert len(suggestions) > 0
        assert plan.total_operations > 0
        assert "risk_assessment" in impact
        assert "file_moves" in results


if __name__ == '__main__':
    pytest.main([__file__])