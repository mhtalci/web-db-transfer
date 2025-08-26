# OpenAPI Specification

The Migration Assistant API provides a comprehensive REST interface with auto-generated OpenAPI documentation. This document covers the complete API specification with examples and use cases.

## 📋 Table of Contents

- [API Overview](#api-overview)
- [OpenAPI Specification](#openapi-specification)
- [Authentication](#authentication)
- [Core Resources](#core-resources)
- [Request/Response Examples](#requestresponse-examples)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [Webhooks](#webhooks)

## 🌐 API Overview

### Base Information
- **OpenAPI Version**: 3.0.3
- **API Version**: 1.0.0
- **Base URL**: `http://localhost:8000` (configurable)
- **Content Type**: `application/json`
- **Documentation URLs**:
  - Swagger UI: `/docs`
  - ReDoc: `/redoc`
  - OpenAPI JSON: `/openapi.json`
  - OpenAPI YAML: `/openapi.yaml`

### Interactive Documentation
The API provides interactive documentation that allows you to:
- Explore all endpoints and their parameters
- Test API calls directly from the browser
- View request/response schemas
- Download OpenAPI specification files

Access the interactive documentation at:
```
http://localhost:8000/docs
```

## 📄 OpenAPI Specification

### Complete OpenAPI JSON
The complete OpenAPI specification is available at `/openapi.json`. Here's the core structure:

```json
{
  "openapi": "3.0.3",
  "info": {
    "title": "Web & Database Migration Assistant API",
    "description": "A comprehensive REST API for migrating web applications and databases between different systems, platforms, and environments",
    "version": "1.0.0",
    "contact": {
      "name": "Migration Assistant Support",
      "url": "https://github.com/migration-assistant/support",
      "email": "support@migration-assistant.com"
    },
    "license": {
      "name": "MIT",
      "url": "https://opensource.org/licenses/MIT"
    }
  },
  "servers": [
    {
      "url": "http://localhost:8000",
      "description": "Development server"
    },
    {
      "url": "https://api.migration-assistant.com",
      "description": "Production server"
    }
  ],
  "paths": {
    "/": {
      "get": {
        "tags": ["Root"],
        "summary": "Root endpoint with API information",
        "operationId": "root",
        "responses": {
          "200": {
            "description": "API information",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/APIInfo"
                }
              }
            }
          }
        }
      }
    },
    "/health": {
      "get": {
        "tags": ["Health"],
        "summary": "Health check endpoint",
        "operationId": "health_check",
        "responses": {
          "200": {
            "description": "Health status",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HealthStatus"
                }
              }
            }
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "APIInfo": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "example": "Web & Database Migration Assistant API"
          },
          "version": {
            "type": "string",
            "example": "1.0.0"
          },
          "description": {
            "type": "string"
          },
          "features": {
            "type": "array",
            "items": {
              "type": "string"
            }
          }
        }
      }
    },
    "securitySchemes": {
      "BearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT"
      },
      "ApiKeyAuth": {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key"
      }
    }
  }
}
```

### Schema Definitions

#### Migration Configuration Schema
```json
{
  "MigrationConfig": {
    "type": "object",
    "required": ["name", "source", "destination"],
    "properties": {
      "name": {
        "type": "string",
        "description": "Human-readable name for the migration",
        "example": "WordPress to AWS Migration"
      },
      "description": {
        "type": "string",
        "description": "Optional description of the migration"
      },
      "source": {
        "$ref": "#/components/schemas/SystemConfig"
      },
      "destination": {
        "$ref": "#/components/schemas/SystemConfig"
      },
      "transfer": {
        "$ref": "#/components/schemas/TransferConfig"
      },
      "safety": {
        "$ref": "#/components/schemas/SafetyConfig"
      },
      "notifications": {
        "$ref": "#/components/schemas/NotificationConfig"
      }
    }
  },
  "SystemConfig": {
    "type": "object",
    "required": ["type", "host"],
    "properties": {
      "type": {
        "type": "string",
        "enum": [
          "wordpress", "drupal", "django", "static", "mysql", 
          "postgresql", "mongodb", "aws-s3", "gcp-gcs", "azure-blob",
          "cpanel", "directadmin", "plesk"
        ],
        "description": "Type of system being migrated"
      },
      "host": {
        "type": "string",
        "description": "Hostname or IP address",
        "example": "old-server.com"
      },
      "port": {
        "type": "integer",
        "description": "Port number (optional)",
        "example": 22
      },
      "username": {
        "type": "string",
        "description": "Username for authentication"
      },
      "password": {
        "type": "string",
        "description": "Password for authentication (use environment variables)"
      },
      "api_key": {
        "type": "string",
        "description": "API key for authentication"
      },
      "database": {
        "$ref": "#/components/schemas/DatabaseConfig"
      },
      "paths": {
        "$ref": "#/components/schemas/PathConfig"
      }
    }
  },
  "DatabaseConfig": {
    "type": "object",
    "required": ["type"],
    "properties": {
      "type": {
        "type": "string",
        "enum": [
          "mysql", "postgresql", "mongodb", "redis", "sqlite",
          "aurora-mysql", "aurora-postgres", "cloud-sql"
        ]
      },
      "host": {
        "type": "string",
        "example": "db-server.com"
      },
      "port": {
        "type": "integer",
        "example": 3306
      },
      "username": {
        "type": "string"
      },
      "password": {
        "type": "string"
      },
      "database": {
        "type": "string",
        "description": "Database name"
      }
    }
  }
}
```

#### Migration Session Schema
```json
{
  "MigrationSession": {
    "type": "object",
    "properties": {
      "id": {
        "type": "string",
        "description": "Unique session identifier",
        "example": "abc123def456"
      },
      "name": {
        "type": "string",
        "example": "WordPress to AWS Migration"
      },
      "status": {
        "type": "string",
        "enum": ["pending", "running", "completed", "failed", "cancelled"],
        "description": "Current migration status"
      },
      "progress": {
        "type": "number",
        "minimum": 0,
        "maximum": 100,
        "description": "Progress percentage"
      },
      "created_at": {
        "type": "string",
        "format": "date-time",
        "description": "Session creation timestamp"
      },
      "start_time": {
        "type": "string",
        "format": "date-time",
        "description": "Migration start timestamp"
      },
      "end_time": {
        "type": "string",
        "format": "date-time",
        "description": "Migration completion timestamp"
      },
      "duration": {
        "type": "number",
        "description": "Migration duration in seconds"
      },
      "current_step": {
        "type": "string",
        "description": "Current migration step"
      },
      "steps_completed": {
        "type": "integer",
        "description": "Number of completed steps"
      },
      "steps_total": {
        "type": "integer",
        "description": "Total number of steps"
      }
    }
  }
}
```

## 🔐 Authentication

### Security Schemes
The API supports multiple authentication methods:

```json
{
  "securitySchemes": {
    "BearerAuth": {
      "type": "http",
      "scheme": "bearer",
      "bearerFormat": "JWT",
      "description": "JWT token authentication"
    },
    "ApiKeyAuth": {
      "type": "apiKey",
      "in": "header",
      "name": "X-API-Key",
      "description": "API key authentication"
    },
    "OAuth2": {
      "type": "oauth2",
      "flows": {
        "authorizationCode": {
          "authorizationUrl": "/auth/authorize",
          "tokenUrl": "/auth/token",
          "scopes": {
            "migrations:read": "Read migration data",
            "migrations:write": "Create and modify migrations",
            "presets:read": "Read preset configurations",
            "presets:write": "Create and modify presets",
            "admin": "Administrative access"
          }
        }
      }
    }
  }
}
```

### Authentication Examples

#### JWT Token Authentication
```bash
# Get JWT token
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "user", "password": "pass"}'

# Use JWT token
curl -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..." \
  http://localhost:8000/migrations/
```

#### API Key Authentication
```bash
# Use API key
curl -H "X-API-Key: your-api-key-here" \
  http://localhost:8000/migrations/
```

## 🔧 Core Resources

### Migrations Resource

#### Create Migration
```yaml
POST /migrations/
summary: Create a new migration session
requestBody:
  required: true
  content:
    application/json:
      schema:
        $ref: '#/components/schemas/MigrationConfig'
      examples:
        wordpress_migration:
          summary: WordPress to AWS Migration
          value:
            name: "WordPress to AWS Migration"
            source:
              type: "wordpress"
              host: "old-server.com"
              username: "user"
              password: "pass"
              database:
                type: "mysql"
                host: "old-server.com"
                username: "wp_user"
                password: "wp_pass"
                database: "wordpress_db"
            destination:
              type: "aws-s3"
              region: "us-east-1"
              bucket: "my-new-website"
responses:
  '201':
    description: Migration session created
    content:
      application/json:
        schema:
          $ref: '#/components/schemas/MigrationCreateResponse'
  '400':
    description: Invalid configuration
    content:
      application/json:
        schema:
          $ref: '#/components/schemas/ErrorResponse'
```

#### Get Migration Status
```yaml
GET /migrations/{session_id}/status
summary: Get migration status by session ID
parameters:
  - name: session_id
    in: path
    required: true
    schema:
      type: string
    description: Unique migration session identifier
responses:
  '200':
    description: Migration status
    content:
      application/json:
        schema:
          $ref: '#/components/schemas/MigrationStatusResponse'
        examples:
          running_migration:
            summary: Running Migration
            value:
              session_id: "abc123def456"
              status: "running"
              progress: 65.5
              current_step: "Transferring files"
              start_time: "2024-08-26T14:30:22.123456Z"
              duration: 1125.5
              steps_completed: 5
              steps_total: 8
  '404':
    description: Migration session not found
```

### Presets Resource

#### List Presets
```yaml
GET /presets/
summary: List available migration presets
responses:
  '200':
    description: List of presets
    content:
      application/json:
        schema:
          type: array
          items:
            $ref: '#/components/schemas/PresetResponse'
        examples:
          preset_list:
            summary: Available Presets
            value:
              - id: "wordpress-mysql"
                name: "WordPress with MySQL"
                description: "WordPress CMS with MySQL database migration"
                source_types: ["wordpress"]
                destination_types: ["aws-s3", "gcp-gcs"]
              - id: "django-postgres"
                name: "Django with PostgreSQL"
                description: "Django application with PostgreSQL database"
                source_types: ["django"]
                destination_types: ["aws-ec2", "gcp-compute"]
```

### Validation Resource

#### Validate Configuration
```yaml
POST /validate/
summary: Validate a migration configuration
requestBody:
  required: true
  content:
    application/json:
      schema:
        $ref: '#/components/schemas/MigrationConfig'
responses:
  '200':
    description: Validation results
    content:
      application/json:
        schema:
          $ref: '#/components/schemas/ValidationResponse'
        examples:
          validation_success:
            summary: Successful Validation
            value:
              valid: true
              checks_performed: 12
              checks_passed: 11
              checks_failed: 0
              warnings: ["Large file detected: video.mp4 (500MB)"]
              errors: []
              can_proceed: true
              estimated_duration: "35-45 minutes"
```

## 📝 Request/Response Examples

### Complete Migration Workflow

#### 1. Create Migration
```http
POST /migrations/ HTTP/1.1
Host: localhost:8000
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
Content-Type: application/json

{
  "name": "WordPress to AWS Migration",
  "description": "Migrating company website to AWS infrastructure",
  "source": {
    "type": "wordpress",
    "host": "old-server.com",
    "port": 22,
    "username": "user",
    "password": "secure_password",
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
      "parallel_transfers": 4
    }
  },
  "safety": {
    "backup_before": true,
    "verify_after": true,
    "rollback_on_failure": true
  }
}
```

**Response:**
```http
HTTP/1.1 201 Created
Content-Type: application/json

{
  "session_id": "abc123def456",
  "status": "created",
  "message": "Migration session created successfully",
  "created_at": "2024-08-26T14:30:22.123456Z"
}
```

#### 2. Start Migration
```http
POST /migrations/abc123def456/start HTTP/1.1
Host: localhost:8000
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
Content-Type: application/json

{
  "auto_rollback": true
}
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "session_id": "abc123def456",
  "status": "started",
  "message": "Migration execution started in background"
}
```

#### 3. Monitor Progress
```http
GET /migrations/abc123def456/status HTTP/1.1
Host: localhost:8000
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "session_id": "abc123def456",
  "status": "running",
  "progress": 65.5,
  "current_step": "Transferring files",
  "start_time": "2024-08-26T14:30:22.123456Z",
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
  }
}
```

### Error Response Examples

#### Validation Error
```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Configuration validation failed",
    "details": {
      "validation_errors": [
        {
          "field": "source.host",
          "message": "Host is not reachable",
          "suggestion": "Check network connectivity and firewall settings"
        },
        {
          "field": "destination.bucket",
          "message": "S3 bucket name contains invalid characters",
          "suggestion": "Use lowercase letters, numbers, and hyphens only"
        }
      ]
    },
    "timestamp": "2024-08-26T14:30:22.123456Z",
    "request_id": "req-abc123def456"
  }
}
```

#### Authentication Error
```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{
  "error": {
    "code": "AUTHENTICATION_REQUIRED",
    "message": "Authentication credentials required",
    "details": {
      "supported_methods": ["Bearer", "API-Key"],
      "auth_url": "/auth/token"
    },
    "timestamp": "2024-08-26T14:30:22.123456Z",
    "request_id": "req-def456ghi789"
  }
}
```

## ⚡ Rate Limiting

### Rate Limit Headers
All API responses include rate limiting headers:

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
X-RateLimit-Window: 3600
```

### Rate Limit Schema
```json
{
  "RateLimitResponse": {
    "type": "object",
    "properties": {
      "error": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "example": "RATE_LIMIT_EXCEEDED"
          },
          "message": {
            "type": "string",
            "example": "Rate limit exceeded"
          },
          "details": {
            "type": "object",
            "properties": {
              "limit": {
                "type": "integer",
                "example": 1000
              },
              "window": {
                "type": "integer",
                "example": 3600
              },
              "reset_time": {
                "type": "string",
                "format": "date-time"
              }
            }
          }
        }
      }
    }
  }
}
```

## 🔗 Webhooks

### Webhook Configuration Schema
```json
{
  "WebhookConfig": {
    "type": "object",
    "required": ["url", "events"],
    "properties": {
      "url": {
        "type": "string",
        "format": "uri",
        "description": "Webhook endpoint URL"
      },
      "events": {
        "type": "array",
        "items": {
          "type": "string",
          "enum": [
            "migration.created",
            "migration.started",
            "migration.progress",
            "migration.completed",
            "migration.failed",
            "migration.cancelled"
          ]
        }
      },
      "headers": {
        "type": "object",
        "additionalProperties": {
          "type": "string"
        }
      },
      "secret": {
        "type": "string",
        "description": "Secret for webhook signature verification"
      }
    }
  }
}
```

### Webhook Payload Schema
```json
{
  "WebhookPayload": {
    "type": "object",
    "properties": {
      "event": {
        "type": "string",
        "example": "migration.progress"
      },
      "timestamp": {
        "type": "string",
        "format": "date-time"
      },
      "data": {
        "type": "object",
        "properties": {
          "session_id": {
            "type": "string"
          },
          "status": {
            "type": "string"
          },
          "progress": {
            "type": "number"
          }
        }
      }
    }
  }
}
```

## 📊 OpenAPI Tools and Integration

### Code Generation
Generate client SDKs using OpenAPI generators:

```bash
# Generate Python client
openapi-generator-cli generate \
  -i http://localhost:8000/openapi.json \
  -g python \
  -o ./python-client

# Generate JavaScript client
openapi-generator-cli generate \
  -i http://localhost:8000/openapi.json \
  -g javascript \
  -o ./js-client

# Generate Go client
openapi-generator-cli generate \
  -i http://localhost:8000/openapi.json \
  -g go \
  -o ./go-client
```

### API Testing
Use the OpenAPI specification for automated testing:

```bash
# Install Dredd for API testing
npm install -g dredd

# Test API against OpenAPI spec
dredd http://localhost:8000/openapi.json http://localhost:8000
```

### Documentation Generation
Generate static documentation:

```bash
# Generate ReDoc documentation
redoc-cli build http://localhost:8000/openapi.json

# Generate Swagger UI
swagger-codegen generate \
  -i http://localhost:8000/openapi.json \
  -l html2 \
  -o ./api-docs
```

This comprehensive OpenAPI documentation provides complete API specification details, examples, and integration guidance. For practical usage examples, see the [API User Guide](../user-guide/api-guide.md).