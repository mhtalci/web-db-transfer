# CLI User Guide

The Migration Assistant CLI provides an interactive, user-friendly interface for managing migrations with Rich formatting, progress bars, and step-by-step guidance.

## 📋 Table of Contents

- [Basic Usage](#basic-usage)
- [Interactive Migration Wizard](#interactive-migration-wizard)
- [Command Reference](#command-reference)
- [Configuration Management](#configuration-management)
- [Preset Management](#preset-management)
- [Validation and Testing](#validation-and-testing)
- [Monitoring and Status](#monitoring-and-status)
- [Advanced Features](#advanced-features)

##  Basic Usage

### Getting Help
```bash
# Show main help
migration-assistant --help

# Show command-specific help
migration-assistant migrate --help
migration-assistant validate --help
migration-assistant status --help
```

### Version Information
```bash
# Show version
migration-assistant --version

# Show detailed version info
migration-assistant version --detailed
```

### Global Options
```bash
# Enable verbose output
migration-assistant --verbose migrate

# Quiet mode (minimal output)
migration-assistant --quiet migrate

# Custom config file
migration-assistant --config /path/to/config.yaml migrate
```

## 🧙‍♂️ Interactive Migration Wizard

The interactive wizard is the easiest way to set up and run migrations:

```bash
migration-assistant migrate
```

### Wizard Flow

#### Step 1: Welcome and Overview
```
 Web & Database Migration Assistant
   Version 1.0.0
   A comprehensive tool for migrating web applications and databases

✨ Features:                     Quick Actions:
• Interactive CLI              migration-assistant help --interactive
• REST API with async support  migration-assistant presets
• Multiple database types      migration-assistant migrate
• Cloud platform integrations migration-assistant serve
• Backup & rollback capabilities
• Comprehensive validation engine
```

#### Step 2: Source System Configuration
```
📍 Source System Configuration

Select your source system type:
❯ WordPress (with MySQL/MariaDB)
  Django (with PostgreSQL)
  Static Website (HTML/CSS/JS)
  Custom Database (MySQL/PostgreSQL/MongoDB)
  cPanel Hosting Account
  DirectAdmin Hosting Account
  Plesk Hosting Account
  Docker Container
  AWS S3 Bucket
  Google Cloud Storage
  Azure Blob Storage

Enter source details:
Host/IP Address: old-server.example.com
Port (optional): 22
Username: myuser
Authentication method:
❯ Password
  SSH Key
  API Token
```

#### Step 3: Database Configuration (if applicable)
```
🗄️ Database Configuration

Database Type: MySQL
Host: old-server.example.com
Port: 3306
Username: db_user
Password: [hidden]
Database Name: my_website_db

 Testing connection...  Connected successfully!
 Found 15 tables, 1.2GB of data
```

#### Step 4: Destination System Configuration
```
 Destination System Configuration

Select your destination system type:
❯ AWS S3 + RDS
  Google Cloud Storage + Cloud SQL
  Azure Blob + Azure Database
  DigitalOcean Spaces + Managed Database
  Custom Server (SSH/SFTP)
  Docker Container
  Kubernetes Cluster

AWS Configuration:
Region: us-east-1
S3 Bucket: my-new-website-bucket
RDS Instance: my-website-db-cluster
```

#### Step 5: Transfer Method Selection
```
🚚 Transfer Method Selection

Available methods for your configuration:
❯ Hybrid Sync (Python + Go acceleration) - Recommended
  SSH/SCP Transfer
  AWS S3 Sync
  rsync over SSH
  FTP/FTPS Transfer
  Direct Database Migration

Performance Options:
 Enable compression
 Parallel transfers (4 threads)
 Resume on interruption
 Verify checksums
```

#### Step 6: Safety and Backup Options
```
🛡️ Safety and Backup Options

Backup Settings:
 Create backup before migration
 Verify backup integrity
 Keep backups for 30 days

Rollback Settings:
 Enable automatic rollback on failure
 Create rollback plan
 Test rollback procedure

Validation Settings:
 Pre-migration validation
 Post-migration verification
 Data integrity checks
```

#### Step 7: Review and Confirmation
```
📋 Migration Summary

Source: WordPress on old-server.example.com
        MySQL database (15 tables, 1.2GB)
        File system (2.5GB, 1,247 files)

Destination: AWS S3 + Aurora MySQL
            Region: us-east-1
            Estimated cost: $12.50/month

Transfer: Hybrid Sync with Go acceleration
         Estimated time: 45 minutes
         Bandwidth usage: ~4GB

Safety: Full backup + automatic rollback enabled

 All validations passed
⚠️  1 warning: Large file detected (video.mp4 - 500MB)

Continue with migration? [Y/n]:
```

#### Step 8: Execution with Progress
```
 Starting Migration: WordPress to AWS

[1/8] Creating backups...                    ████████████████████ 100% 0:02:15
[2/8] Validating configuration...            ████████████████████ 100% 0:00:30
[3/8] Setting up destination...              ████████████████████ 100% 0:01:45
[4/8] Migrating database...                  ████████████████████ 100% 0:08:22
[5/8] Transferring files...                  ████████████████████ 100% 0:12:18
[6/8] Updating configurations...             ████████████████████ 100% 0:01:05
[7/8] Running post-migration tests...        ████████████████████ 100% 0:03:12
[8/8] Generating report...                   ████████████████████ 100% 0:00:45

 Migration completed successfully!
 Total time: 28 minutes 32 seconds
📈 Transfer rate: 2.1 MB/s average
 All verification checks passed

📄 Detailed report saved to: migration-report-20240826-143022.html
🔗 New site URL: https://my-new-website-bucket.s3-website-us-east-1.amazonaws.com
```

##  Command Reference

### migrate
Start a migration process with various options:

```bash
# Interactive wizard (default)
migration-assistant migrate

# Use a preset
migration-assistant migrate --preset wordpress-mysql

# Use configuration file
migration-assistant migrate --config my-migration.yaml

# Non-interactive mode
migration-assistant migrate --non-interactive --config my-migration.yaml

# Dry run (no actual changes)
migration-assistant migrate --dry-run --config my-migration.yaml

# Custom options
migration-assistant migrate \
  --preset wordpress-mysql \
  --backup \
  --verify \
  --parallel 8 \
  --timeout 3600
```

**Options:**
- `--config, -c PATH` - Configuration file path
- `--preset, -p NAME` - Use migration preset
- `--dry-run` - Perform dry run without changes
- `--interactive/--non-interactive` - Interactive mode (default: interactive)
- `--backup/--no-backup` - Create backup before migration
- `--verify/--no-verify` - Verify migration after completion
- `--parallel N` - Number of parallel transfers (default: 4)
- `--timeout N` - Timeout in seconds (default: 3600)
- `--resume SESSION_ID` - Resume interrupted migration

### validate
Validate migration configuration:

```bash
# Validate configuration file
migration-assistant validate --config my-migration.yaml

# Validate with preset
migration-assistant validate --preset wordpress-mysql

# Quick connectivity test
migration-assistant validate --quick --config my-migration.yaml

# Detailed validation report
migration-assistant validate --detailed --config my-migration.yaml
```

**Options:**
- `--config, -c PATH` - Configuration file to validate
- `--preset, -p NAME` - Preset to validate
- `--quick` - Quick validation (connectivity only)
- `--detailed` - Detailed validation report
- `--fix` - Attempt to fix common issues
- `--output FORMAT` - Output format (table, json, yaml)

### status
Check migration status and history:

```bash
# Show all migrations
migration-assistant status

# Show specific migration
migration-assistant status --session SESSION_ID

# Show running migrations only
migration-assistant status --running

# Show failed migrations
migration-assistant status --failed

# Continuous monitoring
migration-assistant status --watch --session SESSION_ID
```

**Options:**
- `--session, -s ID` - Specific session ID
- `--running` - Show only running migrations
- `--failed` - Show only failed migrations
- `--completed` - Show only completed migrations
- `--watch, -w` - Continuous monitoring mode
- `--refresh N` - Refresh interval in seconds (default: 5)

### presets
Manage migration presets:

```bash
# List all presets
migration-assistant presets

# Show preset details
migration-assistant presets --show wordpress-mysql

# Create custom preset
migration-assistant presets --create my-custom-preset --config my-config.yaml

# Update existing preset
migration-assistant presets --update my-custom-preset --config updated-config.yaml

# Delete preset
migration-assistant presets --delete my-custom-preset

# Export preset
migration-assistant presets --export wordpress-mysql --output wordpress-preset.yaml
```

**Options:**
- `--show NAME` - Show preset configuration
- `--create NAME` - Create new preset
- `--update NAME` - Update existing preset
- `--delete NAME` - Delete preset
- `--export NAME` - Export preset to file
- `--import FILE` - Import preset from file
- `--config PATH` - Configuration file for create/update

### rollback
Rollback completed or failed migrations:

```bash
# Rollback specific migration
migration-assistant rollback --session SESSION_ID

# List rollback options
migration-assistant rollback --list --session SESSION_ID

# Rollback to specific backup
migration-assistant rollback --session SESSION_ID --backup BACKUP_ID

# Dry run rollback
migration-assistant rollback --dry-run --session SESSION_ID
```

**Options:**
- `--session, -s ID` - Session ID to rollback
- `--backup, -b ID` - Specific backup to restore
- `--list` - List available rollback options
- `--dry-run` - Test rollback without changes
- `--force` - Force rollback even if risky

### config
Manage configuration files:

```bash
# Generate sample configuration
migration-assistant config --generate --output sample-config.yaml

# Validate configuration syntax
migration-assistant config --validate my-config.yaml

# Convert between formats
migration-assistant config --convert my-config.yaml --output my-config.json

# Encrypt sensitive values
migration-assistant config --encrypt my-config.yaml --output encrypted-config.yaml

# Show configuration schema
migration-assistant config --schema
```

**Options:**
- `--generate` - Generate sample configuration
- `--validate FILE` - Validate configuration file
- `--convert FILE` - Convert configuration format
- `--encrypt FILE` - Encrypt sensitive values
- `--decrypt FILE` - Decrypt configuration
- `--schema` - Show configuration schema
- `--output, -o FILE` - Output file path

### serve
Start the API server:

```bash
# Start with defaults
migration-assistant serve

# Custom host and port
migration-assistant serve --host 0.0.0.0 --port 8080

# Enable authentication
migration-assistant serve --auth-enabled --jwt-secret my-secret

# Development mode
migration-assistant serve --dev --reload

# Production mode
migration-assistant serve --workers 4 --log-level info
```

**Options:**
- `--host HOST` - Host to bind (default: 127.0.0.1)
- `--port PORT` - Port to bind (default: 8000)
- `--workers N` - Number of worker processes
- `--auth-enabled` - Enable authentication
- `--jwt-secret SECRET` - JWT secret key
- `--dev` - Development mode
- `--reload` - Auto-reload on changes
- `--log-level LEVEL` - Logging level

### logs
View and manage logs:

```bash
# Show recent logs
migration-assistant logs

# Follow logs in real-time
migration-assistant logs --follow

# Show logs for specific session
migration-assistant logs --session SESSION_ID

# Filter by log level
migration-assistant logs --level ERROR

# Export logs
migration-assistant logs --export --output migration-logs.txt
```

**Options:**
- `--follow, -f` - Follow logs in real-time
- `--session, -s ID` - Filter by session ID
- `--level LEVEL` - Filter by log level
- `--lines, -n N` - Number of lines to show
- `--export` - Export logs to file
- `--format FORMAT` - Output format (text, json)

## ⚙️ Configuration Management

### Configuration File Format
The CLI supports YAML, JSON, and TOML configuration files:

```yaml
# migration-config.yaml
name: "My Website Migration"
description: "Migrating WordPress site to AWS"

source:
  type: wordpress
  host: old-server.com
  port: 22
  username: myuser
  password: "${SOURCE_PASSWORD}"  # Environment variable
  paths:
    web_root: /var/www/html
    uploads: /var/www/html/wp-content/uploads
  database:
    type: mysql
    host: old-server.com
    port: 3306
    username: wp_user
    password: "${DB_PASSWORD}"
    database: wordpress_db

destination:
  type: aws-s3
  region: us-east-1
  bucket: my-new-website
  database:
    type: aurora-mysql
    cluster: my-website-cluster
    username: admin
    password: "${DEST_DB_PASSWORD}"

transfer:
  method: hybrid_sync
  options:
    compression: true
    parallel_transfers: 4
    chunk_size: "10MB"
    resume_on_failure: true
    verify_checksums: true

safety:
  backup_before: true
  backup_retention_days: 30
  rollback_on_failure: true
  verify_after: true
  maintenance_mode: true

notifications:
  email:
    enabled: true
    recipients: ["admin@example.com"]
    smtp_server: smtp.gmail.com
    smtp_port: 587
    username: notifications@example.com
    password: "${SMTP_PASSWORD}"
  slack:
    enabled: true
    webhook_url: "${SLACK_WEBHOOK}"
    channel: "#migrations"

performance:
  use_go_engine: true
  max_memory_usage: "2GB"
  temp_directory: "/tmp/migration-assistant"
  log_level: INFO
```

### Environment Variables
Sensitive values can be stored in environment variables:

```bash
# Database passwords
export SOURCE_PASSWORD="source_db_password"
export DB_PASSWORD="wordpress_db_password"
export DEST_DB_PASSWORD="aurora_admin_password"

# API keys and tokens
export AWS_ACCESS_KEY_ID="your_aws_key"
export AWS_SECRET_ACCESS_KEY="your_aws_secret"
export SLACK_WEBHOOK="https://hooks.slack.com/services/..."

# SMTP credentials
export SMTP_PASSWORD="your_smtp_password"
```

### Configuration Validation
```bash
# Validate configuration syntax
migration-assistant config --validate my-config.yaml

# Output:
 Configuration is valid
 Found 1 source system (WordPress)
 Found 1 destination system (AWS S3)
 Transfer method: hybrid_sync
⚠️  Warning: Large parallel_transfers value may impact performance
 Suggestion: Consider reducing parallel_transfers to 2-4 for better stability
```

##  Preset Management

### Built-in Presets
```bash
# List all available presets
migration-assistant presets

# Output:
Available Migration Presets:

📱 CMS & Frameworks:
  wordpress-mysql     WordPress with MySQL database
  wordpress-postgres  WordPress with PostgreSQL database
  drupal-mysql       Drupal with MySQL database
  django-postgres    Django application with PostgreSQL
  laravel-mysql      Laravel application with MySQL
  rails-postgres     Ruby on Rails with PostgreSQL

☁️ Cloud Platforms:
  static-s3          Static website to AWS S3
  static-gcs         Static website to Google Cloud Storage
  static-azure       Static website to Azure Blob Storage
  cpanel-aws         cPanel hosting to AWS infrastructure
  shared-vps         Shared hosting to VPS

🗄️ Database Only:
  mysql-postgres     MySQL to PostgreSQL migration
  postgres-mysql     PostgreSQL to MySQL migration
  mongo-postgres     MongoDB to PostgreSQL migration
  redis-postgres     Redis to PostgreSQL migration

🐳 Containers:
  docker-k8s         Docker container to Kubernetes
  vm-docker          Virtual machine to Docker container
```

### Using Presets
```bash
# Use preset with interactive wizard
migration-assistant migrate --preset wordpress-mysql

# Use preset with custom overrides
migration-assistant migrate --preset wordpress-mysql \
  --override source.host=my-old-server.com \
  --override destination.bucket=my-new-bucket
```

### Creating Custom Presets
```bash
# Create preset from existing configuration
migration-assistant presets --create my-custom-preset --config my-config.yaml

# Create preset interactively
migration-assistant presets --create my-custom-preset --interactive
```

### Sharing Presets
```bash
# Export preset to file
migration-assistant presets --export wordpress-mysql --output wordpress-preset.yaml

# Import preset from file
migration-assistant presets --import wordpress-preset.yaml

# Share preset via URL
migration-assistant presets --share my-custom-preset
# Output: https://presets.migration-assistant.com/share/abc123
```

##  Validation and Testing

### Pre-Migration Validation
```bash
# Quick connectivity test
migration-assistant validate --quick --config my-config.yaml

# Output:
 Quick Validation Results:

 Source connectivity (old-server.com:22)
 Source database connectivity (MySQL)
 Destination connectivity (AWS S3)
 Destination database connectivity (Aurora MySQL)
 Required tools available (rsync, mysql, aws-cli)
 Sufficient disk space (10GB available, 4GB required)

 Ready to proceed with migration!
```

### Detailed Validation
```bash
# Comprehensive validation
migration-assistant validate --detailed --config my-config.yaml

# Output:
📋 Detailed Validation Report:

🔗 Connectivity Tests:
   Source SSH connection (old-server.com:22) - 45ms
   Source MySQL connection (old-server.com:3306) - 23ms
   AWS S3 bucket access (my-new-website) - 156ms
   Aurora MySQL cluster access (my-website-cluster) - 89ms

 System Requirements:
   Python 3.11+ (found 3.11.5)
   Go 1.21+ (found 1.21.3)
   rsync (found 3.2.7)
   mysql client (found 8.0.34)
   aws-cli (found 2.13.25)

💾 Storage Analysis:
   Source disk usage: 4.2GB (15,847 files)
   Available temp space: 25GB
   Destination storage: Unlimited (S3)
  ⚠️  Large files detected: 3 files > 100MB

🗄️ Database Analysis:
   Source: MySQL 8.0.34 (15 tables, 1.2GB)
   Destination: Aurora MySQL 8.0 compatible
   Schema compatibility: 100%
   Character set compatibility: utf8mb4

🔐 Security Checks:
   SSH key authentication configured
   Database connections encrypted
   AWS credentials valid
  ⚠️  Source server allows password authentication

 Performance Estimates:
  🕐 Estimated migration time: 35-45 minutes
  📈 Expected transfer rate: 2-3 MB/s
  💰 Estimated AWS costs: $0.15 for transfer

 Recommendations:
   Enable Go acceleration for 2x faster transfers
   Consider disabling password auth on source server
   Schedule migration during low-traffic hours
```

### Dry Run Testing
```bash
# Test migration without making changes
migration-assistant migrate --dry-run --config my-config.yaml

# Output:
🧪 Dry Run Mode - No changes will be made

[1/8] Would create backup of source system
      📁 Files: /tmp/backup-20240826-143022-files.tar.gz (4.2GB)
      🗄️ Database: /tmp/backup-20240826-143022-db.sql (1.2GB)

[2/8] Would validate all connections and requirements
       All validations would pass

[3/8] Would create S3 bucket: my-new-website
      📍 Region: us-east-1
       Encryption: AES-256

[4/8] Would migrate database (15 tables)
       Estimated time: 8-12 minutes
      🔄 Method: mysqldump + mysql restore

[5/8] Would transfer files (15,847 files)
       Estimated time: 20-25 minutes
      🔄 Method: hybrid_sync (Go accelerated)

[6/8] Would update configuration files
      📝 wp-config.php database settings
      📝 .htaccess URL redirects

[7/8] Would run verification tests
       Database integrity checks
       File checksum verification
       Website functionality tests

[8/8] Would generate migration report
      📄 HTML report with detailed results

 Dry run completed successfully!
 Run without --dry-run to execute actual migration
```

##  Monitoring and Status

### Real-time Status Monitoring
```bash
# Watch migration progress
migration-assistant status --watch --session abc123

# Output (updates every 5 seconds):
 Migration Status: abc123

 Overall Progress: ████████████████████ 65% (5/8 steps completed)
⏱️  Elapsed Time: 18m 32s
⏱️  Estimated Remaining: 12m 15s

Current Step: [5/8] Transferring files
Progress: ████████████████░░░░ 78% (12.1GB / 15.5GB)
Rate: 2.3 MB/s (avg: 2.1 MB/s)
ETA: 8m 45s

📁 Files: 12,847 / 15,847 transferred
🗄️ Database:  Completed (8m 22s)
 Verification: ⏳ Pending

Recent Activity:
18:45:23 - Transferred wp-content/uploads/2024/08/image.jpg (2.1MB)
18:45:22 - Transferred wp-content/themes/mytheme/style.css (45KB)
18:45:21 - Transferred wp-content/plugins/plugin.zip (1.8MB)

Press Ctrl+C to stop monitoring (migration will continue)
```

### Migration History
```bash
# Show all migrations
migration-assistant status

# Output:
📋 Migration History:

Recent Migrations:
┌─────────────┬──────────────────────┬──────────┬─────────────┬──────────────┐
│ Session ID  │ Name                 │ Status   │ Started     │ Duration     │
├─────────────┼──────────────────────┼──────────┼─────────────┼──────────────┤
│ abc123      │ WordPress to AWS     │ Running  │ 18:27:15    │ 18m 32s      │
│ def456      │ Django to GCP        │ Complete │ 14:15:30    │ 42m 18s      │
│ ghi789      │ Static to S3         │ Complete │ 12:08:45    │ 8m 12s       │
│ jkl012      │ MySQL to Postgres    │ Failed   │ 10:30:22    │ 15m 8s       │
└─────────────┴──────────────────────┴──────────┴─────────────┴──────────────┘

Summary:
 Completed: 2 migrations
🔄 Running: 1 migration
 Failed: 1 migration
 Success Rate: 66.7%
```

### Detailed Session Information
```bash
# Show detailed session info
migration-assistant status --session abc123

# Output:
📋 Migration Session: abc123

General Information:
  Name: WordPress to AWS
  Created: 2024-08-26 18:27:15
  Started: 2024-08-26 18:27:30
  Status: Running
  Duration: 18m 32s

Configuration:
  Source: WordPress (old-server.com)
  Destination: AWS S3 + Aurora MySQL
  Method: hybrid_sync
  Backup: Enabled
  Verification: Enabled

Progress Details:
  [] 1. Create backups (2m 15s)
  [] 2. Validate configuration (30s)
  [] 3. Setup destination (1m 45s)
  [] 4. Migrate database (8m 22s)
  [🔄] 5. Transfer files (6m 20s / ~15m) - 78%
  [⏳] 6. Update configurations
  [⏳] 7. Run verification tests
  [⏳] 8. Generate report

Performance Metrics:
  Transfer Rate: 2.3 MB/s (current), 2.1 MB/s (average)
  Files Transferred: 12,847 / 15,847 (81%)
  Data Transferred: 12.1GB / 15.5GB (78%)
  Errors: 0
  Retries: 3

Recent Logs:
  18:45:23 INFO  - Transferred wp-content/uploads/2024/08/image.jpg
  18:45:22 INFO  - Transferred wp-content/themes/mytheme/style.css
  18:45:21 INFO  - Transferred wp-content/plugins/plugin.zip
  18:45:20 WARN  - Retrying transfer for large-file.mp4 (attempt 2/3)
```

##  Advanced Features

### Parallel Processing
```bash
# Use multiple parallel transfers
migration-assistant migrate --parallel 8 --config my-config.yaml

# Adjust based on system resources
migration-assistant migrate --parallel auto --config my-config.yaml
```

### Resume Interrupted Migrations
```bash
# Resume from last checkpoint
migration-assistant migrate --resume abc123

# Resume with different settings
migration-assistant migrate --resume abc123 --parallel 2
```

### Custom Scripts and Hooks
```yaml
# In configuration file
hooks:
  pre_migration:
    - script: "./scripts/pre-migration-backup.sh"
      timeout: 300
  post_migration:
    - script: "./scripts/update-dns.sh"
      timeout: 60
    - script: "./scripts/notify-team.py"
      timeout: 30
  on_failure:
    - script: "./scripts/emergency-rollback.sh"
      timeout: 600
```

### Performance Tuning
```bash
# Enable Go acceleration
migration-assistant migrate --use-go-engine --config my-config.yaml

# Adjust memory usage
migration-assistant migrate --max-memory 4GB --config my-config.yaml

# Custom temporary directory
migration-assistant migrate --temp-dir /fast-ssd/temp --config my-config.yaml
```

### Batch Operations
```bash
# Process multiple configurations
migration-assistant migrate --batch configs/*.yaml

# Parallel batch processing
migration-assistant migrate --batch configs/*.yaml --batch-parallel 3
```

### Integration with CI/CD
```bash
# Non-interactive mode for automation
migration-assistant migrate \
  --non-interactive \
  --config production-migration.yaml \
  --output-format json \
  --log-file migration.log

# Exit codes for scripting
if migration-assistant validate --config my-config.yaml; then
    echo "Configuration is valid"
    migration-assistant migrate --config my-config.yaml
else
    echo "Configuration validation failed"
    exit 1
fi
```

## 🎨 Output Formatting

### Rich Console Output
The CLI uses Rich formatting for enhanced readability:

- **Progress Bars**: Real-time progress with ETA
- **Tables**: Structured data display
- **Syntax Highlighting**: Configuration files and logs
- **Icons and Colors**: Visual status indicators
- **Panels and Columns**: Organized information layout

### Output Formats
```bash
# Table format (default)
migration-assistant status --format table

# JSON format for scripting
migration-assistant status --format json

# YAML format
migration-assistant status --format yaml

# CSV format for spreadsheets
migration-assistant status --format csv
```

### Logging Levels
```bash
# Debug level (very verbose)
migration-assistant --log-level DEBUG migrate

# Info level (default)
migration-assistant --log-level INFO migrate

# Warning level (minimal output)
migration-assistant --log-level WARNING migrate

# Error level (errors only)
migration-assistant --log-level ERROR migrate
```

This comprehensive CLI guide covers all aspects of using the Migration Assistant command-line interface. For API usage, see the [API User Guide](api-guide.md), and for specific migration scenarios, check the [Migration Guides](../migration-guides/) section.