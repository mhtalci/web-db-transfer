#!/usr/bin/env python3
"""
Development environment setup script for Migration Assistant.

This script helps set up the development environment with virtual environment
and installs all required dependencies.
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(command: str, cwd: str = None) -> bool:
    """Run a shell command and return success status."""
    try:
        result = subprocess.run(
            command.split(),
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"✓ {command}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {command}")
        print(f"Error: {e.stderr}")
        return False


def main():
    """Set up development environment."""
    print("Setting up Migration Assistant development environment...")
    
    # Check Python version
    if sys.version_info < (3, 11):
        print("Error: Python 3.11 or higher is required")
        sys.exit(1)
    
    print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Create virtual environment if it doesn't exist
    venv_path = Path("venv")
    if not venv_path.exists():
        print("Creating virtual environment...")
        if not run_command("python -m venv venv"):
            print("Failed to create virtual environment")
            sys.exit(1)
    else:
        print("✓ Virtual environment already exists")
    
    # Determine activation script path
    if os.name == 'nt':  # Windows
        activate_script = venv_path / "Scripts" / "activate"
        pip_path = venv_path / "Scripts" / "pip"
    else:  # Unix/Linux/macOS
        activate_script = venv_path / "bin" / "activate"
        pip_path = venv_path / "bin" / "pip"
    
    print(f"Virtual environment created at: {venv_path.absolute()}")
    print(f"To activate: source {activate_script}")
    
    # Install dependencies
    print("Installing dependencies...")
    if not run_command(f"{pip_path} install --upgrade pip"):
        print("Failed to upgrade pip")
        sys.exit(1)
    
    if not run_command(f"{pip_path} install -e .[dev,test]"):
        print("Failed to install dependencies")
        sys.exit(1)
    
    print("\n✓ Development environment setup complete!")
    print("\nNext steps:")
    print(f"1. Activate virtual environment: source {activate_script}")
    print("2. Run tests: pytest")
    print("3. Start CLI: migration-assistant --help")
    print("4. Start API: migration-assistant serve")
    print("\nDevelopment commands:")
    print("- Run tests: pytest")
    print("- Run tests with coverage: pytest --cov=migration_assistant")
    print("- Format code: black migration_assistant tests")
    print("- Sort imports: isort migration_assistant tests")
    print("- Type checking: mypy migration_assistant")


if __name__ == "__main__":
    main()