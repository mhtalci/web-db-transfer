# API User Guide

The Migration Assistant provides a comprehensive REST API built with FastAPI, offering programmatic access to all migration functionality with async support, auto-generated documentation, and multi-tenant capabilities.

## 📋 Table of Contents

- [API Overview](#api-overview)
- [Authentication](#authentication)
- [Getting Started](#getting-started)
- [Core Endpoints](#core-endpoints)
- [Configuration Management](#configuration-management)
- [Migration Lifecycle](#migration-lifecycle)
- [Monitoring and Status](#monitoring-and-status)
- [Error Handling](#error-handling)
- [SDK and Client Libraries](#sdk-and-client-libraries)
- [Advanced Features](#advanced-features)

## 🌐 API Overview

### Base Information
- **Base URL**: `http://localhost:8000` (default)
- **API Version**: v1
- **Documentation**: 
  - Swagger UI: `/docs`
  - ReDoc: `/redoc`
  - OpenAPI JSON: `/openapi.json`
- **Content Type**: `application/json`
- **Authentication**: OAuth2, JWT, API Keys

### Key Features
- **Async Operations**: Long-running migrations with background processing
- **Real-time Updates**: WebSocket support for live progress monitoring
- **Multi-tenant**: Tenant isolation and resource management
- **Auto-generated Docs**: Interactive API documentation
- **Comprehensive Validation**: Request/response validation with detailed errors
- **Rate Limiting**: Built-in rate limiting and throttling

## 🔐 Authentication

### Authentication Methods

#### 1. API Key Authentication
```bash
# Include API key in header
curl -H "X-API-Key: your-api-key" \
     -H "Content-Type: application/json" \
     http://localhost:8000/migrations/
```

#### 2. JWT Token Authentication
```bash
# Get JWT token
curl -X POST http://localhost:8000/auth/token \
     -H "Content-Type: application/json" \
     -d '{"username": "user", "password": "pass"}'

# Use JWT token
curl -H "Authorization: Bearer your-jwt-token" \
     -H "Content-Type: application/json" \
     http://localhost:8000/migrations/
```

#### 3. OAuth2 Authentication
```python
import requests
from requests_oauthlib import OAuth2Session

# OAuth2 flow
oauth = OAuth2Session(client_id='your-client-id')
authorization_url, state = oauth.authorization_url(
    'http://localhost:8000/auth/authorize'
)

# After user authorization
token = oauth.fetch_token(
    'http://localhost:8000/auth/token',
    authorization_response=authorization_response,
    client_secret='your-client-secret'
)

# Use OAuth2 token
headers = {'Authorization': f'Bearer {token["access_token"]}'}
response = requests.get('http://localhost:8000/migrations/', headers=headers)
```

### Multi-tenant Support
```python
# Include tenant ID in requests
headers = {
    'Authorization': 'Bearer your-jwt-token',
    'X-Tenant-ID': 'tenant-123'
}

response = requests.get('http://localhost:8000/migrations/', headers=headers)
```

## 🚀 Getting Started

### Start the API Server
```bash
# Basic startup
migration-assistant serve

# Production configuration
migration-assistant serve \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --auth-enabled \
  --jwt-secret your-secret-key
```

### Health Check
```python
import requests

# Check API health
response = requests.get('http://localhost:8000/health')
print(response.json())

# Expected response:
{
    "status": "healthy",
    "version": "1.0.0",
    "service": "Migration Assistant API",
    "timestamp": "2024-08-26T14:30:22.123456",
    "components": {
        "orchestrator": true,
        "preset_manager": true,
        "validation_engine": true
    }
}
```

### Basic API Usage
```python
import requests
import json

# API base URL
BASE_URL = "http://localhost:8000"

# Headers with authentication
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer your-jwt-token"
}

# Create a migration
migration_config = {
    "name": "WordPress to AWS Migration",
    "source": {
        "type": "wordpress",
        "host": "old-server.com",
        "username": "user",
        "password": "pass",
        "database": {
            "type": "mysql",
            "host": "old-server.com",
            "username": "wp_user",
            "password": "wp_pass",
            "database": "wordpress_db"
        }
    },
    "destination": {
        "type": "aws-s3",
        "region": "us-east-1",
        "bucket": "my-new-website",
        "database": {
            "type": "aurora-mysql",
            "cluster": "my-website-cluster",
            "username": "admin",
            "password": "admin_pass"
        }
    },
    "transfer": {
        "method": "hybrid_sync",
        "options": {
            "compression": True,
            "parallel_transfers": 4
        }
    },
    "safety": {
        "backup_before": True,
        "verify_after": True,
        "rollback_on_failure": True
    }
}

# Create migration session
response = requests.post(
    f"{BASE_URL}/migrations/",
    headers=headers,
    json=migration_config
)

session_data = response.json()
session_id = session_data["session_id"]
print(f"Created migration session: {session_id}")

# Start the migration
response = requests.post(
    f"{BASE_URL}/migrations/{session_id}/start",
    headers=headers,
    json={"auto_rollback": True}
)

print("Migration started!")

# Monitor progress
import time
while True:
    response = requests.get(
        f"{BASE_URL}/migrations/{session_id}/status",
        headers=headers
    )
    status_data = response.json()
    
    print(f"Status: {status_data['status']}, Progress: {status_data['progress']:.1f}%")
    
    if status_data["status"] in ["completed", "failed", "cancelled"]:
        break
    
    time.sleep(5)

print("Migration finished!")
```

## 🔧 Core Endpoints

### Root Endpoint
```http
GET /
```

Returns API information and available features.

**Response:**
```json
{
    "name": "Web & Database Migration Assistant API",
    "version": "1.0.0",
    "description": "A comprehensive REST API for migrating web applications and databases",
    "docs_url": "/docs",
    "redoc_url": "/redoc",
    "health_url": "/health",
    "features": [
        "Async migration execution",
        "Real-time progress tracking",
        "Multiple transfer methods",
        "Database migration support",
        "Backup and rollback capabilities",
        "Platform-specific adapters",
        "Comprehensive validation"
    ]
}
```

### Health Check
```http
GET /health
```

Returns API health status and component availability.

**Response:**
```json
{
    "status": "healthy",
    "version": "1.0.0",
    "service": "Migration Assistant API",
    "timestamp": "2024-08-26T14:30:22.123456",
    "components": {
        "orchestrator": true,
        "preset_manager": true,
        "validation_engine": true
    }
}
```

### System Information
```http
GET /system/types
```

Returns available system types, transfer methods, and database types.

**Response:**
```json
{
    "system_types": [
        "wordpress", "drupal", "django", "static", "mysql", 
        "postgresql", "mongodb", "aws-s3", "gcp-gcs", "azure-blob"
    ],
    "transfer_methods": [
        "ssh", "ftp", "rsync", "s3_sync", "gcs_sync", 
        "azure_sync", "hybrid_sync", "docker_cp"
    ],
    "database_types": [
        "mysql", "postgresql", "mongodb", "redis", "sqlite",
        "aurora-mysql", "aurora-postgres", "cloud-sql"
    ]
}
```

## 📋 Configuration Management

### List Presets
```http
GET /presets/
```

Returns available migration presets.

**Response:**
```json
[
    {
        "id": "wordpress-mysql",
        "name": "WordPress with MySQL",
        "description": "WordPress CMS with MySQL database migration",
        "source_types": ["wordpress"],
        "destination_types": ["aws-s3", "gcp-gcs", "azure-blob"]
    },
    {
        "id": "django-postgres",
        "name": "Django with PostgreSQL",
        "description": "Django application with PostgreSQL database",
        "source_types": ["django"],
        "destination_types": ["aws-ec2", "gcp-compute", "azure-vm"]
    }
]
```

### Get Specific Preset
```http
GET /presets/{preset_id}
```

Returns detailed preset configuration.

**Example:**
```http
GET /presets/wordpress-mysql
```

**Response:**
```json
{
    "id": "wordpress-mysql",
    "name": "WordPress with MySQL",
    "description": "WordPress CMS with MySQL database migration",
    "config_template": {
        "source": {
            "type": "wordpress",
            "host": "{{source_host}}",
            "username": "{{source_username}}",
            "password": "{{source_password}}",
            "database": {
                "type": "mysql",
                "host": "{{db_host}}",
                "username": "{{db_username}}",
                "password": "{{db_password}}",
                "database": "{{db_name}}"
            }
        },
        "destination": {
            "type": "aws-s3",
            "region": "{{aws_region}}",
            "bucket": "{{s3_bucket}}",
            "database": {
                "type": "aurora-mysql",
                "cluster": "{{aurora_cluster}}",
                "username": "{{aurora_username}}",
                "password": "{{aurora_password}}"
            }
        },
        "transfer": {
            "method": "hybrid_sync",
            "options": {
                "compression": true,
                "parallel_transfers": 4
            }
        }
    },
    "custom": false
}
```

### Create Migration from Preset
```http
POST /presets/{preset_id}/create-migration
```

Creates a migration session using a preset with optional overrides.

**Request Body:**
```json
{
    "overrides": {
        "source.host": "my-wordpress-server.com",
        "source.username": "myuser",
        "destination.bucket": "my-new-website-bucket",
        "destination.region": "us-west-2"
    }
}
```

**Response:**
```json
{
    "session_id": "abc123def456",
    "status": "created",
    "message": "Migration session created from preset wordpress-mysql",
    "created_at": "2024-08-26T14:30:22.123456"
}
```

### Validate Configuration
```http
POST /validate/
```

Validates a migration configuration before execution.

**Request Body:**
```json
{
    "name": "Test Migration",
    "source": {
        "type": "wordpress",
        "host": "old-server.com",
        "username": "user",
        "password": "pass",
        "database": {
            "type": "mysql",
            "host": "old-server.com",
            "username": "wp_user",
            "password": "wp_pass",
            "database": "wordpress_db"
        }
    },
    "destination": {
        "type": "aws-s3",
        "region": "us-east-1",
        "bucket": "my-new-website"
    }
}
```

**Response:**
```json
{
    "valid": true,
    "checks_performed": 12,
    "checks_passed": 11,
    "checks_failed": 0,
    "warnings": [
        "Large file detected: video.mp4 (500MB) - consider compression"
    ],
    "errors": [],
    "can_proceed": true,
    "estimated_duration": "35-45 minutes"
}
```

## 🔄 Migration Lifecycle

### Create Migration
```http
POST /migrations/
```

Creates a new migration session.

**Request Body:**
```json
{
    "name": "WordPress to AWS Migration",
    "description": "Migrating company website to AWS infrastructure",
    "source": {
        "type": "wordpress",
        "host": "old-server.com",
        "port": 22,
        "username": "user",
        "password": "secure_password",
        "paths": {
            "web_root": "/var/www/html",
            "uploads": "/var/www/html/wp-content/uploads"
        },
        "database": {
            "type": "mysql",
            "host": "old-server.com",
            "port": 3306,
            "username": "wp_user",
            "password": "wp_password",
            "database": "wordpress_db"
        }
    },
    "destination": {
        "type": "aws-s3",
        "region": "us-east-1",
        "bucket": "my-new-website",
        "database": {
            "type": "aurora-mysql",
            "cluster": "my-website-cluster",
            "username": "admin",
            "password": "admin_password"
        }
    },
    "transfer": {
        "method": "hybrid_sync",
        "options": {
            "compression": true,
            "parallel_transfers": 4,
            "chunk_size": "10MB",
            "resume_on_failure": true,
            "verify_checksums": true
        }
    },
    "safety": {
        "backup_before": true,
        "backup_retention_days": 30,
        "rollback_on_failure": true,
        "verify_after": true,
        "maintenance_mode": true
    },
    "notifications": {
        "email": {
            "enabled": true,
            "recipients": ["admin@example.com"]
        },
        "webhook": {
            "enabled": true,
            "url": "https://api.example.com/migration-webhook"
        }
    }
}
```

**Response:**
```json
{
    "session_id": "abc123def456",
    "status": "created",
    "message": "Migration session created successfully",
    "created_at": "2024-08-26T14:30:22.123456"
}
```

### Start Migration
```http
POST /migrations/{session_id}/start
```

Starts execution of a created migration session.

**Request Body:**
```json
{
    "auto_rollback": true,
    "send_notifications": true
}
```

**Response:**
```json
{
    "session_id": "abc123def456",
    "status": "started",
    "message": "Migration execution started in background"
}
```

### Get Migration Status
```http
GET /migrations/{session_id}/status
```

Returns detailed status of a migration session.

**Response:**
```json
{
    "session_id": "abc123def456",
    "status": "running",
    "progress": 65.5,
    "current_step": "Transferring files",
    "start_time": "2024-08-26T14:30:22.123456",
    "end_time": null,
    "duration": 1125.5,
    "error": null,
    "steps_completed": 5,
    "steps_total": 8,
    "performance_metrics": {
        "transfer_rate_current": "2.3 MB/s",
        "transfer_rate_average": "2.1 MB/s",
        "files_transferred": 12847,
        "files_total": 15847,
        "data_transferred": "12.1 GB",
        "data_total": "15.5 GB"
    },
    "current_operation": {
        "type": "file_transfer",
        "source": "/var/www/html/wp-content/uploads/2024/08/",
        "destination": "s3://my-new-website/wp-content/uploads/2024/08/",
        "progress": 78.2
    }
}
```

### List Migrations
```http
GET /migrations/
```

Returns list of migration sessions with optional filtering.

**Query Parameters:**
- `status_filter`: Filter by status (pending, running, completed, failed)
- `limit`: Maximum results (default: 100)
- `offset`: Results offset (default: 0)

**Example:**
```http
GET /migrations/?status_filter=running&limit=10
```

**Response:**
```json
[
    {
        "session_id": "abc123def456",
        "name": "WordPress to AWS Migration",
        "status": "running",
        "created_at": "2024-08-26T14:30:22.123456",
        "start_time": "2024-08-26T14:30:30.123456",
        "end_time": null,
        "source_type": "wordpress",
        "destination_type": "aws-s3",
        "progress": 65.5
    },
    {
        "session_id": "def456ghi789",
        "name": "Django to GCP Migration",
        "status": "completed",
        "created_at": "2024-08-26T12:15:30.123456",
        "start_time": "2024-08-26T12:15:45.123456",
        "end_time": "2024-08-26T12:58:03.123456",
        "source_type": "django",
        "destination_type": "gcp-gcs",
        "progress": 100.0
    }
]
```

### Cancel Migration
```http
POST /migrations/{session_id}/cancel
```

Cancels a running migration session.

**Response:**
```json
{
    "session_id": "abc123def456",
    "status": "cancelled",
    "message": "Migration cancellation initiated"
}
```

### Rollback Migration
```http
POST /migrations/{session_id}/rollback
```

Initiates rollback of a completed or failed migration.

**Request Body:**
```json
{
    "backup_id": "backup-20240826-143022",
    "rollback_options": {
        "restore_files": true,
        "restore_database": true,
        "restore_configuration": true
    }
}
```

**Response:**
```json
{
    "session_id": "abc123def456",
    "status": "rollback_started",
    "message": "Migration rollback started in background"
}
```

## 📊 Monitoring and Status

### Real-time Progress with WebSockets
```javascript
// JavaScript WebSocket client
const ws = new WebSocket('ws://localhost:8000/ws/migrations/abc123def456');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Progress update:', data);
    
    // Update UI with progress
    updateProgressBar(data.progress);
    updateCurrentStep(data.current_step);
    updateMetrics(data.performance_metrics);
};

ws.onopen = function(event) {
    console.log('Connected to migration progress stream');
};

ws.onclose = function(event) {
    console.log('Disconnected from progress stream');
};
```

### Migration Logs
```http
GET /migrations/{session_id}/logs
```

Returns migration logs with optional filtering.

**Query Parameters:**
- `level`: Filter by log level (DEBUG, INFO, WARNING, ERROR)
- `limit`: Maximum log entries (default: 100)
- `since`: ISO timestamp to get logs since

**Response:**
```json
{
    "session_id": "abc123def456",
    "logs": [
        {
            "timestamp": "2024-08-26T14:45:23.123456",
            "level": "INFO",
            "message": "Transferred wp-content/uploads/2024/08/image.jpg (2.1MB)",
            "component": "file_transfer",
            "details": {
                "file_size": 2097152,
                "transfer_time": 0.95,
                "checksum": "sha256:abc123..."
            }
        },
        {
            "timestamp": "2024-08-26T14:45:20.123456",
            "level": "WARNING",
            "message": "Retrying transfer for large-file.mp4 (attempt 2/3)",
            "component": "file_transfer",
            "details": {
                "file_size": 524288000,
                "error": "Connection timeout",
                "retry_count": 2
            }
        }
    ],
    "total_logs": 1247,
    "has_more": true
}
```

### Performance Metrics
```http
GET /migrations/{session_id}/metrics
```

Returns detailed performance metrics for a migration.

**Response:**
```json
{
    "session_id": "abc123def456",
    "metrics": {
        "overall": {
            "duration": 1125.5,
            "progress": 65.5,
            "estimated_remaining": 735.2
        },
        "transfer": {
            "rate_current": "2.3 MB/s",
            "rate_average": "2.1 MB/s",
            "rate_peak": "4.7 MB/s",
            "bytes_transferred": 13019963392,
            "bytes_total": 16642998272,
            "files_transferred": 12847,
            "files_total": 15847
        },
        "database": {
            "tables_migrated": 15,
            "tables_total": 15,
            "rows_migrated": 125847,
            "rows_total": 125847,
            "data_size": "1.2 GB"
        },
        "system": {
            "cpu_usage": 45.2,
            "memory_usage": "2.1 GB",
            "disk_usage": "15.3 GB",
            "network_usage": "2.3 MB/s"
        },
        "errors": {
            "total_errors": 0,
            "total_warnings": 3,
            "retry_count": 5
        }
    }
}
```

## ❌ Error Handling

### Error Response Format
All API errors follow a consistent format:

```json
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Configuration validation failed",
        "details": {
            "field": "source.host",
            "issue": "Host is not reachable",
            "suggestion": "Check network connectivity and firewall settings"
        },
        "timestamp": "2024-08-26T14:30:22.123456",
        "request_id": "req-abc123def456"
    }
}
```

### Common Error Codes

#### 400 Bad Request
```json
{
    "error": {
        "code": "INVALID_CONFIGURATION",
        "message": "Invalid migration configuration",
        "details": {
            "validation_errors": [
                {
                    "field": "source.type",
                    "message": "Invalid system type: 'invalid_type'"
                },
                {
                    "field": "destination.bucket",
                    "message": "S3 bucket name contains invalid characters"
                }
            ]
        }
    }
}
```

#### 401 Unauthorized
```json
{
    "error": {
        "code": "AUTHENTICATION_REQUIRED",
        "message": "Authentication credentials required",
        "details": {
            "supported_methods": ["Bearer", "API-Key"],
            "auth_url": "/auth/token"
        }
    }
}
```

#### 403 Forbidden
```json
{
    "error": {
        "code": "INSUFFICIENT_PERMISSIONS",
        "message": "Insufficient permissions for this operation",
        "details": {
            "required_scope": "migrations:write",
            "current_scopes": ["migrations:read"]
        }
    }
}
```

#### 404 Not Found
```json
{
    "error": {
        "code": "MIGRATION_NOT_FOUND",
        "message": "Migration session not found",
        "details": {
            "session_id": "invalid-session-id"
        }
    }
}
```

#### 409 Conflict
```json
{
    "error": {
        "code": "MIGRATION_ALREADY_RUNNING",
        "message": "Migration session is already running",
        "details": {
            "session_id": "abc123def456",
            "current_status": "running",
            "started_at": "2024-08-26T14:30:22.123456"
        }
    }
}
```

#### 422 Unprocessable Entity
```json
{
    "error": {
        "code": "VALIDATION_FAILED",
        "message": "Pre-migration validation failed",
        "details": {
            "failed_checks": [
                {
                    "check": "source_connectivity",
                    "error": "Cannot connect to source server",
                    "suggestion": "Verify SSH credentials and network access"
                },
                {
                    "check": "destination_permissions",
                    "error": "Insufficient S3 bucket permissions",
                    "suggestion": "Grant s3:PutObject and s3:GetObject permissions"
                }
            ]
        }
    }
}
```

#### 500 Internal Server Error
```json
{
    "error": {
        "code": "INTERNAL_ERROR",
        "message": "An unexpected error occurred",
        "details": {
            "error_id": "err-abc123def456",
            "support_contact": "support@migration-assistant.com"
        }
    }
}
```

### Error Recovery
```python
import requests
import time

def create_migration_with_retry(config, max_retries=3):
    """Create migration with automatic retry on transient errors."""
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                f"{BASE_URL}/migrations/",
                headers=headers,
                json=config,
                timeout=30
            )
            
            if response.status_code == 201:
                return response.json()
            elif response.status_code in [500, 502, 503, 504]:
                # Transient errors - retry
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
            else:
                # Client errors - don't retry
                response.raise_for_status()
                
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    
    raise Exception(f"Failed to create migration after {max_retries} attempts")
```

## 📚 SDK and Client Libraries

### Python SDK
```python
from migration_assistant_sdk import MigrationClient

# Initialize client
client = MigrationClient(
    base_url="http://localhost:8000",
    api_key="your-api-key"
)

# Create migration
migration = client.migrations.create({
    "name": "WordPress Migration",
    "source": {"type": "wordpress", "host": "old-server.com"},
    "destination": {"type": "aws-s3", "bucket": "new-bucket"}
})

# Start migration
client.migrations.start(migration.session_id)

# Monitor progress
for update in client.migrations.watch(migration.session_id):
    print(f"Progress: {update.progress}%")
    if update.status in ["completed", "failed"]:
        break

# Get final status
final_status = client.migrations.get_status(migration.session_id)
print(f"Migration {final_status.status}")
```

### JavaScript/Node.js SDK
```javascript
const { MigrationClient } = require('migration-assistant-sdk');

// Initialize client
const client = new MigrationClient({
    baseUrl: 'http://localhost:8000',
    apiKey: 'your-api-key'
});

// Create and start migration
async function runMigration() {
    try {
        // Create migration
        const migration = await client.migrations.create({
            name: 'WordPress Migration',
            source: { type: 'wordpress', host: 'old-server.com' },
            destination: { type: 'aws-s3', bucket: 'new-bucket' }
        });

        console.log(`Created migration: ${migration.sessionId}`);

        // Start migration
        await client.migrations.start(migration.sessionId);
        console.log('Migration started');

        // Monitor progress
        const progressStream = client.migrations.watchProgress(migration.sessionId);
        
        progressStream.on('progress', (update) => {
            console.log(`Progress: ${update.progress}%`);
        });

        progressStream.on('completed', (result) => {
            console.log('Migration completed successfully');
        });

        progressStream.on('error', (error) => {
            console.error('Migration failed:', error);
        });

    } catch (error) {
        console.error('Error:', error);
    }
}

runMigration();
```

### Go SDK
```go
package main

import (
    "context"
    "fmt"
    "log"
    
    "github.com/migration-assistant/go-sdk"
)

func main() {
    // Initialize client
    client := migration.NewClient(&migration.Config{
        BaseURL: "http://localhost:8000",
        APIKey:  "your-api-key",
    })

    // Create migration
    config := &migration.MigrationConfig{
        Name: "WordPress Migration",
        Source: migration.SystemConfig{
            Type: "wordpress",
            Host: "old-server.com",
        },
        Destination: migration.SystemConfig{
            Type:   "aws-s3",
            Bucket: "new-bucket",
        },
    }

    migration, err := client.Migrations.Create(context.Background(), config)
    if err != nil {
        log.Fatal(err)
    }

    fmt.Printf("Created migration: %s\n", migration.SessionID)

    // Start migration
    err = client.Migrations.Start(context.Background(), migration.SessionID)
    if err != nil {
        log.Fatal(err)
    }

    // Monitor progress
    progressChan, err := client.Migrations.WatchProgress(context.Background(), migration.SessionID)
    if err != nil {
        log.Fatal(err)
    }

    for update := range progressChan {
        fmt.Printf("Progress: %.1f%%\n", update.Progress)
        if update.Status == "completed" || update.Status == "failed" {
            break
        }
    }

    fmt.Println("Migration finished")
}
```

## 🚀 Advanced Features

### Batch Operations
```http
POST /migrations/batch
```

Create multiple migrations in a single request.

**Request Body:**
```json
{
    "migrations": [
        {
            "name": "Site 1 Migration",
            "source": {"type": "wordpress", "host": "site1.com"},
            "destination": {"type": "aws-s3", "bucket": "site1-new"}
        },
        {
            "name": "Site 2 Migration", 
            "source": {"type": "wordpress", "host": "site2.com"},
            "destination": {"type": "aws-s3", "bucket": "site2-new"}
        }
    ],
    "batch_options": {
        "parallel_limit": 2,
        "stop_on_failure": false
    }
}
```

### Scheduled Migrations
```http
POST /migrations/{session_id}/schedule
```

Schedule a migration for future execution.

**Request Body:**
```json
{
    "schedule_type": "datetime",
    "scheduled_time": "2024-08-27T02:00:00Z",
    "timezone": "UTC",
    "auto_start": true,
    "notifications": {
        "before_start": "1h",
        "on_completion": true
    }
}
```

### Migration Templates
```http
POST /templates/
```

Create reusable migration templates.

**Request Body:**
```json
{
    "name": "WordPress to AWS Template",
    "description": "Standard WordPress to AWS S3 + Aurora migration",
    "template": {
        "source": {
            "type": "wordpress",
            "host": "{{source_host}}",
            "username": "{{source_username}}"
        },
        "destination": {
            "type": "aws-s3",
            "region": "{{aws_region}}",
            "bucket": "{{s3_bucket}}"
        }
    },
    "variables": [
        {"name": "source_host", "type": "string", "required": true},
        {"name": "source_username", "type": "string", "required": true},
        {"name": "aws_region", "type": "string", "default": "us-east-1"},
        {"name": "s3_bucket", "type": "string", "required": true}
    ]
}
```

### Webhooks and Notifications
```http
POST /webhooks/
```

Configure webhooks for migration events.

**Request Body:**
```json
{
    "name": "Migration Notifications",
    "url": "https://api.example.com/migration-webhook",
    "events": [
        "migration.started",
        "migration.completed", 
        "migration.failed",
        "migration.progress"
    ],
    "headers": {
        "Authorization": "Bearer webhook-token",
        "Content-Type": "application/json"
    },
    "retry_policy": {
        "max_retries": 3,
        "retry_delay": 5
    }
}
```

### Migration Analytics
```http
GET /analytics/migrations
```

Get migration analytics and statistics.

**Query Parameters:**
- `start_date`: Start date for analytics (ISO format)
- `end_date`: End date for analytics (ISO format)
- `group_by`: Group results by (day, week, month)

**Response:**
```json
{
    "period": {
        "start": "2024-08-01T00:00:00Z",
        "end": "2024-08-31T23:59:59Z"
    },
    "summary": {
        "total_migrations": 156,
        "successful_migrations": 142,
        "failed_migrations": 14,
        "success_rate": 91.0,
        "average_duration": "28m 45s",
        "total_data_transferred": "2.3 TB"
    },
    "by_type": {
        "wordpress": {"count": 89, "success_rate": 94.4},
        "django": {"count": 34, "success_rate": 88.2},
        "static": {"count": 33, "success_rate": 87.9}
    },
    "performance_trends": [
        {
            "date": "2024-08-01",
            "migrations": 5,
            "avg_duration": "32m 15s",
            "avg_transfer_rate": "1.8 MB/s"
        }
    ]
}
```

This comprehensive API guide covers all aspects of using the Migration Assistant REST API. For CLI usage, see the [CLI User Guide](cli-guide.md), and for specific migration scenarios, check the [Migration Guides](../migration-guides/) section.