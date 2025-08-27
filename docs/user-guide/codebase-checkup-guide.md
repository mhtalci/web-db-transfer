# Codebase Checkup and Cleanup Guide

## Overview

The codebase checkup and cleanup feature provides comprehensive analysis and automated maintenance capabilities for your Python projects. This powerful tool systematically examines code quality, identifies issues, removes redundancies, optimizes structure, and ensures consistency across your entire codebase.

## Features

- **Code Quality Analysis**: Syntax error detection, PEP 8 compliance checking, and code smell identification
- **Duplicate Code Detection**: Find and suggest refactoring for identical or similar code blocks
- **Import Analysis**: Identify unused imports, circular dependencies, and orphaned modules
- **Test Coverage Validation**: Analyze test coverage and identify gaps in testing
- **Code Formatting**: Automated formatting with black, isort, and docstring standardization
- **File Organization**: Optimize directory structure and file placement
- **Configuration Validation**: Validate project configuration files and documentation
- **Comprehensive Reporting**: Generate detailed reports in HTML, JSON, and Markdown formats

## Installation

The codebase checkup feature is included with the migration assistant. Ensure you have the required dependencies:

```bash
# Install with checkup dependencies
pip install migration-assistant[checkup]

# Or install development dependencies
pip install -e .[dev]
```

### Required Tools

The checkup feature integrates with several Python tools that should be installed:

```bash
pip install black isort flake8 mypy pytest pytest-cov
```

## Quick Start

### Basic Checkup

Run a basic analysis of your codebase:

```bash
# Analyze current directory
migration-assistant checkup analyze

# Analyze specific directory
migration-assistant checkup analyze --path /path/to/project

# Generate HTML report
migration-assistant checkup analyze --report-html
```

### Full Checkup with Cleanup

Perform analysis and apply automated fixes:

```bash
# Full checkup with automatic cleanup
migration-assistant checkup run --auto-fix

# Dry run to see what would be changed
migration-assistant checkup run --dry-run

# Create backup before cleanup
migration-assistant checkup run --backup --auto-fix
```

### Interactive Mode

Use interactive mode for guided checkups:

```bash
migration-assistant checkup interactive
```

## Command Reference

### Main Commands

#### `checkup analyze`
Perform code analysis without making changes.

```bash
migration-assistant checkup analyze [OPTIONS]
```

**Options:**
- `--path PATH`: Directory to analyze (default: current directory)
- `--config FILE`: Configuration file path
- `--report-html`: Generate HTML report
- `--report-json`: Generate JSON report
- `--report-markdown`: Generate Markdown report
- `--output-dir DIR`: Output directory for reports
- `--verbose`: Enable verbose output
- `--quiet`: Suppress non-essential output

#### `checkup run`
Perform analysis and optionally apply fixes.

```bash
migration-assistant checkup run [OPTIONS]
```

**Options:**
- `--auto-fix`: Apply automated fixes
- `--dry-run`: Show what would be changed without making changes
- `--backup`: Create backup before making changes
- `--format`: Apply code formatting (black, isort)
- `--imports`: Clean up imports
- `--organize`: Reorganize file structure
- `--max-moves N`: Maximum number of file moves (default: 10)

#### `checkup interactive`
Start interactive checkup mode.

```bash
migration-assistant checkup interactive [OPTIONS]
```

#### `checkup rollback`
Rollback previous checkup changes.

```bash
migration-assistant checkup rollback [BACKUP_ID]
```

### Analysis Commands

#### `checkup quality`
Analyze code quality issues.

```bash
migration-assistant checkup quality [OPTIONS]
```

#### `checkup duplicates`
Find duplicate code blocks.

```bash
migration-assistant checkup duplicates [OPTIONS]
```

**Options:**
- `--similarity FLOAT`: Similarity threshold (0.0-1.0, default: 0.8)
- `--min-lines N`: Minimum lines for duplicate detection (default: 5)

#### `checkup imports`
Analyze import dependencies.

```bash
migration-assistant checkup imports [OPTIONS]
```

#### `checkup coverage`
Analyze test coverage.

```bash
migration-assistant checkup coverage [OPTIONS]
```

#### `checkup structure`
Analyze file organization.

```bash
migration-assistant checkup structure [OPTIONS]
```

### Cleanup Commands

#### `checkup format`
Apply code formatting.

```bash
migration-assistant checkup format [OPTIONS]
```

#### `checkup clean-imports`
Clean up import statements.

```bash
migration-assistant checkup clean-imports [OPTIONS]
```

#### `checkup organize`
Reorganize file structure.

```bash
migration-assistant checkup organize [OPTIONS]
```

## Configuration

### Configuration File

Create a `checkup.toml` file in your project root:

```toml
[checkup]
# Analysis settings
enable_quality_analysis = true
enable_duplicate_detection = true
enable_import_analysis = true
enable_structure_analysis = true

# Cleanup settings
auto_format = false
auto_fix_imports = false
auto_organize_files = false

# Validation settings
check_test_coverage = true
validate_configs = true
validate_docs = true

# Reporting settings
generate_html_report = true
generate_json_report = true
generate_markdown_report = true

# Safety settings
create_backup = true
dry_run = false
max_file_moves = 10

[checkup.quality]
max_complexity = 10
max_line_length = 88
ignore_patterns = ["migrations/*", "venv/*", "__pycache__/*"]

[checkup.duplicates]
similarity_threshold = 0.8
min_duplicate_lines = 5
ignore_test_files = false

[checkup.imports]
remove_unused = true
organize_imports = true
check_circular = true

[checkup.coverage]
min_coverage = 80.0
exclude_patterns = ["tests/*", "conftest.py"]

[checkup.structure]
max_nesting_depth = 3
enforce_init_files = true
```

### Environment Variables

Configure checkup behavior with environment variables:

```bash
# Enable debug logging
export CHECKUP_DEBUG=1

# Set default configuration file
export CHECKUP_CONFIG=/path/to/checkup.toml

# Set default output directory
export CHECKUP_OUTPUT_DIR=/path/to/reports
```

## Understanding Reports

### HTML Reports

HTML reports provide an interactive view of your codebase analysis:

- **Summary Dashboard**: Overview of all issues and metrics
- **Quality Issues**: Detailed breakdown of code quality problems
- **Duplicate Code**: Visual representation of duplicate blocks
- **Import Analysis**: Dependency graph and import issues
- **Coverage Report**: Test coverage visualization
- **File Organization**: Directory structure analysis

### JSON Reports

JSON reports are ideal for programmatic access and CI/CD integration:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "summary": {
    "total_files": 150,
    "issues_found": 25,
    "duplicates_found": 8,
    "coverage_percentage": 85.2
  },
  "quality_issues": [...],
  "duplicates": [...],
  "import_issues": [...],
  "coverage_gaps": [...]
}
```

### Markdown Reports

Markdown reports integrate well with documentation and can be included in README files or wikis.

## Best Practices

### Regular Checkups

- Run checkups before major releases
- Include checkup in your CI/CD pipeline
- Schedule weekly automated checkups
- Review reports regularly with your team

### Gradual Cleanup

- Start with automated formatting
- Address high-priority issues first
- Clean up imports before restructuring
- Test thoroughly after each cleanup phase

### Team Integration

- Share checkup configuration across team
- Include checkup results in code reviews
- Set up automated notifications for issues
- Create team standards based on checkup findings

### Safety First

- Always create backups before cleanup
- Use dry-run mode to preview changes
- Test rollback procedures
- Monitor for regressions after cleanup

## Integration with Development Workflow

### Pre-commit Hooks

Add checkup to your pre-commit configuration:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: codebase-checkup
        name: Codebase Checkup
        entry: migration-assistant checkup analyze --quiet
        language: system
        pass_filenames: false
```

### CI/CD Integration

Include checkup in your GitHub Actions workflow:

```yaml
# .github/workflows/checkup.yml
name: Codebase Checkup
on: [push, pull_request]

jobs:
  checkup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install migration-assistant[checkup]
      - name: Run checkup
        run: |
          migration-assistant checkup analyze --report-json
      - name: Upload reports
        uses: actions/upload-artifact@v3
        with:
          name: checkup-reports
          path: reports/
```

### IDE Integration

Configure your IDE to run checkup on save or as a task:

**VS Code tasks.json:**
```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Codebase Checkup",
      "type": "shell",
      "command": "migration-assistant",
      "args": ["checkup", "analyze", "--quiet"],
      "group": "build",
      "presentation": {
        "echo": true,
        "reveal": "always",
        "focus": false,
        "panel": "shared"
      }
    }
  ]
}
```

## Additional Resources

### Documentation
- **[Installation Guide](checkup-installation.md)**: Detailed installation instructions and setup
- **[Usage Examples](checkup-usage-examples.md)**: Practical examples for various scenarios
- **[Best Practices](checkup-best-practices.md)**: Recommended workflows and team practices
- **[FAQ](checkup-faq.md)**: Frequently asked questions and solutions

### Advanced Topics
- **[Configuration Reference](../advanced/checkup-configuration.md)**: Complete configuration options
- **[Troubleshooting Guide](../advanced/checkup-troubleshooting.md)**: Common issues and solutions
- **[API Documentation](../api/checkup-api.md)**: Programmatic usage and integration

### Examples and Templates
- **[Basic Configuration](../examples/checkup/basic-checkup.toml)**: Simple setup for getting started
- **[CI/CD Configuration](../examples/checkup/ci-checkup.toml)**: Optimized for continuous integration
- **[Development Configuration](../examples/checkup/development-checkup.toml)**: Balanced for active development
- **[Strict Configuration](../examples/checkup/strict-checkup.toml)**: High quality standards
- **[Legacy Configuration](../examples/checkup/legacy-checkup.toml)**: Gradual improvement approach