# Troubleshooting Guide

This comprehensive troubleshooting guide covers common issues, error messages, and solutions for the Web & Database Migration Assistant.

## 📋 Table of Contents

- [General Troubleshooting](#general-troubleshooting)
- [Installation Issues](#installation-issues)
- [Connection Problems](#connection-problems)
- [Authentication Errors](#authentication-errors)
- [Migration Failures](#migration-failures)
- [Performance Issues](#performance-issues)
- [API-Specific Issues](#api-specific-issues)
- [Control Panel Issues](#control-panel-issues)
- [Database Migration Issues](#database-migration-issues)
- [File Transfer Issues](#file-transfer-issues)
- [Logging and Debugging](#logging-and-debugging)

## 🔧 General Troubleshooting

### Quick Diagnostic Commands
```bash
# Check system health
migration-assistant health

# Validate configuration
migration-assistant validate --config your-config.yaml

# Test connectivity
migration-assistant validate --quick --config your-config.yaml

# Check logs
migration-assistant logs --level ERROR --lines 50

# Show version and dependencies
migration-assistant version --detailed
```

### Common Error Patterns

#### Error: "Command not found: migration-assistant"
**Cause**: Migration Assistant not installed or not in PATH
**Solutions**:
```bash
# Check if installed
pip list | grep migration-assistant

# Install if missing
pip install web-database-migration-assistant

# Check PATH
echo $PATH
which migration-assistant

# Reinstall if needed
pip uninstall web-database-migration-assistant
pip install web-database-migration-assistant
```

#### Error: "Permission denied"
**Cause**: Insufficient permissions for file access or execution
**Solutions**:
```bash
# Check file permissions
ls -la /path/to/files

# Fix permissions
chmod +x migration-assistant
sudo chown $USER:$USER /path/to/files

# Run with appropriate user
sudo -u www-data migration-assistant migrate

# Use SSH key instead of password
migration-assistant migrate --ssh-key ~/.ssh/id_rsa
```

#### Error: "Module not found" or Import errors
**Cause**: Missing dependencies or virtual environment issues
**Solutions**:
```bash
# Check Python version
python --version  # Should be 3.11+

# Check virtual environment
which python
pip list

# Reinstall dependencies
pip install -r requirements.txt

# Clear pip cache
pip cache purge
pip install --no-cache-dir web-database-migration-assistant
```

## 🚀 Installation Issues

### Python Version Compatibility
**Issue**: "Python version not supported"
**Solution**:
```bash
# Check Python version
python --version

# Install Python 3.11+ if needed (Ubuntu/Debian)
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev

# Install Python 3.11+ (macOS with Homebrew)
brew install python@3.11

# Create virtual environment with correct Python
python3.11 -m venv venv
source venv/bin/activate
pip install web-database-migration-assistant
```

### Compilation Errors
**Issue**: "Failed building wheel" or "Microsoft Visual C++ required"
**Solutions**:

**Linux (Ubuntu/Debian)**:
```bash
# Install build dependencies
sudo apt-get update
sudo apt-get install python3-dev libpq-dev libmysqlclient-dev build-essential

# Install system libraries
sudo apt-get install libssl-dev libffi-dev libxml2-dev libxslt1-dev
```

**macOS**:
```bash
# Install Xcode command line tools
xcode-select --install

# Install dependencies with Homebrew
brew install postgresql mysql-client openssl libffi

# Set environment variables
export LDFLAGS="-L$(brew --prefix openssl)/lib"
export CPPFLAGS="-I$(brew --prefix openssl)/include"
```

**Windows**:
```bash
# Install Microsoft C++ Build Tools
# Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/

# Or use pre-compiled wheels
pip install --only-binary=all web-database-migration-assistant
```

### Docker Installation Issues
**Issue**: Docker container fails to start
**Solutions**:
```bash
# Check Docker installation
docker --version
docker info

# Pull latest image
docker pull migration-assistant/migration-assistant:latest

# Run with proper permissions
docker run --rm -it \
  -v $(pwd):/workspace \
  -v ~/.ssh:/root/.ssh:ro \
  migration-assistant/migration-assistant:latest

# Check container logs
docker logs container_id
```

## 🌐 Connection Problems

### SSH Connection Issues
**Issue**: "SSH connection failed" or "Connection timeout"
**Diagnosis**:
```bash
# Test SSH connection manually
ssh -v user@hostname

# Test with specific port
ssh -p 2222 user@hostname

# Test SSH key
ssh -i ~/.ssh/id_rsa user@hostname
```

**Solutions**:
```yaml
# In configuration file
source:
  host: your-server.com
  port: 22
  username: user
  ssh_key: ~/.ssh/id_rsa
  ssh_options:
    StrictHostKeyChecking: no
    ConnectTimeout: 30
    ServerAliveInterval: 60
```

### Database Connection Issues
**Issue**: "Database connection failed"
**Diagnosis**:
```bash
# Test MySQL connection
mysql -h hostname -P 3306 -u username -p database_name

# Test PostgreSQL connection
psql -h hostname -p 5432 -U username -d database_name

# Test MongoDB connection
mongo mongodb://username:password@hostname:27017/database_name
```

**Solutions**:
```yaml
# Database configuration with connection options
database:
  type: mysql
  host: db-server.com
  port: 3306
  username: user
  password: pass
  database: mydb
  connection_options:
    connect_timeout: 30
    read_timeout: 60
    charset: utf8mb4
    ssl_disabled: false
```

### Firewall and Network Issues
**Issue**: "Connection refused" or "Network unreachable"
**Diagnosis**:
```bash
# Test port connectivity
telnet hostname 22
nc -zv hostname 22

# Check DNS resolution
nslookup hostname
dig hostname

# Test with different network
ping hostname
traceroute hostname
```

**Solutions**:
```bash
# Use SSH tunnel for database connections
ssh -L 3306:localhost:3306 user@jump-server

# Configure proxy settings
export HTTP_PROXY=http://proxy:8080
export HTTPS_PROXY=http://proxy:8080

# Use VPN if required
# Connect to VPN before running migration
```

## 🔐 Authentication Errors

### SSH Key Authentication
**Issue**: "SSH key authentication failed"
**Solutions**:
```bash
# Check SSH key permissions
chmod 600 ~/.ssh/id_rsa
chmod 644 ~/.ssh/id_rsa.pub

# Add key to SSH agent
ssh-add ~/.ssh/id_rsa

# Test key authentication
ssh -i ~/.ssh/id_rsa user@hostname

# Generate new key if needed
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
```

### API Authentication Issues
**Issue**: "Authentication failed" or "Invalid token"
**Solutions**:
```bash
# Check API token
curl -H "X-API-Key: your-api-key" http://localhost:8000/health

# Get new JWT token
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "user", "password": "pass"}'

# Verify token expiration
# JWT tokens expire after 24 hours by default
```

### Cloud Provider Authentication
**Issue**: "AWS/GCP/Azure authentication failed"
**Solutions**:

**AWS**:
```bash
# Check AWS credentials
aws configure list
aws sts get-caller-identity

# Set credentials
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_DEFAULT_REGION="us-east-1"
```

**Google Cloud**:
```bash
# Check GCP authentication
gcloud auth list
gcloud config list

# Authenticate
gcloud auth login
gcloud auth application-default login
```

**Azure**:
```bash
# Check Azure authentication
az account show
az account list

# Login
az login
```

## ❌ Migration Failures

### Migration Stuck or Hanging
**Issue**: Migration appears to hang or make no progress
**Diagnosis**:
```bash
# Check migration status
migration-assistant status --session SESSION_ID

# Check system resources
top
df -h
free -m

# Check network activity
netstat -an | grep ESTABLISHED
```

**Solutions**:
```bash
# Cancel and restart migration
migration-assistant cancel --session SESSION_ID
migration-assistant migrate --resume SESSION_ID

# Reduce parallel transfers
migration-assistant migrate --parallel 2 --config your-config.yaml

# Increase timeouts
migration-assistant migrate --timeout 7200 --config your-config.yaml
```

### Partial Migration Failures
**Issue**: Some files or data not migrated
**Diagnosis**:
```bash
# Check migration logs
migration-assistant logs --session SESSION_ID --level WARNING

# Compare source and destination
migration-assistant validate --post-migration --session SESSION_ID
```

**Solutions**:
```bash
# Resume from last checkpoint
migration-assistant migrate --resume SESSION_ID

# Retry failed items only
migration-assistant migrate --retry-failed --session SESSION_ID

# Manual verification and fix
migration-assistant migrate --verify-only --session SESSION_ID
```

### Rollback Issues
**Issue**: Rollback fails or incomplete
**Solutions**:
```bash
# Check available backups
migration-assistant rollback --list --session SESSION_ID

# Force rollback with specific backup
migration-assistant rollback --force --backup BACKUP_ID --session SESSION_ID

# Manual rollback steps
migration-assistant rollback --manual --session SESSION_ID
```

## ⚡ Performance Issues

### Slow Transfer Speeds
**Issue**: File transfers are slower than expected
**Diagnosis**:
```bash
# Check network bandwidth
speedtest-cli

# Monitor transfer in real-time
migration-assistant status --watch --session SESSION_ID

# Check system resources
iostat 1
iotop
```

**Solutions**:
```yaml
# Optimize transfer settings
transfer:
  method: hybrid_sync  # Use Go acceleration
  options:
    parallel_transfers: 8  # Increase parallelism
    compression: true      # Enable compression
    chunk_size: "50MB"     # Larger chunks
    tcp_window_size: "64KB"
```

### High Memory Usage
**Issue**: Migration consumes too much memory
**Solutions**:
```yaml
# Limit memory usage
performance:
  max_memory_usage: "2GB"
  streaming_mode: true
  batch_size: 1000
  temp_directory: "/tmp"  # Use fast storage
```

### Database Migration Slow
**Issue**: Database migration takes too long
**Solutions**:
```yaml
# Optimize database migration
database_migration:
  method: parallel_dump
  parallel_jobs: 4
  chunk_size: 10000
  disable_indexes: true  # Rebuild after migration
  skip_triggers: true
```

## 🌐 API-Specific Issues

### API Server Won't Start
**Issue**: "Address already in use" or server startup fails
**Solutions**:
```bash
# Check port usage
lsof -i :8000
netstat -tulpn | grep 8000

# Kill existing process
kill -9 PID

# Use different port
migration-assistant serve --port 8080

# Check configuration
migration-assistant serve --check-config
```

### API Timeouts
**Issue**: API requests timeout
**Solutions**:
```bash
# Increase timeout settings
migration-assistant serve --timeout 300

# Use async endpoints for long operations
# POST /migrations/{id}/start instead of synchronous calls

# Check server logs
migration-assistant logs --api --level ERROR
```

### WebSocket Connection Issues
**Issue**: Real-time updates not working
**Solutions**:
```javascript
// Check WebSocket connection
const ws = new WebSocket('ws://localhost:8000/ws/migrations/session_id');

ws.onerror = function(error) {
    console.error('WebSocket error:', error);
    // Fallback to polling
    setInterval(() => {
        fetch('/migrations/session_id/status')
            .then(response => response.json())
            .then(data => updateUI(data));
    }, 5000);
};
```

## 🎛️ Control Panel Issues

### cPanel API Issues
**Issue**: "cPanel API authentication failed"
**Solutions**:
```bash
# Test cPanel API access
curl -H "Authorization: cpanel username:api_token" \
     "https://your-server.com:2083/execute/Mysql/list_databases"

# Check API token permissions
# Ensure token has required permissions in cPanel

# Use username/password if token fails
export CPANEL_USERNAME="user"
export CPANEL_PASSWORD="pass"
```

### DirectAdmin Connection Issues
**Issue**: "DirectAdmin API connection failed"
**Solutions**:
```bash
# Test DirectAdmin API
curl -u "username:password" \
     "https://your-server.com:2222/CMD_API_DATABASES"

# Check SSL certificate
curl -k -u "username:password" \
     "https://your-server.com:2222/CMD_API_DATABASES"

# Use HTTP if HTTPS fails
export DA_USE_SSL=false
```

### Plesk API Problems
**Issue**: "Plesk API authentication failed"
**Solutions**:
```bash
# Test Plesk API
curl -H "X-API-Key: your_api_key" \
     "https://plesk-server.com:8443/api/v2/domains"

# Check API key permissions
# Ensure API key has required permissions in Plesk

# Use admin credentials if API key fails
export PLESK_USERNAME="admin"
export PLESK_PASSWORD="admin_pass"
```

## 🗄️ Database Migration Issues

### Character Set Issues
**Issue**: "Character set conversion errors"
**Solutions**:
```yaml
# Specify character sets explicitly
database:
  source:
    charset: utf8mb4
    collation: utf8mb4_unicode_ci
  destination:
    charset: utf8mb4
    collation: utf8mb4_unicode_ci
  migration_options:
    preserve_charset: true
    convert_charset: false
```

### Large Database Issues
**Issue**: "Database too large to migrate"
**Solutions**:
```yaml
# Use streaming migration
database_migration:
  method: streaming
  chunk_size: 10000
  parallel_streams: 4
  compression: true
  exclude_tables:
    - "logs"
    - "cache"
    - "sessions"
```

### Foreign Key Constraints
**Issue**: "Foreign key constraint errors"
**Solutions**:
```yaml
# Handle foreign keys properly
database_migration:
  disable_foreign_keys: true
  migration_order:
    - parent_tables
    - child_tables
  post_migration:
    - enable_foreign_keys
    - verify_constraints
```

## 📁 File Transfer Issues

### Permission Errors
**Issue**: "Permission denied" during file transfer
**Solutions**:
```bash
# Check source permissions
ls -la /path/to/files

# Use appropriate user
sudo -u www-data migration-assistant migrate

# Fix permissions before migration
find /path/to/files -type f -exec chmod 644 {} \;
find /path/to/files -type d -exec chmod 755 {} \;
```

### Large File Issues
**Issue**: "Large file transfer fails"
**Solutions**:
```yaml
# Configure large file handling
transfer:
  options:
    large_file_threshold: "1GB"
    large_file_method: "multipart"
    chunk_size: "100MB"
    resume_on_failure: true
    verify_checksums: true
```

### Symbolic Link Issues
**Issue**: "Symbolic links not handled correctly"
**Solutions**:
```yaml
# Configure symlink handling
transfer:
  options:
    follow_symlinks: true
    preserve_symlinks: false
    resolve_symlinks: true
```

## 📊 Logging and Debugging

### Enable Debug Logging
```bash
# CLI debug mode
migration-assistant --log-level DEBUG migrate --config your-config.yaml

# API debug mode
migration-assistant serve --log-level DEBUG

# Save logs to file
migration-assistant migrate --log-file migration-debug.log --config your-config.yaml
```

### Log Analysis
```bash
# Search for errors
grep -i error migration.log

# Search for specific session
grep "SESSION_ID" migration.log

# Count error types
grep -i "error\|warning\|failed" migration.log | sort | uniq -c

# Monitor logs in real-time
tail -f migration.log | grep -i error
```

### Debug Configuration
```yaml
# Add debug settings to config
debug:
  enabled: true
  log_level: DEBUG
  log_requests: true
  log_responses: true
  save_temp_files: true
  temp_directory: "/tmp/migration-debug"
```

### Performance Profiling
```bash
# Profile Python performance
python -m cProfile -o migration.prof migration_assistant/cli/main.py migrate

# Analyze profile
python -c "import pstats; pstats.Stats('migration.prof').sort_stats('cumulative').print_stats(20)"

# Memory profiling
pip install memory-profiler
python -m memory_profiler migration_assistant/cli/main.py migrate
```

## 🆘 Getting Help

### Collect Diagnostic Information
```bash
# Generate diagnostic report
migration-assistant diagnose --output diagnostic-report.zip

# Include system information
migration-assistant diagnose --include-system --output full-diagnostic.zip
```

### Support Channels
1. **GitHub Issues**: [Report bugs and feature requests](https://github.com/migration-assistant/migration-assistant/issues)
2. **GitHub Discussions**: [Ask questions and get community help](https://github.com/migration-assistant/migration-assistant/discussions)
3. **Documentation**: [Browse complete documentation](https://docs.migration-assistant.com)
4. **Enterprise Support**: [Contact enterprise support](mailto:support@migration-assistant.com)

### Before Contacting Support
Please include:
- Migration Assistant version (`migration-assistant --version`)
- Operating system and version
- Python version
- Complete error messages
- Configuration file (with sensitive data removed)
- Log files (if available)
- Steps to reproduce the issue

This troubleshooting guide covers the most common issues. For additional help with specific scenarios, consult the relevant guides in the [Migration Guides](../migration-guides/) section or contact support.