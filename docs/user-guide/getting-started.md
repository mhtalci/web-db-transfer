# Getting Started

Welcome to the Web & Database Migration Assistant! This guide will help you get up and running quickly with both the CLI and API interfaces.

## 📋 Prerequisites

### System Requirements
- **Python**: 3.11 or higher
- **Operating System**: Linux, macOS, or Windows
- **Memory**: Minimum 2GB RAM (4GB+ recommended for large migrations)
- **Disk Space**: At least 1GB free space for temporary files and backups

### Optional Dependencies
- **Go**: 1.21+ (for high-performance operations)
- **Docker**: For containerized migrations and testing
- **Cloud CLI Tools**: AWS CLI, gcloud, Azure CLI (for cloud migrations)

## 🚀 Installation

### Option 1: Install from PyPI (Recommended)
```bash
pip install web-database-migration-assistant
```

### Option 2: Install from Source
```bash
# Clone the repository
git clone https://github.com/migration-assistant/migration-assistant.git
cd migration-assistant

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .
```

### Option 3: Docker Installation
```bash
# Pull the official image
docker pull migration-assistant/migration-assistant:latest

# Run with Docker
docker run -it migration-assistant/migration-assistant:latest migration-assistant --help
```

## ✅ Verify Installation

```bash
# Check version
migration-assistant --version

# Run health check
migration-assistant health

# List available commands
migration-assistant --help
```

Expected output:
```
Migration Assistant version 1.0.0
✅ All components initialized successfully
```

## 🎯 Your First Migration

### Step 1: Interactive Migration Wizard
```bash
migration-assistant migrate
```

This launches the interactive wizard that will guide you through:
1. **Source System Configuration** - Where your data is currently located
2. **Destination System Configuration** - Where you want to migrate to
3. **Transfer Method Selection** - How to move your data
4. **Validation & Safety Options** - Backup and verification settings
5. **Execution** - Running the migration with real-time progress

### Step 2: Using Presets for Common Scenarios
```bash
# List available presets
migration-assistant presets

# Use a WordPress preset
migration-assistant migrate --preset wordpress-mysql
```

Available presets include:
- `wordpress-mysql` - WordPress with MySQL database
- `django-postgres` - Django application with PostgreSQL
- `static-s3` - Static website to AWS S3
- `cpanel-aws` - cPanel hosting to AWS infrastructure

### Step 3: Configuration File Approach
Create a configuration file for repeatable migrations:

```yaml
# my-migration.yaml
name: "My Website Migration"
source:
  type: wordpress
  host: old-server.com
  database:
    type: mysql
    host: old-server.com
    username: wp_user
    password: secure_password
    database: wordpress_db

destination:
  type: aws-s3
  host: s3.amazonaws.com
  bucket: my-new-website
  database:
    type: aurora-mysql
    host: aurora-cluster.amazonaws.com
    username: admin
    password: new_secure_password

transfer:
  method: hybrid_sync
  options:
    compression: true
    parallel_transfers: 4

safety:
  backup_before: true
  verify_after: true
  rollback_on_failure: true
```

Run the migration:
```bash
migration-assistant migrate --config my-migration.yaml
```

## 🌐 API Quick Start

### Start the API Server
```bash
# Start with default settings
migration-assistant serve

# Start with custom port and host
migration-assistant serve --host 0.0.0.0 --port 8080

# Start with authentication enabled
migration-assistant serve --auth-enabled --jwt-secret your-secret-key
```

### Access Interactive Documentation
Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Basic API Usage
```python
import requests

# Create a migration
response = requests.post('http://localhost:8000/migrations/', json={
    "name": "API Test Migration",
    "source": {
        "type": "mysql",
        "host": "source-db.com",
        "username": "user",
        "password": "pass",
        "database": "mydb"
    },
    "destination": {
        "type": "postgresql",
        "host": "dest-db.com",
        "username": "user",
        "password": "pass",
        "database": "mydb"
    }
})

session_id = response.json()['session_id']

# Start the migration
requests.post(f'http://localhost:8000/migrations/{session_id}/start')

# Check status
status = requests.get(f'http://localhost:8000/migrations/{session_id}/status')
print(status.json())
```

## 🔧 Configuration

### Environment Variables
```bash
# Database connections
export MIGRATION_DB_URL="postgresql://user:pass@localhost/migrations"

# Cloud credentials
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"

# API settings
export MIGRATION_API_HOST="0.0.0.0"
export MIGRATION_API_PORT="8000"
export MIGRATION_JWT_SECRET="your-jwt-secret"

# Performance settings
export MIGRATION_USE_GO_ENGINE="true"
export MIGRATION_MAX_PARALLEL_TRANSFERS="8"
```

### Configuration File Locations
The migration assistant looks for configuration files in these locations:
1. `./migration-config.yaml` (current directory)
2. `~/.migration-assistant/config.yaml` (user home)
3. `/etc/migration-assistant/config.yaml` (system-wide)

### Logging Configuration
```yaml
# logging.yaml
logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  handlers:
    console:
      enabled: true
      level: INFO
    file:
      enabled: true
      level: DEBUG
      path: "/var/log/migration-assistant.log"
      max_size: "100MB"
      backup_count: 5
```

## 🛠️ Development Setup

### For Contributors
```bash
# Clone and setup development environment
git clone https://github.com/migration-assistant/migration-assistant.git
cd migration-assistant

# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run with coverage
pytest --cov=migration_assistant --cov-report=html

# Build Go components
cd go-engine
go build -o ../migration_assistant/bin/migration-engine ./cmd/migration-engine
```

### IDE Setup
For VS Code users, recommended extensions:
- Python
- Go
- YAML
- Docker
- REST Client

## 🚨 Common Issues

### Installation Issues
**Problem**: `pip install` fails with compilation errors
**Solution**: 
```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install python3-dev libpq-dev libmysqlclient-dev

# Install system dependencies (macOS)
brew install postgresql mysql-client

# Use pre-compiled wheels
pip install --only-binary=all web-database-migration-assistant
```

### Permission Issues
**Problem**: Permission denied when accessing files or databases
**Solution**:
```bash
# Check file permissions
ls -la /path/to/files

# Run with appropriate user
sudo -u www-data migration-assistant migrate

# Use SSH key authentication instead of passwords
migration-assistant migrate --ssh-key ~/.ssh/id_rsa
```

### Network Issues
**Problem**: Connection timeouts or network errors
**Solution**:
```bash
# Test connectivity
migration-assistant validate --config your-config.yaml

# Use VPN or SSH tunnel if needed
ssh -L 3306:remote-db:3306 user@jump-server

# Adjust timeout settings
migration-assistant migrate --timeout 300 --retries 3
```

## 📚 Next Steps

Now that you have the Migration Assistant installed and running:

1. **Read the CLI Guide** - [CLI User Guide](cli-guide.md) for detailed CLI usage
2. **Explore the API** - [API User Guide](api-guide.md) for programmatic access
3. **Check Migration Guides** - Platform-specific guides in the [migration-guides](../migration-guides/) directory
4. **Performance Tuning** - [Performance Guide](../advanced/performance-tuning.md) for optimization tips

## 🆘 Getting Help

- **Documentation**: Browse the complete documentation in this repository
- **Issues**: Report bugs at [GitHub Issues](https://github.com/migration-assistant/migration-assistant/issues)
- **Discussions**: Ask questions at [GitHub Discussions](https://github.com/migration-assistant/migration-assistant/discussions)
- **Support**: Enterprise support available at support@migration-assistant.com