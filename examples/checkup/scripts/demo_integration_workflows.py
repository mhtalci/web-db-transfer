#!/usr/bin/env python3
"""
Integration Workflows Demonstration for Codebase Checkup

This script demonstrates various integration workflows including
IDE integration, git hooks, and automated workflows.
"""

import asyncio
import json
import os
import sys
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from migration_assistant.checkup import CodebaseOrchestrator, CheckupConfig


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""
    workflow_name: str
    success: bool
    duration_seconds: float
    files_processed: int
    changes_made: int
    error_message: Optional[str] = None


class GitHookIntegration:
    """Handles git hook integration for checkup."""
    
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.git_dir = project_path / ".git"
        self.hooks_dir = self.git_dir / "hooks"
    
    def install_pre_commit_hook(self) -> bool:
        """Install pre-commit hook for checkup."""
        if not self.git_dir.exists():
            print("Not a git repository")
            return False
        
        self.hooks_dir.mkdir(exist_ok=True)
        
        hook_script = '''#!/bin/bash
# Pre-commit hook for codebase checkup

echo "Running codebase checkup..."

# Get list of staged Python files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E "\.py$" || true)

if [ -z "$STAGED_FILES" ]; then
    echo "No Python files to check"
    exit 0
fi

# Run quick checkup on staged files
migration-assistant checkup analyze \\
    --files $STAGED_FILES \\
    --config examples/checkup/development-checkup.toml \\
    --quiet \\
    --no-report

CHECKUP_EXIT_CODE=$?

if [ $CHECKUP_EXIT_CODE -ne 0 ]; then
    echo "❌ Checkup failed. Please fix issues before committing."
    echo "Run 'migration-assistant checkup analyze' for detailed report."
    exit 1
fi

echo "✅ Checkup passed"
exit 0
'''
        
        hook_file = self.hooks_dir / "pre-commit"
        hook_file.write_text(hook_script)
        hook_file.chmod(0o755)
        
        print(f"Pre-commit hook installed at: {hook_file}")
        return True
    
    def install_pre_push_hook(self) -> bool:
        """Install pre-push hook for comprehensive checkup."""
        if not self.git_dir.exists():
            return False
        
        hook_script = '''#!/bin/bash
# Pre-push hook for comprehensive codebase checkup

echo "Running comprehensive checkup before push..."

# Run comprehensive checkup
migration-assistant checkup run \\
    --config examples/checkup/team-checkup.toml \\
    --backup \\
    --report-json

CHECKUP_EXIT_CODE=$?

if [ $CHECKUP_EXIT_CODE -ne 0 ]; then
    echo "❌ Comprehensive checkup failed."
    echo "Please review and fix issues before pushing."
    exit 1
fi

echo "✅ Comprehensive checkup passed"
exit 0
'''
        
        hook_file = self.hooks_dir / "pre-push"
        hook_file.write_text(hook_script)
        hook_file.chmod(0o755)
        
        print(f"Pre-push hook installed at: {hook_file}")
        return True
    
    def create_commit_msg_hook(self) -> bool:
        """Create commit message hook that includes checkup info."""
        if not self.git_dir.exists():
            return False
        
        hook_script = '''#!/bin/bash
# Commit message hook to add checkup info

COMMIT_MSG_FILE=$1

# Run quick analysis
ISSUES=$(migration-assistant checkup analyze --quiet --count-only 2>/dev/null || echo "0")

if [ "$ISSUES" != "0" ]; then
    echo "" >> "$COMMIT_MSG_FILE"
    echo "Checkup: $ISSUES issues found" >> "$COMMIT_MSG_FILE"
fi
'''
        
        hook_file = self.hooks_dir / "commit-msg"
        hook_file.write_text(hook_script)
        hook_file.chmod(0o755)
        
        print(f"Commit message hook installed at: {hook_file}")
        return True


class IDEIntegration:
    """Handles IDE integration workflows."""
    
    def __init__(self, project_path: Path):
        self.project_path = project_path
    
    def create_vscode_settings(self) -> bool:
        """Create VS Code settings for checkup integration."""
        vscode_dir = self.project_path / ".vscode"
        vscode_dir.mkdir(exist_ok=True)
        
        # Settings for checkup integration
        settings = {
            "python.linting.enabled": True,
            "python.linting.flake8Enabled": True,
            "python.linting.mypyEnabled": True,
            "python.formatting.provider": "black",
            "python.sortImports.args": ["--profile", "black"],
            "editor.formatOnSave": True,
            "editor.codeActionsOnSave": {
                "source.organizeImports": True
            },
            "files.associations": {
                "*.toml": "toml"
            },
            "checkup.autoRunOnSave": False,
            "checkup.configFile": "examples/checkup/development-checkup.toml"
        }
        
        settings_file = vscode_dir / "settings.json"
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=2)
        
        # Tasks for running checkup
        tasks = {
            "version": "2.0.0",
            "tasks": [
                {
                    "label": "Checkup: Quick Analysis",
                    "type": "shell",
                    "command": "migration-assistant",
                    "args": [
                        "checkup", "analyze",
                        "--config", "examples/checkup/development-checkup.toml",
                        "--report-html"
                    ],
                    "group": "test",
                    "presentation": {
                        "echo": True,
                        "reveal": "always",
                        "focus": False,
                        "panel": "shared"
                    },
                    "problemMatcher": []
                },
                {
                    "label": "Checkup: Format Code",
                    "type": "shell",
                    "command": "migration-assistant",
                    "args": [
                        "checkup", "format",
                        "--config", "examples/checkup/development-checkup.toml",
                        "--backup"
                    ],
                    "group": "build",
                    "presentation": {
                        "echo": True,
                        "reveal": "always",
                        "focus": False,
                        "panel": "shared"
                    }
                },
                {
                    "label": "Checkup: Full Analysis",
                    "type": "shell",
                    "command": "migration-assistant",
                    "args": [
                        "checkup", "run",
                        "--config", "examples/checkup/comprehensive-checkup.toml",
                        "--report-html",
                        "--backup"
                    ],
                    "group": "test",
                    "presentation": {
                        "echo": True,
                        "reveal": "always",
                        "focus": False,
                        "panel": "shared"
                    }
                }
            ]
        }
        
        tasks_file = vscode_dir / "tasks.json"
        with open(tasks_file, 'w') as f:
            json.dump(tasks, f, indent=2)
        
        print(f"VS Code settings created in: {vscode_dir}")
        return True
    
    def create_pycharm_settings(self) -> bool:
        """Create PyCharm external tools configuration."""
        idea_dir = self.project_path / ".idea"
        idea_dir.mkdir(exist_ok=True)
        
        # External tools configuration
        external_tools = '''<?xml version="1.0" encoding="UTF-8"?>
<project version="4">
  <component name="ToolsProvider">
    <tool name="Checkup Quick Analysis" description="Run quick codebase analysis" showInMainMenu="true" showInEditor="true" showInProject="true" showInSearchPopup="true" disabled="false" useConsole="true" showConsoleOnStdOut="false" showConsoleOnStdErr="false" synchronizeAfterRun="true">
      <exec>
        <option name="COMMAND" value="migration-assistant" />
        <option name="PARAMETERS" value="checkup analyze --config examples/checkup/development-checkup.toml --report-html" />
        <option name="WORKING_DIRECTORY" value="$ProjectFileDir$" />
      </exec>
    </tool>
    <tool name="Checkup Format Code" description="Format code with checkup" showInMainMenu="true" showInEditor="true" showInProject="true" showInSearchPopup="true" disabled="false" useConsole="true" showConsoleOnStdOut="false" showConsoleOnStdErr="false" synchronizeAfterRun="true">
      <exec>
        <option name="COMMAND" value="migration-assistant" />
        <option name="PARAMETERS" value="checkup format --config examples/checkup/development-checkup.toml --backup" />
        <option name="WORKING_DIRECTORY" value="$ProjectFileDir$" />
      </exec>
    </tool>
    <tool name="Checkup Full Analysis" description="Run comprehensive codebase analysis" showInMainMenu="true" showInEditor="false" showInProject="true" showInSearchPopup="true" disabled="false" useConsole="true" showConsoleOnStdOut="false" showConsoleOnStdErr="false" synchronizeAfterRun="true">
      <exec>
        <option name="COMMAND" value="migration-assistant" />
        <option name="PARAMETERS" value="checkup run --config examples/checkup/comprehensive-checkup.toml --report-html --backup" />
        <option name="WORKING_DIRECTORY" value="$ProjectFileDir$" />
      </exec>
    </tool>
  </component>
</project>'''
        
        tools_file = idea_dir / "externalTools.xml"
        tools_file.write_text(external_tools)
        
        print(f"PyCharm external tools created in: {idea_dir}")
        return True


class AutomatedWorkflows:
    """Handles automated workflow scenarios."""
    
    def __init__(self, project_path: Path):
        self.project_path = project_path
    
    async def nightly_quality_check(self) -> WorkflowResult:
        """Simulate nightly quality check workflow."""
        start_time = datetime.now()
        
        try:
            print("🌙 Running nightly quality check...")
            
            config = CheckupConfig(
                enable_quality_analysis=True,
                enable_import_analysis=True,
                enable_duplicate_detection=True,
                enable_coverage_analysis=True,
                generate_html_report=True,
                generate_json_report=True,
                output_directory="nightly-reports",
                timeout=1800  # 30 minutes
            )
            
            orchestrator = CodebaseOrchestrator(config, self.project_path)
            results = await orchestrator.run_analysis_only()
            
            # Generate reports
            await orchestrator.generate_reports(results)
            
            # Send notification (simulated)
            await self._send_quality_notification(results)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            return WorkflowResult(
                workflow_name="nightly_quality_check",
                success=True,
                duration_seconds=duration,
                files_processed=results.files_analyzed,
                changes_made=0  # Analysis only
            )
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            return WorkflowResult(
                workflow_name="nightly_quality_check",
                success=False,
                duration_seconds=duration,
                files_processed=0,
                changes_made=0,
                error_message=str(e)
            )
    
    async def weekly_cleanup(self) -> WorkflowResult:
        """Simulate weekly automated cleanup workflow."""
        start_time = datetime.now()
        
        try:
            print("🧹 Running weekly cleanup...")
            
            config = CheckupConfig(
                enable_quality_analysis=True,
                enable_import_analysis=True,
                auto_format=True,
                auto_fix_imports=True,
                create_backup=True,
                generate_html_report=True,
                output_directory="weekly-cleanup-reports"
            )
            
            orchestrator = CodebaseOrchestrator(config, self.project_path)
            results = await orchestrator.run_full_checkup()
            
            # Count changes made
            changes_made = 0
            if results.cleanup:
                changes_made = (
                    len(results.cleanup.formatting_changes) +
                    len(results.cleanup.import_cleanups) +
                    len(results.cleanup.file_moves)
                )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            return WorkflowResult(
                workflow_name="weekly_cleanup",
                success=True,
                duration_seconds=duration,
                files_processed=results.analysis.files_analyzed,
                changes_made=changes_made
            )
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            return WorkflowResult(
                workflow_name="weekly_cleanup",
                success=False,
                duration_seconds=duration,
                files_processed=0,
                changes_made=0,
                error_message=str(e)
            )
    
    async def release_preparation(self) -> WorkflowResult:
        """Simulate release preparation workflow."""
        start_time = datetime.now()
        
        try:
            print("🚀 Running release preparation...")
            
            config = CheckupConfig(
                enable_quality_analysis=True,
                enable_import_analysis=True,
                enable_duplicate_detection=True,
                enable_structure_analysis=True,
                enable_coverage_analysis=True,
                enable_config_validation=True,
                enable_doc_validation=True,
                auto_format=True,
                auto_fix_imports=True,
                create_backup=True,
                generate_html_report=True,
                generate_json_report=True,
                generate_markdown_report=True,
                output_directory="release-reports"
            )
            
            orchestrator = CodebaseOrchestrator(config, self.project_path)
            results = await orchestrator.run_full_checkup()
            
            # Validate release readiness
            release_ready = await self._validate_release_readiness(results)
            
            changes_made = 0
            if results.cleanup:
                changes_made = (
                    len(results.cleanup.formatting_changes) +
                    len(results.cleanup.import_cleanups)
                )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            return WorkflowResult(
                workflow_name="release_preparation",
                success=release_ready,
                duration_seconds=duration,
                files_processed=results.analysis.files_analyzed,
                changes_made=changes_made,
                error_message=None if release_ready else "Release criteria not met"
            )
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            return WorkflowResult(
                workflow_name="release_preparation",
                success=False,
                duration_seconds=duration,
                files_processed=0,
                changes_made=0,
                error_message=str(e)
            )
    
    async def _send_quality_notification(self, results):
        """Simulate sending quality notification."""
        print(f"📧 Sending quality notification:")
        print(f"  Files analyzed: {results.files_analyzed}")
        print(f"  Issues found: {results.total_issues}")
        print(f"  Quality score: {getattr(results.metrics, 'quality_score', 0):.1f}")
    
    async def _validate_release_readiness(self, results) -> bool:
        """Validate if the codebase is ready for release."""
        # Release criteria
        critical_issues = sum(
            1 for issue in results.analysis.quality_issues 
            if issue.severity == 'critical'
        )
        
        quality_score = getattr(results.analysis.metrics, 'quality_score', 0)
        coverage = getattr(results.analysis.metrics, 'coverage_percentage', 0)
        
        print(f"📋 Release readiness check:")
        print(f"  Critical issues: {critical_issues} (must be 0)")
        print(f"  Quality score: {quality_score:.1f} (must be ≥ 85)")
        print(f"  Coverage: {coverage:.1f}% (must be ≥ 90%)")
        
        return critical_issues == 0 and quality_score >= 85 and coverage >= 90


async def demo_git_hook_integration():
    """Demonstrate git hook integration."""
    print("🔗 Git Hook Integration Demonstration")
    print("=" * 50)
    
    # Create test repository
    repo_dir = Path("git_hook_demo")
    repo_dir.mkdir(exist_ok=True)
    
    try:
        # Initialize git repository
        subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Demo User"], cwd=repo_dir, check=True)
        subprocess.run(["git", "config", "user.email", "demo@example.com"], cwd=repo_dir, check=True)
        
        # Create sample Python file
        (repo_dir / "sample.py").write_text('''
def hello_world():
    print("Hello, World!")

if __name__ == "__main__":
    hello_world()
''')
        
        # Install git hooks
        git_integration = GitHookIntegration(repo_dir)
        
        print("Installing git hooks...")
        git_integration.install_pre_commit_hook()
        git_integration.install_pre_push_hook()
        git_integration.create_commit_msg_hook()
        
        # Test hooks (simulated)
        print("\n🧪 Testing git hooks:")
        print("  Pre-commit hook: ✅ Installed")
        print("  Pre-push hook: ✅ Installed")
        print("  Commit-msg hook: ✅ Installed")
        
        # Add and commit file to test hooks
        subprocess.run(["git", "add", "sample.py"], cwd=repo_dir, check=True)
        
        print("\n📝 Simulating git commit (hooks would run here)")
        print("  Pre-commit hook would analyze staged files")
        print("  Commit-msg hook would add checkup info to commit message")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Git command failed: {e}")
        return False
    finally:
        # Clean up
        import shutil
        if repo_dir.exists():
            shutil.rmtree(repo_dir)


async def demo_ide_integration():
    """Demonstrate IDE integration."""
    print("\n💻 IDE Integration Demonstration")
    print("=" * 50)
    
    # Create test project
    project_dir = Path("ide_integration_demo")
    project_dir.mkdir(exist_ok=True)
    
    try:
        # Create sample project structure
        (project_dir / "main.py").write_text('''
"""Main application module."""

def main():
    """Main function."""
    print("Hello from IDE integration demo!")

if __name__ == "__main__":
    main()
''')
        
        (project_dir / "utils.py").write_text('''
"""Utility functions."""

def helper_function(data):
    """Helper function."""
    return data.strip() if data else ""
''')
        
        # Set up IDE integrations
        ide_integration = IDEIntegration(project_dir)
        
        print("Setting up IDE integrations...")
        ide_integration.create_vscode_settings()
        ide_integration.create_pycharm_settings()
        
        print("\n📁 Created IDE configuration files:")
        vscode_dir = project_dir / ".vscode"
        if vscode_dir.exists():
            print(f"  VS Code: {vscode_dir}")
            for file in vscode_dir.iterdir():
                print(f"    - {file.name}")
        
        idea_dir = project_dir / ".idea"
        if idea_dir.exists():
            print(f"  PyCharm: {idea_dir}")
            for file in idea_dir.iterdir():
                print(f"    - {file.name}")
        
        print("\n🔧 IDE Integration Features:")
        print("  - Automatic formatting on save")
        print("  - Import organization")
        print("  - Linting integration")
        print("  - Custom tasks for checkup commands")
        print("  - External tools configuration")
        
        return True
        
    finally:
        # Clean up
        import shutil
        if project_dir.exists():
            shutil.rmtree(project_dir)


async def demo_automated_workflows():
    """Demonstrate automated workflows."""
    print("\n🤖 Automated Workflows Demonstration")
    print("=" * 50)
    
    # Create test project
    project_dir = Path("automated_workflows_demo")
    project_dir.mkdir(exist_ok=True)
    
    try:
        # Create sample project files
        files_content = {
            "app.py": '''
"""Main application."""

import json
from typing import Dict, Any

def process_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process input data."""
    if not data:
        return {}
    
    result = {}
    for key, value in data.items():
        if value is not None:
            result[key] = str(value).strip()
    
    return result

def main():
    """Main function."""
    sample_data = {"name": "test", "value": 123}
    result = process_data(sample_data)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
''',
            "utils.py": '''
"""Utility functions."""

def validate_input(data):
    """Validate input data."""
    return data is not None and len(str(data).strip()) > 0

def format_output(data):
    """Format output data."""
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if v}
    return data
''',
            "tests/test_app.py": '''
"""Tests for app module."""

import unittest
from app import process_data

class TestApp(unittest.TestCase):
    """Test cases for app module."""
    
    def test_process_data_empty(self):
        """Test processing empty data."""
        result = process_data({})
        self.assertEqual(result, {})
    
    def test_process_data_valid(self):
        """Test processing valid data."""
        data = {"name": "test", "value": 123}
        result = process_data(data)
        self.assertEqual(result, {"name": "test", "value": "123"})

if __name__ == "__main__":
    unittest.main()
'''
        }
        
        for file_path, content in files_content.items():
            full_path = project_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
        
        # Set up automated workflows
        workflows = AutomatedWorkflows(project_dir)
        
        # Run different workflow scenarios
        print("Running automated workflow scenarios...")
        
        # Nightly quality check
        nightly_result = await workflows.nightly_quality_check()
        print(f"\n🌙 Nightly Quality Check:")
        print(f"  Success: {'✅' if nightly_result.success else '❌'}")
        print(f"  Duration: {nightly_result.duration_seconds:.1f}s")
        print(f"  Files processed: {nightly_result.files_processed}")
        
        # Weekly cleanup
        weekly_result = await workflows.weekly_cleanup()
        print(f"\n🧹 Weekly Cleanup:")
        print(f"  Success: {'✅' if weekly_result.success else '❌'}")
        print(f"  Duration: {weekly_result.duration_seconds:.1f}s")
        print(f"  Files processed: {weekly_result.files_processed}")
        print(f"  Changes made: {weekly_result.changes_made}")
        
        # Release preparation
        release_result = await workflows.release_preparation()
        print(f"\n🚀 Release Preparation:")
        print(f"  Success: {'✅' if release_result.success else '❌'}")
        print(f"  Duration: {release_result.duration_seconds:.1f}s")
        print(f"  Files processed: {release_result.files_processed}")
        print(f"  Changes made: {release_result.changes_made}")
        if release_result.error_message:
            print(f"  Error: {release_result.error_message}")
        
        return [nightly_result, weekly_result, release_result]
        
    finally:
        # Clean up
        import shutil
        if project_dir.exists():
            shutil.rmtree(project_dir)


async def demo_watch_mode_simulation():
    """Demonstrate watch mode simulation."""
    print("\n👀 Watch Mode Simulation")
    print("=" * 50)
    
    # Create test project
    project_dir = Path("watch_mode_demo")
    project_dir.mkdir(exist_ok=True)
    
    try:
        # Create initial file
        test_file = project_dir / "watched_file.py"
        test_file.write_text('''
def initial_function():
    print("Initial version")
''')
        
        print("Simulating file watch mode...")
        print("(In real implementation, this would use file system events)")
        
        # Simulate file changes and checkup runs
        changes = [
            '''
def initial_function():
    print("Initial version")

def new_function():
    print("Added new function")
''',
            '''
def initial_function():
    """Added docstring."""
    print("Initial version")

def new_function():
    """Added docstring."""
    print("Added new function")

def another_function(param1,param2):  # Style issue
    return param1+param2
''',
            '''
def initial_function():
    """Added docstring."""
    print("Initial version")

def new_function():
    """Added docstring."""
    print("Added new function")

def another_function(param1: int, param2: int) -> int:  # Fixed style
    """Add two parameters."""
    return param1 + param2
'''
        ]
        
        config = CheckupConfig(
            enable_quality_analysis=True,
            enable_import_analysis=True,
            generate_json_report=True,
            output_directory="watch-reports"
        )
        
        for i, change in enumerate(changes, 1):
            print(f"\n📝 File change {i}:")
            test_file.write_text(change)
            
            # Run checkup on file change
            orchestrator = CodebaseOrchestrator(config, project_dir)
            results = await orchestrator.run_analysis_only()
            
            print(f"  Issues found: {results.total_issues}")
            if results.total_issues > 0:
                print(f"  Sample issue: {results.all_issues[0].message}")
            else:
                print(f"  No issues found!")
        
        print(f"\n✅ Watch mode simulation completed")
        
    finally:
        # Clean up
        import shutil
        if project_dir.exists():
            shutil.rmtree(project_dir)


def create_integration_examples():
    """Create integration example files."""
    print("\n📜 Creating Integration Examples")
    print("=" * 50)
    
    # Create Makefile with checkup targets
    makefile_content = '''# Makefile with checkup integration

.PHONY: checkup checkup-quick checkup-format checkup-ci

# Quick checkup for development
checkup-quick:
	migration-assistant checkup analyze \\
		--config examples/checkup/development-checkup.toml \\
		--report-html

# Full checkup with formatting
checkup:
	migration-assistant checkup run \\
		--config examples/checkup/team-checkup.toml \\
		--backup \\
		--report-html

# Format code only
checkup-format:
	migration-assistant checkup format \\
		--config examples/checkup/development-checkup.toml \\
		--backup

# CI checkup
checkup-ci:
	migration-assistant checkup analyze \\
		--config examples/checkup/ci-checkup.toml \\
		--report-json \\
		--report-xml

# Install git hooks
install-hooks:
	cp examples/checkup/hooks/pre-commit .git/hooks/
	cp examples/checkup/hooks/pre-push .git/hooks/
	chmod +x .git/hooks/pre-commit .git/hooks/pre-push

# Clean checkup reports
clean-reports:
	rm -rf *-reports/ checkup-reports/
'''
    
    with open("example-Makefile", "w") as f:
        f.write(makefile_content)
    
    # Create package.json scripts for Node.js projects
    package_json = {
        "name": "checkup-integration-example",
        "version": "1.0.0",
        "scripts": {
            "checkup": "migration-assistant checkup run --config examples/checkup/team-checkup.toml --backup",
            "checkup:quick": "migration-assistant checkup analyze --config examples/checkup/development-checkup.toml",
            "checkup:format": "migration-assistant checkup format --config examples/checkup/development-checkup.toml --backup",
            "checkup:ci": "migration-assistant checkup analyze --config examples/checkup/ci-checkup.toml --report-json",
            "precommit": "npm run checkup:quick",
            "prepush": "npm run checkup"
        }
    }
    
    with open("example-package.json", "w") as f:
        json.dump(package_json, f, indent=2)
    
    # Create tox configuration
    tox_ini = '''[tox]
envlist = py39, checkup

[testenv]
deps = pytest
commands = pytest tests/

[testenv:checkup]
deps = migration-assistant[checkup]
commands = 
    migration-assistant checkup analyze --config examples/checkup/ci-checkup.toml --report-xml
    migration-assistant checkup format --config examples/checkup/development-checkup.toml --dry-run

[testenv:checkup-full]
deps = migration-assistant[checkup]
commands = 
    migration-assistant checkup run --config examples/checkup/comprehensive-checkup.toml --backup --report-html
'''
    
    with open("example-tox.ini", "w") as f:
        f.write(tox_ini)
    
    print("Created integration examples:")
    print("  - example-Makefile")
    print("  - example-package.json")
    print("  - example-tox.ini")


async def main():
    """Run integration workflows demonstrations."""
    print("🚀 Integration Workflows Demonstration")
    print("=" * 60)
    
    try:
        # Run demonstrations
        git_success = await demo_git_hook_integration()
        ide_success = await demo_ide_integration()
        workflow_results = await demo_automated_workflows()
        await demo_watch_mode_simulation()
        
        # Create integration examples
        create_integration_examples()
        
        print(f"\n✅ Integration workflows demo completed!")
        print("\nKey features demonstrated:")
        print("  - Git hook integration (pre-commit, pre-push)")
        print("  - IDE integration (VS Code, PyCharm)")
        print("  - Automated workflows (nightly, weekly, release)")
        print("  - Watch mode simulation")
        print("  - Build tool integration (Make, npm, tox)")
        
        print(f"\nIntegration results:")
        print(f"  Git hooks: {'✅ Success' if git_success else '❌ Failed'}")
        print(f"  IDE setup: {'✅ Success' if ide_success else '❌ Failed'}")
        
        successful_workflows = sum(1 for result in workflow_results if result.success)
        print(f"  Automated workflows: {successful_workflows}/{len(workflow_results)} successful")
        
        print(f"\nGenerated files:")
        print("  - example-Makefile")
        print("  - example-package.json")
        print("  - example-tox.ini")
        
    except Exception as e:
        print(f"❌ Integration workflows demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Demo interrupted by user")
        sys.exit(1)