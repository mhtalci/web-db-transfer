# Codebase Checkup Configuration Reference

## Overview

This document provides a comprehensive reference for all configuration options available in the codebase checkup and cleanup system. Configuration can be specified through configuration files, command-line arguments, or environment variables.

## Configuration File Format

The checkup system uses TOML format for configuration files. The default configuration file name is `checkup.toml` and should be placed in your project root.

### Basic Structure

```toml
[checkup]
# Global checkup settings

[checkup.quality]
# Code quality analysis settings

[checkup.duplicates]
# Duplicate code detection settings

[checkup.imports]
# Import analysis settings

[checkup.coverage]
# Test coverage settings

[checkup.structure]
# File structure analysis settings

[checkup.formatting]
# Code formatting settings

[checkup.reporting]
# Report generation settings

[checkup.safety]
# Safety and backup settings
```

## Global Settings

### `[checkup]` Section

#### Analysis Control

```toml
[checkup]
# Enable/disable analysis modules
enable_quality_analysis = true      # Enable code quality analysis
enable_duplicate_detection = true   # Enable duplicate code detection
enable_import_analysis = true       # Enable import dependency analysis
enable_structure_analysis = true    # Enable file structure analysis
enable_coverage_analysis = true     # Enable test coverage analysis
enable_config_validation = true     # Enable configuration validation
enable_doc_validation = true        # Enable documentation validation
```

#### Cleanup Control

```toml
[checkup]
# Enable/disable cleanup operations
auto_format = false                 # Automatically format code with black/isort
auto_fix_imports = false           # Automatically fix import issues
auto_organize_files = false        # Automatically reorganize file structure
auto_fix_quality = false           # Automatically fix quality issues where possible
```

#### General Settings

```toml
[checkup]
# General behavior settings
dry_run = false                     # Preview changes without applying them
verbose = false                     # Enable verbose output
quiet = false                       # Suppress non-essential output
parallel_analysis = true            # Enable parallel processing
max_workers = 4                     # Maximum number of worker processes
timeout = 300                       # Analysis timeout in seconds
```

#### File and Directory Settings

```toml
[checkup]
# File handling settings
include_patterns = ["*.py"]         # File patterns to include
exclude_patterns = [                # File patterns to exclude
    "venv/*",
    "__pycache__/*",
    "*.pyc",
    ".git/*",
    "node_modules/*"
]
max_file_size = 1048576            # Maximum file size to analyze (bytes)
follow_symlinks = false            # Follow symbolic links
```

## Code Quality Settings

### `[checkup.quality]` Section

```toml
[checkup.quality]
# Complexity analysis
max_complexity = 10                 # Maximum cyclomatic complexity
max_nesting_depth = 4              # Maximum nesting depth
max_function_length = 50           # Maximum function length (lines)
max_class_length = 200             # Maximum class length (lines)

# Style checking
max_line_length = 88               # Maximum line length (PEP 8: 79, Black: 88)
enforce_docstrings = true          # Require docstrings for public methods
check_type_hints = true            # Check for missing type hints
enforce_naming_conventions = true   # Enforce PEP 8 naming conventions

# Code smell detection
detect_code_smells = true          # Enable code smell detection
smell_threshold = 0.7              # Code smell detection threshold
check_dead_code = true             # Detect unreachable code
check_unused_variables = true      # Detect unused variables

# Tool integration
use_flake8 = true                  # Use flake8 for style checking
use_mypy = true                    # Use mypy for type checking
use_pylint = false                 # Use pylint for additional checks
use_bandit = true                  # Use bandit for security checks

# Custom rules
custom_rules = [                   # Custom quality rules
    "no_print_statements",
    "require_return_type_hints"
]
```

## Duplicate Code Detection Settings

### `[checkup.duplicates]` Section

```toml
[checkup.duplicates]
# Detection parameters
similarity_threshold = 0.8          # Similarity threshold (0.0-1.0)
min_duplicate_lines = 5            # Minimum lines for duplicate detection
min_duplicate_tokens = 50          # Minimum tokens for duplicate detection
ignore_whitespace = true           # Ignore whitespace differences
ignore_comments = true             # Ignore comment differences

# Analysis scope
check_functions = true             # Check for duplicate functions
check_classes = true               # Check for duplicate classes
check_methods = true               # Check for duplicate methods
check_blocks = true                # Check for duplicate code blocks

# Filtering
ignore_test_files = false          # Ignore test files in duplicate detection
ignore_generated_files = true     # Ignore generated files
exclude_patterns = [               # Patterns to exclude from duplicate detection
    "migrations/*",
    "tests/fixtures/*"
]

# Refactoring suggestions
suggest_refactoring = true         # Generate refactoring suggestions
min_refactor_confidence = 0.8      # Minimum confidence for refactoring suggestions
suggest_abstractions = true        # Suggest common abstractions
```

## Import Analysis Settings

### `[checkup.imports]` Section

```toml
[checkup.imports]
# Import cleanup
remove_unused = true               # Remove unused imports
organize_imports = true            # Organize import order
group_imports = true               # Group imports by type
sort_imports = true                # Sort imports alphabetically

# Dependency analysis
check_circular = true              # Check for circular imports
check_missing = true               # Check for missing imports
analyze_dependencies = true        # Analyze dependency relationships
detect_orphaned_modules = true     # Detect orphaned modules

# Import style
force_single_line = false          # Force single-line imports
combine_star_imports = false       # Combine star imports
remove_duplicate_imports = true    # Remove duplicate imports
normalize_import_paths = true      # Normalize import paths

# Tool integration
use_isort = true                   # Use isort for import organization
isort_profile = "black"            # isort profile to use
custom_import_order = [            # Custom import order
    "FUTURE",
    "STDLIB",
    "THIRDPARTY",
    "FIRSTPARTY",
    "LOCALFOLDER"
]
```

## Test Coverage Settings

### `[checkup.coverage]` Section

```toml
[checkup.coverage]
# Coverage requirements
min_coverage = 80.0                # Minimum coverage percentage
min_function_coverage = 70.0       # Minimum function coverage
min_branch_coverage = 75.0         # Minimum branch coverage
min_line_coverage = 80.0           # Minimum line coverage

# Coverage analysis
include_patterns = ["src/*"]       # Patterns to include in coverage
exclude_patterns = [               # Patterns to exclude from coverage
    "tests/*",
    "conftest.py",
    "*/migrations/*"
]
ignore_missing_imports = true      # Ignore missing imports in coverage

# Test quality
check_test_quality = true          # Analyze test quality
detect_redundant_tests = true      # Detect redundant test cases
suggest_missing_tests = true       # Suggest missing test cases
min_test_complexity = 2            # Minimum test complexity

# Tool integration
use_pytest_cov = true              # Use pytest-cov for coverage
coverage_report_format = "html"    # Coverage report format
generate_coverage_badge = true     # Generate coverage badge
```

## File Structure Settings

### `[checkup.structure]` Section

```toml
[checkup.structure]
# Directory organization
max_nesting_depth = 3              # Maximum directory nesting depth
enforce_init_files = true          # Require __init__.py files
check_naming_conventions = true    # Check directory/file naming
suggest_reorganization = true      # Suggest file reorganization

# File placement rules
group_related_files = true         # Group related files together
separate_tests = true              # Keep tests in separate directories
organize_by_feature = false        # Organize by feature vs. by type
enforce_package_structure = true   # Enforce Python package structure

# Empty directory handling
remove_empty_dirs = true           # Remove empty directories
ignore_git_dirs = true             # Ignore .git directories
preserve_placeholder_files = true  # Preserve .gitkeep files

# File organization
max_files_per_directory = 20       # Maximum files per directory
suggest_subdirectories = true      # Suggest creating subdirectories
check_file_sizes = true            # Check for oversized files
max_single_file_size = 1000        # Maximum lines per file
```

## Code Formatting Settings

### `[checkup.formatting]` Section

```toml
[checkup.formatting]
# Black configuration
use_black = true                   # Use black for code formatting
black_line_length = 88             # Black line length
black_target_version = ["py39"]    # Black target Python versions
black_skip_string_normalization = false  # Skip string normalization

# isort configuration
use_isort = true                   # Use isort for import sorting
isort_profile = "black"            # isort profile
isort_line_length = 88             # isort line length
isort_multi_line_output = 3        # isort multi-line output mode

# Docstring formatting
format_docstrings = true           # Format docstrings
docstring_style = "google"         # Docstring style (google, numpy, sphinx)
enforce_docstring_format = true    # Enforce consistent docstring format

# Additional formatting
remove_trailing_whitespace = true  # Remove trailing whitespace
ensure_newline_at_eof = true       # Ensure newline at end of file
normalize_line_endings = true      # Normalize line endings
```

## Reporting Settings

### `[checkup.reporting]` Section

```toml
[checkup.reporting]
# Report generation
generate_html_report = true        # Generate HTML report
generate_json_report = true        # Generate JSON report
generate_markdown_report = true    # Generate Markdown report
generate_xml_report = false        # Generate XML report

# Report content
include_metrics = true             # Include code metrics
include_trends = true              # Include trend analysis
include_suggestions = true         # Include improvement suggestions
include_examples = true            # Include code examples

# Report formatting
html_theme = "default"             # HTML report theme
include_source_code = true         # Include source code in reports
syntax_highlighting = true         # Enable syntax highlighting
interactive_charts = true          # Enable interactive charts

# Output settings
output_directory = "reports"       # Report output directory
report_filename_template = "checkup-{timestamp}"  # Report filename template
compress_reports = false           # Compress report files
```

## Safety and Backup Settings

### `[checkup.safety]` Section

```toml
[checkup.safety]
# Backup settings
create_backup = true               # Create backup before changes
backup_directory = ".checkup-backups"  # Backup directory
max_backups = 10                   # Maximum number of backups to keep
compress_backups = true            # Compress backup files

# Safety limits
max_file_moves = 10                # Maximum file moves per run
max_file_deletions = 5             # Maximum file deletions per run
max_changes_per_file = 50          # Maximum changes per file
require_confirmation = true        # Require user confirmation for destructive operations

# Rollback settings
enable_rollback = true             # Enable rollback functionality
rollback_timeout = 3600            # Rollback timeout (seconds)
auto_rollback_on_error = true      # Automatically rollback on error

# Validation
validate_before_changes = true     # Validate changes before applying
run_tests_after_changes = true     # Run tests after applying changes
check_syntax_after_changes = true  # Check syntax after changes
```

## Environment Variables

Configuration can also be controlled through environment variables:

```bash
# Global settings
export CHECKUP_CONFIG="/path/to/checkup.toml"
export CHECKUP_OUTPUT_DIR="/path/to/reports"
export CHECKUP_VERBOSE="1"
export CHECKUP_DRY_RUN="1"

# Analysis settings
export CHECKUP_ENABLE_QUALITY="1"
export CHECKUP_ENABLE_DUPLICATES="1"
export CHECKUP_ENABLE_IMPORTS="1"
export CHECKUP_ENABLE_COVERAGE="1"

# Cleanup settings
export CHECKUP_AUTO_FORMAT="0"
export CHECKUP_AUTO_FIX_IMPORTS="0"
export CHECKUP_CREATE_BACKUP="1"

# Tool settings
export CHECKUP_BLACK_LINE_LENGTH="88"
export CHECKUP_ISORT_PROFILE="black"
export CHECKUP_MIN_COVERAGE="80"
```

## Command-Line Override

Most configuration options can be overridden via command-line arguments:

```bash
# Override analysis settings
migration-assistant checkup analyze --no-quality --no-duplicates

# Override cleanup settings
migration-assistant checkup run --auto-format --no-backup

# Override reporting settings
migration-assistant checkup analyze --report-html --output-dir custom-reports

# Override safety settings
migration-assistant checkup run --max-moves 20 --no-confirmation
```

## Configuration Validation

The checkup system validates configuration files and provides helpful error messages:

```bash
# Validate configuration
migration-assistant checkup validate-config

# Check configuration with specific file
migration-assistant checkup validate-config --config custom-checkup.toml
```

## Configuration Examples

### Minimal Configuration

```toml
[checkup]
enable_quality_analysis = true
auto_format = true
create_backup = true
```

### Strict Configuration

```toml
[checkup]
enable_quality_analysis = true
enable_duplicate_detection = true
enable_import_analysis = true
enable_coverage_analysis = true

[checkup.quality]
max_complexity = 8
max_line_length = 79
enforce_docstrings = true
check_type_hints = true

[checkup.coverage]
min_coverage = 90.0
min_function_coverage = 85.0

[checkup.safety]
require_confirmation = true
max_file_moves = 5
```

### CI/CD Configuration

```toml
[checkup]
enable_quality_analysis = true
enable_duplicate_detection = true
generate_json_report = true
quiet = true
dry_run = false

[checkup.reporting]
output_directory = "ci-reports"
include_metrics = true

[checkup.safety]
create_backup = false
require_confirmation = false
```

## Best Practices

1. **Start Simple**: Begin with minimal configuration and gradually add more settings
2. **Team Consistency**: Share configuration files across your team
3. **Environment-Specific**: Use different configurations for development, CI, and production
4. **Regular Updates**: Review and update configuration as your project evolves
5. **Documentation**: Document custom configuration choices for your team