# Quick Start Guide - CMS Migration Assistant

Get up and running with the CMS Migration Assistant in under 10 minutes! This guide covers the most common migration scenarios with step-by-step instructions.

## 🚀 Installation

### Prerequisites
- Python 3.8+
- Node.js 14+ (for Ghost migrations)
- .NET 6+ (for Umbraco migrations)
- Docker (optional, for containerized deployment)

### Quick Install
```bash
# Clone the repository
git clone https://github.com/mhtalci/web-db-transfer.git
cd web-db-transfer

# Install dependencies
pip install -e .

# Verify installation
python -c "from migration_assistant.platforms.factory import PlatformAdapterFactory; print('✅ Installation successful!')"
```

## 🔍 Quick Platform Detection

Detect what CMS platform you're working with:

```python
from migration_assistant.platforms.factory import PlatformAdapterFactory
from migration_assistant.models.config import SystemConfig, DatabaseConfig
from pathlib import Path

# Create basic config
config = SystemConfig(
    type="detection",
    host="localhost",
    database=DatabaseConfig(
        db_type="mysql",
        host="localhost",
        port=3306,
        name="temp_db",
        user="temp_user", 
        password="temp_pass"
    )
)

# Detect platform
path = Path("/path/to/your/cms")
adapter = await PlatformAdapterFactory.detect_platform(path, config)

if adapter:
    print(f"✅ Detected: {adapter.platform_type}")
    info = await adapter.analyze_platform(path)
    print(f"   Version: {info.version}")
    print(f"   Database: {info.database_type}")
else:
    print("❌ No supported CMS platform detected")
```

## 🏥 Quick Health Check

Check if your CMS is ready for migration:

```python
from migration_assistant.validators.cms_validator import CMSHealthChecker

# Perform health check
checker = CMSHealthChecker("wordpress", Path("/path/to/wordpress"))
health_result = await checker.run_health_check()

print(f"Health Score: {health_result['health_score']}/100")
print(f"Issues Found: {health_result['total_issues']}")

# Show critical issues
critical_issues = [
    issue for issue in health_result['issues'] 
    if issue['severity'] == 'critical'
]

if critical_issues:
    print("\n🚨 Critical Issues:")
    for issue in critical_issues:
        print(f"   • {issue['message']}")
        if issue['fix_suggestion']:
            print(f"     Fix: {issue['fix_suggestion']}")
```

## 🔄 Quick Migration Scenarios

### Scenario 1: WordPress to WordPress (Server Move)

```python
from migration_assistant.orchestrators.cms_migration_orchestrator import CMSMigrationOrchestrator

# Create orchestrator
orchestrator = CMSMigrationOrchestrator()

# Create migration plan
plan = await orchestrator.create_migration_plan(
    source_platform="wordpress",
    destination_platform="wordpress",
    source_path=Path("/var/www/old-wordpress"),
    destination_path=Path("/var/www/new-wordpress"),
    options={
        'create_backup': True,
        'verify_integrity': True
    }
)

print(f"Migration Plan: {plan.id}")
print(f"Estimated Time: {plan.total_estimated_duration // 60} minutes")

# Execute migration
print("Starting migration...")
async for progress in orchestrator.execute_migration(plan.id):
    if 'progress' in progress:
        print(f"Progress: {progress['progress']:.1f}% - {progress['message']}")
    else:
        print(f"Status: {progress['message']}")
```

### Scenario 2: WordPress to Drupal (Platform Change)

```python
# Cross-platform migration with content transformation
plan = await orchestrator.create_migration_plan(
    source_platform="wordpress",
    destination_platform="drupal",
    source_path=Path("/var/www/wordpress"),
    destination_path=Path("/var/www/drupal"),
    options={
        'create_backup': True,
        'transform_content': True,
        'map_taxonomies': True,
        'preserve_urls': True
    }
)

print(f"Cross-platform migration planned: {plan.id}")
print(f"Steps: {len(plan.steps)}")
print(f"Complexity: Complex (estimated {plan.total_estimated_duration // 60} minutes)")
```

### Scenario 3: Magento to Shopware (E-commerce)

```python
# E-commerce platform migration
plan = await orchestrator.create_migration_plan(
    source_platform="magento",
    destination_platform="shopware", 
    source_path=Path("/var/www/magento"),
    destination_path=Path("/var/www/shopware"),
    options={
        'migrate_products': True,
        'migrate_customers': True,
        'migrate_orders': True,
        'preserve_seo_urls': True
    }
)

print(f"E-commerce migration planned: {plan.id}")
print("Will migrate: products, customers, orders, SEO URLs")
```

## 🌐 Quick API Usage

Start the API server and use REST endpoints:

```bash
# Start API server
python -m migration_assistant.api.main

# In another terminal, test the API
curl -X GET "http://localhost:8000/api/v1/cms/platforms"
```

### Detect Platform via API
```bash
curl -X POST "http://localhost:8000/api/v1/cms/detect" \
  -H "Content-Type: application/json" \
  -d '{"path": "/var/www/wordpress"}'
```

### Health Check via API
```bash
curl -X POST "http://localhost:8000/api/v1/cms/health-check" \
  -H "Content-Type: application/json" \
  -d '{"platform_type": "wordpress", "path": "/var/www/wordpress"}'
```

### Create Migration Plan via API
```bash
curl -X POST "http://localhost:8000/api/v1/cms/migration/plan" \
  -H "Content-Type: application/json" \
  -d '{
    "source_platform": "wordpress",
    "destination_platform": "wordpress",
    "source_path": "/var/www/source",
    "destination_path": "/var/www/destination",
    "options": {"create_backup": true}
  }'
```

## 📊 Quick Performance Monitoring

Monitor migration performance in real-time:

```python
from migration_assistant.monitoring.cms_metrics import CMSPerformanceMonitor

# Start monitoring
monitor = CMSPerformanceMonitor("migration_123")
await monitor.start_monitoring()

# Add alert for high memory usage
async def memory_alert(alert):
    if alert['type'] == 'memory_high':
        print(f"⚠️ Memory Alert: {alert['message']}")

monitor.add_alert_callback(memory_alert)

# Get current metrics
metrics = monitor.get_current_metrics()
print(f"Memory Usage: {metrics['system_metrics']['memory_usage_percent']:.1f}%")
print(f"Files Processed: {metrics['files_processed']:,}")
print(f"Throughput: {metrics['average_throughput_mbps']:.2f} MB/s")
```

## 🔒 Quick Security Check

Perform security analysis:

```python
from migration_assistant.utils.cms_utils import CMSSecurityAnalyzer

# Check file permissions
permission_check = CMSSecurityAnalyzer.check_file_permissions(Path("/var/www/wordpress"))

if permission_check['issues']:
    print("🔒 Security Issues Found:")
    for issue in permission_check['issues']:
        print(f"   • {issue}")
    
    print("\n💡 Recommendations:")
    for rec in permission_check['recommendations']:
        print(f"   • {rec}")
else:
    print("✅ No security issues found")
```

## 🎯 Common Use Cases

### 1. Server Migration Checklist
```python
# Quick server migration workflow
async def quick_server_migration(source_path, destination_path):
    """Complete server migration workflow."""
    
    # 1. Detect platform
    adapter = await PlatformAdapterFactory.detect_platform(source_path, config)
    print(f"✅ Detected: {adapter.platform_type}")
    
    # 2. Health check
    checker = CMSHealthChecker(adapter.platform_type, source_path)
    health = await checker.run_health_check()
    print(f"✅ Health Score: {health['health_score']}/100")
    
    # 3. Create migration plan
    orchestrator = CMSMigrationOrchestrator()
    plan = await orchestrator.create_migration_plan(
        adapter.platform_type, adapter.platform_type,
        source_path, destination_path,
        {'create_backup': True}
    )
    print(f"✅ Migration Plan: {plan.id}")
    
    # 4. Execute migration
    print("🚀 Starting migration...")
    async for progress in orchestrator.execute_migration(plan.id):
        if 'progress' in progress:
            print(f"   {progress['progress']:.1f}% - {progress['message']}")
    
    print("✅ Migration completed!")

# Usage
await quick_server_migration(
    Path("/var/www/old-site"),
    Path("/var/www/new-site")
)
```

### 2. Batch Health Checks
```python
# Check health of multiple sites
sites = [
    ("/var/www/site1", "wordpress"),
    ("/var/www/site2", "drupal"),
    ("/var/www/site3", "magento")
]

for site_path, platform in sites:
    checker = CMSHealthChecker(platform, Path(site_path))
    health = await checker.run_health_check()
    
    status = "🟢" if health['health_score'] >= 80 else "🟡" if health['health_score'] >= 60 else "🔴"
    print(f"{status} {site_path}: {health['health_score']}/100 ({health['total_issues']} issues)")
```

### 3. Migration Compatibility Matrix
```python
# Check compatibility between platforms
platforms = ["wordpress", "drupal", "joomla", "magento", "shopware"]

print("Migration Compatibility Matrix:")
print("Source → Destination | Compatible | Complexity")
print("-" * 50)

for source in platforms:
    for dest in platforms:
        if source != dest:
            compatible = PlatformAdapterFactory.validate_platform_compatibility(source, dest)
            complexity = PlatformAdapterFactory.get_migration_complexity(source, dest)
            
            status = "✅" if compatible else "❌"
            print(f"{source:10} → {dest:10} | {status:8} | {complexity}")
```

## 🚨 Quick Troubleshooting

### Common Issues and Solutions

#### Issue: Platform Not Detected
```python
# Debug platform detection
detected_indicators = CMSFileAnalyzer.detect_cms_indicators(Path("/path/to/cms"))

print("CMS Indicators Found:")
for cms, indicators in detected_indicators.items():
    print(f"  {cms}: {indicators}")

# If no indicators found, check:
# 1. Path is correct
# 2. Files have proper permissions
# 3. Directory structure is intact
```

#### Issue: Health Check Fails
```python
# Get detailed health information
health_result = await checker.run_health_check()

# Focus on critical issues first
critical_issues = [i for i in health_result['issues'] if i['severity'] == 'critical']

for issue in critical_issues:
    print(f"🚨 CRITICAL: {issue['message']}")
    if issue['fix_suggestion']:
        print(f"   Fix: {issue['fix_suggestion']}")
```

#### Issue: Migration Stalls
```python
# Check migration status
status = await orchestrator.get_migration_status(migration_id)

# Look for failed steps
failed_steps = [s for s in status['steps'] if s['status'] == 'failed']

if failed_steps:
    print("Failed steps:")
    for step in failed_steps:
        print(f"  ❌ {step['name']}: {step.get('error_message', 'Unknown error')}")
```

## 📚 Next Steps

Once you're comfortable with the basics:

1. **Read the [Advanced CMS Migration Guide](docs/user-guide/advanced-cms-migration.md)** for complex scenarios
2. **Explore the [API Reference](docs/api-reference.md)** for integration options
3. **Check [Platform-Specific Guides](docs/cms-platforms.md)** for detailed platform information
4. **Review [Best Practices](docs/user-guide/best-practices.md)** for production deployments

## 🆘 Getting Help

- **Documentation**: Check the `docs/` directory for comprehensive guides
- **Examples**: Run `python examples/cms_platform_demo.py` for interactive examples
- **Issues**: Report bugs and feature requests on GitHub
- **Community**: Join our community discussions for tips and support

---

**🎉 Congratulations!** You're now ready to perform enterprise-grade CMS migrations with confidence!