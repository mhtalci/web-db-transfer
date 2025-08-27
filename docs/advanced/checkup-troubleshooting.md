# Codebase Checkup Troubleshooting Guide

## Overview

This guide helps you diagnose and resolve common issues when using the codebase checkup and cleanup system. Issues are organized by category with symptoms, causes, and solutions.

## General Issues

### Checkup Won't Start

**Symptoms:**
- Command not found error
- Import errors when running checkup
- Permission denied errors

**Causes and Solutions:**

#### Command Not Found
```bash
# Error: migration-assistant: command not found
```

**Solution:**
```bash
# Ensure migration-assistant is installed
pip install migration-assistant[checkup]

# Or install in development mode
pip install -e .[dev]

# Verify installation
migration-assistant --version
```

#### Import Errors
```bash
# Error: ModuleNotFoundError: No module named 'migration_assistant.checkup'
```

**Solution:**
```bash
# Install with checkup dependencies
pip install migration-assistant[checkup]

# Or install missing dependencies manually
pip install black isort flake8 mypy pytest pytest-cov
```

#### Permission Errors
```bash
# Error: PermissionError: [Errno 13] Permission denied
```

**Solution:**
```bash
# Check file permissions
ls -la

# Fix permissions if needed
chmod +r *.py
chmod +w .  # For creating reports/backups

# Run with appropriate user permissions
sudo migration-assistant checkup analyze  # If necessary
```

### Configuration Issues

#### Invalid Configuration File

**Symptoms:**
```bash
# Error: Invalid configuration file: checkup.toml
# Error: TOML parsing error at line 15
```

**Solution:**
```bash
# Validate configuration syntax
migration-assistant checkup validate-config

# Check TOML syntax online or with a TOML validator
python -c "import toml; toml.load('checkup.toml')"

# Use minimal configuration to test
echo '[checkup]\nenable_quality_analysis = true' > checkup.toml
```

#### Configuration Not Found

**Symptoms:**
```bash
# Warning: Configuration file not found, using defaults
```

**Solution:**
```bash
# Create default configuration
migration-assistant checkup init-config

# Specify configuration file explicitly
migration-assistant checkup analyze --config /path/to/checkup.toml

# Set environment variable
export CHECKUP_CONFIG=/path/to/checkup.toml
```

## Analysis Issues

### Code Quality Analysis Problems

#### Flake8 Not Found

**Symptoms:**
```bash
# Error: flake8 not found in PATH
# Error: Quality analysis failed: flake8 command not available
```

**Solution:**
```bash
# Install flake8
pip install flake8

# Verify installation
flake8 --version

# Disable flake8 if not needed
# In checkup.toml:
[checkup.quality]
use_flake8 = false
```

#### MyPy Type Checking Errors

**Symptoms:**
```bash
# Error: mypy analysis failed
# Error: Cannot find implementation or library stub
```

**Solution:**
```bash
# Install mypy and type stubs
pip install mypy types-requests types-PyYAML

# Configure mypy in pyproject.toml
[tool.mypy]
ignore_missing_imports = true
strict_optional = false

# Disable mypy if causing issues
[checkup.quality]
use_mypy = false
```

#### Large File Analysis Timeout

**Symptoms:**
```bash
# Error: Analysis timeout after 300 seconds
# Warning: Skipping large file: huge_file.py (2MB)
```

**Solution:**
```bash
# Increase timeout
migration-assistant checkup analyze --timeout 600

# Or in configuration:
[checkup]
timeout = 600
max_file_size = 2097152  # 2MB

# Exclude large files
[checkup]
exclude_patterns = ["large_files/*", "*.log"]
```

### Duplicate Detection Issues

#### High Memory Usage

**Symptoms:**
```bash
# Error: MemoryError during duplicate detection
# System becomes unresponsive during analysis
```

**Solution:**
```bash
# Reduce similarity threshold
[checkup.duplicates]
similarity_threshold = 0.9  # More strict

# Increase minimum duplicate size
min_duplicate_lines = 10

# Process files in smaller batches
[checkup]
max_workers = 2  # Reduce parallel processing

# Exclude large directories
exclude_patterns = ["vendor/*", "node_modules/*"]
```

#### False Positives

**Symptoms:**
- Common code patterns flagged as duplicates
- Test fixtures reported as duplicates
- Generated code flagged as duplicates

**Solution:**
```toml
[checkup.duplicates]
# Increase similarity threshold
similarity_threshold = 0.95

# Ignore test files
ignore_test_files = true

# Exclude generated files
exclude_patterns = [
    "migrations/*",
    "tests/fixtures/*",
    "*_pb2.py",  # Protocol buffer files
    "generated/*"
]

# Ignore common patterns
ignore_comments = true
ignore_whitespace = true
```

### Import Analysis Issues

#### Circular Import False Positives

**Symptoms:**
```bash
# Warning: Circular import detected: module_a -> module_b -> module_a
# But the imports are actually conditional or in functions
```

**Solution:**
```toml
[checkup.imports]
# More sophisticated circular import detection
analyze_dependencies = true

# Exclude certain patterns
exclude_patterns = [
    "*/migrations/*",
    "tests/*"
]
```

**Manual verification:**
```bash
# Check actual imports
python -c "import module_a; import module_b"

# Use import graph visualization
pip install pydeps
pydeps your_package --show
```

#### Unused Import False Positives

**Symptoms:**
- Imports used in type hints flagged as unused
- Imports used in string annotations flagged as unused
- Dynamic imports flagged as unused

**Solution:**
```python
# Use explicit type checking imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from some_module import SomeClass

# Add noqa comments for dynamic imports
import importlib  # noqa: F401 - used dynamically

# Configure in checkup.toml
[checkup.imports]
check_type_hint_imports = true
ignore_dynamic_imports = true
```

## Cleanup Issues

### Code Formatting Problems

#### Black Formatting Conflicts

**Symptoms:**
```bash
# Error: Black formatting failed
# Error: Cannot format file.py: invalid syntax
```

**Solution:**
```bash
# Check syntax first
python -m py_compile file.py

# Run black manually to see detailed error
black --check --diff file.py

# Fix syntax errors before formatting
migration-assistant checkup analyze --no-format

# Configure black settings
[checkup.formatting]
black_line_length = 88
black_skip_string_normalization = false
```

#### isort Import Conflicts

**Symptoms:**
```bash
# Error: isort formatting conflicts with black
# Imports keep changing between runs
```

**Solution:**
```toml
[checkup.formatting]
isort_profile = "black"  # Use black-compatible profile
isort_line_length = 88

[tool.isort]
profile = "black"
line_length = 88
```

### File Organization Issues

#### File Move Failures

**Symptoms:**
```bash
# Error: Cannot move file: Permission denied
# Error: File move would break imports
```

**Solution:**
```bash
# Check permissions
ls -la file.py
chmod +w file.py

# Use dry run to preview moves
migration-assistant checkup organize --dry-run

# Limit number of moves
[checkup.safety]
max_file_moves = 5
require_confirmation = true

# Fix imports after moves
migration-assistant checkup clean-imports
```

#### Import Breakage After Reorganization

**Symptoms:**
```bash
# Error: ModuleNotFoundError after file reorganization
# Import statements no longer work
```

**Solution:**
```bash
# Rollback changes
migration-assistant checkup rollback

# Use smaller reorganization steps
[checkup.structure]
suggest_reorganization = true
max_files_per_directory = 10

# Update imports automatically
[checkup.imports]
normalize_import_paths = true
```

## Performance Issues

### Slow Analysis

**Symptoms:**
- Analysis takes very long time
- High CPU usage during analysis
- System becomes unresponsive

**Solutions:**

#### Reduce Scope
```toml
[checkup]
# Exclude large directories
exclude_patterns = [
    "venv/*",
    "node_modules/*",
    "*.log",
    "data/*"
]

# Limit file size
max_file_size = 1048576  # 1MB
```

#### Optimize Settings
```toml
[checkup]
# Reduce parallel processing
max_workers = 2

# Disable expensive analysis
enable_duplicate_detection = false  # Most expensive
enable_structure_analysis = false

[checkup.duplicates]
# Make duplicate detection faster
similarity_threshold = 0.95  # More strict
min_duplicate_lines = 10     # Larger minimum
```

#### Progressive Analysis
```bash
# Analyze specific components
migration-assistant checkup quality --path src/
migration-assistant checkup imports --path src/core/
migration-assistant checkup duplicates --path src/utils/
```

### Memory Issues

**Symptoms:**
```bash
# Error: MemoryError
# System runs out of memory during analysis
```

**Solutions:**

```toml
[checkup]
# Process files in smaller batches
max_workers = 1
parallel_analysis = false

# Exclude large files
max_file_size = 524288  # 512KB

[checkup.duplicates]
# Reduce memory usage for duplicate detection
min_duplicate_lines = 15
similarity_threshold = 0.9
```

## Backup and Recovery Issues

### Backup Creation Failures

**Symptoms:**
```bash
# Error: Cannot create backup directory
# Error: Insufficient disk space for backup
```

**Solution:**
```bash
# Check disk space
df -h

# Check permissions
ls -la .checkup-backups/
mkdir -p .checkup-backups
chmod +w .checkup-backups

# Configure backup location
[checkup.safety]
backup_directory = "/tmp/checkup-backups"
compress_backups = true  # Save space
```

### Rollback Failures

**Symptoms:**
```bash
# Error: Cannot rollback: backup not found
# Error: Rollback failed: file conflicts
```

**Solution:**
```bash
# List available backups
migration-assistant checkup list-backups

# Force rollback with specific backup
migration-assistant checkup rollback --backup-id 20240115-103000 --force

# Manual rollback
cp -r .checkup-backups/20240115-103000/* .
```

## Integration Issues

### CI/CD Integration Problems

#### GitHub Actions Failures

**Symptoms:**
```yaml
# Error in GitHub Actions:
# migration-assistant: command not found
```

**Solution:**
```yaml
# .github/workflows/checkup.yml
- name: Install dependencies
  run: |
    pip install migration-assistant[checkup]
    
- name: Run checkup
  run: |
    migration-assistant checkup analyze --quiet --report-json
```

#### Pre-commit Hook Issues

**Symptoms:**
```bash
# Pre-commit hook fails
# Checkup runs on every file change
```

**Solution:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: codebase-checkup
        name: Codebase Checkup
        entry: migration-assistant checkup analyze --quiet --no-report
        language: system
        pass_filenames: false
        stages: [commit]  # Only run on commit
```

### IDE Integration Issues

#### VS Code Task Failures

**Symptoms:**
- Task doesn't run
- No output in terminal
- Command not found in VS Code

**Solution:**
```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Codebase Checkup",
      "type": "shell",
      "command": "${workspaceFolder}/venv/bin/migration-assistant",
      "args": ["checkup", "analyze", "--verbose"],
      "group": "build",
      "presentation": {
        "echo": true,
        "reveal": "always",
        "focus": false,
        "panel": "shared"
      },
      "options": {
        "cwd": "${workspaceFolder}"
      }
    }
  ]
}
```

## Debugging Tips

### Enable Debug Logging

```bash
# Enable verbose output
migration-assistant checkup analyze --verbose

# Enable debug logging
export CHECKUP_DEBUG=1
migration-assistant checkup analyze

# Save debug output
migration-assistant checkup analyze --verbose > checkup-debug.log 2>&1
```

### Isolate Issues

```bash
# Test with minimal configuration
echo '[checkup]\nenable_quality_analysis = true' > test-checkup.toml
migration-assistant checkup analyze --config test-checkup.toml

# Test single file
migration-assistant checkup analyze --path single_file.py

# Test specific analyzer
migration-assistant checkup quality --path src/
```

### Check Dependencies

```bash
# Verify all tools are available
black --version
isort --version
flake8 --version
mypy --version
pytest --version

# Check Python version compatibility
python --version
```

## Getting Help

### Log Analysis

When reporting issues, include:

1. **Command used:**
   ```bash
   migration-assistant checkup analyze --verbose
   ```

2. **Configuration file:**
   ```toml
   # Contents of checkup.toml
   ```

3. **Error output:**
   ```bash
   # Full error message and stack trace
   ```

4. **Environment info:**
   ```bash
   python --version
   pip list | grep -E "(migration-assistant|black|isort|flake8|mypy)"
   ```

### Common Solutions Summary

| Issue | Quick Fix |
|-------|-----------|
| Command not found | `pip install migration-assistant[checkup]` |
| Import errors | `pip install black isort flake8 mypy pytest pytest-cov` |
| Config errors | `migration-assistant checkup validate-config` |
| Memory issues | Reduce `max_workers`, increase `min_duplicate_lines` |
| Slow analysis | Add `exclude_patterns`, disable expensive analyzers |
| Permission errors | Check file permissions, run with appropriate user |
| Backup failures | Check disk space, verify backup directory permissions |

### Support Resources

- **Documentation**: Check the [User Guide](../user-guide/codebase-checkup-guide.md)
- **Configuration**: See [Configuration Reference](checkup-configuration.md)
- **API**: Review [API Documentation](../api/checkup-api.md)
- **Issues**: Report bugs on the project's issue tracker
- **Community**: Join discussions in the project's community channels