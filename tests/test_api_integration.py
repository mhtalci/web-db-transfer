"""
API integration tests for the CMS migration system.
Tests the REST API endpoints and their interactions.
"""

import pytest
import asyncio
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

# Import the API application
from migration_assistant.api.cms_endpoints import router
from fastapi import FastAPI

# Create test app
app = FastAPI()
app.include_router(router)

client = TestClient(app)


@pytest.fixture
def temp_cms_structure():
    """Create temporary CMS directory structures for API testing."""
    temp_dir = Path(tempfile.mkdtemp())
    
    # WordPress structure
    wp_dir = temp_dir / "wordpress"
    wp_dir.mkdir()
    (wp_dir / "wp-config.php").write_text("""<?php
define('DB_NAME', 'wordpress_db');
define('DB_USER', 'wp_user');
define('DB_PASSWORD', 'wp_pass');
define('DB_HOST', 'localhost');
$table_prefix = 'wp_';
""")
    (wp_dir / "wp-includes").mkdir()
    (wp_dir / "wp-admin").mkdir()
    (wp_dir / "wp-includes" / "version.php").write_text("<?php\n$wp_version = '6.4.2';")
    
    yield {
        'temp_dir': temp_dir,
        'wordpress': wp_dir
    }
    
    # Cleanup
    shutil.rmtree(temp_dir)


class TestAPIEndpoints:
    """Test all API endpoints."""
    
    def test_health_endpoint(self):
        """Test API health check endpoint."""
        response = client.get("/api/v1/cms/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
        assert "features" in data
        assert data["supported_platforms"] == 12
        
        # Check features
        features = data["features"]
        expected_features = [
            "platform_detection",
            "health_checking", 
            "migration_orchestration",
            "real_time_monitoring",
            "performance_analytics"
        ]
        
        for feature in expected_features:
            assert features[feature] is True
    
    def test_get_platforms_endpoint(self):
        """Test get supported platforms endpoint."""
        response = client.get("/api/v1/cms/platforms")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_platforms" in data
        assert "platforms" in data
        assert "categories" in data
        
        assert data["total_platforms"] >= 12
        
        # Check categories
        categories = data["categories"]
        assert "content_management" in categories
        assert "ecommerce" in categories
        
        # Check specific platforms
        platforms = data["platforms"]
        expected_platforms = [
            "wordpress", "drupal", "joomla", "magento", 
            "shopware", "prestashop", "opencart", "ghost",
            "craftcms", "typo3", "concrete5", "umbraco"
        ]
        
        for platform in expected_platforms:
            assert platform in platforms
            assert "supported_versions" in platforms[platform]
            assert len(platforms[platform]["supported_versions"]) > 0
    
    def test_detect_platform_endpoint(self, temp_cms_structure):
        """Test platform detection endpoint."""
        wp_path = str(temp_cms_structure['wordpress'])
        
        response = client.post(
            "/api/v1/cms/detect",
            json={"path": wp_path}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "detected_platforms" in data
        assert "analysis_time" in data
        assert "path" in data
        
        assert data["path"] == wp_path
        assert data["analysis_time"] > 0
        
        # Should detect WordPress
        detected = data["detected_platforms"]
        assert len(detected) > 0
        
        wp_platform = next((p for p in detected if p["platform_type"] == "wordpress"), None)
        assert wp_platform is not None
        assert wp_platform["version"] == "6.4.2"
        assert wp_platform["framework"] == "wordpress"
        assert wp_platform["database_type"] == "mysql"
    
    def test_detect_platform_nonexistent_path(self):
        """Test platform detection with non-existent path."""
        response = client.post(
            "/api/v1/cms/detect",
            json={"path": "/nonexistent/path"}
        )
        assert response.status_code == 404
        assert "Path does not exist" in response.json()["detail"]
    
    def test_health_check_endpoint(self, temp_cms_structure):
        """Test health check endpoint."""
        wp_path = str(temp_cms_structure['wordpress'])
        
        response = client.post(
            "/api/v1/cms/health-check",
            json={
                "platform_type": "wordpress",
                "path": wp_path
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["platform"] == "wordpress"
        assert "health_score" in data
        assert "total_issues" in data
        assert "severity_breakdown" in data
        assert "issues" in data
        assert "recommendations" in data
        
        assert 0 <= data["health_score"] <= 100
        assert data["total_issues"] >= 0
        
        # Check severity breakdown structure
        severity_breakdown = data["severity_breakdown"]
        assert "critical" in severity_breakdown
        assert "error" in severity_breakdown
        assert "warning" in severity_breakdown
        assert "info" in severity_breakdown
    
    def test_compatibility_check_endpoint(self):
        """Test compatibility check endpoint."""
        response = client.post(
            "/api/v1/cms/compatibility-check",
            json={
                "source_platform": "wordpress",
                "source_version": "6.4.2",
                "destination_platform": "drupal",
                "destination_version": "10.1"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "compatible" in data
        assert "migration_complexity" in data
        assert "estimated_success_rate" in data
        assert "issues" in data
        assert "warnings" in data
        
        assert isinstance(data["compatible"], bool)
        assert data["migration_complexity"] in ["simple", "moderate", "complex", "unsupported"]
        assert 0 <= data["estimated_success_rate"] <= 100
    
    def test_create_migration_plan_endpoint(self, temp_cms_structure):
        """Test migration plan creation endpoint."""
        wp_path = str(temp_cms_structure['wordpress'])
        dest_path = str(temp_cms_structure['temp_dir'] / "destination")
        
        response = client.post(
            "/api/v1/cms/migration/plan",
            json={
                "source_platform": "wordpress",
                "destination_platform": "wordpress",
                "source_path": wp_path,
                "destination_path": dest_path,
                "options": {
                    "create_backup": True,
                    "verify_integrity": True
                }
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "migration_id" in data
        assert "total_steps" in data
        assert "estimated_duration" in data
        assert "steps" in data
        
        assert data["migration_id"].startswith("migration_")
        assert data["total_steps"] > 0
        assert data["estimated_duration"] > 0
        
        # Check steps structure
        steps = data["steps"]
        assert len(steps) == data["total_steps"]
        
        for step in steps:
            assert "id" in step
            assert "name" in step
            assert "stage" in step
            assert "description" in step
            assert "estimated_duration" in step
            assert "dependencies" in step
    
    def test_execute_migration_endpoint(self, temp_cms_structure):
        """Test migration execution endpoint."""
        # First create a migration plan
        wp_path = str(temp_cms_structure['wordpress'])
        dest_path = str(temp_cms_structure['temp_dir'] / "destination")
        
        plan_response = client.post(
            "/api/v1/cms/migration/plan",
            json={
                "source_platform": "wordpress",
                "destination_platform": "wordpress",
                "source_path": wp_path,
                "destination_path": dest_path,
                "options": {"create_backup": False}  # Skip backup for testing
            }
        )
        assert plan_response.status_code == 200
        migration_id = plan_response.json()["migration_id"]
        
        # Execute the migration
        response = client.post(
            "/api/v1/cms/migration/execute",
            json={"migration_id": migration_id}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["migration_id"] == migration_id
        assert data["status"] == "started"
        assert "message" in data
    
    def test_migration_status_endpoint(self, temp_cms_structure):
        """Test migration status endpoint."""
        # Create a migration plan first
        wp_path = str(temp_cms_structure['wordpress'])
        dest_path = str(temp_cms_structure['temp_dir'] / "destination")
        
        plan_response = client.post(
            "/api/v1/cms/migration/plan",
            json={
                "source_platform": "wordpress",
                "destination_platform": "wordpress",
                "source_path": wp_path,
                "destination_path": dest_path
            }
        )
        migration_id = plan_response.json()["migration_id"]
        
        # Get migration status
        response = client.get(f"/api/v1/cms/migration/{migration_id}/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data["migration_id"] == migration_id
        assert "source_platform" in data
        assert "destination_platform" in data
        assert "overall_progress" in data
        assert "completed_steps" in data
        assert "total_steps" in data
        assert "current_stage" in data
        assert "steps" in data
        
        assert 0 <= data["overall_progress"] <= 100
        assert data["completed_steps"] >= 0
        assert data["total_steps"] > 0
    
    def test_migration_control_endpoints(self, temp_cms_structure):
        """Test migration control endpoints (pause/resume/cancel)."""
        # Create a migration plan
        wp_path = str(temp_cms_structure['wordpress'])
        dest_path = str(temp_cms_structure['temp_dir'] / "destination")
        
        plan_response = client.post(
            "/api/v1/cms/migration/plan",
            json={
                "source_platform": "wordpress",
                "destination_platform": "wordpress",
                "source_path": wp_path,
                "destination_path": dest_path
            }
        )
        migration_id = plan_response.json()["migration_id"]
        
        # Test pause
        pause_response = client.post(f"/api/v1/cms/migration/{migration_id}/pause")
        assert pause_response.status_code == 200
        assert pause_response.json()["status"] == "paused"
        
        # Test resume
        resume_response = client.post(f"/api/v1/cms/migration/{migration_id}/resume")
        assert resume_response.status_code == 200
        assert resume_response.json()["status"] == "resumed"
        
        # Test cancel
        cancel_response = client.post(f"/api/v1/cms/migration/{migration_id}/cancel")
        assert cancel_response.status_code == 200
        assert cancel_response.json()["status"] == "cancelled"
    
    def test_statistics_endpoint(self):
        """Test global statistics endpoint."""
        response = client.get("/api/v1/cms/statistics")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_migrations" in data
        assert "successful_migrations" in data
        assert "success_rate_percent" in data
        assert "total_platforms_supported" in data
        assert "most_popular_platforms" in data
        assert "average_migration_time_minutes" in data
        assert "total_data_migrated_gb" in data
        assert "platform_compatibility_matrix" in data
        
        assert data["total_platforms_supported"] == 12
        assert 0 <= data["success_rate_percent"] <= 100
        
        # Check popular platforms structure
        popular_platforms = data["most_popular_platforms"]
        assert len(popular_platforms) > 0
        
        for platform in popular_platforms:
            assert "platform" in platform
            assert "migrations" in platform
            assert "success_rate" in platform
    
    def test_error_handling(self):
        """Test API error handling."""
        # Test invalid platform type
        response = client.post(
            "/api/v1/cms/health-check",
            json={
                "platform_type": "invalid_platform",
                "path": "/some/path"
            }
        )
        assert response.status_code == 500
        assert "detail" in response.json()
        
        # Test missing required fields
        response = client.post(
            "/api/v1/cms/detect",
            json={}  # Missing path
        )
        assert response.status_code == 422  # Validation error
        
        # Test non-existent migration ID
        response = client.get("/api/v1/cms/migration/nonexistent/status")
        assert response.status_code == 404


class TestAPIIntegration:
    """Test API integration scenarios."""
    
    def test_full_migration_workflow_via_api(self, temp_cms_structure):
        """Test complete migration workflow through API."""
        wp_path = str(temp_cms_structure['wordpress'])
        dest_path = str(temp_cms_structure['temp_dir'] / "destination")
        
        # 1. Detect platform
        detect_response = client.post(
            "/api/v1/cms/detect",
            json={"path": wp_path}
        )
        assert detect_response.status_code == 200
        detected = detect_response.json()["detected_platforms"]
        assert len(detected) > 0
        platform_type = detected[0]["platform_type"]
        
        # 2. Health check
        health_response = client.post(
            "/api/v1/cms/health-check",
            json={
                "platform_type": platform_type,
                "path": wp_path
            }
        )
        assert health_response.status_code == 200
        health_score = health_response.json()["health_score"]
        assert 0 <= health_score <= 100
        
        # 3. Compatibility check
        compat_response = client.post(
            "/api/v1/cms/compatibility-check",
            json={
                "source_platform": platform_type,
                "destination_platform": platform_type
            }
        )
        assert compat_response.status_code == 200
        assert compat_response.json()["compatible"] is True
        
        # 4. Create migration plan
        plan_response = client.post(
            "/api/v1/cms/migration/plan",
            json={
                "source_platform": platform_type,
                "destination_platform": platform_type,
                "source_path": wp_path,
                "destination_path": dest_path,
                "options": {"create_backup": False}
            }
        )
        assert plan_response.status_code == 200
        migration_id = plan_response.json()["migration_id"]
        
        # 5. Check initial status
        status_response = client.get(f"/api/v1/cms/migration/{migration_id}/status")
        assert status_response.status_code == 200
        initial_status = status_response.json()
        assert initial_status["overall_progress"] == 0
        
        # 6. Execute migration (in background)
        execute_response = client.post(
            "/api/v1/cms/migration/execute",
            json={"migration_id": migration_id}
        )
        assert execute_response.status_code == 200
        
        print(f"✅ Full API workflow completed for migration {migration_id}")
    
    def test_concurrent_api_requests(self, temp_cms_structure):
        """Test concurrent API requests."""
        wp_path = str(temp_cms_structure['wordpress'])
        
        import threading
        import time
        
        results = []
        errors = []
        
        def make_request():
            try:
                response = client.post(
                    "/api/v1/cms/detect",
                    json={"path": wp_path}
                )
                results.append(response.status_code)
            except Exception as e:
                errors.append(str(e))
        
        # Create 10 concurrent threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
        
        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        total_time = time.time() - start_time
        
        # Check results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10
        assert all(status == 200 for status in results)
        
        print(f"✅ 10 concurrent API requests completed in {total_time:.3f}s")
        print(f"   Average response time: {total_time/10:.3f}s")
    
    def test_api_performance_under_load(self, temp_cms_structure):
        """Test API performance under load."""
        wp_path = str(temp_cms_structure['wordpress'])
        
        # Make many sequential requests
        response_times = []
        
        for i in range(20):
            start_time = time.time()
            response = client.get("/api/v1/cms/platforms")
            response_time = time.time() - start_time
            
            assert response.status_code == 200
            response_times.append(response_time)
        
        # Analyze performance
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)
        
        # Response times should be reasonable
        assert avg_response_time < 1.0, f"Average response time too high: {avg_response_time:.3f}s"
        assert max_response_time < 2.0, f"Max response time too high: {max_response_time:.3f}s"
        
        print(f"✅ API performance test completed")
        print(f"   Average response time: {avg_response_time:.3f}s")
        print(f"   Min response time: {min_response_time:.3f}s")
        print(f"   Max response time: {max_response_time:.3f}s")


class TestAPIValidation:
    """Test API input validation and error handling."""
    
    def test_input_validation(self):
        """Test API input validation."""
        # Test invalid JSON
        response = client.post(
            "/api/v1/cms/detect",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422
        
        # Test missing required fields
        response = client.post(
            "/api/v1/cms/compatibility-check",
            json={"source_platform": "wordpress"}  # Missing destination_platform
        )
        assert response.status_code == 422
        
        # Test invalid field values
        response = client.post(
            "/api/v1/cms/health-check",
            json={
                "platform_type": "",  # Empty string
                "path": "/some/path"
            }
        )
        assert response.status_code in [400, 422, 500]  # Should be handled gracefully
    
    def test_response_format_consistency(self, temp_cms_structure):
        """Test that API responses have consistent formats."""
        wp_path = str(temp_cms_structure['wordpress'])
        
        # Test multiple endpoints and verify response structure
        endpoints_to_test = [
            ("GET", "/api/v1/cms/platforms", None),
            ("POST", "/api/v1/cms/detect", {"path": wp_path}),
            ("POST", "/api/v1/cms/health-check", {"platform_type": "wordpress", "path": wp_path}),
            ("GET", "/api/v1/cms/statistics", None),
            ("GET", "/api/v1/cms/health", None)
        ]
        
        for method, endpoint, payload in endpoints_to_test:
            if method == "GET":
                response = client.get(endpoint)
            else:
                response = client.post(endpoint, json=payload)
            
            assert response.status_code == 200, f"Endpoint {endpoint} failed"
            
            # All successful responses should return JSON
            data = response.json()
            assert isinstance(data, dict), f"Endpoint {endpoint} didn't return JSON object"
            
            print(f"✅ {method} {endpoint} - Response format valid")


if __name__ == "__main__":
    # Run API integration tests
    pytest.main([__file__, "-v", "--tb=short"])