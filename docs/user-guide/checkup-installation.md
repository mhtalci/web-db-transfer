# Codebase Checkup Installation Guide

## Overview

This guide provides detailed installation instructions for the codebase checkup and cleanup feature of the Migration Assistant. The checkup system requires specific dependencies and tools to function properly.

## System Requirements

### Operating System Support
- **Linux**: Ubuntu 18.04+, CentOS 7+, Debian 9+, RHEL 7+
- **macOS**: 10.14 (Mojave) or later
- **Windows**: Windows 10 with WSL2 (recommended) or native Windows

### Python Requirements
- **Python Version**: 3.8 or higher (3.9+ recommended)
- **pip**: Latest version (upgrade with `pip install --upgrade pip`)
- **Virtual Environment**: Recommended for isolation

### System Dependencies
- **Git**: For version control integration
- **Node.js**: 14+ (for some report features)
- **Disk Space**: Minimum 500MB free space for reports and backups

## Installation Methods

### Method 1: Standard Installation (Recommended)

#### Step 1: Install Migration Assistant with Checkup Support

```bash
# Install from PyPI with checkup dependencies
pip install migration-assistant[checkup]

# Verify installation
migration-assistant --version
migration-assistant checkup --help
```

#### Step 2: Install Required Tools

```bash
# Install code formatting and analysis tools
pip install black isort flake8 mypy pytest pytest-cov

# Verify tool installations
black --version
isort --version
flake8 --version
mypy --version
pytest --version
```

#### Step 3: Verify Installation

```bash
# Run basic checkup test
migration-assistant checkup analyze --help

# Test with a simple Python file
echo "print('hello')" > test.py
migration-assistant checkup analyze --path test.py
rm test.py
```

### Method 2: Development Installation

For contributors or advanced users who want the latest features:

```bash
# Clone the repository
git clone https://github.com/mhtalci/web-db-transfer.git
cd web-db-transfer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .[dev]

# Install additional development tools
pip install pre-commit tox

# Set up pre-commit hooks (optional)
pre-commit install
```

### Method 3: Docker Installation

For containerized environments:

```bash
# Pull the official image
docker pull migration-assistant:latest

# Run checkup in container
docker run --rm -v $(pwd):/workspace migration-assistant:latest \
  checkup analyze --path /workspace

# Or build from source
git clone https://github.com/mhtalci/web-db-transfer.git
cd web-db-transfer
docker build -t migration-assistant-local .
```

## Tool Dependencies

### Core Analysis Tools

#### Black (Code Formatter)
```bash
# Install black
pip install black

# Configure black (optional)
cat > pyproject.toml << EOF
[tool.black]
line-length = 88
target-version = ['py38']
include = '\.pyi?$'
EOF
```

#### isort (Import Sorter)
```bash
# Install isort
pip install isort

# Configure isort for black compatibility
cat >> pyproject.toml << EOF
[tool.isort]
profile = "black"
line_length = 88
EOF
```

#### Flake8 (Style Checker)
```bash
# Install flake8
pip install flake8

# Configure flake8
cat > .flake8 << EOF
[flake8]
max-line-length = 88
extend-ignore = E203, W503
exclude = venv,__pycache__,.git
EOF
```

#### MyPy (Type Checker)
```bash
# Install mypy
pip install mypy

# Configure mypy
cat >> pyproject.toml << EOF
[tool.mypy]
python_version = "3.8"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
EOF
```

#### Pytest (Testing Framework)
```bash
# Install pytest with coverage
pip install pytest pytest-cov

# Configure pytest
cat > pytest.ini << EOF
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = --strict-markers --disable-warnings
EOF
```

### Optional Tools

#### Bandit (Security Scanner)
```bash
# Install bandit for security analysis
pip install bandit

# Configure bandit
cat > .bandit << EOF
[bandit]
exclude_dirs = tests,venv
skips = B101,B601
EOF
```

#### Pylint (Additional Linting)
```bash
# Install pylint (optional, can be noisy)
pip install pylint

# Generate pylint config
pylint --generate-rcfile > .pylintrc
```

## Configuration Setup

### Basic Configuration

Create a basic checkup configuration file:

```bash
# Create basic configuration
cat > checkup.toml << EOF
[checkup]
enable_quality_analysis = true
enable_import_analysis = true
auto_format = true
create_backup = true

[checkup.quality]
max_complexity = 10
max_line_length = 88
use_flake8 = true
use_mypy = true

[checkup.formatting]
use_black = true
use_isort = true
isort_profile = "black"

[checkup.reporting]
generate_html_report = true
output_directory = "checkup-reports"
EOF
```

### Environment Variables

Set up environment variables for consistent behavior:

```bash
# Add to your shell profile (.bashrc, .zshrc, etc.)
export CHECKUP_CONFIG="checkup.toml"
export CHECKUP_OUTPUT_DIR="checkup-reports"
export CHECKUP_DEBUG=0

# For development
export CHECKUP_VERBOSE=1
```

## Verification and Testing

### Basic Functionality Test

```bash
# Create a test Python file with issues
cat > test_checkup.py << 'EOF'
import os
import sys
import unused_module

def complex_function(a,b,c,d,e):
    if a:
        if b:
            if c:
                if d:
                    if e:
                        return "deeply nested"
    return None

class   BadlyFormatted:
    def method_without_docstring(self):
        pass

print("hello world")
EOF

# Run checkup analysis
migration-assistant checkup analyze --path test_checkup.py --verbose

# Clean up
rm test_checkup.py
```

### Integration Test

```bash
# Test with a real project structure
mkdir -p test_project/src test_project/tests
cat > test_project/src/main.py << 'EOF'
"""Main module."""
import sys
from typing import List

def process_data(items: List[str]) -> None:
    """Process a list of items."""
    for item in items:
        print(f"Processing: {item}")

if __name__ == "__main__":
    process_data(sys.argv[1:])
EOF

cat > test_project/tests/test_main.py << 'EOF'
"""Tests for main module."""
import pytest
from src.main import process_data

def test_process_data():
    """Test process_data function."""
    # This would normally capture output
    process_data(["test"])
EOF

# Run full checkup
cd test_project
migration-assistant checkup run --dry-run --verbose
cd ..
rm -rf test_project
```

## Troubleshooting Installation

### Common Issues

#### Python Version Issues
```bash
# Check Python version
python --version

# If using older Python, install newer version
# Ubuntu/Debian:
sudo apt update
sudo apt install python3.9 python3.9-pip python3.9-venv

# macOS with Homebrew:
brew install python@3.9

# Create virtual environment with specific Python
python3.9 -m venv venv
```

#### Permission Issues
```bash
# If getting permission errors
pip install --user migration-assistant[checkup]

# Or use virtual environment
python -m venv checkup-env
source checkup-env/bin/activate
pip install migration-assistant[checkup]
```

#### Tool Not Found Errors
```bash
# If tools are not found in PATH
which black isort flake8 mypy

# Add to PATH if needed (add to shell profile)
export PATH="$HOME/.local/bin:$PATH"

# Or install in virtual environment
pip install --upgrade black isort flake8 mypy
```

#### Import Errors
```bash
# If getting import errors
pip install --upgrade migration-assistant[checkup]

# Check installed packages
pip list | grep -E "(migration|black|isort|flake8|mypy)"

# Reinstall if necessary
pip uninstall migration-assistant
pip install migration-assistant[checkup]
```

### Platform-Specific Issues

#### Windows Issues
```bash
# Use WSL2 for best compatibility
wsl --install

# Or install Windows-specific tools
pip install colorama  # For colored output
```

#### macOS Issues
```bash
# Install Xcode command line tools
xcode-select --install

# Use Homebrew for system dependencies
brew install python@3.9
```

#### Linux Issues
```bash
# Install system dependencies
# Ubuntu/Debian:
sudo apt install python3-dev python3-pip python3-venv

# CentOS/RHEL:
sudo yum install python3-devel python3-pip
```

## Performance Optimization

### Large Codebases

For large codebases, optimize installation and configuration:

```bash
# Install with performance optimizations
pip install migration-assistant[checkup,performance]

# Configure for large codebases
cat > checkup-large.toml << EOF
[checkup]
parallel_analysis = true
max_workers = 4
timeout = 600
max_file_size = 1048576  # 1MB

exclude_patterns = [
    "venv/*",
    "node_modules/*",
    "*.log",
    "build/*",
    "dist/*"
]

[checkup.duplicates]
enable_duplicate_detection = false  # Disable for initial runs

[checkup.reporting]
generate_html_report = false  # Faster without HTML
generate_json_report = true
EOF
```

### Memory Optimization

```bash
# For memory-constrained environments
export CHECKUP_MAX_WORKERS=1
export CHECKUP_PARALLEL_ANALYSIS=false

# Use minimal configuration
cat > checkup-minimal.toml << EOF
[checkup]
enable_quality_analysis = true
enable_duplicate_detection = false
enable_structure_analysis = false
max_workers = 1
parallel_analysis = false
EOF
```

## Next Steps

After successful installation:

1. **Read the User Guide**: [Codebase Checkup Guide](codebase-checkup-guide.md)
2. **Configure Your Project**: [Configuration Reference](../advanced/checkup-configuration.md)
3. **Run Your First Checkup**: Follow the Quick Start section
4. **Integrate with CI/CD**: See integration examples
5. **Explore Advanced Features**: Check the API documentation

## Getting Help

If you encounter issues during installation:

1. **Check the Troubleshooting Guide**: [Troubleshooting](../advanced/checkup-troubleshooting.md)
2. **Verify System Requirements**: Ensure all prerequisites are met
3. **Check Tool Versions**: Ensure compatible versions are installed
4. **Review Error Messages**: Look for specific error details
5. **Seek Community Support**: Join project discussions or file issues

## Maintenance

### Keeping Tools Updated

```bash
# Update migration assistant
pip install --upgrade migration-assistant[checkup]

# Update analysis tools
pip install --upgrade black isort flake8 mypy pytest pytest-cov

# Check for outdated packages
pip list --outdated
```

### Configuration Updates

```bash
# Validate configuration after updates
migration-assistant checkup validate-config

# Update configuration for new features
migration-assistant checkup init-config --update
```

This installation guide ensures users can successfully set up the codebase checkup system with all necessary dependencies and configurations.