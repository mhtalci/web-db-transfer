# CMS Migration API Reference

The CMS Migration API provides comprehensive REST endpoints for managing CMS platform detection, health checking, migration orchestration, and real-time monitoring.

## Base URL
```
http://localhost:8000/api/v1/cms
```

## Authentication
Currently, the API does not require authentication. In production environments, implement appropriate authentication mechanisms.

## Endpoints Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/platforms` | GET | Get supported CMS platforms |
| `/detect` | POST | Detect CMS platforms at path |
| `/health-check` | POST | Perform CMS health check |
| `/compatibility-check` | POST | Check migration compatibility |
| `/migration/plan` | POST | Create migration plan |
| `/migration/execute` | POST | Execute migration plan |
| `/migration/{id}/status` | GET | Get migration status |
| `/migration/{id}/stream` | GET | Stream real-time progress |
| `/migration/{id}/pause` | POST | Pause migration |
| `/migration/{id}/resume` | POST | Resume migration |
| `/migration/{id}/cancel` | POST | Cancel migration |
| `/migration/{id}/report` | GET | Get migration report |
| `/statistics` | GET | Get global statistics |
| `/health` | GET | API health check |

## Detailed Endpoint Documentation

### GET /platforms
Get list of all supported CMS platforms with detailed information.

**Response:**
```json
{
  "total_platforms": 12,
  "platforms": {
    "wordpress": {
      "platform_type": "wordpress",
      "supported_versions": ["4.0", "4.1", "...", "6.5"],
      "class_name": "WordPressAdapter"
    },
    "magento": {
      "platform_type": "magento", 
      "supported_versions": ["2.0", "2.1", "2.2", "2.3", "2.4"],
      "class_name": "MagentoAdapter"
    }
  },
  "categories": {
    "content_management": ["wordpress", "drupal", "joomla", "typo3", "concrete5", "ghost", "craftcms", "umbraco"],
    "ecommerce": ["magento", "shopware", "prestashop", "opencart"]
  }
}
```

### POST /detect
Detect CMS platforms at the specified path.

**Request:**
```json
{
  "path": "/path/to/cms/installation"
}
```

**Response:**
```json
{
  "detected_platforms": [
    {
      "platform_type": "wordpress",
      "version": "6.4.2",
      "framework": "wordpress",
      "database_type": "mysql",
      "config_files": ["wp-config.php", ".htaccess"],
      "dependencies": [
        {
          "name": "php",
          "version": ">=7.4",
          "required": true
        },
        {
          "name": "mysql",
          "version": ">=5.7", 
          "required": true
        }
      ]
    }
  ],
  "analysis_time": 2.34,
  "path": "/path/to/cms/installation"
}
```

### POST /health-check
Perform comprehensive health check on CMS installation.

**Request:**
```json
{
  "platform_type": "wordpress",
  "path": "/path/to/wordpress"
}
```

**Response:**
```json
{
  "platform": "wordpress",
  "health_score": 85,
  "total_issues": 3,
  "severity_breakdown": {
    "critical": 0,
    "error": 1,
    "warning": 2,
    "info": 0
  },
  "issues": [
    {
      "severity": "error",
      "category": "Security",
      "message": "wp-config.php has overly permissive permissions",
      "details": "File permissions are 644, should be 600",
      "fix_suggestion": "Run: chmod 600 wp-config.php"
    },
    {
      "severity": "warning",
      "category": "Performance", 
      "message": "Large number of files detected: 15,847",
      "fix_suggestion": "Consider cleaning up unnecessary files"
    }
  ],
  "recommendations": [
    "Fix 1 security issue before migration",
    "Review performance optimizations"
  ]
}
```

### POST /compatibility-check
Check compatibility between source and destination platforms.

**Request:**
```json
{
  "source_platform": "wordpress",
  "source_version": "6.4.2",
  "destination_platform": "drupal",
  "destination_version": "10.1"
}
```

**Response:**
```json
{
  "compatible": true,
  "migration_complexity": "complex",
  "estimated_success_rate": 82,
  "issues": [],
  "warnings": [
    "Cross-platform migration will require content transformation",
    "Plugin compatibility cannot be guaranteed"
  ]
}
```

### POST /migration/plan
Create a detailed migration plan.

**Request:**
```json
{
  "source_platform": "wordpress",
  "destination_platform": "wordpress",
  "source_path": "/path/to/source",
  "destination_path": "/path/to/destination",
  "options": {
    "create_backup": true,
    "cleanup_temp_files": true,
    "verify_integrity": true
  }
}
```

**Response:**
```json
{
  "migration_id": "migration_1703123456",
  "total_steps": 15,
  "estimated_duration": 2700,
  "steps": [
    {
      "id": "health_check_source",
      "name": "Source Health Check",
      "stage": "preparation",
      "description": "Analyze source platform health and readiness",
      "estimated_duration": 120,
      "dependencies": []
    },
    {
      "id": "create_backup",
      "name": "Create Backup",
      "stage": "backup",
      "description": "Create full backup of source platform",
      "estimated_duration": 600,
      "dependencies": ["health_check_source"]
    }
  ]
}
```

### POST /migration/execute
Execute migration plan with background processing.

**Request:**
```json
{
  "migration_id": "migration_1703123456"
}
```

**Response:**
```json
{
  "migration_id": "migration_1703123456",
  "status": "started",
  "message": "Migration execution started. Use /migration/{migration_id}/status for updates."
}
```

### GET /migration/{migration_id}/status
Get current migration status and progress.

**Response:**
```json
{
  "migration_id": "migration_1703123456",
  "source_platform": "wordpress",
  "destination_platform": "wordpress",
  "overall_progress": 45.5,
  "completed_steps": 7,
  "failed_steps": 0,
  "total_steps": 15,
  "elapsed_time": 1234.5,
  "estimated_remaining_time": 1465.5,
  "current_stage": "export",
  "performance": {
    "files_processed": 8547,
    "bytes_processed": 2147483648,
    "average_throughput_mbps": 12.5,
    "system_metrics": {
      "memory_usage_percent": 67.2,
      "cpu_usage_percent": 45.8,
      "disk_usage_percent": 23.1
    }
  },
  "steps": [
    {
      "id": "health_check_source",
      "name": "Source Health Check",
      "stage": "preparation",
      "status": "completed",
      "progress": 100.0,
      "error_message": null
    }
  ]
}
```

### GET /migration/{migration_id}/stream
Stream real-time migration progress using Server-Sent Events.

**Response (Stream):**
```
data: {"migration_id": "migration_1703123456", "overall_progress": 45.5, "message": "Exporting database...", "timestamp": "2023-12-21T10:30:45Z"}

data: {"migration_id": "migration_1703123456", "overall_progress": 47.2, "message": "Database export completed", "timestamp": "2023-12-21T10:31:15Z"}
```

### POST /migration/{migration_id}/pause
Pause an active migration.

**Response:**
```json
{
  "migration_id": "migration_1703123456",
  "status": "paused"
}
```

### POST /migration/{migration_id}/resume
Resume a paused migration.

**Response:**
```json
{
  "migration_id": "migration_1703123456", 
  "status": "resumed"
}
```

### POST /migration/{migration_id}/cancel
Cancel an active migration.

**Response:**
```json
{
  "migration_id": "migration_1703123456",
  "status": "cancelled"
}
```

### GET /migration/{migration_id}/report
Get comprehensive migration performance report.

**Response:**
```json
{
  "migration_id": "migration_1703123456",
  "report_generated": "2023-12-21T11:45:30Z",
  "migration_duration": 2847.3,
  "overall_metrics": {
    "files_processed": 12847,
    "bytes_processed": 3221225472,
    "database_records": 45678,
    "errors": 2,
    "warnings": 5,
    "average_throughput_mbps": 15.2
  },
  "performance_statistics": {
    "files_per_second": 4.51,
    "error_rate_percent": 0.016,
    "throughput_mbps": 15.2,
    "performance_grade": "A"
  },
  "step_performance": {
    "export_database": {
      "total_duration": 456.7,
      "average_duration": 456.7,
      "execution_count": 1,
      "error_count": 0,
      "success_rate_percent": 100.0
    }
  },
  "recommendations": [
    "Performance is optimal - no specific recommendations",
    "Consider enabling compression for future migrations"
  ]
}
```

### GET /statistics
Get global migration statistics and platform performance data.

**Response:**
```json
{
  "total_migrations": 1247,
  "successful_migrations": 1189,
  "success_rate_percent": 95.3,
  "total_platforms_supported": 12,
  "most_popular_platforms": [
    {
      "platform": "wordpress",
      "migrations": 456,
      "success_rate": 97.8
    },
    {
      "platform": "drupal", 
      "migrations": 234,
      "success_rate": 94.2
    }
  ],
  "average_migration_time_minutes": 42,
  "total_data_migrated_gb": 15847.3,
  "platform_compatibility_matrix": {
    "wordpress": ["wordpress", "drupal", "ghost"],
    "drupal": ["drupal", "wordpress", "ghost"],
    "magento": ["magento", "shopware", "prestashop", "opencart"]
  }
}
```

### GET /health
API health check and service status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2023-12-21T12:00:00Z",
  "version": "2.0.0",
  "features": {
    "platform_detection": true,
    "health_checking": true,
    "migration_orchestration": true,
    "real_time_monitoring": true,
    "performance_analytics": true
  },
  "supported_platforms": 12
}
```

## Error Responses

All endpoints return consistent error responses:

```json
{
  "detail": "Error description",
  "status_code": 400
}
```

Common HTTP status codes:
- `200` - Success
- `400` - Bad Request (invalid parameters)
- `404` - Not Found (resource doesn't exist)
- `500` - Internal Server Error

## Rate Limiting

The API implements rate limiting to prevent abuse:
- **Detection endpoints**: 10 requests per minute
- **Migration endpoints**: 5 requests per minute  
- **Status endpoints**: 60 requests per minute
- **Streaming endpoints**: 1 concurrent connection per migration

## WebSocket Support

For real-time updates, the API also supports WebSocket connections:

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/cms/migration/migration_123/ws');

ws.onmessage = function(event) {
    const progress = JSON.parse(event.data);
    console.log(`Progress: ${progress.overall_progress}%`);
};
```

## SDK Examples

### Python SDK
```python
import aiohttp
import asyncio

class CMSMigrationClient:
    def __init__(self, base_url="http://localhost:8000/api/v1/cms"):
        self.base_url = base_url
    
    async def detect_platforms(self, path):
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/detect", 
                                   json={"path": path}) as response:
                return await response.json()
    
    async def create_migration_plan(self, source_platform, destination_platform, 
                                  source_path, destination_path, options=None):
        data = {
            "source_platform": source_platform,
            "destination_platform": destination_platform,
            "source_path": source_path,
            "destination_path": destination_path,
            "options": options or {}
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/migration/plan", 
                                   json=data) as response:
                return await response.json()

# Usage
client = CMSMigrationClient()
platforms = await client.detect_platforms("/path/to/cms")
```

### JavaScript SDK
```javascript
class CMSMigrationClient {
    constructor(baseUrl = 'http://localhost:8000/api/v1/cms') {
        this.baseUrl = baseUrl;
    }
    
    async detectPlatforms(path) {
        const response = await fetch(`${this.baseUrl}/detect`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({path})
        });
        return response.json();
    }
    
    async streamMigrationProgress(migrationId, callback) {
        const eventSource = new EventSource(
            `${this.baseUrl}/migration/${migrationId}/stream`
        );
        
        eventSource.onmessage = (event) => {
            const progress = JSON.parse(event.data);
            callback(progress);
        };
        
        return eventSource;
    }
}

// Usage
const client = new CMSMigrationClient();
const platforms = await client.detectPlatforms('/path/to/cms');
```

## Best Practices

1. **Always check health** before starting migrations
2. **Monitor progress** using streaming endpoints for long-running operations
3. **Handle errors gracefully** with appropriate retry logic
4. **Use background tasks** for migration execution
5. **Implement proper logging** for debugging and auditing
6. **Set up alerts** for critical migration failures
7. **Regular backups** before any migration operation