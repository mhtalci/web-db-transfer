#!/usr/bin/env python3
"""
Demo script showing connectivity validation functionality.
"""

import asyncio
import json
from migration_assistant.validation.connectivity import ConnectivityValidator, ValidationResult


async def demo_connectivity_validation():
    """Demonstrate connectivity validation with various configurations"""
    
    validator = ConnectivityValidator()
    
    # Example 1: WordPress to AWS migration
    print("=== WordPress to AWS Migration Validation ===")
    wordpress_config = {
        'source': {
            'type': 'wordpress',
            'host': 'example.com',
            'port': 3306,
            'db_type': 'mysql',
            'db_user': 'wp_user',
            'db_password': 'wp_password',
            'db_name': 'wordpress_db',
            'ssh_config': {
                'username': 'webuser',
                'password': 'ssh_password'
            }
        },
        'destination': {
            'type': 'aws-s3',
            'host': 's3.amazonaws.com',
            'db_type': 'aurora-mysql',
            'cloud_config': {
                'provider': 'aws',
                'region': 'us-east-1',
                'access_key_id': 'AKIAEXAMPLE',
                'secret_access_key': 'example-secret-key'
            }
        }
    }
    
    results = await validator.validate_all(wordpress_config)
    print_validation_results(results)
    
    # Example 2: Django to GCP migration
    print("\n=== Django to GCP Migration Validation ===")
    django_config = {
        'source': {
            'type': 'django',
            'host': 'django-server.com',
            'port': 5432,
            'db_type': 'postgresql',
            'db_user': 'django_user',
            'db_password': 'django_password',
            'db_name': 'django_db'
        },
        'destination': {
            'type': 'gcp-storage',
            'host': 'storage.googleapis.com',
            'db_type': 'cloud-sql-postgres',
            'cloud_config': {
                'provider': 'gcp',
                'project_id': 'my-project',
                'service_account_path': '/path/to/service-account.json'
            }
        }
    }
    
    results = await validator.validate_all(django_config)
    print_validation_results(results)
    
    # Example 3: MongoDB to Azure migration
    print("\n=== MongoDB to Azure Migration Validation ===")
    mongo_config = {
        'source': {
            'type': 'mongodb',
            'host': 'mongo.example.com',
            'port': 27017,
            'db_type': 'mongodb',
            'db_user': 'mongo_user',
            'db_password': 'mongo_password',
            'db_name': 'app_database'
        },
        'destination': {
            'type': 'azure-cosmos',
            'host': 'cosmos.azure.com',
            'db_type': 'cosmos-mongo',
            'cloud_config': {
                'provider': 'azure',
                'account_name': 'mycosmosaccount',
                'account_key': 'azure-account-key'
            }
        }
    }
    
    results = await validator.validate_all(mongo_config)
    print_validation_results(results)
    
    # Example 4: Local SQLite to Redis migration
    print("\n=== SQLite to Redis Migration Validation ===")
    sqlite_config = {
        'source': {
            'type': 'sqlite',
            'db_type': 'sqlite',
            'db_path': '/tmp/app.db'
        },
        'destination': {
            'type': 'redis',
            'host': 'redis.example.com',
            'port': 6379,
            'db_type': 'redis',
            'db_password': 'redis_password'
        }
    }
    
    results = await validator.validate_all(sqlite_config)
    print_validation_results(results)


def print_validation_results(results):
    """Print validation results in a formatted way"""
    
    success_count = sum(1 for r in results if r.result == ValidationResult.SUCCESS)
    failed_count = sum(1 for r in results if r.result == ValidationResult.FAILED)
    warning_count = sum(1 for r in results if r.result == ValidationResult.WARNING)
    skipped_count = sum(1 for r in results if r.result == ValidationResult.SKIPPED)
    
    print(f"Validation Summary: {success_count} passed, {failed_count} failed, {warning_count} warnings, {skipped_count} skipped")
    print("-" * 80)
    
    for result in results:
        status_icon = {
            ValidationResult.SUCCESS: "✅",
            ValidationResult.FAILED: "❌",
            ValidationResult.WARNING: "⚠️",
            ValidationResult.SKIPPED: "⏭️"
        }[result.result]
        
        print(f"{status_icon} {result.name}: {result.message}")
        
        if result.remediation:
            print(f"   💡 Remediation: {result.remediation}")
        
        if result.details:
            print(f"   📋 Details: {json.dumps(result.details, indent=6)}")
    
    print()


async def demo_individual_checks():
    """Demonstrate individual connectivity checks"""
    
    print("=== Individual Connectivity Checks ===")
    validator = ConnectivityValidator()
    
    # Test MySQL connectivity
    mysql_config = {
        'host': 'localhost',
        'port': 3306,
        'db_user': 'root',
        'db_password': 'password',
        'db_name': 'test'
    }
    
    print("Testing MySQL connectivity...")
    result = await validator._check_mysql_connectivity(mysql_config, 'test-mysql')
    print(f"Result: {result.result.value} - {result.message}")
    
    # Test network connectivity
    print("\nTesting network connectivity...")
    result = await validator._check_network_connectivity('google.com', 80, 'test-network')
    print(f"Result: {result.result.value} - {result.message}")
    
    # Test SSH connectivity (will likely fail without proper setup)
    ssh_config = {
        'host': 'example.com',
        'ssh_config': {
            'username': 'testuser',
            'password': 'testpass'
        }
    }
    
    print("\nTesting SSH connectivity...")
    result = await validator._check_ssh_connectivity(ssh_config, 'test-ssh')
    print(f"Result: {result.result.value} - {result.message}")


if __name__ == '__main__':
    print("Migration Assistant - Connectivity Validation Demo")
    print("=" * 60)
    
    # Run the demo
    asyncio.run(demo_connectivity_validation())
    
    print("\n" + "=" * 60)
    asyncio.run(demo_individual_checks())