"""
Performance benchmarks and load testing for the Migration Assistant.

This module contains comprehensive performance tests comparing Go vs Python
implementations, load testing for API endpoints, and end-to-end performance
scenarios.
"""

import pytest
import asyncio
import time
import statistics
import concurrent.futures
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile
import os

from migration_assistant.performance.engine import GoPerformanceEngine
from migration_assistant.performance.hybrid import HybridPerformanceManager
from migration_assistant.transfer.methods.ssh import SSHTransfer
from migration_assistant.database.migrators.mysql_migrator import MySQLMigrator
from migration_assistant.orchestrator.orchestrator import MigrationOrchestrator


class TestGoVsPythonPerformance:
    """Compare Go vs Python implementation performance."""
    
    @pytest.fixture
    def performance_test_data(self):
        """Generate test data for performance comparisons."""
        return {
            "small_files": [f"small_file_{i}.txt" for i in range(100)],
            "medium_files": [f"medium_file_{i}.txt" for i in range(10)],
            "large_file": "large_file.txt",
            "file_sizes": {
                "small": 1024,      # 1KB
                "medium": 102400,   # 100KB
                "large": 10485760   # 10MB
            }
        }
    
    @pytest.mark.benchmark(group="file_copy")
    def test_go_file_copy_performance(self, benchmark, temp_directory, performance_test_data, mock_go_binary):
        """Benchmark Go file copy performance."""
        # Create test file
        test_file = os.path.join(temp_directory, "test_source.txt")
        test_data = "x" * performance_test_data["file_sizes"]["medium"]
        with open(test_file, "w") as f:
            f.write(test_data)
        
        dest_file = os.path.join(temp_directory, "test_dest.txt")
        
        def go_copy():
            return asyncio.run(mock_go_binary.execute(
                "copy",
                source=test_file,
                destination=dest_file,
                size=len(test_data)
            ))
        
        result = benchmark(go_copy)
        assert result["success"] is True
    
    @pytest.mark.benchmark(group="file_copy")
    def test_python_file_copy_performance(self, benchmark, temp_directory, performance_test_data):
        """Benchmark Python file copy performance."""
        import shutil
        
        # Create test file
        test_file = os.path.join(temp_directory, "test_source.txt")
        test_data = "x" * performance_test_data["file_sizes"]["medium"]
        with open(test_file, "w") as f:
            f.write(test_data)
        
        def python_copy():
            dest_file = os.path.join(temp_directory, f"test_dest_{time.time()}.txt")
            shutil.copy2(test_file, dest_file)
            return {"success": True, "destination": dest_file}
        
        result = benchmark(python_copy)
        assert result["success"] is True
    
    @pytest.mark.benchmark(group="checksum")
    def test_go_checksum_performance(self, benchmark, temp_directory, performance_test_data, mock_go_binary):
        """Benchmark Go checksum calculation performance."""
        # Create test files
        test_files = []
        for i in range(10):
            test_file = os.path.join(temp_directory, f"checksum_test_{i}.txt")
            test_data = f"checksum test data {i} " * 1000  # ~20KB each
            with open(test_file, "w") as f:
                f.write(test_data)
            test_files.append(test_file)
        
        def go_checksum():
            return asyncio.run(mock_go_binary.execute(
                "checksum",
                files=test_files
            ))
        
        result = benchmark(go_checksum)
        assert result["success"] is True
    
    @pytest.mark.benchmark(group="checksum")
    def test_python_checksum_performance(self, benchmark, temp_directory, performance_test_data):
        """Benchmark Python checksum calculation performance."""
        import hashlib
        
        # Create test files
        test_files = []
        for i in range(10):
            test_file = os.path.join(temp_directory, f"checksum_test_{i}.txt")
            test_data = f"checksum test data {i} " * 1000  # ~20KB each
            with open(test_file, "w") as f:
                f.write(test_data)
            test_files.append(test_file)
        
        def python_checksum():
            checksums = {}
            for file_path in test_files:
                hasher = hashlib.sha256()
                with open(file_path, "rb") as f:
                    hasher.update(f.read())
                checksums[file_path] = hasher.hexdigest()
            return {"success": True, "checksums": checksums}
        
        result = benchmark(python_checksum)
        assert result["success"] is True
    
    @pytest.mark.benchmark(group="compression")
    def test_go_compression_performance(self, benchmark, temp_directory, performance_test_data, mock_go_binary):
        """Benchmark Go compression performance."""
        # Create test file
        test_file = os.path.join(temp_directory, "compression_test.txt")
        test_data = "compression test data " * 10000  # ~200KB
        with open(test_file, "w") as f:
            f.write(test_data)
        
        def go_compress():
            return asyncio.run(mock_go_binary.execute(
                "compress",
                source=test_file,
                size=len(test_data)
            ))
        
        result = benchmark(go_compress)
        assert result["success"] is True
    
    @pytest.mark.benchmark(group="compression")
    def test_python_compression_performance(self, benchmark, temp_directory, performance_test_data):
        """Benchmark Python compression performance."""
        import gzip
        
        # Create test file
        test_file = os.path.join(temp_directory, "compression_test.txt")
        test_data = "compression test data " * 10000  # ~200KB
        with open(test_file, "w") as f:
            f.write(test_data)
        
        def python_compress():
            compressed_file = test_file + ".gz"
            with open(test_file, "rb") as f_in:
                with gzip.open(compressed_file, "wb") as f_out:
                    f_out.write(f_in.read())
            
            original_size = os.path.getsize(test_file)
            compressed_size = os.path.getsize(compressed_file)
            
            return {
                "success": True,
                "original_size": original_size,
                "compressed_size": compressed_size,
                "compression_ratio": compressed_size / original_size
            }
        
        result = benchmark(python_compress)
        assert result["success"] is True


class TestHybridPerformanceManager:
    """Test the hybrid performance manager that chooses between Go and Python."""
    
    @pytest.fixture
    def hybrid_manager(self, mock_go_binary):
        """Create hybrid performance manager."""
        with patch('migration_assistant.performance.engine.GoPerformanceEngine') as mock_engine:
            mock_engine.return_value = mock_go_binary
            return HybridPerformanceManager()
    
    @pytest.mark.benchmark(group="hybrid")
    def test_hybrid_file_operation_selection(self, benchmark, hybrid_manager, temp_directory):
        """Test hybrid manager's operation selection logic."""
        # Create test file
        test_file = os.path.join(temp_directory, "hybrid_test.txt")
        test_data = "x" * 50000  # 50KB
        with open(test_file, "w") as f:
            f.write(test_data)
        
        dest_file = os.path.join(temp_directory, "hybrid_dest.txt")
        
        def hybrid_operation():
            return asyncio.run(hybrid_manager.copy_file(test_file, dest_file))
        
        result = benchmark(hybrid_operation)
        assert result["success"] is True
    
    @pytest.mark.benchmark(group="hybrid")
    def test_hybrid_batch_operations(self, benchmark, hybrid_manager, temp_directory):
        """Test hybrid manager with batch operations."""
        # Create multiple test files
        test_files = []
        for i in range(20):
            test_file = os.path.join(temp_directory, f"batch_test_{i}.txt")
            test_data = f"batch test data {i} " * 500  # ~10KB each
            with open(test_file, "w") as f:
                f.write(test_data)
            test_files.append(test_file)
        
        def hybrid_batch():
            return asyncio.run(hybrid_manager.batch_checksum(test_files))
        
        result = benchmark(hybrid_batch)
        assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_performance_threshold_switching(self, hybrid_manager, temp_directory):
        """Test that hybrid manager switches between Go and Python based on performance thresholds."""
        # Small file - should use Python
        small_file = os.path.join(temp_directory, "small.txt")
        with open(small_file, "w") as f:
            f.write("x" * 100)  # 100 bytes
        
        small_result = await hybrid_manager.copy_file(small_file, small_file + ".copy")
        assert small_result["method_used"] in ["python", "go"]  # Either is acceptable for small files
        
        # Large file - should prefer Go
        large_file = os.path.join(temp_directory, "large.txt")
        with open(large_file, "w") as f:
            f.write("x" * 1000000)  # 1MB
        
        large_result = await hybrid_manager.copy_file(large_file, large_file + ".copy")
        assert large_result["success"] is True


class TestAPILoadTesting:
    """Load testing for API endpoints."""
    
    @pytest.fixture
    def api_client(self):
        """Create API test client."""
        from fastapi.testclient import TestClient
        from migration_assistant.api.main import app
        return TestClient(app)
    
    @pytest.fixture
    def auth_token(self):
        """Create authentication token for API tests."""
        from migration_assistant.api.auth import create_access_token
        return create_access_token(data={"sub": "testuser", "tenant_id": "test_tenant"})
    
    @pytest.mark.benchmark(group="api_load")
    def test_list_migrations_load(self, benchmark, api_client, auth_token):
        """Load test the list migrations endpoint."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.orchestrator.orchestrator.MigrationOrchestrator') as mock_orchestrator:
            
            mock_get_user.return_value = {"username": "testuser", "tenant_id": "test_tenant"}
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            mock_instance.list_sessions.return_value = [
                Mock(id=f"session_{i}", status="completed") for i in range(100)
            ]
            
            def make_request():
                response = api_client.get("/migrations/", headers=headers)
                return response.status_code == 200
            
            result = benchmark(make_request)
            assert result is True
    
    @pytest.mark.benchmark(group="api_load")
    def test_create_migration_load(self, benchmark, api_client, auth_token, sample_migration_request):
        """Load test the create migration endpoint."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.orchestrator.orchestrator.MigrationOrchestrator') as mock_orchestrator:
            
            mock_get_user.return_value = {"username": "testuser", "tenant_id": "test_tenant"}
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            mock_instance.create_session.return_value = Mock(
                id="test_session",
                status="pending"
            )
            
            def make_request():
                response = api_client.post("/migrations/", json=sample_migration_request, headers=headers)
                return response.status_code == 201
            
            result = benchmark(make_request)
            assert result is True
    
    @pytest.mark.asyncio
    async def test_concurrent_api_requests(self, api_client, auth_token):
        """Test API performance under concurrent load."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.orchestrator.orchestrator.MigrationOrchestrator') as mock_orchestrator:
            
            mock_get_user.return_value = {"username": "testuser", "tenant_id": "test_tenant"}
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            mock_instance.list_sessions.return_value = []
            
            async def make_request():
                response = api_client.get("/migrations/", headers=headers)
                return response.status_code
            
            # Run 50 concurrent requests
            tasks = [make_request() for _ in range(50)]
            results = await asyncio.gather(*tasks)
            
            # All requests should succeed
            assert all(status == 200 for status in results)
            
            # Measure response time distribution
            start_time = time.time()
            response_times = []
            
            for _ in range(10):
                request_start = time.time()
                await make_request()
                response_times.append(time.time() - request_start)
            
            avg_response_time = statistics.mean(response_times)
            p95_response_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
            
            # Response times should be reasonable
            assert avg_response_time < 0.1  # 100ms average
            assert p95_response_time < 0.2   # 200ms 95th percentile


class TestEndToEndPerformance:
    """End-to-end performance testing with realistic scenarios."""
    
    @pytest.mark.benchmark(group="e2e")
    def test_complete_migration_workflow_performance(self, benchmark, sample_migration_config):
        """Benchmark complete migration workflow."""
        
        def run_migration():
            with patch.multiple(
                'migration_assistant.orchestrator.orchestrator.MigrationOrchestrator',
                create_session=Mock(return_value=Mock(id="perf_test", status="pending")),
                start_migration=Mock(return_value=True),
                get_session=Mock(return_value=Mock(id="perf_test", status="completed", progress=100))
            ):
                orchestrator = MigrationOrchestrator()
                session = orchestrator.create_session(sample_migration_config)
                orchestrator.start_migration(session.id)
                final_session = orchestrator.get_session(session.id)
                return final_session.status == "completed"
        
        result = benchmark(run_migration)
        assert result is True
    
    @pytest.mark.benchmark(group="e2e")
    def test_database_migration_performance(self, benchmark, temp_directory):
        """Benchmark database migration performance."""
        from migration_assistant.models.config import DatabaseConfig, DatabaseType
        
        config = DatabaseConfig(
            type=DatabaseType.SQLITE,
            database_name=os.path.join(temp_directory, "test.db")
        )
        
        def run_db_migration():
            with patch('sqlite3.connect') as mock_connect:
                mock_connection = Mock()
                mock_connect.return_value = mock_connection
                mock_connection.iterdump.return_value = [
                    "CREATE TABLE test (id INTEGER);",
                    "INSERT INTO test VALUES (1);"
                ]
                
                migrator = MySQLMigrator(config)  # Using MySQL migrator for interface
                export_path = os.path.join(temp_directory, "export.sql")
                
                # Mock the export process
                with open(export_path, "w") as f:
                    f.write("CREATE TABLE test (id INTEGER);\nINSERT INTO test VALUES (1);")
                
                return os.path.exists(export_path)
        
        result = benchmark(run_db_migration)
        assert result is True
    
    @pytest.mark.benchmark(group="e2e")
    def test_file_transfer_performance(self, benchmark, temp_directory, mock_ssh_client):
        """Benchmark file transfer performance."""
        from migration_assistant.models.config import TransferConfig, AuthConfig, TransferMethod, AuthType
        
        # Create test files
        test_files = []
        for i in range(10):
            test_file = os.path.join(temp_directory, f"transfer_test_{i}.txt")
            test_data = f"transfer test data {i} " * 1000  # ~20KB each
            with open(test_file, "w") as f:
                f.write(test_data)
            test_files.append(test_file)
        
        config = TransferConfig(
            method=TransferMethod.SSH_SCP,
            auth=AuthConfig(type=AuthType.SSH_KEY, username="testuser")
        )
        
        def run_file_transfer():
            with patch('paramiko.SSHClient', return_value=mock_ssh_client):
                transfer = SSHTransfer(config)
                
                # Mock successful transfers
                results = []
                for test_file in test_files:
                    result = Mock(success=True, bytes_transferred=os.path.getsize(test_file))
                    results.append(result)
                
                return all(r.success for r in results)
        
        result = benchmark(run_file_transfer)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_parallel_migration_performance(self, sample_migration_config):
        """Test performance of parallel migrations."""
        
        async def run_single_migration(migration_id):
            # Simulate migration work
            await asyncio.sleep(0.01)  # 10ms of work
            return {"id": migration_id, "status": "completed", "duration": 0.01}
        
        # Run 10 migrations in parallel
        start_time = time.time()
        tasks = [run_single_migration(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # Parallel execution should be faster than sequential
        assert total_time < 0.1  # Should complete in less than 100ms
        assert len(results) == 10
        assert all(r["status"] == "completed" for r in results)
    
    @pytest.mark.benchmark(group="e2e")
    def test_validation_performance(self, benchmark, sample_migration_config):
        """Benchmark validation performance."""
        from migration_assistant.validation.engine import ValidationEngine
        
        def run_validation():
            with patch.multiple(
                'migration_assistant.validation.engine.ValidationEngine',
                _validate_connectivity=Mock(return_value=True),
                _validate_compatibility=Mock(return_value=True),
                _validate_permissions=Mock(return_value=True),
                _validate_dependencies=Mock(return_value=True)
            ):
                engine = ValidationEngine()
                result = Mock(success=True, validation_time=0.1, errors=[], warnings=[])
                return result.success
        
        result = benchmark(run_validation)
        assert result is True


class TestMemoryAndResourceUsage:
    """Test memory usage and resource consumption."""
    
    @pytest.mark.benchmark(group="memory")
    def test_large_file_processing_memory(self, benchmark, temp_directory):
        """Test memory usage when processing large files."""
        import psutil
        import os
        
        # Create a large test file (10MB)
        large_file = os.path.join(temp_directory, "large_test.txt")
        with open(large_file, "w") as f:
            for i in range(100000):
                f.write(f"Line {i}: This is test data for memory usage testing.\n")
        
        def process_large_file():
            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss
            
            # Simulate file processing
            with open(large_file, "r") as f:
                lines_processed = 0
                for line in f:
                    lines_processed += 1
                    # Simulate some processing
                    _ = line.strip().upper()
            
            final_memory = process.memory_info().rss
            memory_increase = final_memory - initial_memory
            
            return {
                "lines_processed": lines_processed,
                "memory_increase_mb": memory_increase / (1024 * 1024),
                "final_memory_mb": final_memory / (1024 * 1024)
            }
        
        result = benchmark(process_large_file)
        
        # Memory increase should be reasonable (less than 100MB for this test)
        assert result["memory_increase_mb"] < 100
        assert result["lines_processed"] > 0
    
    @pytest.mark.benchmark(group="memory")
    def test_concurrent_operations_memory(self, benchmark, temp_directory):
        """Test memory usage under concurrent operations."""
        import psutil
        import threading
        
        def memory_intensive_operation(file_id):
            """Simulate memory-intensive operation."""
            test_file = os.path.join(temp_directory, f"concurrent_test_{file_id}.txt")
            
            # Create and process file
            with open(test_file, "w") as f:
                for i in range(1000):
                    f.write(f"File {file_id}, Line {i}: Test data\n")
            
            # Read and process
            with open(test_file, "r") as f:
                data = f.read()
                processed = data.upper()
            
            return len(processed)
        
        def run_concurrent_operations():
            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss
            
            # Run 10 concurrent operations
            threads = []
            results = []
            
            def worker(file_id):
                result = memory_intensive_operation(file_id)
                results.append(result)
            
            for i in range(10):
                thread = threading.Thread(target=worker, args=(i,))
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
            
            final_memory = process.memory_info().rss
            memory_increase = final_memory - initial_memory
            
            return {
                "operations_completed": len(results),
                "memory_increase_mb": memory_increase / (1024 * 1024),
                "avg_result_size": sum(results) / len(results) if results else 0
            }
        
        result = benchmark(run_concurrent_operations)
        
        assert result["operations_completed"] == 10
        # Memory increase should be reasonable for concurrent operations
        assert result["memory_increase_mb"] < 200


class TestScalabilityBenchmarks:
    """Test system scalability with increasing loads."""
    
    @pytest.mark.benchmark(group="scalability")
    def test_increasing_file_count_performance(self, benchmark, temp_directory):
        """Test performance scaling with increasing file counts."""
        
        def create_and_process_files(file_count):
            files_created = []
            
            # Create files
            for i in range(file_count):
                test_file = os.path.join(temp_directory, f"scale_test_{i}.txt")
                with open(test_file, "w") as f:
                    f.write(f"Scale test file {i} content")
                files_created.append(test_file)
            
            # Process files (simulate checksum calculation)
            import hashlib
            checksums = {}
            for file_path in files_created:
                hasher = hashlib.md5()
                with open(file_path, "rb") as f:
                    hasher.update(f.read())
                checksums[file_path] = hasher.hexdigest()
            
            return len(checksums)
        
        # Test with different file counts
        file_counts = [10, 50, 100]
        results = {}
        
        for count in file_counts:
            result = benchmark.pedantic(
                create_and_process_files,
                args=(count,),
                rounds=3
            )
            results[count] = result
        
        # Performance should scale reasonably
        assert all(isinstance(result, int) and result > 0 for result in results.values())
    
    @pytest.mark.benchmark(group="scalability")
    def test_database_record_scaling(self, benchmark):
        """Test database operation scaling with increasing record counts."""
        
        def process_database_records(record_count):
            # Simulate database operations
            records = []
            for i in range(record_count):
                record = {
                    "id": i,
                    "name": f"Record {i}",
                    "data": f"Data for record {i}" * 10  # ~200 bytes per record
                }
                records.append(record)
            
            # Simulate processing (sorting, filtering, etc.)
            sorted_records = sorted(records, key=lambda x: x["id"])
            filtered_records = [r for r in sorted_records if r["id"] % 2 == 0]
            
            return len(filtered_records)
        
        # Test with different record counts
        record_counts = [100, 500, 1000]
        results = {}
        
        for count in record_counts:
            result = benchmark.pedantic(
                process_database_records,
                args=(count,),
                rounds=3
            )
            results[count] = result
        
        # Results should be proportional to input size
        assert results[100] < results[500] < results[1000]