# Frequently Asked Questions (FAQ)

This FAQ covers common questions about the Web & Database Migration Assistant, its features, limitations, and best practices.

## 📋 Table of Contents

- [General Questions](#general-questions)
- [Installation and Setup](#installation-and-setup)
- [Migration Capabilities](#migration-capabilities)
- [Performance and Scalability](#performance-and-scalability)
- [Security and Privacy](#security-and-privacy)
- [Troubleshooting](#troubleshooting)
- [API and Integration](#api-and-integration)
- [Pricing and Licensing](#pricing-and-licensing)

## 🌐 General Questions

### What is the Web & Database Migration Assistant?
The Web & Database Migration Assistant is a comprehensive Python-based tool that provides both CLI and API interfaces for migrating web applications and databases between different systems, platforms, and environments. It supports various source and destination types including control panels (cPanel, DirectAdmin, Plesk), cloud platforms (AWS, GCP, Azure), and containerized environments.

### What makes this migration tool different from others?
Key differentiators include:
- **Hybrid Python-Go Architecture**: Combines Python's flexibility with Go's performance
- **Control Panel Integration**: Native API support for cPanel, DirectAdmin, and Plesk
- **Comprehensive Validation**: Pre-migration checks and post-migration verification
- **Interactive CLI**: Rich-formatted, user-friendly command-line interface
- **REST API**: Full programmatic access with auto-generated documentation
- **Multi-tenant Support**: Enterprise-ready with tenant isolation
- **Extensive Testing**: 90%+ test coverage with Docker-based integration tests

### Is this tool suitable for enterprise use?
Yes, the Migration Assistant is designed for enterprise use with features like:
- Multi-tenant architecture with tenant isolation
- Role-based access control and authentication
- Comprehensive audit logging
- Batch migration capabilities
- API-first design for integration
- Professional support options

### What platforms are supported?
**Operating Systems**: Linux, macOS, Windows
**Source Systems**: WordPress, Drupal, Django, static sites, cPanel, DirectAdmin, Plesk, various databases
**Destination Systems**: AWS, Google Cloud, Azure, DigitalOcean, custom servers, containers
**Databases**: MySQL, PostgreSQL, MongoDB, Redis, SQLite, cloud databases

## 🚀 Installation and Setup

### What are the system requirements?
**Minimum Requirements**:
- Python 3.11 or higher
- 2GB RAM (4GB+ recommended for large migrations)
- 1GB free disk space for temporary files and backups
- Network connectivity to source and destination systems

**Optional Dependencies**:
- Go 1.21+ (for high-performance operations)
- Docker (for containerized migrations and testing)
- Cloud CLI tools (AWS CLI, gcloud, Azure CLI)

### How do I install the Migration Assistant?
```bash
# Install from PyPI (recommended)
pip install web-database-migration-assistant

# Install from source
git clone https://github.com/migration-assistant/migration-assistant.git
cd migration-assistant
pip install -e .

# Docker installation
docker pull migration-assistant/migration-assistant:latest
```

### Do I need to install Go separately?
Go is optional but recommended for high-performance operations. The tool will work with Python-only implementations if Go is not available. To install Go:
```bash
# Linux/macOS
wget https://go.dev/dl/go1.21.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.21.linux-amd64.tar.gz
export PATH=$PATH:/usr/local/go/bin

# macOS with Homebrew
brew install go

# Windows
# Download installer from https://golang.org/dl/
```

### Can I run this in a Docker container?
Yes, Docker containers are fully supported:
```bash
# Run CLI in container
docker run -it migration-assistant/migration-assistant:latest migration-assistant --help

# Run API server in container
docker run -p 8000:8000 migration-assistant/migration-assistant:latest migration-assistant serve

# Mount configuration files
docker run -v $(pwd)/config:/config migration-assistant/migration-assistant:latest migration-assistant migrate --config /config/migration.yaml
```

## 🔄 Migration Capabilities

### What types of migrations are supported?
**Website Migrations**:
- Static websites (HTML/CSS/JS)
- CMS platforms (WordPress, Drupal, Joomla)
- Web frameworks (Django, Flask, Laravel, Rails)
- Control panel hosting (cPanel, DirectAdmin, Plesk)

**Database Migrations**:
- Relational databases (MySQL, PostgreSQL, SQLite, SQL Server)
- NoSQL databases (MongoDB, Redis, Cassandra)
- Cloud databases (AWS RDS, Google Cloud SQL, Azure Database)

**Infrastructure Migrations**:
- Server-to-cloud migrations
- Container migrations (Docker, Kubernetes)
- Cloud-to-cloud migrations
- Hybrid cloud setups

### Can I migrate from shared hosting providers?
Yes, the Migration Assistant has native support for popular control panels:
- **cPanel**: API v2/UAPI integration for account, database, and email extraction
- **DirectAdmin**: Native API integration for user and domain management
- **Plesk**: REST API integration for hosting configuration extraction

### How are email accounts handled during migration?
Email migration capabilities include:
- Mailbox extraction and migration
- Email forwarding rules
- Autoresponders and filters
- Mailing lists
- Migration to cloud email services (AWS WorkMail, Google Workspace, Office 365)

### Can I migrate SSL certificates?
Yes, SSL certificate migration is supported:
- Extract certificates from control panels
- Migrate to cloud certificate managers (AWS Certificate Manager, Let's Encrypt)
- Automatic certificate validation and installation
- Force HTTPS redirection setup

### What about DNS records?
DNS migration features include:
- Zone file extraction from control panels
- Migration to cloud DNS services (Route 53, Cloud DNS, Azure DNS)
- Automatic record creation and validation
- Optional nameserver updates

## ⚡ Performance and Scalability

### How fast are migrations?
Performance depends on several factors:
- **Data size**: Typical speeds of 2-5 MB/s for file transfers
- **Network bandwidth**: Limited by available bandwidth
- **Go acceleration**: 2-3x faster than Python-only operations
- **Parallel transfers**: Configurable parallelism (default: 4 threads)

**Typical Migration Times**:
- Small website (< 1GB): 10-20 minutes
- Medium website (1-10GB): 30-90 minutes
- Large website (10-100GB): 2-8 hours
- Enterprise migration (100GB+): 8+ hours

### Can I run multiple migrations simultaneously?
Yes, the Migration Assistant supports:
- **Batch migrations**: Process multiple sites in parallel
- **API concurrency**: Multiple API clients can run migrations simultaneously
- **Resource management**: Configurable limits to prevent system overload
- **Queue management**: Automatic queuing and scheduling of migrations

### How do I optimize migration performance?
**Performance Tuning Options**:
```yaml
# Enable Go acceleration
performance:
  use_go_engine: true
  max_parallel_transfers: 8
  chunk_size: "50MB"
  compression: true

# Database optimization
database_migration:
  parallel_jobs: 4
  batch_size: 10000
  disable_indexes: true  # Rebuild after migration
```

### What are the scalability limits?
**Tested Limits**:
- **File count**: Successfully tested with 1M+ files
- **Database size**: Tested with databases up to 1TB
- **Concurrent migrations**: Up to 10 simultaneous migrations per server
- **API throughput**: 1000+ requests per minute

## 🔐 Security and Privacy

### How are credentials stored and transmitted?
**Security Measures**:
- Credentials stored in environment variables or encrypted configuration files
- All network communications use encrypted connections (HTTPS, SSH, TLS)
- API authentication via JWT tokens, API keys, or OAuth2
- Support for SSH key authentication instead of passwords
- Integration with credential management systems (AWS Secrets Manager, etc.)

### Is data encrypted during migration?
Yes, multiple encryption layers:
- **In transit**: All data transfers use encrypted protocols (SSH, HTTPS, TLS)
- **At rest**: Temporary files can be encrypted using system encryption
- **Database connections**: All database connections use SSL/TLS encryption
- **Cloud storage**: Integration with cloud encryption services

### What data is logged?
**Logging Practices**:
- Migration progress and status information
- Error messages and debugging information
- Performance metrics and timing data
- **NOT logged**: Passwords, API keys, or sensitive data content
- Configurable log levels and retention policies

### Can I run migrations in air-gapped environments?
Partial support for air-gapped environments:
- **Offline mode**: CLI can work without internet for local migrations
- **Package dependencies**: All Python dependencies can be pre-installed
- **Go binaries**: Can be compiled and distributed separately
- **Limitations**: Cloud migrations require internet connectivity

## 🔧 Troubleshooting

### What should I do if a migration fails?
**Immediate Steps**:
1. Check the error message and logs: `migration-assistant logs --session SESSION_ID`
2. Verify connectivity: `migration-assistant validate --quick --config your-config.yaml`
3. Try resuming: `migration-assistant migrate --resume SESSION_ID`
4. If needed, rollback: `migration-assistant rollback --session SESSION_ID`

### How do I resume a failed migration?
```bash
# Resume from last checkpoint
migration-assistant migrate --resume SESSION_ID

# Resume with different settings
migration-assistant migrate --resume SESSION_ID --parallel 2

# Retry only failed items
migration-assistant migrate --retry-failed --session SESSION_ID
```

### Can I rollback a migration?
Yes, rollback capabilities include:
- **Automatic rollback**: On migration failure (if enabled)
- **Manual rollback**: Using backup files created before migration
- **Partial rollback**: Rollback specific components (files, database, configuration)
- **Verification**: Test rollback procedures before execution

### Where can I get help?
**Support Channels**:
- **Documentation**: Complete guides and API reference
- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Community support and questions
- **Enterprise Support**: Professional support for enterprise customers

## 🌐 API and Integration

### Is there a REST API?
Yes, a comprehensive REST API built with FastAPI:
- **Auto-generated documentation**: Swagger UI and ReDoc
- **Async support**: Long-running migrations with background processing
- **Multi-tenant**: Tenant isolation and resource management
- **Authentication**: OAuth2, JWT, and API key support
- **WebSocket support**: Real-time progress updates

### Can I integrate with CI/CD pipelines?
Yes, the Migration Assistant is designed for automation:
```bash
# Non-interactive mode
migration-assistant migrate --non-interactive --config production.yaml

# JSON output for parsing
migration-assistant status --format json

# Exit codes for scripting
if migration-assistant validate --config my-config.yaml; then
    migration-assistant migrate --config my-config.yaml
fi
```

### Are there client SDKs available?
Client SDKs are available for:
- **Python**: Official SDK with async support
- **JavaScript/Node.js**: Full-featured client library
- **Go**: Native Go client
- **Other languages**: Auto-generated from OpenAPI specification

### Can I create custom integrations?
Yes, multiple integration options:
- **REST API**: Full programmatic access
- **Webhooks**: Real-time event notifications
- **Custom presets**: Create reusable migration templates
- **Plugin system**: Extend functionality with custom modules

## 💰 Pricing and Licensing

### What is the licensing model?
The Migration Assistant is open source under the MIT License:
- **Free for all use**: Personal, commercial, and enterprise
- **No usage restrictions**: Unlimited migrations and users
- **Source code available**: Full transparency and customization
- **Community support**: Free community support via GitHub

### Is there commercial support available?
Yes, commercial support options include:
- **Professional Support**: Email support with SLA
- **Enterprise Support**: Phone support, custom development, training
- **Managed Services**: Fully managed migration services
- **Custom Development**: Feature development and customization

### Can I use this for commercial purposes?
Yes, the MIT license allows:
- **Commercial use**: Use in commercial products and services
- **Modification**: Customize and extend the software
- **Distribution**: Include in your products or services
- **Private use**: Use internally without restrictions

### Are there any usage limits?
No built-in usage limits:
- **Unlimited migrations**: No restrictions on number of migrations
- **Unlimited data**: No limits on data transfer amounts
- **Unlimited users**: No restrictions on number of users
- **Rate limiting**: Configurable API rate limits for server protection

## 🔮 Future Development

### What features are planned?
**Upcoming Features**:
- Additional control panel support (Virtualmin, ISPConfig)
- More cloud platform integrations
- Enhanced container migration capabilities
- Machine learning for migration optimization
- Advanced monitoring and analytics

### How can I request features?
**Feature Requests**:
- **GitHub Issues**: Submit feature requests with detailed descriptions
- **GitHub Discussions**: Discuss ideas with the community
- **Enterprise Customers**: Direct feature requests through support channels
- **Contributions**: Submit pull requests for new features

### Can I contribute to the project?
Yes, contributions are welcome:
- **Code contributions**: Bug fixes, new features, improvements
- **Documentation**: Improve guides, add examples, fix errors
- **Testing**: Report bugs, test new features, improve test coverage
- **Community support**: Help other users in discussions

### How often are updates released?
**Release Schedule**:
- **Major releases**: Every 6 months with new features
- **Minor releases**: Monthly with bug fixes and improvements
- **Security updates**: As needed for security issues
- **Beta releases**: Available for testing new features

---

**Still have questions?** 

Check the [Troubleshooting Guide](troubleshooting.md) for technical issues, browse the complete [documentation](../README.md), or ask the community in [GitHub Discussions](https://github.com/migration-assistant/migration-assistant/discussions).