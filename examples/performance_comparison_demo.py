#!/usr/bin/env python3
"""
Performance Comparison Demo

This script demonstrates the performance differences between Go and Python
implementations for various operations in the migration assistant.
"""

import asyncio
import logging
import os
import tempfile
import time
from pathlib import Path

from migration_assistant.performance import HybridPerformanceEngine


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def create_test_files(temp_dir: str, num_files: int = 5, file_size_kb: int = 1024):
    """Create test files for performance testing."""
    test_files = []
    
    for i in range(num_files):
        file_path = Path(temp_dir) / f"test_file_{i}.txt"
        
        # Create file with specified size
        content = f"Test file {i} content.\n" * (file_size_kb * 1024 // 20)  # Approximate size
        file_path.write_text(content)
        
        test_files.append(str(file_path))
        logger.info(f"Created test file: {file_path} ({file_path.stat().st_size} bytes)")
    
    return test_files


async def benchmark_file_copy(engine: HybridPerformanceEngine, source_files: list, temp_dir: str):
    """Benchmark file copying operations."""
    logger.info("=== File Copy Benchmark ===")
    
    for i, source_file in enumerate(source_files):
        dest_file = Path(temp_dir) / f"copy_dest_{i}.txt"
        
        logger.info(f"Copying file {i+1}/{len(source_files)}: {Path(source_file).name}")
        
        # Test with Go engine (if available)
        if engine.go_engine.is_available():
            start_time = time.time()
            go_result = await engine.go_engine.copy_file(source_file, f"{dest_file}_go.txt")
            go_time = time.time() - start_time
            
            if go_result and go_result.success:
                logger.info(f"  Go: {go_time:.3f}s, {go_result.transfer_rate_mbps:.2f} MB/s")
            else:
                logger.error("  Go: Failed")
        
        # Test with Python engine
        start_time = time.time()
        python_result = await engine.python_engine.copy_file(source_file, f"{dest_file}_python.txt")
        python_time = time.time() - start_time
        
        if python_result and python_result.success:
            logger.info(f"  Python: {python_time:.3f}s, {python_result.transfer_rate_mbps:.2f} MB/s")
        else:
            logger.error("  Python: Failed")
        
        # Test with hybrid engine (automatic selection)
        start_time = time.time()
        hybrid_result = await engine.copy_file(source_file, f"{dest_file}_hybrid.txt")
        hybrid_time = time.time() - start_time
        
        if hybrid_result and hybrid_result.success:
            logger.info(f"  Hybrid: {hybrid_time:.3f}s, {hybrid_result.transfer_rate_mbps:.2f} MB/s")
        else:
            logger.error("  Hybrid: Failed")
        
        logger.info("")


async def benchmark_checksum_calculation(engine: HybridPerformanceEngine, source_files: list):
    """Benchmark checksum calculation operations."""
    logger.info("=== Checksum Calculation Benchmark ===")
    
    # Test with Go engine (if available)
    if engine.go_engine.is_available():
        start_time = time.time()
        go_results = await engine.go_engine.calculate_checksums(source_files)
        go_time = time.time() - start_time
        
        if go_results:
            logger.info(f"Go: {go_time:.3f}s for {len(source_files)} files")
            for result in go_results[:2]:  # Show first 2 results
                logger.info(f"  {Path(result.file).name}: SHA256={result.sha256[:16]}...")
        else:
            logger.error("Go: Failed")
    
    # Test with Python engine
    start_time = time.time()
    python_results = await engine.python_engine.calculate_checksums(source_files)
    python_time = time.time() - start_time
    
    if python_results:
        logger.info(f"Python: {python_time:.3f}s for {len(source_files)} files")
        for result in python_results[:2]:  # Show first 2 results
            logger.info(f"  {Path(result.file).name}: SHA256={result.sha256[:16]}...")
    else:
        logger.error("Python: Failed")
    
    # Test with hybrid engine
    start_time = time.time()
    hybrid_results = await engine.calculate_checksums(source_files)
    hybrid_time = time.time() - start_time
    
    if hybrid_results:
        logger.info(f"Hybrid: {hybrid_time:.3f}s for {len(source_files)} files")
    else:
        logger.error("Hybrid: Failed")
    
    logger.info("")


async def benchmark_system_monitoring(engine: HybridPerformanceEngine):
    """Benchmark system monitoring operations."""
    logger.info("=== System Monitoring Benchmark ===")
    
    # Test with Go engine (if available)
    if engine.go_engine.is_available():
        start_time = time.time()
        go_stats = await engine.go_engine.get_system_stats()
        go_time = time.time() - start_time
        
        if go_stats:
            logger.info(f"Go: {go_time:.3f}s")
            logger.info(f"  CPU: {go_stats.cpu.get('count', 0)} cores")
            logger.info(f"  Memory: {go_stats.memory.get('total', 0) / (1024**3):.1f} GB total")
            logger.info(f"  Disks: {len(go_stats.disk)} partitions")
        else:
            logger.error("Go: Failed")
    
    # Test with Python engine
    start_time = time.time()
    python_stats = await engine.python_engine.get_system_stats()
    python_time = time.time() - start_time
    
    if python_stats:
        logger.info(f"Python: {python_time:.3f}s")
        logger.info(f"  CPU: {python_stats.cpu.get('count', 0)} cores")
        logger.info(f"  Memory: {python_stats.memory.get('total', 0) / (1024**3):.1f} GB total")
        logger.info(f"  Disks: {len(python_stats.disk)} partitions")
    else:
        logger.error("Python: Failed")
    
    # Test with hybrid engine
    start_time = time.time()
    hybrid_stats = await engine.get_system_stats()
    hybrid_time = time.time() - start_time
    
    if hybrid_stats:
        logger.info(f"Hybrid: {hybrid_time:.3f}s")
    else:
        logger.error("Hybrid: Failed")
    
    logger.info("")


async def benchmark_compression(engine: HybridPerformanceEngine, source_files: list, temp_dir: str):
    """Benchmark compression operations."""
    logger.info("=== Compression Benchmark ===")
    
    # Use the first file for compression testing
    source_file = source_files[0]
    source_size = Path(source_file).stat().st_size
    
    logger.info(f"Compressing file: {Path(source_file).name} ({source_size} bytes)")
    
    # Test with Go engine (if available)
    if engine.go_engine.is_available():
        go_dest = Path(temp_dir) / "compressed_go.gz"
        start_time = time.time()
        go_result = await engine.go_engine.compress_file(source_file, str(go_dest))
        go_time = time.time() - start_time
        
        if go_result and go_result.get("success"):
            compressed_size = go_result.get("compressed_size", 0)
            ratio = go_result.get("compression_ratio", 0)
            logger.info(f"Go: {go_time:.3f}s, {compressed_size} bytes, {ratio:.2%} ratio")
        else:
            logger.error("Go: Failed")
    
    # Test with Python engine
    python_dest = Path(temp_dir) / "compressed_python.gz"
    start_time = time.time()
    python_result = await engine.python_engine.compress_file(source_file, str(python_dest))
    python_time = time.time() - start_time
    
    if python_result and python_result.get("success"):
        compressed_size = python_result.get("compressed_size", 0)
        ratio = python_result.get("compression_ratio", 0)
        logger.info(f"Python: {python_time:.3f}s, {compressed_size} bytes, {ratio:.2%} ratio")
    else:
        logger.error("Python: Failed")
    
    # Test with hybrid engine
    hybrid_dest = Path(temp_dir) / "compressed_hybrid.gz"
    start_time = time.time()
    hybrid_result = await engine.compress_file(source_file, str(hybrid_dest))
    hybrid_time = time.time() - start_time
    
    if hybrid_result and hybrid_result.get("success"):
        compressed_size = hybrid_result.get("compressed_size", 0)
        ratio = hybrid_result.get("compression_ratio", 0)
        logger.info(f"Hybrid: {hybrid_time:.3f}s, {compressed_size} bytes, {ratio:.2%} ratio")
    else:
        logger.error("Hybrid: Failed")
    
    logger.info("")


async def run_comprehensive_comparison(engine: HybridPerformanceEngine, temp_dir: str):
    """Run comprehensive performance comparison using built-in comparison method."""
    logger.info("=== Comprehensive Performance Comparison ===")
    
    if not engine.go_engine.is_available():
        logger.warning("Go engine not available, skipping comprehensive comparison")
        return
    
    # Create a test file for comparison
    test_file = Path(temp_dir) / "comparison_test.txt"
    test_content = "Performance comparison test content.\n" * 10000
    test_file.write_text(test_content)
    
    # Compare file copy performance
    dest_file = Path(temp_dir) / "comparison_dest.txt"
    logger.info("Comparing file copy performance...")
    
    copy_comparison = await engine.compare_performance(
        "copy",
        str(test_file),
        str(dest_file),
        iterations=3
    )
    
    if "comparison" in copy_comparison and copy_comparison["comparison"]:
        comp = copy_comparison["comparison"]
        logger.info(f"Copy Performance:")
        logger.info(f"  Go average: {comp.get('go_avg_ms', 0):.2f}ms")
        logger.info(f"  Python average: {comp.get('python_avg_ms', 0):.2f}ms")
        logger.info(f"  Speedup: {comp.get('speedup', 0):.2f}x")
        logger.info(f"  Go is faster: {comp.get('go_faster', False)}")
        logger.info(f"  Performance improvement: {comp.get('performance_improvement', 0):.1f}%")
    
    # Clean up
    if dest_file.exists():
        dest_file.unlink()
    
    # Compare checksum performance
    logger.info("Comparing checksum performance...")
    
    checksum_comparison = await engine.compare_performance(
        "checksum",
        [str(test_file)],
        iterations=3
    )
    
    if "comparison" in checksum_comparison and checksum_comparison["comparison"]:
        comp = checksum_comparison["comparison"]
        logger.info(f"Checksum Performance:")
        logger.info(f"  Go average: {comp.get('go_avg_ms', 0):.2f}ms")
        logger.info(f"  Python average: {comp.get('python_avg_ms', 0):.2f}ms")
        logger.info(f"  Speedup: {comp.get('speedup', 0):.2f}x")
        logger.info(f"  Go is faster: {comp.get('go_faster', False)}")
        logger.info(f"  Performance improvement: {comp.get('performance_improvement', 0):.1f}%")
    
    logger.info("")


async def main():
    """Main demo function."""
    logger.info("Starting Performance Comparison Demo")
    logger.info("=" * 50)
    
    # Initialize hybrid engine
    engine = HybridPerformanceEngine()
    
    # Display engine status
    status = engine.get_engine_status()
    logger.info("Engine Status:")
    logger.info(f"  Go Engine: {'Available' if status['go_engine']['available'] else 'Not Available'}")
    if status['go_engine']['available']:
        logger.info(f"    Binary Path: {status['go_engine']['binary_path']}")
    logger.info(f"  Python Engine: {'Available' if status['python_engine']['available'] else 'Not Available'}")
    logger.info(f"  Preferred Engine: {status['preferred_engine']}")
    logger.info("")
    
    # Create temporary directory and test files
    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info(f"Using temporary directory: {temp_dir}")
        
        # Create test files
        logger.info("Creating test files...")
        test_files = await create_test_files(temp_dir, num_files=3, file_size_kb=512)
        logger.info("")
        
        # Run benchmarks
        await benchmark_file_copy(engine, test_files, temp_dir)
        await benchmark_checksum_calculation(engine, test_files)
        await benchmark_system_monitoring(engine)
        await benchmark_compression(engine, test_files, temp_dir)
        await run_comprehensive_comparison(engine, temp_dir)
    
    logger.info("Performance Comparison Demo completed!")


if __name__ == "__main__":
    asyncio.run(main())