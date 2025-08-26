# Migration Assistant Testing Framework

This directory contains a comprehensive testing framework for the Web & Database Migration Assistant, providing 90%+ code coverage with unit tests, integration tests, performance benchmarks, and end-to-end testing scenarios.

## Testing Architecture

### Test Types

1. **Unit Tests** - Fast, isolated tests for individual components
2. **Integration Tests** - Tests with real databases and services using Docker
3. **Performance Tests** - Benchmarks comparing Go vs Python implementations
4. **End-to-End Tests** - Complete migration workflows with realistic scenarios
5. **Load Tests** - API and system performance under high load
6. **Security Tests** - Vulnerability scanning and security validation

### Test Structure

```
tests/
├── conftest.py                          # Pytest configuration and fixtures
├── test_comprehensive_validation.py     # Validation engine tests (90%+ coverage)
├── test_comprehensive_database.py       # Database migration tests (90%+ coverage)
├── test_comprehensive_transfer.py       # File transfer tests (90%+ coverage)
├── test_comprehensive_api.py            # API tests with auth and multi-tenant
├── test_performance_benchmarks.py       # Go vs Python performance comparisons
├── test_end_to_end.py                  # Complete migration scenarios
├── test_load_testing.py                # Load testing for APIs and systems
├── fixtures/                           # Test fixtures and mock services
│   ├── mock-apis/                      # Mock control panel APIs
│   ├── mysql/                          # MySQL test data
│   ├── postgres/                       # PostgreSQL test data
│   ├── mongo/                          # MongoDB test data
│   ├── scripts/                        # Test data generation and cleanup
│   ├── Dockerfile.integration          # Integration test environment
│   └── Dockerfile.performance          # Performance test environment
└── README.md                           # This file
```

## Quick Start

### Prerequisites

- Python 3.11+
- Go 1.21+
- Docker and Docker Compose
- pytest and testing dependencies

### Install Dependencies

```bash
# Install Python dependencies
pip install -e ".[dev,test]"

# Build Go binary
cd go-engine && go build -o bin/migration-engine ./cmd/migration-engine
```

### Run All Tests

```bash
# Run comprehensive test suite
python tests/run_comprehensive_tests.py

# Run specific test types
python tests/run_comprehensive_tests.py --suites unit_tests integration_tests

# Run with coverage
python tests/run_comprehensive_tests.py --verbose
```

### Run Individual Test Suites

```bash
# Unit tests only (fast)
pytest tests/ -v -m "not integration and not benchmark"

# Integration tests (requires Docker)
pytest tests/ -v -m "integration"

# Performance benchmarks
pytest tests/ -v -m "benchmark" --benchmark-only

# Load tests
pytest tests/test_load_testing.py -v
```

## Test Environment Setup

### Docker Test Environment

The testing framework uses Docker Compose to provide isolated test environments:

```bash
# Start test environment
docker-compose -f docker-compose.test.yml up -d

# Run integration tests
pytest tests/ -v -m "integration"

# Stop test environment
docker-compose -f docker-compose.test.yml down -v
```

### Test Services

- **MySQL 8.0** - Port 3307
- **PostgreSQL 15** - Port 5433
- **MongoDB 6.0** - Port 27018
- **Redis 7** - Port 6380
- **LocalStack** - Port 4566 (AWS services)
- **Mock cPanel API** - Port 2083
- **Mock DirectAdmin API** - Port 2222
- **Mock Plesk API** - Port 8443
- **FTP Server** - Port 21
- **SSH Server** - Port 2222

### Test Data Generation

```bash
# Generate test data
python tests/fixtures/scripts/seed_test_data.py --output-dir /tmp/test-data

# Clean up test data
python tests/fixtures/scripts/cleanup_test_data.py --verbose
```

## Test Categories

### Unit Tests

Fast, isolated tests with mocked dependencies:

```bash
# Run all unit tests
pytest tests/test_comprehensive_*.py -v

# Run specific component tests
pytest tests/test_comprehensive_validation.py -v
pytest tests/test_comprehensive_database.py -v
pytest tests/test_comprehensive_transfer.py -v
pytest tests/test_comprehensive_api.py -v
```

**Coverage Areas:**
- Validation engine (connectivity, compatibility, permissions, dependencies)
- Database migration (MySQL, PostgreSQL, SQLite, MongoDB, Redis)
- File transfer (SSH, FTP, cloud storage, Docker, Kubernetes)
- API endpoints (authentication, multi-tenant, CRUD operations)
- Configuration management and presets
- Error handling and recovery

### Integration Tests

Tests with real services using Docker containers:

```bash
# Start test environment first
docker-compose -f docker-compose.test.yml up -d

# Run integration tests
pytest tests/ -v -m "integration"

# Specific integration scenarios
pytest tests/test_end_to_end.py::TestWordPressMigrationE2E -v
pytest tests/test_end_to_end.py::TestControlPanelMigrationE2E -v
pytest tests/test_end_to_end.py::TestDatabaseMigrationE2E -v
```

**Test Scenarios:**
- WordPress migration from shared hosting to AWS S3
- Control panel (cPanel/DirectAdmin/Plesk) migrations
- Database migrations between different systems
- Multi-site and complex application migrations
- Rollback and recovery scenarios

### Performance Tests

Benchmarks comparing Go vs Python implementations:

```bash
# Run performance benchmarks
pytest tests/test_performance_benchmarks.py -v --benchmark-only

# Compare Go vs Python file operations
pytest tests/test_performance_benchmarks.py::TestGoVsPythonPerformance -v --benchmark-only

# Test hybrid performance manager
pytest tests/test_performance_benchmarks.py::TestHybridPerformanceManager -v --benchmark-only
```

**Benchmark Areas:**
- File copy operations (Go vs Python)
- Checksum calculations (parallel vs sequential)
- Compression performance
- Database operations
- API response times
- Memory usage under load

### Load Tests

API and system performance under high concurrent load:

```bash
# Run load tests
pytest tests/test_load_testing.py -v

# API load testing
pytest tests/test_load_testing.py::TestAPILoadTesting -v

# Database load testing
pytest tests/test_load_testing.py::TestDatabaseLoadTesting -v

# File transfer load testing
pytest tests/test_load_testing.py::TestFileTransferLoadTesting -v
```

**Load Test Scenarios:**
- Concurrent API requests (10-50 users)
- Database connection pooling
- File transfer throughput
- Memory usage monitoring
- System resource utilization

### End-to-End Tests

Complete migration workflows with realistic scenarios:

```bash
# Run E2E tests
pytest tests/test_end_to_end.py -v

# WordPress migration E2E
pytest tests/test_end_to_end.py::TestWordPressMigrationE2E::test_complete_wordpress_migration -v

# Control panel migration E2E
pytest tests/test_end_to_end.py::TestControlPanelMigrationE2E::test_cpanel_multi_site_migration -v
```

## Test Configuration

### Environment Variables

```bash
# Test database connections
export TEST_DATABASE_MYSQL_HOST=localhost
export TEST_DATABASE_MYSQL_PORT=3307
export TEST_DATABASE_POSTGRES_HOST=localhost
export TEST_DATABASE_POSTGRES_PORT=5433
export TEST_DATABASE_MONGO_HOST=localhost
export TEST_DATABASE_MONGO_PORT=27018
export TEST_DATABASE_REDIS_HOST=localhost
export TEST_DATABASE_REDIS_PORT=6380

# Mock services
export TEST_LOCALSTACK_HOST=localhost
export TEST_LOCALSTACK_PORT=4566
export TEST_CPANEL_HOST=localhost
export TEST_CPANEL_PORT=2083

# Test data paths
export TEST_DATA_PATH=/tmp/test-data
export GO_BINARY_PATH=./go-engine/bin/migration-engine
```

### Pytest Configuration

Key pytest settings in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
minversion = "7.0"
addopts = "-ra -q --strict-markers --strict-config"
testpaths = ["tests"]
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests",
    "benchmark: marks tests as benchmark tests",
]
```

### Coverage Configuration

Coverage settings for comprehensive reporting:

```toml
[tool.coverage.run]
source = ["migration_assistant"]
omit = ["*/tests/*", "*/test_*", "*/__pycache__/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if self.debug:",
    "raise AssertionError",
    "raise NotImplementedError",
]
```

## Mock Services

### Control Panel APIs

Mock implementations of popular control panel APIs:

- **cPanel API** - Simulates cPanel v2/UAPI endpoints
- **DirectAdmin API** - Simulates DirectAdmin API calls
- **Plesk API** - Simulates Plesk XML API

### Cloud Services

Mock cloud service implementations:

- **AWS S3** - LocalStack S3 simulation
- **Google Cloud Storage** - Mock GCS client
- **Azure Blob Storage** - Mock Azure client

### Database Services

Containerized database services with test data:

- **MySQL 8.0** - With sample WordPress-like schema
- **PostgreSQL 15** - With advanced features (functions, triggers)
- **MongoDB 6.0** - With complex document structures
- **Redis 7** - With various data types

## Performance Benchmarking

### Go vs Python Comparisons

The testing framework includes comprehensive benchmarks comparing Go and Python implementations:

```python
# Example benchmark results
@pytest.mark.benchmark(group="file_copy")
def test_go_vs_python_file_copy():
    # Go implementation: ~50MB/s
    # Python implementation: ~20MB/s
    # Go is ~2.5x faster for large files
```

### Benchmark Categories

1. **File Operations**
   - Copy performance
   - Checksum calculations
   - Compression ratios

2. **Database Operations**
   - Connection establishment
   - Query execution
   - Data transfer rates

3. **Network Operations**
   - HTTP requests
   - File transfers
   - Concurrent connections

4. **Memory Usage**
   - Peak memory consumption
   - Memory leaks detection
   - Garbage collection impact

## Continuous Integration

### GitHub Actions Workflow

The project includes a comprehensive CI/CD pipeline:

```yaml
# .github/workflows/comprehensive-tests.yml
- Unit Tests (Python 3.11, 3.12)
- Go Tests with benchmarks
- Integration Tests with Docker
- Performance Tests (scheduled)
- Security Scans
- Code Quality Checks
```

### Test Execution Matrix

- **Unit Tests**: Run on every push/PR
- **Integration Tests**: Run on main branch and PRs
- **Performance Tests**: Run nightly or on `[perf]` tag
- **Load Tests**: Run weekly or on demand

## Test Data Management

### Test Data Generation

```bash
# Generate comprehensive test data
python tests/fixtures/scripts/seed_test_data.py \
    --output-dir /tmp/test-data \
    --text-files 1000 \
    --binary-files 50
```

### Test Data Cleanup

```bash
# Clean up all test resources
python tests/fixtures/scripts/cleanup_test_data.py --verbose

# Clean up only Docker resources
python tests/fixtures/scripts/cleanup_test_data.py --docker-only

# Verify cleanup
python tests/fixtures/scripts/cleanup_test_data.py --verify
```

## Debugging Tests

### Running Individual Tests

```bash
# Run single test with verbose output
pytest tests/test_comprehensive_validation.py::TestValidationEngine::test_validate_migration_success -v -s

# Run with debugger
pytest tests/test_comprehensive_validation.py::TestValidationEngine::test_validate_migration_success -v -s --pdb

# Run with coverage
pytest tests/test_comprehensive_validation.py -v --cov=migration_assistant --cov-report=html
```

### Test Debugging Tools

- **pytest-xdist** - Parallel test execution
- **pytest-benchmark** - Performance benchmarking
- **pytest-mock** - Advanced mocking capabilities
- **pytest-asyncio** - Async test support
- **pytest-cov** - Coverage reporting

### Log Analysis

```bash
# View test logs
docker-compose -f docker-compose.test.yml logs

# View specific service logs
docker-compose -f docker-compose.test.yml logs mysql-test

# Follow logs in real-time
docker-compose -f docker-compose.test.yml logs -f integration-test
```

## Best Practices

### Writing Tests

1. **Use descriptive test names** that explain what is being tested
2. **Follow AAA pattern** - Arrange, Act, Assert
3. **Mock external dependencies** in unit tests
4. **Use real services** in integration tests
5. **Test error conditions** as well as success paths
6. **Include performance assertions** in benchmark tests

### Test Organization

1. **Group related tests** in classes
2. **Use fixtures** for common setup
3. **Mark tests appropriately** (integration, benchmark, slow)
4. **Keep tests independent** - no shared state
5. **Clean up resources** after tests

### Performance Testing

1. **Establish baselines** for performance metrics
2. **Test with realistic data sizes**
3. **Monitor resource usage**
4. **Compare implementations** (Go vs Python)
5. **Set performance thresholds**

## Troubleshooting

### Common Issues

1. **Docker containers not starting**
   ```bash
   docker-compose -f docker-compose.test.yml ps
   docker-compose -f docker-compose.test.yml logs
   ```

2. **Database connection failures**
   ```bash
   # Check if containers are healthy
   docker-compose -f docker-compose.test.yml ps
   
   # Test database connectivity
   docker exec migration_test_mysql mysql -u testuser -ptestpass -e "SELECT 1"
   ```

3. **Test data not found**
   ```bash
   # Regenerate test data
   python tests/fixtures/scripts/seed_test_data.py
   ```

4. **Go binary not found**
   ```bash
   # Build Go binary
   cd go-engine && go build -o bin/migration-engine ./cmd/migration-engine
   ```

### Performance Issues

1. **Slow test execution**
   - Use `pytest-xdist` for parallel execution
   - Skip slow tests with `-m "not slow"`
   - Use smaller test datasets

2. **Memory issues**
   - Monitor memory usage with `pytest-benchmark`
   - Clean up resources in test teardown
   - Use memory profiling tools

3. **Docker resource limits**
   - Increase Docker memory limits
   - Clean up unused containers and volumes
   - Monitor disk space usage

## Contributing

### Adding New Tests

1. **Follow naming conventions** - `test_*.py` files
2. **Use appropriate markers** - `@pytest.mark.integration`
3. **Add fixtures** for reusable test setup
4. **Update documentation** - Add test descriptions
5. **Ensure coverage** - Aim for 90%+ coverage

### Test Review Checklist

- [ ] Tests are independent and can run in any order
- [ ] External dependencies are properly mocked
- [ ] Integration tests use Docker services
- [ ] Performance tests include baseline assertions
- [ ] Error conditions are tested
- [ ] Test names are descriptive
- [ ] Fixtures are used for common setup
- [ ] Resources are cleaned up properly
- [ ] Documentation is updated

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [pytest-benchmark Documentation](https://pytest-benchmark.readthedocs.io/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [Go Testing Documentation](https://golang.org/pkg/testing/)