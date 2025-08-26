#!/usr/bin/env python3
"""
Mock cPanel API server for testing.

This server simulates cPanel API v2/UAPI endpoints for testing
the migration assistant's control panel integration.
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Mock cPanel API", version="1.0.0")
security = HTTPBasic()

# Mock data
MOCK_ACCOUNTS = [
    {
        "user": "testuser1",
        "domain": "test1.com",
        "email": "user1@test1.com",
        "plan": "basic",
        "disk_used": 1024000,
        "disk_limit": 5120000,
        "created": "2023-01-15"
    },
    {
        "user": "testuser2", 
        "domain": "test2.com",
        "email": "user2@test2.com",
        "plan": "premium",
        "disk_used": 2048000,
        "disk_limit": 10240000,
        "created": "2023-02-20"
    }
]

MOCK_DATABASES = [
    {
        "name": "testuser1_wp",
        "user": "testuser1",
        "size": 512000,
        "type": "mysql",
        "host": "localhost"
    },
    {
        "name": "testuser2_app",
        "user": "testuser2", 
        "size": 1024000,
        "type": "mysql",
        "host": "localhost"
    }
]

MOCK_EMAIL_ACCOUNTS = [
    {
        "email": "admin@test1.com",
        "user": "testuser1",
        "quota": 1000,
        "usage": 500,
        "domain": "test1.com"
    },
    {
        "email": "info@test2.com",
        "user": "testuser2",
        "quota": 2000, 
        "usage": 1200,
        "domain": "test2.com"
    }
]

MOCK_DNS_RECORDS = [
    {
        "domain": "test1.com",
        "name": "test1.com",
        "type": "A",
        "record": "192.168.1.100",
        "ttl": 3600
    },
    {
        "domain": "test1.com",
        "name": "www.test1.com",
        "type": "CNAME", 
        "record": "test1.com",
        "ttl": 3600
    }
]

# Authentication
def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify API credentials."""
    if credentials.username != "testuser" or credentials.password != "testpass":
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return credentials.username

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "mock-cpanel-api"}

# cPanel API v2 endpoints
@app.get("/json-api/cpanel")
async def cpanel_api_v2(
    cpanel_jsonapi_module: str = Query(...),
    cpanel_jsonapi_func: str = Query(...),
    cpanel_jsonapi_apiversion: str = Query(default="2"),
    username: str = Depends(verify_credentials)
):
    """cPanel API v2 endpoint."""
    
    if cpanel_jsonapi_module == "Email" and cpanel_jsonapi_func == "listpops":
        return {
            "cpanelresult": {
                "data": [acc for acc in MOCK_EMAIL_ACCOUNTS if acc["user"] == username],
                "event": {"result": 1}
            }
        }
    
    elif cpanel_jsonapi_module == "Mysql" and cpanel_jsonapi_func == "listdbs":
        return {
            "cpanelresult": {
                "data": [db for db in MOCK_DATABASES if db["user"] == username],
                "event": {"result": 1}
            }
        }
    
    elif cpanel_jsonapi_module == "StatsBar" and cpanel_jsonapi_func == "stat":
        account = next((acc for acc in MOCK_ACCOUNTS if acc["user"] == username), None)
        if account:
            return {
                "cpanelresult": {
                    "data": [account],
                    "event": {"result": 1}
                }
            }
    
    raise HTTPException(status_code=404, detail="API function not found")

# UAPI endpoints
@app.get("/execute/{module}/{function}")
async def uapi_endpoint(
    module: str,
    function: str,
    username: str = Depends(verify_credentials)
):
    """cPanel UAPI endpoint."""
    
    if module == "Email" and function == "list_pops":
        return {
            "status": 1,
            "data": [acc for acc in MOCK_EMAIL_ACCOUNTS if acc["user"] == username],
            "metadata": {"result": 1}
        }
    
    elif module == "Mysql" and function == "list_databases":
        return {
            "status": 1,
            "data": [db for db in MOCK_DATABASES if db["user"] == username],
            "metadata": {"result": 1}
        }
    
    elif module == "DnsLookup" and function == "name_to_ip":
        return {
            "status": 1,
            "data": [{"ip": "192.168.1.100"}],
            "metadata": {"result": 1}
        }
    
    raise HTTPException(status_code=404, detail="UAPI function not found")

# Backup endpoints
@app.post("/backup/create")
async def create_backup(
    username: str = Depends(verify_credentials)
):
    """Create account backup."""
    backup_id = f"backup_{username}_{int(time.time())}"
    return {
        "status": "success",
        "backup_id": backup_id,
        "message": f"Backup created for {username}",
        "estimated_time": "5-10 minutes"
    }

@app.get("/backup/status/{backup_id}")
async def backup_status(
    backup_id: str,
    username: str = Depends(verify_credentials)
):
    """Get backup status."""
    return {
        "status": "completed",
        "backup_id": backup_id,
        "progress": 100,
        "file_path": f"/home/{username}/backups/{backup_id}.tar.gz",
        "size": 1024000
    }

# File manager endpoints
@app.get("/files/list")
async def list_files(
    path: str = Query(default="/"),
    username: str = Depends(verify_credentials)
):
    """List files in directory."""
    mock_files = [
        {
            "name": "public_html",
            "type": "directory",
            "size": 0,
            "permissions": "0755",
            "modified": "2024-01-01 12:00:00"
        },
        {
            "name": "index.html",
            "type": "file", 
            "size": 2048,
            "permissions": "0644",
            "modified": "2024-01-01 12:00:00"
        },
        {
            "name": "wp-config.php",
            "type": "file",
            "size": 4096,
            "permissions": "0600",
            "modified": "2024-01-01 12:00:00"
        }
    ]
    
    return {
        "status": "success",
        "path": path,
        "files": mock_files
    }

# SSL certificate endpoints
@app.get("/ssl/list")
async def list_ssl_certificates(
    username: str = Depends(verify_credentials)
):
    """List SSL certificates."""
    account = next((acc for acc in MOCK_ACCOUNTS if acc["user"] == username), None)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    return {
        "status": "success",
        "certificates": [
            {
                "domain": account["domain"],
                "issuer": "Let's Encrypt",
                "expires": "2024-12-31",
                "status": "valid"
            }
        ]
    }

# Error simulation endpoints
@app.get("/error/simulate/{error_type}")
async def simulate_error(
    error_type: str,
    username: str = Depends(verify_credentials)
):
    """Simulate various error conditions for testing."""
    
    if error_type == "timeout":
        time.sleep(30)  # Simulate timeout
        return {"status": "timeout"}
    
    elif error_type == "server_error":
        raise HTTPException(status_code=500, detail="Internal server error")
    
    elif error_type == "rate_limit":
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    elif error_type == "maintenance":
        raise HTTPException(status_code=503, detail="Server under maintenance")
    
    return {"status": "error", "type": error_type}

if __name__ == "__main__":
    port = int(os.getenv("API_PORT", 2083))
    host = os.getenv("API_HOST", "0.0.0.0")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )