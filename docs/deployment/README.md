# Deployment Guide

This guide covers deploying the Web & Database Migration Assistant in various environments, from development to production.

## 📋 Table of Contents

- [Deployment Overview](#deployment-overview)
- [Docker Deployment](#docker-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Cloud Platform Deployment](#cloud-platform-deployment)
- [Traditional Server Deployment](#traditional-server-deployment)
- [Configuration Management](#configuration-management)
- [Monitoring and Logging](#monitoring-and-logging)
- [Security Considerations](#security-considerations)

## 🌐 Deployment Overview

### Deployment Options
The Migration Assistant can be deployed in several ways:

1. **Standalone CLI**: Single-user command-line tool
2. **API Server**: Multi-user REST API service
3. **Docker Container**: Containerized deployment
4. **Kubernetes**: Scalable container orchestration
5. **Cloud Services**: Managed cloud deployments
6. **Hybrid**: CLI + API server combination

### Architecture Components
- **CLI Application**: Interactive command-line interface
- **API Server**: FastAPI-based REST API
- **Go Engine**: High-performance binary for file operations
- **Database**: Optional persistent storage for sessions
- **Message Queue**: Optional for background job processing
- **Load Balancer**: For high-availability deployments

## 🐳 Docker Deployment

### Single Container Deployment
```bash
# Pull the official image
docker pull migration-assistant/migration-assistant:latest

# Run CLI in container
docker run -it --rm \
  -v $(pwd)/config:/config \
  -v $(pwd)/data:/data \
  migration-assistant/migration-assistant:latest \
  migration-assistant migrate --config /config/migration.yaml

# Run API server
docker run -d \
  --name migration-api \
  -p 8000:8000 \
  -v $(pwd)/config:/config \
  -e MIGRATION_CONFIG_FILE=/config/api-config.yaml \
  migration-assistant/migration-assistant:latest \
  migration-assistant serve --host 0.0.0.0 --port 8000
```

### Docker Compose Deployment
```yaml
# docker-compose.yml
version: '3.8'

services:
  migration-api:
    image: migration-assistant/migration-assistant:latest
    ports:
      - "8000:8000"
    environment:
      - MIGRATION_DB_URL=postgresql://user:pass@db:5432/migrations
      - MIGRATION_JWT_SECRET=your-secret-key
      - MIGRATION_USE_GO_ENGINE=true
    volumes:
      - ./config:/config
      - ./data:/data
      - ./logs:/logs
    command: migration-assistant serve --host 0.0.0.0 --port 8000
    depends_on:
      - db
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=migrations
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - migration-api
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

### Custom Dockerfile
```dockerfile
# Dockerfile.production
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    openssh-client \
    rsync \
    mysql-client \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Go
RUN curl -L https://go.dev/dl/go1.21.5.linux-amd64.tar.gz | tar -C /usr/local -xz
ENV PATH="/usr/local/go/bin:${PATH}"

# Create app user
RUN useradd --create-home --shell /bin/bash app
USER app
WORKDIR /home/app

# Copy application
COPY --chown=app:app . .

# Install Python dependencies
RUN pip install --user --no-cache-dir -e .

# Build Go binaries
RUN cd go-engine && go build -o ../migration_assistant/bin/migration-engine ./cmd/migration-engine

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["migration-assistant", "serve", "--host", "0.0.0.0", "--port", "8000"]
```

## ☸️ Kubernetes Deployment

### Basic Deployment
```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: migration-assistant
---
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: migration-assistant
  namespace: migration-assistant
  labels:
    app: migration-assistant
spec:
  replicas: 3
  selector:
    matchLabels:
      app: migration-assistant
  template:
    metadata:
      labels:
        app: migration-assistant
    spec:
      containers:
      - name: migration-assistant
        image: migration-assistant/migration-assistant:latest
        ports:
        - containerPort: 8000
        env:
        - name: MIGRATION_DB_URL
          valueFrom:
            secretKeyRef:
              name: migration-secrets
              key: database-url
        - name: MIGRATION_JWT_SECRET
          valueFrom:
            secretKeyRef:
              name: migration-secrets
              key: jwt-secret
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        volumeMounts:
        - name: config
          mountPath: /config
        - name: data
          mountPath: /data
      volumes:
      - name: config
        configMap:
          name: migration-config
      - name: data
        persistentVolumeClaim:
          claimName: migration-data
---
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: migration-assistant-service
  namespace: migration-assistant
spec:
  selector:
    app: migration-assistant
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
---
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: migration-assistant-ingress
  namespace: migration-assistant
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  tls:
  - hosts:
    - migration-api.yourdomain.com
    secretName: migration-tls
  rules:
  - host: migration-api.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: migration-assistant-service
            port:
              number: 80
```

### Helm Chart
```yaml
# helm/migration-assistant/Chart.yaml
apiVersion: v2
name: migration-assistant
description: A Helm chart for Migration Assistant
type: application
version: 1.0.0
appVersion: "1.0.0"

# helm/migration-assistant/values.yaml
replicaCount: 3

image:
  repository: migration-assistant/migration-assistant
  pullPolicy: IfNotPresent
  tag: "latest"

service:
  type: ClusterIP
  port: 80
  targetPort: 8000

ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: migration-api.yourdomain.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: migration-tls
      hosts:
        - migration-api.yourdomain.com

resources:
  limits:
    cpu: 1000m
    memory: 2Gi
  requests:
    cpu: 250m
    memory: 512Mi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 80
  targetMemoryUtilizationPercentage: 80

persistence:
  enabled: true
  storageClass: "fast-ssd"
  size: 10Gi

postgresql:
  enabled: true
  auth:
    postgresPassword: "secure-password"
    database: "migrations"

redis:
  enabled: true
  auth:
    enabled: false
```

## ☁️ Cloud Platform Deployment

### AWS Deployment

#### ECS Fargate
```json
{
  "family": "migration-assistant",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::account:role/migrationAssistantTaskRole",
  "containerDefinitions": [
    {
      "name": "migration-assistant",
      "image": "migration-assistant/migration-assistant:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "MIGRATION_USE_GO_ENGINE",
          "value": "true"
        }
      ],
      "secrets": [
        {
          "name": "MIGRATION_DB_URL",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:migration-db-url"
        },
        {
          "name": "MIGRATION_JWT_SECRET",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:migration-jwt-secret"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/migration-assistant",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
```

#### Lambda Deployment
```python
# lambda/handler.py
import json
from mangum import Mangum
from migration_assistant.api.main import app

# Create Lambda handler
handler = Mangum(app, lifespan="off")

def lambda_handler(event, context):
    """AWS Lambda handler for Migration Assistant API."""
    return handler(event, context)
```

```yaml
# serverless.yml
service: migration-assistant-api

provider:
  name: aws
  runtime: python3.11
  region: us-east-1
  timeout: 900  # 15 minutes
  memorySize: 3008
  environment:
    MIGRATION_DB_URL: ${ssm:/migration-assistant/db-url}
    MIGRATION_JWT_SECRET: ${ssm:/migration-assistant/jwt-secret}
  iamRoleStatements:
    - Effect: Allow
      Action:
        - s3:*
        - rds:*
        - secretsmanager:GetSecretValue
      Resource: "*"

functions:
  api:
    handler: lambda.handler.lambda_handler
    events:
      - http:
          path: /{proxy+}
          method: ANY
          cors: true
    layers:
      - arn:aws:lambda:us-east-1:123456789:layer:migration-assistant-deps:1

plugins:
  - serverless-python-requirements
  - serverless-offline

custom:
  pythonRequirements:
    dockerizePip: true
    slim: true
```

### Google Cloud Deployment

#### Cloud Run
```yaml
# cloudrun.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: migration-assistant
  annotations:
    run.googleapis.com/ingress: all
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/maxScale: "10"
        run.googleapis.com/cpu-throttling: "false"
        run.googleapis.com/execution-environment: gen2
    spec:
      containerConcurrency: 100
      timeoutSeconds: 900
      containers:
      - image: gcr.io/project-id/migration-assistant:latest
        ports:
        - containerPort: 8000
        env:
        - name: MIGRATION_DB_URL
          valueFrom:
            secretKeyRef:
              name: migration-secrets
              key: database-url
        resources:
          limits:
            cpu: "2"
            memory: "4Gi"
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
```

#### GKE Deployment
```bash
# Deploy to GKE
gcloud container clusters create migration-cluster \
  --num-nodes=3 \
  --machine-type=e2-standard-4 \
  --enable-autoscaling \
  --min-nodes=1 \
  --max-nodes=10

kubectl apply -f k8s/
```

### Azure Deployment

#### Container Instances
```json
{
  "apiVersion": "2021-03-01",
  "type": "Microsoft.ContainerInstance/containerGroups",
  "name": "migration-assistant",
  "location": "East US",
  "properties": {
    "containers": [
      {
        "name": "migration-assistant",
        "properties": {
          "image": "migration-assistant/migration-assistant:latest",
          "ports": [
            {
              "port": 8000,
              "protocol": "TCP"
            }
          ],
          "environmentVariables": [
            {
              "name": "MIGRATION_USE_GO_ENGINE",
              "value": "true"
            }
          ],
          "resources": {
            "requests": {
              "cpu": 1,
              "memoryInGB": 2
            }
          }
        }
      }
    ],
    "osType": "Linux",
    "ipAddress": {
      "type": "Public",
      "ports": [
        {
          "port": 8000,
          "protocol": "TCP"
        }
      ]
    },
    "restartPolicy": "Always"
  }
}
```

## 🖥️ Traditional Server Deployment

### Systemd Service
```ini
# /etc/systemd/system/migration-assistant.service
[Unit]
Description=Migration Assistant API
After=network.target
Wants=network.target

[Service]
Type=simple
User=migration
Group=migration
WorkingDirectory=/opt/migration-assistant
Environment=PATH=/opt/migration-assistant/venv/bin
Environment=MIGRATION_CONFIG_FILE=/etc/migration-assistant/config.yaml
ExecStart=/opt/migration-assistant/venv/bin/migration-assistant serve --host 0.0.0.0 --port 8000
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Nginx Configuration
```nginx
# /etc/nginx/sites-available/migration-assistant
upstream migration_assistant {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;  # Additional instances
    server 127.0.0.1:8002;
}

server {
    listen 80;
    server_name migration-api.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name migration-api.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/migration-api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/migration-api.yourdomain.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;

    location / {
        proxy_pass http://migration_assistant;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /health {
        proxy_pass http://migration_assistant;
        access_log off;
    }
}
```

## ⚙️ Configuration Management

### Environment Variables
```bash
# Production environment variables
export MIGRATION_ENV=production
export MIGRATION_DEBUG=false
export MIGRATION_LOG_LEVEL=INFO

# Database
export MIGRATION_DB_URL=postgresql://user:pass@db:5432/migrations

# Authentication
export MIGRATION_JWT_SECRET=your-very-secure-secret-key
export MIGRATION_JWT_EXPIRE_HOURS=24

# Performance
export MIGRATION_USE_GO_ENGINE=true
export MIGRATION_MAX_WORKERS=4
export MIGRATION_MAX_MEMORY=4GB

# Cloud credentials
export AWS_ACCESS_KEY_ID=your-aws-key
export AWS_SECRET_ACCESS_KEY=your-aws-secret
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/gcp-credentials.json
export AZURE_CLIENT_ID=your-azure-client-id
export AZURE_CLIENT_SECRET=your-azure-secret
export AZURE_TENANT_ID=your-azure-tenant
```

### Configuration Files
```yaml
# config/production.yaml
environment: production
debug: false
log_level: INFO

server:
  host: 0.0.0.0
  port: 8000
  workers: 4
  max_connections: 1000

database:
  url: ${MIGRATION_DB_URL}
  pool_size: 20
  max_overflow: 30
  echo: false

authentication:
  jwt_secret: ${MIGRATION_JWT_SECRET}
  jwt_expire_hours: 24
  enable_api_keys: true

performance:
  use_go_engine: true
  max_memory: 4GB
  temp_directory: /tmp/migration-assistant
  cleanup_temp_files: true

monitoring:
  enable_metrics: true
  metrics_port: 9090
  health_check_interval: 30

logging:
  level: INFO
  format: json
  file: /var/log/migration-assistant/app.log
  max_size: 100MB
  backup_count: 5
```

## 📊 Monitoring and Logging

### Prometheus Configuration
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'migration-assistant'
    static_configs:
      - targets: ['migration-api:8000']
    metrics_path: /health/metrics
    scrape_interval: 30s
```

### Grafana Dashboard
```json
{
  "dashboard": {
    "title": "Migration Assistant Metrics",
    "panels": [
      {
        "title": "API Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "migration_assistant_request_duration_seconds",
            "legendFormat": "{{method}} {{endpoint}}"
          }
        ]
      },
      {
        "title": "Active Migrations",
        "type": "stat",
        "targets": [
          {
            "expr": "migration_assistant_active_migrations_total"
          }
        ]
      },
      {
        "title": "System Resources",
        "type": "graph",
        "targets": [
          {
            "expr": "migration_assistant_cpu_usage_percent",
            "legendFormat": "CPU Usage"
          },
          {
            "expr": "migration_assistant_memory_usage_percent",
            "legendFormat": "Memory Usage"
          }
        ]
      }
    ]
  }
}
```

### Log Aggregation
```yaml
# filebeat.yml
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /var/log/migration-assistant/*.log
  fields:
    service: migration-assistant
  fields_under_root: true

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
  index: "migration-assistant-%{+yyyy.MM.dd}"

logging.level: info
```

## 🔒 Security Considerations

### Security Checklist
- [ ] Use HTTPS/TLS for all communications
- [ ] Implement proper authentication and authorization
- [ ] Store secrets in secure secret management systems
- [ ] Enable audit logging for all operations
- [ ] Use network security groups/firewalls
- [ ] Implement rate limiting and DDoS protection
- [ ] Regular security updates and vulnerability scanning
- [ ] Backup encryption and secure storage
- [ ] Principle of least privilege for service accounts
- [ ] Container image scanning and signing

### Security Configuration
```yaml
# security.yaml
security:
  tls:
    enabled: true
    cert_file: /etc/ssl/certs/migration-assistant.crt
    key_file: /etc/ssl/private/migration-assistant.key
    min_version: "1.2"
  
  authentication:
    required: true
    methods: ["jwt", "api_key", "oauth2"]
    session_timeout: 3600
  
  authorization:
    rbac_enabled: true
    default_role: "user"
  
  audit:
    enabled: true
    log_file: /var/log/migration-assistant/audit.log
    log_level: INFO
  
  rate_limiting:
    enabled: true
    requests_per_minute: 100
    burst_size: 20
```

This comprehensive deployment guide covers all major deployment scenarios. Choose the deployment method that best fits your infrastructure and requirements.