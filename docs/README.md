# Web & Database Migration Assistant Documentation

Welcome to the comprehensive documentation for the Web & Database Migration Assistant - a powerful Python-based tool that provides both CLI and API interfaces for migrating web applications and databases between different systems, platforms, and environments.

## 📚 Documentation Structure

### User Guides
- [**Getting Started**](user-guide/getting-started.md) - Quick start guide and installation
- [**CLI User Guide**](user-guide/cli-guide.md) - Complete CLI interface documentation
- [**API User Guide**](user-guide/api-guide.md) - REST API usage and examples
- [**Configuration Guide**](user-guide/configuration.md) - Configuration options and presets

### Migration Guides
- [**Control Panel Migrations**](migration-guides/control-panels.md) - cPanel, DirectAdmin, and Plesk migrations
- [**Database Migrations**](migration-guides/databases.md) - Database-specific migration guides
- [**Cloud Platform Migrations**](migration-guides/cloud-platforms.md) - AWS, GCP, Azure migrations
- [**CMS & Framework Migrations**](migration-guides/cms-frameworks.md) - WordPress, Django, etc.

### API Documentation
- [**OpenAPI Specification**](api/openapi.md) - Complete API reference
- [**Authentication**](api/authentication.md) - API authentication methods
- [**Examples & Use Cases**](api/examples.md) - Practical API usage examples

### Advanced Topics
- [**Performance Tuning**](advanced/performance-tuning.md) - Python-Go hybrid optimization
- [**Troubleshooting**](advanced/troubleshooting.md) - Common issues and solutions
- [**FAQ**](advanced/faq.md) - Frequently asked questions
- [**Security**](advanced/security.md) - Security considerations and best practices

### Developer Documentation
- [**Architecture**](developer/architecture.md) - System architecture and design
- [**Contributing**](developer/contributing.md) - Development setup and contribution guide
- [**Testing**](developer/testing.md) - Testing framework and guidelines
- [**API Development**](developer/api-development.md) - Extending the API

## 🚀 Quick Start

### Installation
```bash
# Install from PyPI
pip install web-database-migration-assistant

# Or install from source
git clone https://github.com/migration-assistant/migration-assistant.git
cd migration-assistant
pip install -e .
```

### CLI Quick Start
```bash
# Interactive migration wizard
migration-assistant migrate

# List available presets
migration-assistant presets

# Validate configuration
migration-assistant validate --config my-config.yaml

# Check migration status
migration-assistant status
```

### API Quick Start
```bash
# Start the API server
migration-assistant serve --port 8000

# Access interactive documentation
open http://localhost:8000/docs
```

## 🎯 Key Features

- **Interactive CLI** with Rich formatting and step-by-step guidance
- **REST API** with async support and auto-generated OpenAPI documentation
- **Multiple Database Support** - MySQL, PostgreSQL, MongoDB, Redis, SQLite, and more
- **Cloud Platform Integration** - AWS, GCP, Azure with native SDK support
- **Control Panel Support** - cPanel, DirectAdmin, Plesk API integration
- **High Performance** - Go-accelerated file operations and data processing
- **Comprehensive Validation** - Pre-migration checks and compatibility testing
- **Backup & Recovery** - Automatic backups with rollback capabilities
- **Multi-tenant Support** - Enterprise-ready with tenant isolation
- **Extensive Testing** - 90%+ test coverage with Docker-based integration tests

## 📖 Documentation Conventions

### Code Examples
All code examples are tested and verified. Look for these indicators:
- ✅ **Tested** - Code has been tested in the development environment
- 🔧 **Configuration** - Configuration file examples
- 🌐 **API** - REST API examples
- 💻 **CLI** - Command-line interface examples

### Platform Support
- 🐧 **Linux** - Fully supported
- 🍎 **macOS** - Fully supported  
- 🪟 **Windows** - Supported with limitations (see platform-specific notes)

### Version Information
This documentation is for version **1.0.0** of the Migration Assistant. Version-specific features are clearly marked.

## 🆘 Getting Help

- **Documentation Issues**: [GitHub Issues](https://github.com/migration-assistant/migration-assistant/issues)
- **Community Support**: [GitHub Discussions](https://github.com/migration-assistant/migration-assistant/discussions)
- **Enterprise Support**: [Contact Us](mailto:support@migration-assistant.com)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.