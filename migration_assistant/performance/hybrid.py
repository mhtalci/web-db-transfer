"""
Hybrid Performance Engine - Combines Go and Python implementations with automatic fallback.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union

from .engine import GoPerformanceEngine, CopyResult, ChecksumResult, SystemStats
from .fallback import PythonFallbackEngine

logger = logging.getLogger(__name__)


class HybridPerformanceEngine:
    """
    Hybrid performance engine that uses Go for high-performance operations
    and falls back to Python implementations when Go is unavailable.
    
    This class automatically selects the best available implementation
    and provides performance comparison capabilities.
    """
    
    def __init__(self, go_binary_path: Optional[str] = None, prefer_go: bool = True):
        """
        Initialize the Hybrid Performance Engine.
        
        Args:
            go_binary_path: Path to the Go binary
            prefer_go: Whether to prefer Go implementation when available
        """
        self.go_engine = GoPerformanceEngine(go_binary_path)
        self.python_engine = PythonFallbackEngine()
        self.prefer_go = prefer_go
        
        # Log which engines are available
        if self.go_engine.is_available():
            logger.info(f"Go performance engine available at: {self.go_engine.get_binary_path()}")
        else:
            logger.warning("Go performance engine not available, using Python fallback")
        
        logger.info(f"Hybrid engine initialized - Go: {self.go_engine.is_available()}, Python: {self.python_engine.is_available()}")
    
    def _get_preferred_engine(self) -> Union[GoPerformanceEngine, PythonFallbackEngine]:
        """Get the preferred engine based on availability and settings."""
        if self.prefer_go and self.go_engine.is_available():
            return self.go_engine
        return self.python_engine
    
    def _get_fallback_engine(self) -> Union[GoPerformanceEngine, PythonFallbackEngine]:
        """Get the fallback engine."""
        if self.prefer_go and self.go_engine.is_available():
            return self.python_engine
        return self.go_engine if self.go_engine.is_available() else self.python_engine
    
    async def copy_file(self, source: str, destination: str, use_fallback_on_error: bool = True) -> Optional[CopyResult]:
        """
        Copy a file using the best available engine.
        
        Args:
            source: Source file path
            destination: Destination file path
            use_fallback_on_error: Whether to try fallback engine on error
            
        Returns:
            CopyResult with copy statistics or None if failed
        """
        engine = self._get_preferred_engine()
        engine_name = "Go" if isinstance(engine, GoPerformanceEngine) else "Python"
        
        logger.debug(f"Copying file using {engine_name} engine: {source} -> {destination}")
        
        try:
            result = await engine.copy_file(source, destination)
            if result and result.success:
                logger.debug(f"File copy successful using {engine_name} engine")
                return result
            
            if use_fallback_on_error:
                logger.warning(f"{engine_name} engine failed, trying fallback")
                fallback_engine = self._get_fallback_engine()
                fallback_name = "Go" if isinstance(fallback_engine, GoPerformanceEngine) else "Python"
                
                if fallback_engine != engine:  # Avoid infinite recursion
                    logger.debug(f"Using {fallback_name} fallback engine")
                    result = await fallback_engine.copy_file(source, destination)
                    if result and result.success:
                        logger.info(f"File copy successful using {fallback_name} fallback engine")
                        return result
            
            logger.error("File copy failed with all available engines")
            return None
            
        except Exception as e:
            logger.error(f"File copy failed with {engine_name} engine: {e}")
            
            if use_fallback_on_error:
                try:
                    fallback_engine = self._get_fallback_engine()
                    fallback_name = "Go" if isinstance(fallback_engine, GoPerformanceEngine) else "Python"
                    
                    if fallback_engine != engine:
                        logger.debug(f"Trying {fallback_name} fallback engine after exception")
                        result = await fallback_engine.copy_file(source, destination)
                        if result and result.success:
                            logger.info(f"File copy successful using {fallback_name} fallback engine after exception")
                            return result
                except Exception as fallback_error:
                    logger.error(f"Fallback engine also failed: {fallback_error}")
            
            return None
    
    async def calculate_checksums(self, files: List[str], use_fallback_on_error: bool = True) -> Optional[List[ChecksumResult]]:
        """
        Calculate checksums using the best available engine.
        
        Args:
            files: List of file paths
            use_fallback_on_error: Whether to try fallback engine on error
            
        Returns:
            List of ChecksumResult objects or None if failed
        """
        engine = self._get_preferred_engine()
        engine_name = "Go" if isinstance(engine, GoPerformanceEngine) else "Python"
        
        logger.debug(f"Calculating checksums using {engine_name} engine for {len(files)} files")
        
        try:
            result = await engine.calculate_checksums(files)
            if result:
                logger.debug(f"Checksum calculation successful using {engine_name} engine")
                return result
            
            if use_fallback_on_error:
                logger.warning(f"{engine_name} engine failed, trying fallback")
                fallback_engine = self._get_fallback_engine()
                fallback_name = "Go" if isinstance(fallback_engine, GoPerformanceEngine) else "Python"
                
                if fallback_engine != engine:
                    logger.debug(f"Using {fallback_name} fallback engine")
                    result = await fallback_engine.calculate_checksums(files)
                    if result:
                        logger.info(f"Checksum calculation successful using {fallback_name} fallback engine")
                        return result
            
            logger.error("Checksum calculation failed with all available engines")
            return None
            
        except Exception as e:
            logger.error(f"Checksum calculation failed with {engine_name} engine: {e}")
            
            if use_fallback_on_error:
                try:
                    fallback_engine = self._get_fallback_engine()
                    fallback_name = "Go" if isinstance(fallback_engine, GoPerformanceEngine) else "Python"
                    
                    if fallback_engine != engine:
                        logger.debug(f"Trying {fallback_name} fallback engine after exception")
                        result = await fallback_engine.calculate_checksums(files)
                        if result:
                            logger.info(f"Checksum calculation successful using {fallback_name} fallback engine after exception")
                            return result
                except Exception as fallback_error:
                    logger.error(f"Fallback engine also failed: {fallback_error}")
            
            return None
    
    async def compress_file(self, source: str, destination: str, use_fallback_on_error: bool = True) -> Optional[Dict[str, Any]]:
        """
        Compress a file using the best available engine.
        
        Args:
            source: Source file or directory path
            destination: Destination compressed file path
            use_fallback_on_error: Whether to try fallback engine on error
            
        Returns:
            Compression result dictionary or None if failed
        """
        engine = self._get_preferred_engine()
        engine_name = "Go" if isinstance(engine, GoPerformanceEngine) else "Python"
        
        logger.debug(f"Compressing file using {engine_name} engine: {source} -> {destination}")
        
        try:
            result = await engine.compress_file(source, destination)
            if result and result.get("success"):
                logger.debug(f"Compression successful using {engine_name} engine")
                return result
            
            if use_fallback_on_error:
                logger.warning(f"{engine_name} engine failed, trying fallback")
                fallback_engine = self._get_fallback_engine()
                fallback_name = "Go" if isinstance(fallback_engine, GoPerformanceEngine) else "Python"
                
                if fallback_engine != engine:
                    logger.debug(f"Using {fallback_name} fallback engine")
                    result = await fallback_engine.compress_file(source, destination)
                    if result and result.get("success"):
                        logger.info(f"Compression successful using {fallback_name} fallback engine")
                        return result
            
            logger.error("Compression failed with all available engines")
            return None
            
        except Exception as e:
            logger.error(f"Compression failed with {engine_name} engine: {e}")
            
            if use_fallback_on_error:
                try:
                    fallback_engine = self._get_fallback_engine()
                    fallback_name = "Go" if isinstance(fallback_engine, GoPerformanceEngine) else "Python"
                    
                    if fallback_engine != engine:
                        logger.debug(f"Trying {fallback_name} fallback engine after exception")
                        result = await fallback_engine.compress_file(source, destination)
                        if result and result.get("success"):
                            logger.info(f"Compression successful using {fallback_name} fallback engine after exception")
                            return result
                except Exception as fallback_error:
                    logger.error(f"Fallback engine also failed: {fallback_error}")
            
            return None
    
    async def get_system_stats(self, use_fallback_on_error: bool = True) -> Optional[SystemStats]:
        """
        Get system statistics using the best available engine.
        
        Args:
            use_fallback_on_error: Whether to try fallback engine on error
            
        Returns:
            SystemStats object or None if failed
        """
        engine = self._get_preferred_engine()
        engine_name = "Go" if isinstance(engine, GoPerformanceEngine) else "Python"
        
        logger.debug(f"Getting system stats using {engine_name} engine")
        
        try:
            result = await engine.get_system_stats()
            if result:
                logger.debug(f"System stats retrieved successfully using {engine_name} engine")
                return result
            
            if use_fallback_on_error:
                logger.warning(f"{engine_name} engine failed, trying fallback")
                fallback_engine = self._get_fallback_engine()
                fallback_name = "Go" if isinstance(fallback_engine, GoPerformanceEngine) else "Python"
                
                if fallback_engine != engine:
                    logger.debug(f"Using {fallback_name} fallback engine")
                    result = await fallback_engine.get_system_stats()
                    if result:
                        logger.info(f"System stats retrieved successfully using {fallback_name} fallback engine")
                        return result
            
            logger.error("System stats retrieval failed with all available engines")
            return None
            
        except Exception as e:
            logger.error(f"System stats retrieval failed with {engine_name} engine: {e}")
            
            if use_fallback_on_error:
                try:
                    fallback_engine = self._get_fallback_engine()
                    fallback_name = "Go" if isinstance(fallback_engine, GoPerformanceEngine) else "Python"
                    
                    if fallback_engine != engine:
                        logger.debug(f"Trying {fallback_name} fallback engine after exception")
                        result = await fallback_engine.get_system_stats()
                        if result:
                            logger.info(f"System stats retrieved successfully using {fallback_name} fallback engine after exception")
                            return result
                except Exception as fallback_error:
                    logger.error(f"Fallback engine also failed: {fallback_error}")
            
            return None
    
    async def transfer_files(self, source: str, destination: str, method: str = "concurrent", use_fallback_on_error: bool = True) -> Optional[Dict[str, Any]]:
        """
        Transfer files using the best available engine.
        
        Args:
            source: Source path or URL
            destination: Destination path
            method: Transfer method
            use_fallback_on_error: Whether to try fallback engine on error
            
        Returns:
            Transfer result dictionary or None if failed
        """
        engine = self._get_preferred_engine()
        engine_name = "Go" if isinstance(engine, GoPerformanceEngine) else "Python"
        
        logger.debug(f"Transferring files using {engine_name} engine: {source} -> {destination}")
        
        try:
            result = await engine.transfer_files(source, destination, method)
            if result and result.get("success"):
                logger.debug(f"File transfer successful using {engine_name} engine")
                return result
            
            if use_fallback_on_error:
                logger.warning(f"{engine_name} engine failed, trying fallback")
                fallback_engine = self._get_fallback_engine()
                fallback_name = "Go" if isinstance(fallback_engine, GoPerformanceEngine) else "Python"
                
                if fallback_engine != engine:
                    logger.debug(f"Using {fallback_name} fallback engine")
                    result = await fallback_engine.transfer_files(source, destination, method)
                    if result and result.get("success"):
                        logger.info(f"File transfer successful using {fallback_name} fallback engine")
                        return result
            
            logger.error("File transfer failed with all available engines")
            return None
            
        except Exception as e:
            logger.error(f"File transfer failed with {engine_name} engine: {e}")
            
            if use_fallback_on_error:
                try:
                    fallback_engine = self._get_fallback_engine()
                    fallback_name = "Go" if isinstance(fallback_engine, GoPerformanceEngine) else "Python"
                    
                    if fallback_engine != engine:
                        logger.debug(f"Trying {fallback_name} fallback engine after exception")
                        result = await fallback_engine.transfer_files(source, destination, method)
                        if result and result.get("success"):
                            logger.info(f"File transfer successful using {fallback_name} fallback engine after exception")
                            return result
                except Exception as fallback_error:
                    logger.error(f"Fallback engine also failed: {fallback_error}")
            
            return None
    
    async def compare_performance(self, operation: str, *args, **kwargs) -> Dict[str, Any]:
        """
        Compare performance between Go and Python implementations.
        
        Args:
            operation: Operation to compare (copy, checksum, compress, monitor)
            *args, **kwargs: Operation arguments
            
        Returns:
            Performance comparison results
        """
        if not self.go_engine.is_available():
            logger.warning("Go engine not available, cannot perform comparison")
            return {"error": "Go engine not available"}
        
        iterations = kwargs.pop('iterations', 3)
        results = {"go": [], "python": [], "comparison": {}}
        
        # Test Go implementation
        logger.info(f"Benchmarking Go implementation for {operation}")
        try:
            if hasattr(self.go_engine, 'benchmark_operation'):
                go_result = await self.go_engine.benchmark_operation(operation, *args, iterations=iterations, **kwargs)
                results["go"] = go_result
            else:
                # Manual benchmarking
                for i in range(iterations):
                    if operation == "copy":
                        result = await self.go_engine.copy_file(*args, **kwargs)
                    elif operation == "checksum":
                        result = await self.go_engine.calculate_checksums(*args, **kwargs)
                    elif operation == "compress":
                        result = await self.go_engine.compress_file(*args, **kwargs)
                    elif operation == "monitor":
                        result = await self.go_engine.get_system_stats()
                    
                    results["go"].append({"success": result is not None, "result": result})
        except Exception as e:
            logger.error(f"Go benchmarking failed: {e}")
            results["go"] = {"error": str(e)}
        
        # Test Python implementation
        logger.info(f"Benchmarking Python implementation for {operation}")
        try:
            for i in range(iterations):
                if operation == "copy":
                    result = await self.python_engine.copy_file(*args, **kwargs)
                elif operation == "checksum":
                    result = await self.python_engine.calculate_checksums(*args, **kwargs)
                elif operation == "compress":
                    result = await self.python_engine.compress_file(*args, **kwargs)
                elif operation == "monitor":
                    result = await self.python_engine.get_system_stats()
                
                results["python"].append({"success": result is not None, "result": result})
        except Exception as e:
            logger.error(f"Python benchmarking failed: {e}")
            results["python"] = {"error": str(e)}
        
        # Calculate comparison metrics
        if isinstance(results["go"], list) and isinstance(results["python"], list):
            go_times = []
            python_times = []
            
            for go_result in results["go"]:
                if go_result["success"] and go_result["result"]:
                    if hasattr(go_result["result"], 'duration_ms'):
                        go_times.append(go_result["result"].duration_ms)
            
            for python_result in results["python"]:
                if python_result["success"] and python_result["result"]:
                    if hasattr(python_result["result"], 'duration_ms'):
                        python_times.append(python_result["result"].duration_ms)
            
            if go_times and python_times:
                avg_go = sum(go_times) / len(go_times)
                avg_python = sum(python_times) / len(python_times)
                
                results["comparison"] = {
                    "go_avg_ms": avg_go,
                    "python_avg_ms": avg_python,
                    "speedup": avg_python / avg_go if avg_go > 0 else 0,
                    "go_faster": avg_go < avg_python,
                    "performance_improvement": ((avg_python - avg_go) / avg_python * 100) if avg_python > 0 else 0
                }
        
        return results
    
    def get_engine_status(self) -> Dict[str, Any]:
        """Get status of both engines."""
        return {
            "go_engine": {
                "available": self.go_engine.is_available(),
                "binary_path": self.go_engine.get_binary_path()
            },
            "python_engine": {
                "available": self.python_engine.is_available()
            },
            "preferred_engine": "Go" if (self.prefer_go and self.go_engine.is_available()) else "Python"
        }
    
    def set_preference(self, prefer_go: bool):
        """Set engine preference."""
        self.prefer_go = prefer_go
        logger.info(f"Engine preference set to: {'Go' if prefer_go else 'Python'}")
    
    def is_available(self) -> bool:
        """Check if at least one engine is available."""
        return self.go_engine.is_available() or self.python_engine.is_available()