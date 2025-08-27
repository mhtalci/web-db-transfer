# Codebase Checkup Examples

This directory contains example configurations, workflows, and demonstration scripts for the codebase checkup and cleanup system.

## Contents

### Configuration Examples
- `basic-checkup.toml` - Minimal configuration for getting started
- `development-checkup.toml` - Balanced settings for active development
- `team-checkup.toml` - Standardized settings for team environments
- `production-checkup.toml` - High-reliability settings for production analysis
- `strict-checkup.toml` - Strict configuration for high-quality codebases
- `ci-checkup.toml` - Configuration optimized for CI/CD environments
- `legacy-checkup.toml` - Configuration for legacy codebase cleanup
- `security-focused-checkup.toml` - Security-focused analysis configuration

### Workflow Examples
- `workflows/github-actions.yml` - GitHub Actions workflow with checkup
- `workflows/gitlab-ci.yml` - GitLab CI/CD pipeline integration
- `workflows/azure-pipelines.yml` - Azure DevOps pipeline configuration
- `workflows/jenkins-pipeline.groovy` - Jenkins pipeline script
- `workflows/pre-commit-config.yaml` - Pre-commit hooks configuration
- `workflows/docker-compose.yml` - Docker Compose for containerized checkup
- `workflows/kubernetes-job.yaml` - Kubernetes job and CronJob examples

### Demonstration Scripts
- `scripts/demo_basic_usage.py` - Basic API usage demonstration
- `scripts/demo_custom_analyzer.py` - Custom analyzer implementation
- `scripts/demo_batch_processing.py` - Batch processing multiple projects
- `scripts/demo_ci_integration.py` - CI/CD integration examples
- `scripts/demo_advanced_features.py` - Advanced features and customization
- `scripts/demo_integration_workflows.py` - Integration workflows and automation

## Quick Start

1. Copy a configuration file that matches your needs
2. Customize the settings for your project
3. Run the checkup:
   ```bash
   migration-assistant checkup run --config your-config.toml
   ```

## Configuration Selection Guide

| Use Case | Configuration File | Description |
|----------|-------------------|-------------|
| New to checkup | `basic-checkup.toml` | Simple settings to get started |
| Active development | `development-checkup.toml` | Balanced settings for dev work |
| Team collaboration | `team-checkup.toml` | Standardized team settings |
| Production analysis | `production-checkup.toml` | High-reliability production settings |
| High-quality project | `strict-checkup.toml` | Strict rules for quality code |
| CI/CD pipeline | `ci-checkup.toml` | Optimized for automated environments |
| Legacy codebase | `legacy-checkup.toml` | Gradual improvement approach |
| Security focus | `security-focused-checkup.toml` | Security-focused analysis |

## Running Examples

### Basic Usage
```bash
# Copy example configuration
cp examples/checkup/basic-checkup.toml checkup.toml

# Run checkup
migration-assistant checkup run --auto-format --backup
```

### Development Workflow
```bash
# Use development configuration
migration-assistant checkup analyze --config examples/checkup/development-checkup.toml

# Apply formatting only
migration-assistant checkup format --config examples/checkup/development-checkup.toml
```

### CI/CD Integration
```bash
# Run in CI environment
migration-assistant checkup analyze --config examples/checkup/ci-checkup.toml --quiet --report-json

# Security-focused analysis
migration-assistant checkup analyze --config examples/checkup/security-focused-checkup.toml --report-json

# Team workflow
migration-assistant checkup run --config examples/checkup/team-checkup.toml --backup --report-html
```

### Docker Integration
```bash
# Build checkup container
docker build -f examples/checkup/workflows/Dockerfile.checkup -t checkup:latest .

# Run checkup in container
docker run --rm -v $(pwd):/workspace checkup:latest \
  migration-assistant checkup analyze --config examples/checkup/ci-checkup.toml

# Use Docker Compose
docker-compose -f examples/checkup/workflows/docker-compose.yml up checkup
```

### Batch Processing
```bash
# Run batch processing demo
python examples/checkup/scripts/demo_batch_processing.py

# Run CI integration demo
python examples/checkup/scripts/demo_ci_integration.py

# Run advanced features demo
python examples/checkup/scripts/demo_advanced_features.py
```

## Customization

All example configurations can be customized by:

1. Copying the example file to your project root
2. Renaming it to `checkup.toml`
3. Modifying settings to match your project needs
4. Testing with `--dry-run` first

For detailed configuration options, see the [Configuration Reference](../../docs/advanced/checkup-configuration.md).