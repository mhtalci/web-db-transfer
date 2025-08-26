# Web Database Transfer Assistant

A simple, production-ready tool for transferring websites and databases between servers of the same type. Focused on reliable same-type transfers (MySQL to MySQL, PostgreSQL to PostgreSQL, etc.) rather than complex cross-database migrations.

## Features

### 🚀 **Enterprise-Grade CMS Migration**
- **12+ CMS Platforms**: WordPress, Drupal, Joomla, Magento, Shopware, PrestaShop, OpenCart, Ghost, Craft CMS, TYPO3, Concrete5, Umbraco
- **Intelligent Orchestration**: AI-powered migration planning with dependency resolution
- **Real-time Monitoring**: Live progress tracking with performance analytics
- **Health Validation**: Comprehensive pre/post-migration health checks with scoring
- **Security Analysis**: Automated vulnerability scanning and permission validation

### 🔧 **Advanced Migration Capabilities**
- **Same-Platform Migrations**: Server-to-server moves with optimization
- **Cross-Platform Migrations**: Content transformation and data mapping
- **Pause/Resume/Cancel**: Full migration control with rollback support
- **Background Processing**: Non-blocking execution with streaming updates
- **Performance Optimization**: Automatic bottleneck detection and recommendations

### 🛠 **Technical Excellence**
- **Same-Type Database Transfers**: MySQL, PostgreSQL, MongoDB, SQLite, Redis
- **Multiple Transfer Methods**: SSH/SCP, FTP/SFTP, Rsync, Cloud storage (AWS S3, Google Cloud, Azure)
- **Control Panel Integration**: cPanel, Plesk, DirectAdmin, CyberPanel, WHM
- **High Performance**: Go-powered engine with Python orchestration
- **RESTful API**: Comprehensive API with real-time streaming support

### 🔒 **Security & Reliability**
- **Encrypted Transfers**: End-to-end encryption with integrity verification
- **Automated Backups**: Smart backup strategies with rollback capabilities
- **Error Recovery**: Intelligent retry logic with exponential backoff
- **Audit Logging**: Comprehensive logging and compliance reporting
- **Access Control**: Role-based permissions and secure credential management

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/mhtalci/web-db-transfer.git
cd web-db-transfer

# Install Python dependencies
pip install -e .

# Build Go performance engine
./scripts/build-go-binaries.sh
```

### Basic Usage

#### CLI Interface
```bash
# Interactive CMS migration setup
python -m migration_assistant.cli.main

# Quick CMS migration with health check
migration-assistant cms migrate \
  --source-platform wordpress \
  --source-path /var/www/wordpress \
  --destination-platform wordpress \
  --destination-path /var/www/new-wordpress \
  --health-check

# Advanced migration with monitoring
migration-assistant cms migrate \
  --source-platform magento \
  --destination-platform shopware \
  --real-time-monitoring \
  --performance-alerts
```

#### Advanced API Interface
```bash
# Start the enhanced API server
python -m migration_assistant.api.main

# Detect CMS platforms
curl -X POST http://localhost:8000/api/v1/cms/detect \
  -H "Content-Type: application/json" \
  -d '{"path": "/var/www/cms"}'

# Perform health check
curl -X POST http://localhost:8000/api/v1/cms/health-check \
  -H "Content-Type: application/json" \
  -d '{"platform_type": "wordpress", "path": "/var/www/wordpress"}'

# Create and execute migration plan
curl -X POST http://localhost:8000/api/v1/cms/migration/plan \
  -H "Content-Type: application/json" \
  -d '{
    "source_platform": "wordpress",
    "destination_platform": "drupal",
    "source_path": "/var/www/wordpress",
    "destination_path": "/var/www/drupal",
    "options": {"create_backup": true, "real_time_monitoring": true}
  }'

# Stream real-time migration progress
curl -N http://localhost:8000/api/v1/cms/migration/{migration_id}/stream
```

#### Python SDK Usage
```python
from migration_assistant.orchestrators.cms_migration_orchestrator import CMSMigrationOrchestrator
from migration_assistant.validators.cms_validator import CMSHealthChecker

# Create orchestrator
orchestrator = CMSMigrationOrchestrator()

# Perform health check
checker = CMSHealthChecker("wordpress", Path("/var/www/wordpress"))
health_result = await checker.run_health_check()
print(f"Health Score: {health_result['health_score']}/100")

# Create and execute migration
plan = await orchestrator.create_migration_plan(
    source_platform="wordpress",
    destination_platform="wordpress",
    source_path=Path("/source"),
    destination_path=Path("/destination")
)

# Execute with real-time monitoring
async for progress in orchestrator.execute_migration(plan.id):
    print(f"Progress: {progress.get('progress', 0):.1f}% - {progress['message']}")
```

## Configuration

### Environment Variables
```bash
export MIGRATION_LOG_LEVEL=INFO
export MIGRATION_BACKUP_ENABLED=true
export MIGRATION_PERFORMANCE_ENGINE=go
```

### Configuration File
Create `config.yaml`:
```yaml
transfer:
  backup:
    enabled: true
    retention_days: 30
  performance:
    engine: "go"
    max_concurrent_transfers: 5
  security:
    encrypt_transfers: true
    validate_checksums: true
  validation:
    check_connectivity: true
    verify_space: true
```

## Supported Platforms

### Control Panels
- cPanel/WHM
- Plesk
- DirectAdmin
- CyberPanel

### CMS Platforms
#### Content Management
- WordPress (4.0 - 6.5)
- Drupal (7.0 - 10.1)
- Joomla (3.0 - 5.0)
- TYPO3 (8.7 - 12.4)
- Concrete5 (8.0 - 9.2)
- Ghost (3.0 - 5.0)
- Craft CMS (3.0 - 4.4)
- Umbraco (8.0 - 13.0)

#### E-commerce
- Magento (2.0 - 2.4)
- Shopware (5.0 - 6.5)
- PrestaShop (1.6 - 8.1)
- OpenCart (2.0 - 4.0)

### Cloud Providers
- AWS (EC2, RDS, S3)
- Google Cloud Platform
- Microsoft Azure
- DigitalOcean

### Databases
- MySQL/MariaDB
- PostgreSQL
- MongoDB
- SQLite
- Redis

## Documentation

### 📚 **User Guides**
- [Getting Started Guide](docs/user-guide/getting-started.md)
- [Advanced CMS Migration Guide](docs/user-guide/advanced-cms-migration.md)
- [CLI Reference](docs/user-guide/cli-guide.md)
- [Migration Best Practices](docs/user-guide/best-practices.md)

### 🔧 **Technical Documentation**
- [CMS Platform Support](docs/cms-platforms.md) - Comprehensive platform documentation
- [API Reference](docs/api-reference.md) - Complete REST API documentation
- [Architecture Overview](docs/technical/architecture.md)
- [Performance Optimization](docs/technical/performance.md)

### 🚀 **Advanced Features**
- [Health Checking System](docs/advanced/health-checking.md)
- [Migration Orchestration](docs/advanced/orchestration.md)
- [Real-time Monitoring](docs/advanced/monitoring.md)
- [Security Analysis](docs/advanced/security.md)

### 📋 **Migration Guides**
- [WordPress Migrations](docs/migration-guides/wordpress.md)
- [E-commerce Platform Migrations](docs/migration-guides/ecommerce.md)
- [Cross-Platform Migrations](docs/migration-guides/cross-platform.md)
- [Troubleshooting Guide](docs/migration-guides/troubleshooting.md)

## Development

### Running Tests
```bash
# Run all tests
python -m pytest tests/

# Run specific test categories
python -m pytest tests/test_comprehensive_*.py

# Run with coverage
python -m pytest --cov=migration_assistant tests/
```

### Building
```bash
# Build Go binaries
./scripts/build-go-binaries.sh

# Run development setup
python -m pip install -e ".[dev]"
```

## Production Deployment

### Docker
```bash
# Build and run with Docker Compose
docker-compose up -d
```

### Systemd Service
```bash
# Install as system service
sudo cp scripts/migration-assistant.service /etc/systemd/system/
sudo systemctl enable migration-assistant
sudo systemctl start migration-assistant
```

## Security

- All transfers are encrypted by default
- Credentials are stored securely using industry-standard encryption
- Data integrity is verified using checksums
- Comprehensive audit logging
- Support for SSH key authentication

## Performance

- Go-powered transfer engine for maximum performance
- Concurrent transfer support
- Compression and deduplication
- Bandwidth throttling
- Resume interrupted transfers

## Support

- [FAQ](docs/advanced/faq.md)
- [Troubleshooting Guide](docs/advanced/troubleshooting.md)
- [Performance Tuning](docs/advanced/performance-tuning.md)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and updates.