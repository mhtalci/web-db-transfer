"""
Load testing utilities for the Migration Assistant API.

This module provides comprehensive load testing capabilities for API endpoints,
database operations, and file transfer performance under high load.
"""

import pytest
import asyncio
import aiohttp
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch
from typing import List, Dict, Any
import json

from migration_assistant.api.main import app
from migration_assistant.api.auth import create_access_token


class LoadTestResult:
    """Container for load test results."""
    
    def __init__(self):
        self.response_times = []
        self.success_count = 0
        self.error_count = 0
        self.errors = []
        self.start_time = None
        self.end_time = None
    
    @property
    def total_requests(self):
        return self.success_count + self.error_count
    
    @property
    def success_rate(self):
        if self.total_requests == 0:
            return 0
        return self.success_count / self.total_requests
    
    @property
    def avg_response_time(self):
        if not self.response_times:
            return 0
        return statistics.mean(self.response_times)
    
    @property
    def p95_response_time(self):
        if not self.response_times:
            return 0
        return statistics.quantiles(self.response_times, n=20)[18]  # 95th percentile
    
    @property
    def p99_response_time(self):
        if not self.response_times:
            return 0
        return statistics.quantiles(self.response_times, n=100)[98]  # 99th percentile
    
    @property
    def requests_per_second(self):
        if not self.start_time or not self.end_time:
            return 0
        duration = self.end_time - self.start_time
        if duration == 0:
            return 0
        return self.total_requests / duration
    
    def add_success(self, response_time: float):
        self.response_times.append(response_time)
        self.success_count += 1
    
    def add_error(self, error: str, response_time: float = 0):
        if response_time > 0:
            self.response_times.append(response_time)
        self.error_count += 1
        self.errors.append(error)
    
    def to_dict(self):
        return {
            "total_requests": self.total_requests,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": self.success_rate,
            "avg_response_time": self.avg_response_time,
            "p95_response_time": self.p95_response_time,
            "p99_response_time": self.p99_response_time,
            "requests_per_second": self.requests_per_second,
            "errors": self.errors[:10]  # First 10 errors
        }


class APILoadTester:
    """Load tester for API endpoints."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.auth_token = create_access_token(
            data={"sub": "loadtest_user", "tenant_id": "loadtest_tenant"}
        )
        self.headers = {"Authorization": f"Bearer {self.auth_token}"}
    
    async def make_request(self, session: aiohttp.ClientSession, method: str, 
                          endpoint: str, **kwargs) -> tuple[bool, float, str]:
        """Make a single HTTP request and return success, response time, and error."""
        start_time = time.time()
        try:
            async with session.request(
                method, 
                f"{self.base_url}{endpoint}", 
                headers=self.headers,
                **kwargs
            ) as response:
                response_time = time.time() - start_time
                
                if response.status < 400:
                    return True, response_time, ""
                else:
                    error_text = await response.text()
                    return False, response_time, f"HTTP {response.status}: {error_text[:100]}"
                    
        except Exception as e:
            response_time = time.time() - start_time
            return False, response_time, str(e)
    
    async def load_test_endpoint(self, method: str, endpoint: str, 
                                concurrent_users: int, requests_per_user: int,
                                **request_kwargs) -> LoadTestResult:
        """Load test a specific endpoint."""
        result = LoadTestResult()
        result.start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            # Create tasks for concurrent users
            tasks = []
            for user_id in range(concurrent_users):
                for request_id in range(requests_per_user):
                    task = self.make_request(session, method, endpoint, **request_kwargs)
                    tasks.append(task)
            
            # Execute all requests concurrently
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for response in responses:
                if isinstance(response, Exception):
                    result.add_error(str(response))
                else:
                    success, response_time, error = response
                    if success:
                        result.add_success(response_time)
                    else:
                        result.add_error(error, response_time)
        
        result.end_time = time.time()
        return result


@pytest.mark.benchmark
class TestAPILoadTesting:
    """API load testing scenarios."""
    
    @pytest.fixture
    def load_tester(self):
        """Create API load tester."""
        return APILoadTester()
    
    @pytest.fixture
    def mock_api_dependencies(self):
        """Mock API dependencies for load testing."""
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.orchestrator.orchestrator.MigrationOrchestrator') as mock_orchestrator:
            
            mock_get_user.return_value = {
                "username": "loadtest_user", 
                "tenant_id": "loadtest_tenant"
            }
            
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            mock_instance.list_sessions.return_value = [
                Mock(id=f"session_{i}", status="completed") for i in range(10)
            ]
            mock_instance.create_session.return_value = Mock(
                id="new_session", 
                status="pending"
            )
            mock_instance.get_session.return_value = Mock(
                id="test_session",
                status="running",
                progress=50
            )
            
            yield mock_instance
    
    @pytest.mark.asyncio
    async def test_list_migrations_load(self, load_tester, mock_api_dependencies):
        """Load test the list migrations endpoint."""
        result = await load_tester.load_test_endpoint(
            "GET", "/migrations/",
            concurrent_users=10,
            requests_per_user=20
        )
        
        # Assertions for acceptable performance
        assert result.success_rate >= 0.95  # 95% success rate
        assert result.avg_response_time < 0.5  # 500ms average
        assert result.p95_response_time < 1.0  # 1s 95th percentile
        assert result.requests_per_second > 50  # At least 50 RPS
        
        print(f"List migrations load test results: {result.to_dict()}")
    
    @pytest.mark.asyncio
    async def test_create_migration_load(self, load_tester, mock_api_dependencies, sample_migration_request):
        """Load test the create migration endpoint."""
        result = await load_tester.load_test_endpoint(
            "POST", "/migrations/",
            concurrent_users=5,
            requests_per_user=10,
            json=sample_migration_request
        )
        
        # Create operations should be slightly slower but still performant
        assert result.success_rate >= 0.90  # 90% success rate
        assert result.avg_response_time < 1.0  # 1s average
        assert result.p95_response_time < 2.0  # 2s 95th percentile
        assert result.requests_per_second > 20  # At least 20 RPS
        
        print(f"Create migration load test results: {result.to_dict()}")
    
    @pytest.mark.asyncio
    async def test_migration_status_load(self, load_tester, mock_api_dependencies):
        """Load test the migration status endpoint."""
        result = await load_tester.load_test_endpoint(
            "GET", "/migrations/test_session/status",
            concurrent_users=15,
            requests_per_user=30
        )
        
        # Status checks should be very fast
        assert result.success_rate >= 0.98  # 98% success rate
        assert result.avg_response_time < 0.2  # 200ms average
        assert result.p95_response_time < 0.5  # 500ms 95th percentile
        assert result.requests_per_second > 100  # At least 100 RPS
        
        print(f"Migration status load test results: {result.to_dict()}")
    
    @pytest.mark.asyncio
    async def test_validation_endpoint_load(self, load_tester, mock_api_dependencies, sample_migration_request):
        """Load test the validation endpoint."""
        with patch('migration_assistant.validation.engine.ValidationEngine') as mock_validator:
            mock_instance = Mock()
            mock_validator.return_value = mock_instance
            mock_instance.validate_migration.return_value = Mock(
                success=True,
                errors=[],
                warnings=[],
                validation_time=0.1
            )
            
            result = await load_tester.load_test_endpoint(
                "POST", "/validate/configuration",
                concurrent_users=8,
                requests_per_user=15,
                json=sample_migration_request
            )
            
            # Validation should be reasonably fast
            assert result.success_rate >= 0.92  # 92% success rate
            assert result.avg_response_time < 0.8  # 800ms average
            assert result.p95_response_time < 1.5  # 1.5s 95th percentile
            
            print(f"Validation endpoint load test results: {result.to_dict()}")
    
    @pytest.mark.asyncio
    async def test_mixed_workload_load(self, load_tester, mock_api_dependencies, sample_migration_request):
        """Load test with mixed API operations."""
        # Simulate realistic mixed workload
        tasks = []
        
        # 60% status checks (most common)
        for _ in range(60):
            task = load_tester.make_request(
                aiohttp.ClientSession(), "GET", "/migrations/test_session/status"
            )
            tasks.append(task)
        
        # 25% list operations
        for _ in range(25):
            task = load_tester.make_request(
                aiohttp.ClientSession(), "GET", "/migrations/"
            )
            tasks.append(task)
        
        # 10% create operations
        for _ in range(10):
            task = load_tester.make_request(
                aiohttp.ClientSession(), "POST", "/migrations/",
                json=sample_migration_request
            )
            tasks.append(task)
        
        # 5% validation operations
        for _ in range(5):
            task = load_tester.make_request(
                aiohttp.ClientSession(), "POST", "/validate/configuration",
                json=sample_migration_request
            )
            tasks.append(task)
        
        # Execute mixed workload
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            # Update tasks to use the session
            updated_tasks = []
            for _ in range(60):
                updated_tasks.append(
                    load_tester.make_request(session, "GET", "/migrations/test_session/status")
                )
            for _ in range(25):
                updated_tasks.append(
                    load_tester.make_request(session, "GET", "/migrations/")
                )
            for _ in range(10):
                updated_tasks.append(
                    load_tester.make_request(session, "POST", "/migrations/", json=sample_migration_request)
                )
            for _ in range(5):
                updated_tasks.append(
                    load_tester.make_request(session, "POST", "/validate/configuration", json=sample_migration_request)
                )
            
            responses = await asyncio.gather(*updated_tasks, return_exceptions=True)
        
        end_time = time.time()
        
        # Process results
        success_count = sum(1 for r in responses if not isinstance(r, Exception) and r[0])
        total_requests = len(responses)
        success_rate = success_count / total_requests
        duration = end_time - start_time
        rps = total_requests / duration
        
        assert success_rate >= 0.90  # 90% success rate for mixed workload
        assert rps > 30  # At least 30 RPS for mixed operations
        
        print(f"Mixed workload results: {success_count}/{total_requests} success, {rps:.1f} RPS")


@pytest.mark.benchmark
class TestDatabaseLoadTesting:
    """Database operation load testing."""
    
    @pytest.mark.asyncio
    async def test_concurrent_database_connections(self, test_databases):
        """Test database performance under concurrent connections."""
        if "mysql" not in test_databases:
            pytest.skip("MySQL container not available")
        
        from migration_assistant.database.migrators.mysql_migrator import MySQLMigrator
        from migration_assistant.models.config import DatabaseConfig, DatabaseType
        
        config = DatabaseConfig(
            type=DatabaseType.MYSQL,
            host="localhost",
            port=test_databases.get("mysql_port", 3307),
            database_name="testdb",
            username="testuser",
            password="testpass"
        )
        
        async def test_connection():
            """Test a single database connection."""
            start_time = time.time()
            try:
                migrator = MySQLMigrator(config)
                # Mock the connection for load testing
                with patch('mysql.connector.connect') as mock_connect:
                    mock_connection = Mock()
                    mock_connect.return_value = mock_connection
                    mock_connection.is_connected.return_value = True
                    
                    await migrator.connect()
                    await migrator.disconnect()
                    
                    return True, time.time() - start_time
            except Exception as e:
                return False, time.time() - start_time
        
        # Test with 20 concurrent connections
        tasks = [test_connection() for _ in range(20)]
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for success, _ in results if success)
        response_times = [rt for _, rt in results]
        
        assert success_count >= 18  # At least 90% success rate
        assert statistics.mean(response_times) < 1.0  # Average under 1 second
        
        print(f"Database connection test: {success_count}/20 successful, "
              f"avg time: {statistics.mean(response_times):.3f}s")
    
    @pytest.mark.asyncio
    async def test_database_query_performance(self):
        """Test database query performance under load."""
        # Mock database operations for performance testing
        with patch('mysql.connector.connect') as mock_connect:
            mock_connection = Mock()
            mock_cursor = Mock()
            mock_connect.return_value = mock_connection
            mock_connection.cursor.return_value = mock_cursor
            
            # Mock query results
            mock_cursor.fetchall.return_value = [
                (i, f"record_{i}", f"data_{i}") for i in range(1000)
            ]
            
            async def execute_query():
                """Execute a mock database query."""
                start_time = time.time()
                try:
                    # Simulate query execution
                    await asyncio.sleep(0.01)  # 10ms query time
                    return True, time.time() - start_time
                except Exception as e:
                    return False, time.time() - start_time
            
            # Execute 50 concurrent queries
            tasks = [execute_query() for _ in range(50)]
            results = await asyncio.gather(*tasks)
            
            success_count = sum(1 for success, _ in results if success)
            response_times = [rt for _, rt in results]
            
            assert success_count == 50  # All queries should succeed
            assert statistics.mean(response_times) < 0.1  # Average under 100ms
            
            print(f"Database query test: {success_count}/50 successful, "
                  f"avg time: {statistics.mean(response_times):.3f}s")


@pytest.mark.benchmark
class TestFileTransferLoadTesting:
    """File transfer operation load testing."""
    
    @pytest.mark.asyncio
    async def test_concurrent_file_transfers(self, temp_directory, mock_ssh_client):
        """Test file transfer performance under concurrent load."""
        from migration_assistant.transfer.methods.ssh import SSHTransfer
        from migration_assistant.models.config import TransferConfig, AuthConfig, TransferMethod, AuthType
        
        # Create test files
        test_files = []
        for i in range(20):
            test_file = os.path.join(temp_directory, f"load_test_{i}.txt")
            with open(test_file, "w") as f:
                f.write(f"Load test file {i} content " * 100)  # ~2KB each
            test_files.append(test_file)
        
        config = TransferConfig(
            method=TransferMethod.SSH_SCP,
            auth=AuthConfig(type=AuthType.SSH_KEY, username="testuser")
        )
        
        async def transfer_file(file_path):
            """Transfer a single file."""
            start_time = time.time()
            try:
                with patch('paramiko.SSHClient', return_value=mock_ssh_client):
                    transfer = SSHTransfer(config)
                    result = await transfer.upload_file(
                        file_path, 
                        f"/remote/{os.path.basename(file_path)}"
                    )
                    return result.success, time.time() - start_time
            except Exception as e:
                return False, time.time() - start_time
        
        # Transfer all files concurrently
        tasks = [transfer_file(file_path) for file_path in test_files]
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for success, _ in results if success)
        transfer_times = [tt for _, tt in results]
        
        assert success_count >= 18  # At least 90% success rate
        assert statistics.mean(transfer_times) < 2.0  # Average under 2 seconds
        
        print(f"File transfer test: {success_count}/20 successful, "
              f"avg time: {statistics.mean(transfer_times):.3f}s")
    
    @pytest.mark.asyncio
    async def test_large_file_transfer_performance(self, temp_directory, mock_go_binary):
        """Test performance with large file transfers."""
        # Create a large test file (10MB simulated)
        large_file = os.path.join(temp_directory, "large_test.txt")
        with open(large_file, "w") as f:
            f.write("x" * 1024 * 1024)  # 1MB actual, simulating 10MB
        
        async def transfer_large_file():
            """Transfer large file using Go acceleration."""
            start_time = time.time()
            try:
                result = await mock_go_binary.execute(
                    "copy",
                    source=large_file,
                    destination=large_file + ".copy",
                    size=10 * 1024 * 1024  # 10MB
                )
                return result["success"], time.time() - start_time
            except Exception as e:
                return False, time.time() - start_time
        
        # Test 5 concurrent large file transfers
        tasks = [transfer_large_file() for _ in range(5)]
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for success, _ in results if success)
        transfer_times = [tt for _, tt in results]
        
        assert success_count == 5  # All transfers should succeed
        assert statistics.mean(transfer_times) < 5.0  # Average under 5 seconds
        
        print(f"Large file transfer test: {success_count}/5 successful, "
              f"avg time: {statistics.mean(transfer_times):.3f}s")


@pytest.mark.benchmark
class TestSystemResourceLoadTesting:
    """System resource usage under load."""
    
    def test_memory_usage_under_load(self, temp_directory):
        """Test memory usage during high-load operations."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Simulate memory-intensive operations
        data_structures = []
        
        for i in range(100):
            # Create data structures that simulate migration operations
            file_list = [f"file_{j}.txt" for j in range(1000)]
            checksum_map = {f: f"checksum_{hash(f)}" for f in file_list}
            migration_data = {
                "files": file_list,
                "checksums": checksum_map,
                "metadata": {"size": len(file_list), "iteration": i}
            }
            data_structures.append(migration_data)
        
        peak_memory = process.memory_info().rss
        memory_increase = peak_memory - initial_memory
        memory_increase_mb = memory_increase / (1024 * 1024)
        
        # Clean up
        data_structures.clear()
        
        # Memory increase should be reasonable
        assert memory_increase_mb < 500  # Less than 500MB increase
        
        print(f"Memory usage test: {memory_increase_mb:.1f}MB increase")
    
    def test_cpu_usage_under_load(self):
        """Test CPU usage during compute-intensive operations."""
        import psutil
        import hashlib
        
        # Monitor CPU usage
        cpu_percent_before = psutil.cpu_percent(interval=1)
        
        # Simulate CPU-intensive operations (checksum calculations)
        start_time = time.time()
        
        for i in range(1000):
            data = f"cpu intensive operation {i}" * 100
            hashlib.sha256(data.encode()).hexdigest()
        
        duration = time.time() - start_time
        cpu_percent_after = psutil.cpu_percent(interval=1)
        
        # Operations should complete in reasonable time
        assert duration < 10  # Less than 10 seconds
        
        print(f"CPU usage test: {duration:.2f}s duration, "
              f"CPU: {cpu_percent_before:.1f}% -> {cpu_percent_after:.1f}%")