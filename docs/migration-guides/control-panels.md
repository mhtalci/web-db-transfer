# Control Panel Migration Guide

This guide covers migrating from popular hosting control panels (cPanel, DirectAdmin, and Plesk) to modern cloud infrastructure or other hosting environments.

## 📋 Table of Contents

- [Overview](#overview)
- [cPanel Migrations](#cpanel-migrations)
- [DirectAdmin Migrations](#directadmin-migrations)
- [Plesk Migrations](#plesk-migrations)
- [Common Migration Patterns](#common-migration-patterns)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## 🌐 Overview

Control panel migrations involve extracting websites, databases, email accounts, and configurations from managed hosting environments and migrating them to new platforms. The Migration Assistant provides native API integration for major control panels.

### Supported Control Panels
- **cPanel/WHM** - API v2/UAPI integration
- **DirectAdmin** - Native API integration  
- **Plesk** - REST API integration

### Common Migration Destinations
- **Cloud Platforms**: AWS, Google Cloud, Azure
- **VPS/Dedicated Servers**: With or without control panels
- **Container Platforms**: Docker, Kubernetes
- **Static Hosting**: Netlify, Vercel, GitHub Pages
- **Managed Hosting**: WordPress.com, Shopify, etc.

## 🔧 cPanel Migrations

### Prerequisites
- cPanel API access (API Token or Username/Password)
- WHM access (for reseller accounts)
- SSH access (optional, for file system access)
- Database access credentials

### Authentication Setup

#### API Token Method (Recommended)
```bash
# Generate API token in cPanel
# Security → Manage API Tokens → Create Token

export CPANEL_API_TOKEN="your_api_token_here"
export CPANEL_USERNAME="your_cpanel_username"
export CPANEL_HOST="your-server.com"
export CPANEL_PORT="2083"  # 2083 for SSL, 2082 for non-SSL
```

#### Username/Password Method
```bash
export CPANEL_USERNAME="your_cpanel_username"
export CPANEL_PASSWORD="your_cpanel_password"
export CPANEL_HOST="your-server.com"
export CPANEL_PORT="2083"
```

### Configuration Examples

#### Single Domain Migration
```yaml
# cpanel-single-domain.yaml
name: "cPanel Single Domain Migration"
description: "Migrate single domain from cPanel to AWS"

source:
  type: cpanel
  host: shared-hosting.com
  port: 2083
  control_panel:
    type: cpanel
    username: myuser
    api_token: "${CPANEL_API_TOKEN}"
    ssl: true
  accounts:
    - domain: example.com
      username: myuser
      databases: ["myuser_wp", "myuser_shop"]
      email_accounts: true
      subdomains: true
      addon_domains: true

destination:
  type: aws-s3
  region: us-east-1
  bucket: example-com-new
  database:
    type: aurora-mysql
    cluster: example-cluster
    username: admin
    password: "${AURORA_PASSWORD}"

transfer:
  method: hybrid_sync
  options:
    preserve_permissions: true
    preserve_timestamps: true
    compress_files: true
    parallel_transfers: 4

migration_options:
  preserve_email_accounts: true
  migrate_dns_records: true
  migrate_ssl_certificates: true
  migrate_cron_jobs: true
  migrate_subdomains: true
  migrate_addon_domains: true
```

#### Multi-Domain Migration
```yaml
# cpanel-multi-domain.yaml
name: "cPanel Multi-Domain Migration"
description: "Migrate multiple domains from cPanel reseller account"

source:
  type: cpanel
  host: reseller-hosting.com
  port: 2087  # WHM port
  control_panel:
    type: cpanel_whm
    username: reseller_user
    api_token: "${WHM_API_TOKEN}"
    ssl: true
  accounts:
    - domain: site1.com
      username: site1user
      databases: ["site1_wp"]
    - domain: site2.com
      username: site2user
      databases: ["site2_shop", "site2_blog"]
    - domain: site3.com
      username: site3user
      databases: ["site3_app"]

destination:
  type: aws-multi-site
  region: us-east-1
  sites:
    - domain: site1.com
      bucket: site1-com-new
      database: site1-cluster
    - domain: site2.com
      bucket: site2-com-new
      database: site2-cluster
    - domain: site3.com
      bucket: site3-com-new
      database: site3-cluster

batch_options:
  parallel_migrations: 2
  stop_on_failure: false
  individual_backups: true
```

### CLI Usage

#### Interactive Migration
```bash
# Start interactive cPanel migration wizard
migration-assistant migrate --preset cpanel-aws

# Follow the prompts:
# 1. Enter cPanel server details
# 2. Choose authentication method
# 3. Select domains to migrate
# 4. Configure destination
# 5. Review and execute
```

#### Configuration File Migration
```bash
# Validate cPanel configuration
migration-assistant validate --config cpanel-migration.yaml

# Run migration
migration-assistant migrate --config cpanel-migration.yaml

# Monitor progress
migration-assistant status --watch --session SESSION_ID
```

### API Usage

#### Create cPanel Migration
```python
import requests

# Create migration session
migration_config = {
    "name": "cPanel to AWS Migration",
    "source": {
        "type": "cpanel",
        "host": "shared-hosting.com",
        "port": 2083,
        "control_panel": {
            "type": "cpanel",
            "username": "myuser",
            "api_token": "your_api_token",
            "ssl": True
        },
        "accounts": [
            {
                "domain": "example.com",
                "username": "myuser",
                "databases": ["myuser_wp"],
                "email_accounts": True,
                "subdomains": True
            }
        ]
    },
    "destination": {
        "type": "aws-s3",
        "region": "us-east-1",
        "bucket": "example-com-new",
        "database": {
            "type": "aurora-mysql",
            "cluster": "example-cluster",
            "username": "admin",
            "password": "secure_password"
        }
    },
    "migration_options": {
        "preserve_email_accounts": True,
        "migrate_dns_records": True,
        "migrate_ssl_certificates": True
    }
}

response = requests.post(
    "http://localhost:8000/migrations/",
    headers={"Authorization": "Bearer your-jwt-token"},
    json=migration_config
)

session_id = response.json()["session_id"]
print(f"Created migration session: {session_id}")
```

### cPanel-Specific Features

#### Email Account Migration
```yaml
email_migration:
  preserve_mailboxes: true
  migrate_to: aws-workmail  # or google-workspace, office365
  forwarders: true
  autoresponders: true
  filters: true
  mailing_lists: true
```

#### DNS Record Migration
```yaml
dns_migration:
  migrate_zone_files: true
  destination_dns: route53  # or cloudflare, google-dns
  preserve_ttl: true
  update_nameservers: false  # Set to true for automatic NS update
```

#### SSL Certificate Migration
```yaml
ssl_migration:
  migrate_certificates: true
  destination: aws-certificate-manager
  auto_validate: true
  force_https: true
```

#### Cron Job Migration
```yaml
cron_migration:
  migrate_cron_jobs: true
  destination: aws-eventbridge  # or google-scheduler, azure-functions
  convert_to_serverless: true
```

## 🔧 DirectAdmin Migrations

### Prerequisites
- DirectAdmin admin or user account
- API access enabled
- SSH access (recommended)
- Database access credentials

### Authentication Setup
```bash
export DA_USERNAME="admin"  # or user account
export DA_PASSWORD="your_password"
export DA_HOST="your-server.com"
export DA_PORT="2222"  # Default DirectAdmin port
```

### Configuration Examples

#### Basic DirectAdmin Migration
```yaml
# directadmin-migration.yaml
name: "DirectAdmin to DigitalOcean Migration"
description: "Migrate from DirectAdmin to DigitalOcean managed services"

source:
  type: directadmin
  host: da-server.com
  port: 2222
  control_panel:
    type: directadmin
    username: admin
    password: "${DA_PASSWORD}"
    ssl: true
  accounts:
    - domain: mysite.com
      username: mysite
      databases: ["mysite_db"]
      email_accounts: true

destination:
  type: digitalocean
  region: nyc3
  droplet:
    size: s-2vcpu-4gb
    image: ubuntu-20-04-x64
  database:
    type: managed-mysql
    size: db-s-1vcpu-1gb

transfer:
  method: ssh_rsync
  options:
    preserve_permissions: true
    exclude_patterns:
      - "*.log"
      - "tmp/*"
      - "cache/*"
```

#### DirectAdmin Reseller Migration
```yaml
# directadmin-reseller.yaml
name: "DirectAdmin Reseller Migration"
description: "Migrate entire reseller account with multiple users"

source:
  type: directadmin
  host: da-reseller.com
  port: 2222
  control_panel:
    type: directadmin
    username: reseller_admin
    password: "${DA_PASSWORD}"
    ssl: true
    reseller_mode: true
  accounts: "all"  # Migrate all accounts under reseller

destination:
  type: aws-multi-tenant
  region: us-west-2
  organization_unit: my-hosting-company
  
batch_options:
  parallel_migrations: 3
  create_separate_aws_accounts: true
  billing_separation: true
```

### CLI Usage

#### DirectAdmin Migration Wizard
```bash
# Start DirectAdmin migration
migration-assistant migrate --preset directadmin-aws

# Validate DirectAdmin connection
migration-assistant validate --quick \
  --source-type directadmin \
  --source-host da-server.com \
  --source-username admin
```

### DirectAdmin-Specific Features

#### User Account Structure
DirectAdmin has a hierarchical structure:
- **Admin**: Server administrator
- **Reseller**: Can create user accounts
- **User**: Individual hosting accounts

```yaml
source:
  control_panel:
    account_type: reseller  # admin, reseller, or user
    include_subaccounts: true
    account_filter:
      - "user1"
      - "user2"
      # Or use "all" for all accounts
```

#### DirectAdmin File Structure
```yaml
file_mapping:
  domains: "/home/user/domains/domain.com/public_html"
  private_html: "/home/user/domains/domain.com/private_html"
  email: "/home/user/imap/domain.com"
  backups: "/home/user/backups"
  logs: "/var/log/httpd/domains/domain.com.log"
```

## 🔧 Plesk Migrations

### Prerequisites
- Plesk admin or customer account
- REST API access
- SSH access (optional)
- Database access credentials

### Authentication Setup
```bash
export PLESK_HOST="plesk-server.com"
export PLESK_API_KEY="your_api_key"
# Or username/password
export PLESK_USERNAME="admin"
export PLESK_PASSWORD="your_password"
```

### Configuration Examples

#### Plesk to Google Cloud Migration
```yaml
# plesk-gcp-migration.yaml
name: "Plesk to Google Cloud Migration"
description: "Migrate Plesk hosting to Google Cloud Platform"

source:
  type: plesk
  host: plesk-server.com
  control_panel:
    type: plesk
    api_key: "${PLESK_API_KEY}"
    version: "18.0"  # Plesk version
  accounts:
    - domain: example.com
      subscription_id: "12345"
      databases: ["example_db"]
      email_accounts: true
      applications: ["wordpress", "joomla"]

destination:
  type: gcp
  project: my-project-id
  region: us-central1
  services:
    compute: compute-engine
    storage: cloud-storage
    database: cloud-sql-mysql
    dns: cloud-dns

migration_options:
  migrate_plesk_extensions: true
  convert_applications: true
  preserve_file_permissions: true
```

#### Plesk Multi-Subscription Migration
```yaml
# plesk-multi-subscription.yaml
name: "Plesk Multi-Subscription Migration"
description: "Migrate multiple Plesk subscriptions"

source:
  type: plesk
  host: plesk-server.com
  control_panel:
    type: plesk
    api_key: "${PLESK_API_KEY}"
  subscriptions:
    - subscription_id: "12345"
      domain: site1.com
      plan: "unlimited"
    - subscription_id: "12346"
      domain: site2.com
      plan: "business"
    - subscription_id: "12347"
      domain: site3.com
      plan: "starter"

destination:
  type: azure
  resource_group: plesk-migration-rg
  location: eastus
  services:
    app_service: true
    database: azure-mysql
    storage: blob-storage
    cdn: azure-cdn
```

### Plesk-Specific Features

#### Application Migration
Plesk supports various applications that need special handling:

```yaml
application_migration:
  wordpress:
    preserve_plugins: true
    update_urls: true
    migrate_uploads: true
  joomla:
    preserve_extensions: true
    update_configuration: true
  drupal:
    preserve_modules: true
    update_settings: true
```

#### Plesk Extension Migration
```yaml
extension_migration:
  migrate_extensions: true
  supported_extensions:
    - "wp-toolkit"
    - "git"
    - "nodejs"
    - "docker"
  convert_to_native: true  # Convert to cloud-native equivalents
```

## 🔄 Common Migration Patterns

### Pattern 1: Shared Hosting to Cloud
```yaml
# shared-to-cloud.yaml
migration_pattern: shared_to_cloud
source:
  type: cpanel  # or directadmin, plesk
  shared_hosting: true
destination:
  type: aws-s3
  serverless: true
  services:
    - lambda
    - api-gateway
    - rds-aurora
```

### Pattern 2: Control Panel to Container
```yaml
# control-panel-to-container.yaml
migration_pattern: control_panel_to_container
source:
  type: cpanel
destination:
  type: kubernetes
  containerization:
    web_server: nginx
    application: php-fpm
    database: mysql
    orchestration: helm
```

### Pattern 3: Multi-Tenant Migration
```yaml
# multi-tenant-migration.yaml
migration_pattern: multi_tenant
source:
  type: plesk
  reseller_account: true
destination:
  type: aws-organizations
  account_per_tenant: true
  billing_separation: true
```

## 🔍 Validation and Testing

### Pre-Migration Validation
```bash
# Validate control panel access
migration-assistant validate --config cpanel-migration.yaml

# Test specific components
migration-assistant validate --quick \
  --test connectivity,databases,email,dns

# Generate validation report
migration-assistant validate --detailed \
  --output validation-report.html
```

### Dry Run Testing
```bash
# Perform dry run
migration-assistant migrate --dry-run --config cpanel-migration.yaml

# Test with limited scope
migration-assistant migrate --dry-run \
  --config cpanel-migration.yaml \
  --limit-domains example.com \
  --skip-email
```

## 🚨 Troubleshooting

### Common Issues

#### API Access Problems
```bash
# Test cPanel API access
curl -H "Authorization: cpanel username:api_token" \
     "https://your-server.com:2083/execute/Mysql/list_databases"

# Test DirectAdmin API access
curl -u "username:password" \
     "https://your-server.com:2222/CMD_API_DATABASES"

# Test Plesk API access
curl -H "X-API-Key: your_api_key" \
     "https://plesk-server.com:8443/api/v2/domains"
```

#### Connection Issues
```yaml
# Add connection troubleshooting
troubleshooting:
  connection_timeout: 60
  retry_attempts: 3
  use_ssh_tunnel: true
  ssh_tunnel:
    host: jump-server.com
    username: tunnel_user
    key_file: ~/.ssh/tunnel_key
```

#### Large File Handling
```yaml
# Handle large files and databases
large_file_handling:
  chunk_size: "100MB"
  parallel_chunks: 4
  compression: true
  resume_on_failure: true
  exclude_large_files: false
  large_file_threshold: "1GB"
```

#### Email Migration Issues
```yaml
# Email migration troubleshooting
email_troubleshooting:
  preserve_folder_structure: true
  convert_mailbox_format: true
  handle_large_mailboxes: true
  migrate_in_batches: true
  batch_size: 1000  # emails per batch
```

### Error Recovery
```bash
# Resume failed migration
migration-assistant migrate --resume SESSION_ID

# Rollback partial migration
migration-assistant rollback --session SESSION_ID

# Fix specific issues and retry
migration-assistant migrate --config fixed-config.yaml \
  --skip-completed-steps
```

## ✅ Best Practices

### Pre-Migration Planning
1. **Inventory Assessment**
   - Document all domains, subdomains, and addon domains
   - List all databases and their sizes
   - Catalog email accounts and mailbox sizes
   - Identify custom applications and configurations

2. **Access Preparation**
   - Generate API tokens instead of using passwords
   - Test API access before migration
   - Ensure SSH access is available as backup
   - Document all credentials securely

3. **Destination Preparation**
   - Set up cloud accounts and permissions
   - Configure DNS zones in advance
   - Prepare SSL certificates
   - Set up monitoring and alerting

### During Migration
1. **Monitoring**
   - Use real-time progress monitoring
   - Set up alerts for failures
   - Monitor resource usage on both ends
   - Keep logs for troubleshooting

2. **Communication**
   - Notify users of maintenance windows
   - Provide status updates
   - Have rollback plan ready
   - Document any issues encountered

### Post-Migration
1. **Verification**
   - Test all websites and applications
   - Verify database integrity
   - Check email functionality
   - Validate SSL certificates

2. **DNS Cutover**
   - Update DNS records gradually
   - Use low TTL values initially
   - Monitor traffic patterns
   - Keep old servers running temporarily

3. **Cleanup**
   - Remove temporary files and backups
   - Update documentation
   - Archive migration logs
   - Plan for old server decommissioning

### Security Considerations
1. **Credential Management**
   - Use API tokens instead of passwords
   - Rotate credentials after migration
   - Use encrypted connections only
   - Store credentials securely

2. **Data Protection**
   - Encrypt data in transit
   - Verify backup integrity
   - Use secure transfer methods
   - Comply with data protection regulations

3. **Access Control**
   - Limit API access to necessary functions
   - Use principle of least privilege
   - Monitor access logs
   - Revoke unused access

This comprehensive guide covers all aspects of migrating from control panels to modern hosting environments. For additional help with specific scenarios, consult the [Troubleshooting Guide](../advanced/troubleshooting.md) or contact support.