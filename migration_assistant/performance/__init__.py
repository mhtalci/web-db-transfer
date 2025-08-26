"""
Performance module for high-speed operations using Go binary.

This module provides Python wrappers for Go-based high-performance operations
including file operations, checksums, compression, and system monitoring.
"""

from .engine import GoPerformanceEngine
from .fallback import PythonFallbackEngine
from .hybrid import HybridPerformanceEngine

__all__ = [
    'GoPerformanceEngine',
    'PythonFallbackEngine', 
    'HybridPerformanceEngine'
]