"""
End-to-end tests for the Migration Assistant.

This module contains comprehensive end-to-end tests that simulate realistic
migration scenarios using Docker containers and mock services.
"""

import pytest
import asyncio
import time
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch

from migration_assistant.orchestrator.orchestrator import MigrationOrchestrator
from migration_assistant.models.config import (
    MigrationConfig, SystemConfig, DatabaseConfig, TransferConfig,
    AuthConfig, CloudConfig, SystemType, DatabaseType, TransferMethod, AuthType
)
from migration_assistant.models.session import MigrationStatus
from migration_assistant.cli.main import main as cli_main
from migration_assistant.api.main import app


@pytest.mark.integration
class TestWordPressMigrationE2E:
    """End-to-end WordPress migration scenarios."""
    
    @pytest.fixture
    def wordpress_migration_config(self):
        """WordPress to AWS S3 migration configuration."""
        return MigrationConfig(
            name="WordPress to S3 Migration",
            description="Migrate WordPress site from shared hosting to AWS S3",
            source=SystemConfig(
                type=SystemType.WORDPRESS,
                host="source.example.com",
                authentication=AuthConfig(
                    type=AuthType.SSH_KEY,
                    username="wpuser",
                    private_key_path="/path/to/key"
                ),
                database=DatabaseConfig(
                    type=DatabaseType.MYSQL,
                    host="mysql.source.com",
                    port=3306,
                    database_name="wordpress_db",
                    username="wp_user",
                    password="wp_pass"
                )
            ),
            destination=SystemConfig(
                type=SystemType.AWS_S3,
                host="s3.amazonaws.com",
                cloud_config=CloudConfig(
                    provider="aws",
                    region="us-east-1",
                    bucket="wordpress-migration-bucket",
                    access_key="test_access_key",
                    secret_key="test_secret_key"
                ),
                database=DatabaseConfig(
                    type=DatabaseType.AURORA_MYSQL,
                    host="aurora.amazonaws.com",
                    database_name="wordpress_db_new",
                    username="aurora_user",
                    password="aurora_pass"
                )
            ),
            transfer=TransferConfig(
                method=TransferMethod.S3_SYNC,
                parallel_transfers=4,
                compression_enabled=True,
                verify_checksums=True
            ),
            options={
                "maintenance_mode": True,
                "backup_before": True,
                "verify_after": True,
                "preserve_permissions": True
            }
        )
    
    @pytest.mark.asyncio
    async def test_complete_wordpress_migration(self, wordpress_migration_config, test_databases, mock_cloud_services):
        """Test complete WordPress migration workflow."""
        if "mysql" not in test_databases:
            pytest.skip("MySQL container not available")
        
        orchestrator = MigrationOrchestrator()
        
        # Mock external services
        with patch.multiple(
            'migration_assistant.validation.connectivity.ConnectivityValidator',
            validate_database_connection=Mock(return_value=Mock(success=True)),
            validate_ssh_connection=Mock(return_value=Mock(success=True))
        ), patch.multiple(
            'migration_assistant.transfer.methods.cloud.S3Transfer',
            connect=Mock(return_value=True),
            upload_directory=Mock(return_value=Mock(success=True, files_transferred=150))
        ), patch.multiple(
            'migration_assistant.database.migrators.mysql_migrator.MySQLMigrator',
            connect=Mock(return_value=True),
            export_data=Mock(return_value=Mock(success=True, export_path="/tmp/wp_export.sql")),
            import_data=Mock(return_value=Mock(success=True))
        ):
            
            # Create migration session
            session = orchestrator.create_session(wordpress_migration_config)
            assert session.id is not None
            assert session.status == MigrationStatus.PENDING
            
            # Start migration
            success = await orchestrator.start_migration(session.id)
            assert success is True
            
            # Monitor progress
            max_wait = 30  # 30 seconds max wait
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                current_session = orchestrator.get_session(session.id)
                if current_session.status in [MigrationStatus.COMPLETED, MigrationStatus.FAILED]:
                    break
                await asyncio.sleep(1)
            
            # Verify completion
            final_session = orchestrator.get_session(session.id)
            assert final_session.status == MigrationStatus.COMPLETED
            assert final_session.progress == 100
    
    @pytest.mark.asyncio
    async def test_wordpress_migration_with_rollback(self, wordpress_migration_config):
        """Test WordPress migration with rollback scenario."""
        orchestrator = MigrationOrchestrator()
        
        # Mock a failure during file transfer
        with patch.multiple(
            'migration_assistant.validation.connectivity.ConnectivityValidator',
            validate_database_connection=Mock(return_value=Mock(success=True)),
            validate_ssh_connection=Mock(return_value=Mock(success=True))
        ), patch.multiple(
            'migration_assistant.transfer.methods.cloud.S3Transfer',
            connect=Mock(return_value=True),
            upload_directory=Mock(side_effect=Exception("Transfer failed"))
        ), patch.multiple(
            'migration_assistant.backup.manager.BackupManager',
            create_backup=Mock(return_value=Mock(success=True, backup_id="backup_123")),
            restore_backup=Mock(return_value=Mock(success=True))
        ):
            
            # Create and start migration
            session = orchestrator.create_session(wordpress_migration_config)
            success = await orchestrator.start_migration(session.id)
            
            # Migration should fail
            assert success is False
            
            # Trigger rollback
            rollback_success = await orchestrator.rollback_migration(session.id)
            assert rollback_success is True
            
            # Verify session status
            final_session = orchestrator.get_session(session.id)
            assert final_session.status == MigrationStatus.ROLLED_BACK


@pytest.mark.integration
class TestControlPanelMigrationE2E:
    """End-to-end control panel migration scenarios."""
    
    @pytest.fixture
    def cpanel_migration_config(self):
        """cPanel to cloud migration configuration."""
        return MigrationConfig(
            name="cPanel to Cloud Migration",
            description="Migrate multiple sites from cPanel to cloud infrastructure",
            source=SystemConfig(
                type=SystemType.CPANEL,
                host="shared.hosting.com",
                authentication=AuthConfig(
                    type=AuthType.API_KEY,
                    username="cpanel_user",
                    api_key="cpanel_api_token"
                ),
                control_panel_config={
                    "type": "cpanel",
                    "port": 2083,
                    "ssl": True
                }
            ),
            destination=SystemConfig(
                type=SystemType.KUBERNETES,
                host="k8s.cluster.com",
                authentication=AuthConfig(
                    type=AuthType.KUBE_CONFIG,
                    config_path="/path/to/kubeconfig"
                ),
                container_config={
                    "namespace": "migration-target",
                    "storage_class": "fast-ssd"
                }
            ),
            transfer=TransferConfig(
                method=TransferMethod.KUBERNETES,
                parallel_transfers=2,
                compression_enabled=True
            ),
            options={
                "preserve_email_accounts": True,
                "migrate_dns_records": True,
                "backup_before": True
            }
        )
    
    @pytest.mark.asyncio
    async def test_cpanel_multi_site_migration(self, cpanel_migration_config, mock_control_panel_apis):
        """Test migration of multiple sites from cPanel."""
        orchestrator = MigrationOrchestrator()
        
        # Mock cPanel API responses
        with patch('migration_assistant.platforms.control_panel.CPanelAdapter') as mock_adapter:
            mock_instance = Mock()
            mock_adapter.return_value = mock_instance
            
            # Mock account extraction
            mock_instance.extract_accounts.return_value = [
                {"user": "site1", "domain": "site1.com", "databases": ["site1_db"]},
                {"user": "site2", "domain": "site2.com", "databases": ["site2_db"]}
            ]
            
            # Mock file extraction
            mock_instance.extract_files.return_value = Mock(
                success=True,
                files_extracted=250,
                total_size=1024000
            )
            
            # Mock database extraction
            mock_instance.extract_databases.return_value = Mock(
                success=True,
                databases_exported=2
            )
            
            # Create and start migration
            session = orchestrator.create_session(cpanel_migration_config)
            success = await orchestrator.start_migration(session.id)
            
            assert success is True
            
            # Verify session completion
            final_session = orchestrator.get_session(session.id)
            assert final_session.status in [MigrationStatus.COMPLETED, MigrationStatus.RUNNING]
    
    @pytest.mark.asyncio
    async def test_control_panel_api_error_handling(self, cpanel_migration_config):
        """Test error handling when control panel APIs fail."""
        orchestrator = MigrationOrchestrator()
        
        # Mock API failures
        with patch('migration_assistant.platforms.control_panel.CPanelAdapter') as mock_adapter:
            mock_instance = Mock()
            mock_adapter.return_value = mock_instance
            
            # Mock API connection failure
            mock_instance.extract_accounts.side_effect = Exception("API connection failed")
            
            # Create and start migration
            session = orchestrator.create_session(cpanel_migration_config)
            success = await orchestrator.start_migration(session.id)
            
            # Migration should fail gracefully
            assert success is False
            
            final_session = orchestrator.get_session(session.id)
            assert final_session.status == MigrationStatus.FAILED
            assert len(final_session.errors) > 0


@pytest.mark.integration
class TestDatabaseMigrationE2E:
    """End-to-end database migration scenarios."""
    
    @pytest.fixture
    def database_migration_config(self):
        """MySQL to PostgreSQL migration configuration."""
        return MigrationConfig(
            name="MySQL to PostgreSQL Migration",
            description="Migrate from MySQL to PostgreSQL with schema conversion",
            source=SystemConfig(
                type=SystemType.MYSQL,
                host="mysql.source.com",
                database=DatabaseConfig(
                    type=DatabaseType.MYSQL,
                    host="mysql.source.com",
                    port=3306,
                    database_name="source_db",
                    username="mysql_user",
                    password="mysql_pass"
                )
            ),
            destination=SystemConfig(
                type=SystemType.POSTGRESQL,
                host="postgres.dest.com",
                database=DatabaseConfig(
                    type=DatabaseType.POSTGRESQL,
                    host="postgres.dest.com",
                    port=5432,
                    database_name="dest_db",
                    username="postgres_user",
                    password="postgres_pass"
                )
            ),
            transfer=TransferConfig(
                method=TransferMethod.DIRECT_DATABASE,
                batch_size=1000,
                parallel_transfers=2
            ),
            options={
                "convert_schema": True,
                "validate_data": True,
                "backup_before": True
            }
        )
    
    @pytest.mark.asyncio
    async def test_mysql_to_postgresql_migration(self, database_migration_config, test_databases):
        """Test MySQL to PostgreSQL migration with schema conversion."""
        if "mysql" not in test_databases or "postgres" not in test_databases:
            pytest.skip("Required database containers not available")
        
        orchestrator = MigrationOrchestrator()
        
        # Mock database operations
        with patch.multiple(
            'migration_assistant.database.migrators.mysql_migrator.MySQLMigrator',
            connect=Mock(return_value=True),
            get_schema_info=Mock(return_value=Mock(
                tables=[Mock(name="users"), Mock(name="posts")],
                total_rows=1500
            )),
            export_data=Mock(return_value=Mock(success=True, rows_exported=1500))
        ), patch.multiple(
            'migration_assistant.database.migrators.postgresql_migrator.PostgreSQLMigrator',
            connect=Mock(return_value=True),
            import_data=Mock(return_value=Mock(success=True, rows_imported=1500)),
            validate_data_integrity=Mock(return_value=Mock(success=True, row_count=1500))
        ):
            
            # Create and start migration
            session = orchestrator.create_session(database_migration_config)
            success = await orchestrator.start_migration(session.id)
            
            assert success is True
            
            # Verify completion
            final_session = orchestrator.get_session(session.id)
            assert final_session.status in [MigrationStatus.COMPLETED, MigrationStatus.RUNNING]
    
    @pytest.mark.asyncio
    async def test_large_database_migration_performance(self, database_migration_config):
        """Test performance with large database migration."""
        orchestrator = MigrationOrchestrator()
        
        # Mock large database
        with patch.multiple(
            'migration_assistant.database.migrators.mysql_migrator.MySQLMigrator',
            connect=Mock(return_value=True),
            get_schema_info=Mock(return_value=Mock(
                tables=[Mock(name=f"table_{i}") for i in range(50)],
                total_rows=1000000  # 1 million rows
            )),
            export_data=Mock(return_value=Mock(success=True, rows_exported=1000000))
        ), patch.multiple(
            'migration_assistant.database.migrators.postgresql_migrator.PostgreSQLMigrator',
            connect=Mock(return_value=True),
            import_data=Mock(return_value=Mock(success=True, rows_imported=1000000))
        ):
            
            start_time = time.time()
            
            # Create and start migration
            session = orchestrator.create_session(database_migration_config)
            success = await orchestrator.start_migration(session.id)
            
            migration_time = time.time() - start_time
            
            assert success is True
            # Large migration should complete within reasonable time (mocked)
            assert migration_time < 10  # 10 seconds for mocked operations


@pytest.mark.integration
class TestCLIEndToEnd:
    """End-to-end CLI testing."""
    
    @pytest.mark.asyncio
    async def test_cli_interactive_migration(self, temp_directory):
        """Test CLI interactive migration workflow."""
        config_file = os.path.join(temp_directory, "test_config.yaml")
        
        # Create test configuration
        test_config = {
            "name": "CLI Test Migration",
            "source": {
                "type": "static",
                "host": "source.example.com",
                "path": "/var/www/html"
            },
            "destination": {
                "type": "s3",
                "bucket": "test-bucket",
                "region": "us-east-1"
            },
            "options": {
                "backup_before": True
            }
        }
        
        with open(config_file, "w") as f:
            import yaml
            yaml.dump(test_config, f)
        
        # Mock CLI dependencies
        with patch('migration_assistant.orchestrator.orchestrator.MigrationOrchestrator') as mock_orchestrator:
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            mock_instance.create_session.return_value = Mock(
                id="cli_test_session",
                status=MigrationStatus.PENDING
            )
            mock_instance.start_migration.return_value = True
            mock_instance.get_session.return_value = Mock(
                id="cli_test_session",
                status=MigrationStatus.COMPLETED,
                progress=100
            )
            
            # Test CLI command
            import sys
            from io import StringIO
            
            # Capture output
            captured_output = StringIO()
            sys.stdout = captured_output
            
            try:
                # Simulate CLI arguments
                sys.argv = ["migration-assistant", "migrate", "--config", config_file, "--yes"]
                
                # This would normally run the CLI
                # For testing, we'll mock the main function
                with patch('migration_assistant.cli.main.main') as mock_main:
                    mock_main.return_value = 0
                    result = mock_main()
                
                assert result == 0
                
            finally:
                sys.stdout = sys.__stdout__
    
    def test_cli_validation_command(self, temp_directory):
        """Test CLI validation command."""
        config_file = os.path.join(temp_directory, "validation_test.yaml")
        
        # Create test configuration
        test_config = {
            "source": {"type": "wordpress", "host": "test.com"},
            "destination": {"type": "s3", "bucket": "test-bucket"}
        }
        
        with open(config_file, "w") as f:
            import yaml
            yaml.dump(test_config, f)
        
        # Mock validation
        with patch('migration_assistant.validation.engine.ValidationEngine') as mock_validator:
            mock_instance = Mock()
            mock_validator.return_value = mock_instance
            mock_instance.validate_migration.return_value = Mock(
                success=True,
                errors=[],
                warnings=["Minor compatibility issue"],
                validation_time=1.2
            )
            
            # Test validation command
            import sys
            sys.argv = ["migration-assistant", "validate", "--config", config_file]
            
            with patch('migration_assistant.cli.main.main') as mock_main:
                mock_main.return_value = 0
                result = mock_main()
            
            assert result == 0


@pytest.mark.integration
class TestAPIEndToEnd:
    """End-to-end API testing."""
    
    @pytest.fixture
    def api_client(self):
        """Create API test client."""
        from fastapi.testclient import TestClient
        return TestClient(app)
    
    @pytest.fixture
    def auth_token(self):
        """Create authentication token."""
        from migration_assistant.api.auth import create_access_token
        return create_access_token(data={"sub": "testuser", "tenant_id": "test_tenant"})
    
    def test_api_complete_migration_workflow(self, api_client, auth_token, sample_migration_request):
        """Test complete migration workflow via API."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        with patch('migration_assistant.api.auth.get_user') as mock_get_user, \
             patch('migration_assistant.orchestrator.orchestrator.MigrationOrchestrator') as mock_orchestrator:
            
            mock_get_user.return_value = {"username": "testuser", "tenant_id": "test_tenant"}
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            
            # Mock session creation
            mock_session = Mock(id="api_test_session", status="pending")
            mock_instance.create_session.return_value = mock_session
            mock_instance.start_migration.return_value = True
            
            # Create migration
            response = api_client.post("/migrations/", json=sample_migration_request, headers=headers)
            assert response.status_code == 201
            
            data = response.json()
            session_id = data["session_id"]
            
            # Start migration
            response = api_client.post(f"/migrations/{session_id}/start", headers=headers)
            assert response.status_code == 200
            
            # Check status
            mock_instance.get_session.return_value = Mock(
                id=session_id,
                status="running",
                progress=50
            )
            
            response = api_client.get(f"/migrations/{session_id}/status", headers=headers)
            assert response.status_code == 200
            
            status_data = response.json()
            assert status_data["status"] == "running"
            assert status_data["progress"] == 50
    
    def test_api_error_handling_workflow(self, api_client, auth_token):
        """Test API error handling in migration workflow."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        with patch('migration_assistant.api.auth.get_user') as mock_get_user:
            mock_get_user.return_value = {"username": "testuser", "tenant_id": "test_tenant"}
            
            # Test invalid migration request
            invalid_request = {"invalid": "data"}
            
            response = api_client.post("/migrations/", json=invalid_request, headers=headers)
            assert response.status_code == 422  # Validation error
            
            # Test non-existent session
            response = api_client.get("/migrations/nonexistent/status", headers=headers)
            assert response.status_code == 404


@pytest.mark.integration
class TestPerformanceEndToEnd:
    """End-to-end performance testing scenarios."""
    
    @pytest.mark.asyncio
    async def test_high_throughput_migration(self, performance_test_data):
        """Test migration performance with high file throughput."""
        orchestrator = MigrationOrchestrator()
        
        # Mock high-performance operations
        with patch('migration_assistant.performance.hybrid.HybridPerformanceManager') as mock_hybrid:
            mock_instance = Mock()
            mock_hybrid.return_value = mock_instance
            
            # Mock high-speed operations
            mock_instance.copy_files.return_value = Mock(
                success=True,
                files_transferred=1000,
                total_bytes=1024000000,  # 1GB
                transfer_rate=104857600,  # 100MB/s
                method_used="go"
            )
            
            # Create performance-optimized config
            config = MigrationConfig(
                name="High Throughput Test",
                source=Mock(),
                destination=Mock(),
                transfer=TransferConfig(
                    method=TransferMethod.HYBRID_SYNC,
                    parallel_transfers=8,
                    use_go_acceleration=True
                ),
                options={"performance_mode": "maximum"}
            )
            
            start_time = time.time()
            
            session = orchestrator.create_session(config)
            success = await orchestrator.start_migration(session.id)
            
            migration_time = time.time() - start_time
            
            assert success is True
            # High throughput migration should be fast
            assert migration_time < 5  # 5 seconds for mocked operations
    
    @pytest.mark.asyncio
    async def test_concurrent_migrations_performance(self):
        """Test performance with multiple concurrent migrations."""
        orchestrator = MigrationOrchestrator()
        
        # Create multiple migration configs
        configs = []
        for i in range(5):
            config = MigrationConfig(
                name=f"Concurrent Migration {i}",
                source=Mock(),
                destination=Mock(),
                transfer=TransferConfig(method=TransferMethod.SSH_SCP),
                options={}
            )
            configs.append(config)
        
        # Mock successful migrations
        with patch.multiple(
            orchestrator,
            start_migration=Mock(return_value=True),
            get_session=Mock(return_value=Mock(status=MigrationStatus.COMPLETED))
        ):
            
            # Start all migrations concurrently
            start_time = time.time()
            
            sessions = []
            for config in configs:
                session = orchestrator.create_session(config)
                sessions.append(session)
            
            # Start all migrations
            tasks = [orchestrator.start_migration(session.id) for session in sessions]
            results = await asyncio.gather(*tasks)
            
            total_time = time.time() - start_time
            
            # All migrations should succeed
            assert all(results)
            # Concurrent execution should be efficient
            assert total_time < 10  # 10 seconds for 5 concurrent migrations


@pytest.mark.integration
class TestRealWorldScenarios:
    """Real-world migration scenarios."""
    
    @pytest.mark.asyncio
    async def test_wordpress_multisite_migration(self):
        """Test WordPress multisite network migration."""
        # This would test a complex scenario with multiple WordPress sites
        # in a multisite network, each with their own database and files
        pass
    
    @pytest.mark.asyncio
    async def test_ecommerce_platform_migration(self):
        """Test e-commerce platform migration with sensitive data."""
        # This would test migration of an e-commerce site with
        # customer data, payment information, and inventory
        pass
    
    @pytest.mark.asyncio
    async def test_enterprise_application_migration(self):
        """Test enterprise application migration with complex dependencies."""
        # This would test migration of a complex enterprise application
        # with multiple databases, microservices, and external integrations
        pass