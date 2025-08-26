# Web Database Migration Assistant

A comprehensive, production-ready tool for migrating websites and databases between servers with support for multiple platforms, databases, and transfer methods.

## Features

- **Multi-Database Support**: MySQL, PostgreSQL, MongoDB, SQLite, Redis
- **Multiple Transfer Methods**: SSH/SCP, FTP/SFTP, Rsync, Cloud storage (AWS S3, Google Cloud, Azure)
- **Platform Integration**: cPanel, Plesk, DirectAdmin, WordPress, Drupal, and more
- **High Performance**: Go-powered engine with Python orchestration
- **Comprehensive Validation**: Pre-migration checks, data integrity validation
- **Backup & Recovery**: Automated backups with rollback capabilities
- **Real-time Monitoring**: Progress tracking and performance metrics
- **Security**: Encrypted transfers, credential management, data sanitization

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
# Interactive migration setup
python -m migration_assistant.cli.main

# Quick migration with preset
migration-assistant migrate --preset wordpress-to-cpanel --source-host example.com --dest-host newserver.com
```

#### API Interface
```bash
# Start the API server
python -m migration_assistant.api.main

# Use the REST API
curl -X POST http://localhost:8000/api/v1/migrations \
  -H "Content-Type: application/json" \
  -d '{"source": {...}, "destination": {...}}'
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
migration:
  backup:
    enabled: true
    retention_days: 30
  performance:
    engine: "go"
    max_concurrent_transfers: 5
  security:
    encrypt_transfers: true
    validate_checksums: true
```

## Supported Platforms

### Control Panels
- cPanel/WHM
- Plesk
- DirectAdmin
- CyberPanel

### CMS Platforms
- WordPress
- Drupal
- Joomla
- Magento

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

- [Getting Started Guide](docs/user-guide/getting-started.md)
- [CLI Reference](docs/user-guide/cli-guide.md)
- [API Documentation](docs/user-guide/api-guide.md)
- [Migration Guides](docs/migration-guides/)
- [Advanced Configuration](docs/advanced/)

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