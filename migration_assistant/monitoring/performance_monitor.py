"""
Performance monitoring system for migration operations.

This module provides performance metrics collection, resource monitoring,
and transfer rate analysis for migration operations.
"""

import asyncio
import psutil
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from collections import deque
from enum import Enum

from pydantic import BaseModel


class MetricType(str, Enum):
    """Types of performance metrics."""
    TRANSFER_RATE = "transfer_rate"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    DISK_IO = "disk_io"
    NETWORK_IO = "network_io"
    DATABASE_OPERATIONS = "database_operations"
    FILE_OPERATIONS = "file_operations"


class ResourceType(str, Enum):
    """Types of system resources."""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"


@dataclass
class PerformanceMetric:
    """Individual performance metric data point."""
    timestamp: datetime
    metric_type: MetricType
    value: float
    unit: str
    session_id: Optional[str] = None
    step_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceUsage:
    """System resource usage snapshot."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_read_mb_per_sec: float
    disk_write_mb_per_sec: float
    network_sent_mb_per_sec: float
    network_recv_mb_per_sec: float
    active_connections: int
    process_count: int


@dataclass
class TransferMetrics:
    """File transfer performance metrics."""
    session_id: str
    step_id: Optional[str]
    start_time: datetime
    current_time: datetime
    bytes_transferred: int
    total_bytes: int
    files_transferred: int
    total_files: int
    current_rate_mbps: float
    average_rate_mbps: float
    peak_rate_mbps: float
    efficiency_percent: float  # actual vs theoretical max
    errors_count: int
    retries_count: int


@dataclass
class DatabaseMetrics:
    """Database operation performance metrics."""
    session_id: str
    step_id: Optional[str]
    operation_type: str  # dump, restore, migrate, etc.
    start_time: datetime
    current_time: datetime
    records_processed: int
    total_records: int
    current_rate_rps: float  # records per second
    average_rate_rps: float
    connection_pool_size: int
    active_connections: int
    query_time_avg_ms: float
    errors_count: int


class PerformanceMonitor:
    """
    Performance monitoring system for migration operations.
    
    Collects and analyzes performance metrics including transfer rates,
    resource usage, and operation efficiency.
    """
    
    def __init__(
        self,
        collection_interval: float = 1.0,
        max_history_size: int = 1000
    ):
        """
        Initialize performance monitor.
        
        Args:
            collection_interval: Interval between metric collections (seconds)
            max_history_size: Maximum number of metrics to keep in memory
        """
        self.collection_interval = collection_interval
        self.max_history_size = max_history_size
        
        # Metric storage
        self._metrics: Dict[str, deque] = {}
        self._resource_history: deque = deque(maxlen=max_history_size)
        self._transfer_metrics: Dict[str, TransferMetrics] = {}
        self._database_metrics: Dict[str, DatabaseMetrics] = {}
        
        # Monitoring state
        self._monitoring_active = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable[[PerformanceMetric], None]] = []
        
        # Baseline measurements
        self._baseline_cpu = 0.0
        self._baseline_memory = 0.0
        self._baseline_disk_io = {"read": 0.0, "write": 0.0}
        self._baseline_network_io = {"sent": 0.0, "recv": 0.0}
        
        # Previous measurements for rate calculations
        self._prev_disk_io = None
        self._prev_network_io = None
        self._prev_timestamp = None
    
    def add_callback(self, callback: Callable[[PerformanceMetric], None]):
        """Add a performance metric callback."""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[PerformanceMetric], None]):
        """Remove a performance metric callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    async def start_monitoring(self, session_id: Optional[str] = None):
        """
        Start performance monitoring.
        
        Args:
            session_id: Optional session ID for context
        """
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        
        # Collect baseline measurements
        await self._collect_baseline()
        
        # Start monitoring task
        self._monitoring_task = asyncio.create_task(
            self._monitoring_loop(session_id)
        )
    
    async def stop_monitoring(self):
        """Stop performance monitoring."""
        self._monitoring_active = False
        
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
    
    def start_transfer_tracking(
        self,
        session_id: str,
        step_id: Optional[str] = None,
        total_bytes: int = 0,
        total_files: int = 0
    ):
        """
        Start tracking file transfer performance.
        
        Args:
            session_id: Migration session ID
            step_id: Optional step ID
            total_bytes: Total bytes to transfer
            total_files: Total files to transfer
        """
        tracking_key = f"{session_id}:{step_id or 'transfer'}"
        
        self._transfer_metrics[tracking_key] = TransferMetrics(
            session_id=session_id,
            step_id=step_id,
            start_time=datetime.utcnow(),
            current_time=datetime.utcnow(),
            bytes_transferred=0,
            total_bytes=total_bytes,
            files_transferred=0,
            total_files=total_files,
            current_rate_mbps=0.0,
            average_rate_mbps=0.0,
            peak_rate_mbps=0.0,
            efficiency_percent=0.0,
            errors_count=0,
            retries_count=0
        )
    
    def update_transfer_progress(
        self,
        session_id: str,
        bytes_transferred: int,
        files_transferred: int,
        step_id: Optional[str] = None,
        errors: int = 0,
        retries: int = 0
    ):
        """
        Update file transfer progress.
        
        Args:
            session_id: Migration session ID
            bytes_transferred: Bytes transferred so far
            files_transferred: Files transferred so far
            step_id: Optional step ID
            errors: Number of errors encountered
            retries: Number of retries performed
        """
        tracking_key = f"{session_id}:{step_id or 'transfer'}"
        
        if tracking_key not in self._transfer_metrics:
            return
        
        metrics = self._transfer_metrics[tracking_key]
        current_time = datetime.utcnow()
        
        # Update basic metrics
        metrics.current_time = current_time
        metrics.bytes_transferred = bytes_transferred
        metrics.files_transferred = files_transferred
        metrics.errors_count = errors
        metrics.retries_count = retries
        
        # Calculate rates
        elapsed_seconds = (current_time - metrics.start_time).total_seconds()
        if elapsed_seconds > 0:
            # Average rate in MB/s
            metrics.average_rate_mbps = (bytes_transferred / (1024 * 1024)) / elapsed_seconds
            
            # Current rate (based on recent progress)
            # This would need more sophisticated tracking for accurate current rate
            metrics.current_rate_mbps = metrics.average_rate_mbps
            
            # Update peak rate
            if metrics.current_rate_mbps > metrics.peak_rate_mbps:
                metrics.peak_rate_mbps = metrics.current_rate_mbps
        
        # Calculate efficiency (placeholder - would need network capacity info)
        theoretical_max_mbps = 100.0  # Assume 100 MB/s theoretical max
        metrics.efficiency_percent = min(
            (metrics.current_rate_mbps / theoretical_max_mbps) * 100, 100.0
        )
        
        # Emit metric
        self._emit_metric(PerformanceMetric(
            timestamp=current_time,
            metric_type=MetricType.TRANSFER_RATE,
            value=metrics.current_rate_mbps,
            unit="MB/s",
            session_id=session_id,
            step_id=step_id,
            metadata={
                "bytes_transferred": bytes_transferred,
                "files_transferred": files_transferred,
                "efficiency_percent": metrics.efficiency_percent
            }
        ))
    
    def start_database_tracking(
        self,
        session_id: str,
        operation_type: str,
        step_id: Optional[str] = None,
        total_records: int = 0
    ):
        """
        Start tracking database operation performance.
        
        Args:
            session_id: Migration session ID
            operation_type: Type of database operation
            step_id: Optional step ID
            total_records: Total records to process
        """
        tracking_key = f"{session_id}:{step_id or 'database'}"
        
        self._database_metrics[tracking_key] = DatabaseMetrics(
            session_id=session_id,
            step_id=step_id,
            operation_type=operation_type,
            start_time=datetime.utcnow(),
            current_time=datetime.utcnow(),
            records_processed=0,
            total_records=total_records,
            current_rate_rps=0.0,
            average_rate_rps=0.0,
            connection_pool_size=0,
            active_connections=0,
            query_time_avg_ms=0.0,
            errors_count=0
        )
    
    def update_database_progress(
        self,
        session_id: str,
        records_processed: int,
        step_id: Optional[str] = None,
        connection_info: Optional[Dict[str, Any]] = None,
        query_time_ms: Optional[float] = None,
        errors: int = 0
    ):
        """
        Update database operation progress.
        
        Args:
            session_id: Migration session ID
            records_processed: Records processed so far
            step_id: Optional step ID
            connection_info: Connection pool information
            query_time_ms: Average query time in milliseconds
            errors: Number of errors encountered
        """
        tracking_key = f"{session_id}:{step_id or 'database'}"
        
        if tracking_key not in self._database_metrics:
            return
        
        metrics = self._database_metrics[tracking_key]
        current_time = datetime.utcnow()
        
        # Update basic metrics
        metrics.current_time = current_time
        metrics.records_processed = records_processed
        metrics.errors_count = errors
        
        if connection_info:
            metrics.connection_pool_size = connection_info.get("pool_size", 0)
            metrics.active_connections = connection_info.get("active_connections", 0)
        
        if query_time_ms is not None:
            metrics.query_time_avg_ms = query_time_ms
        
        # Calculate rates
        elapsed_seconds = (current_time - metrics.start_time).total_seconds()
        if elapsed_seconds > 0:
            metrics.average_rate_rps = records_processed / elapsed_seconds
            metrics.current_rate_rps = metrics.average_rate_rps  # Simplified
        
        # Emit metric
        self._emit_metric(PerformanceMetric(
            timestamp=current_time,
            metric_type=MetricType.DATABASE_OPERATIONS,
            value=metrics.current_rate_rps,
            unit="records/s",
            session_id=session_id,
            step_id=step_id,
            metadata={
                "records_processed": records_processed,
                "operation_type": metrics.operation_type,
                "query_time_avg_ms": metrics.query_time_avg_ms,
                "active_connections": metrics.active_connections
            }
        ))
    
    def get_transfer_metrics(
        self,
        session_id: str,
        step_id: Optional[str] = None
    ) -> Optional[TransferMetrics]:
        """Get current transfer metrics."""
        tracking_key = f"{session_id}:{step_id or 'transfer'}"
        return self._transfer_metrics.get(tracking_key)
    
    def get_database_metrics(
        self,
        session_id: str,
        step_id: Optional[str] = None
    ) -> Optional[DatabaseMetrics]:
        """Get current database metrics."""
        tracking_key = f"{session_id}:{step_id or 'database'}"
        return self._database_metrics.get(tracking_key)
    
    def get_resource_usage_history(
        self,
        minutes: int = 10
    ) -> List[ResourceUsage]:
        """
        Get resource usage history for the specified time period.
        
        Args:
            minutes: Number of minutes of history to return
            
        Returns:
            List of resource usage snapshots
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        
        return [
            usage for usage in self._resource_history
            if usage.timestamp >= cutoff_time
        ]
    
    def get_performance_summary(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Get performance summary for a session.
        
        Args:
            session_id: Migration session ID
            
        Returns:
            Performance summary dictionary
        """
        summary = {
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "transfer_metrics": {},
            "database_metrics": {},
            "resource_usage": None
        }
        
        # Collect transfer metrics
        for key, metrics in self._transfer_metrics.items():
            if metrics.session_id == session_id:
                summary["transfer_metrics"][key] = {
                    "step_id": metrics.step_id,
                    "bytes_transferred": metrics.bytes_transferred,
                    "total_bytes": metrics.total_bytes,
                    "files_transferred": metrics.files_transferred,
                    "total_files": metrics.total_files,
                    "average_rate_mbps": metrics.average_rate_mbps,
                    "peak_rate_mbps": metrics.peak_rate_mbps,
                    "efficiency_percent": metrics.efficiency_percent,
                    "errors_count": metrics.errors_count
                }
        
        # Collect database metrics
        for key, metrics in self._database_metrics.items():
            if metrics.session_id == session_id:
                summary["database_metrics"][key] = {
                    "step_id": metrics.step_id,
                    "operation_type": metrics.operation_type,
                    "records_processed": metrics.records_processed,
                    "total_records": metrics.total_records,
                    "average_rate_rps": metrics.average_rate_rps,
                    "query_time_avg_ms": metrics.query_time_avg_ms,
                    "active_connections": metrics.active_connections,
                    "errors_count": metrics.errors_count
                }
        
        # Get current resource usage
        if self._resource_history:
            latest_usage = self._resource_history[-1]
            summary["resource_usage"] = {
                "cpu_percent": latest_usage.cpu_percent,
                "memory_percent": latest_usage.memory_percent,
                "memory_used_mb": latest_usage.memory_used_mb,
                "disk_read_mb_per_sec": latest_usage.disk_read_mb_per_sec,
                "disk_write_mb_per_sec": latest_usage.disk_write_mb_per_sec,
                "network_sent_mb_per_sec": latest_usage.network_sent_mb_per_sec,
                "network_recv_mb_per_sec": latest_usage.network_recv_mb_per_sec
            }
        
        return summary
    
    def cleanup_session(self, session_id: str):
        """Clean up performance tracking data for a session."""
        # Remove transfer metrics
        keys_to_remove = [
            key for key in self._transfer_metrics.keys()
            if self._transfer_metrics[key].session_id == session_id
        ]
        for key in keys_to_remove:
            del self._transfer_metrics[key]
        
        # Remove database metrics
        keys_to_remove = [
            key for key in self._database_metrics.keys()
            if self._database_metrics[key].session_id == session_id
        ]
        for key in keys_to_remove:
            del self._database_metrics[key]
    
    async def _collect_baseline(self):
        """Collect baseline system measurements."""
        try:
            self._baseline_cpu = psutil.cpu_percent(interval=1)
            
            memory = psutil.virtual_memory()
            self._baseline_memory = memory.percent
            
            disk_io = psutil.disk_io_counters()
            if disk_io:
                self._baseline_disk_io = {
                    "read": disk_io.read_bytes,
                    "write": disk_io.write_bytes
                }
            
            network_io = psutil.net_io_counters()
            if network_io:
                self._baseline_network_io = {
                    "sent": network_io.bytes_sent,
                    "recv": network_io.bytes_recv
                }
        except Exception as e:
            print(f"Error collecting baseline metrics: {e}")
    
    async def _monitoring_loop(self, session_id: Optional[str]):
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                await self._collect_system_metrics(session_id)
                await asyncio.sleep(self.collection_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.collection_interval)
    
    async def _collect_system_metrics(self, session_id: Optional[str]):
        """Collect system performance metrics."""
        try:
            current_time = datetime.utcnow()
            
            # CPU usage
            cpu_percent = psutil.cpu_percent()
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk I/O
            disk_io = psutil.disk_io_counters()
            disk_read_rate = 0.0
            disk_write_rate = 0.0
            
            if disk_io and self._prev_disk_io and self._prev_timestamp:
                time_delta = (current_time - self._prev_timestamp).total_seconds()
                if time_delta > 0:
                    read_delta = disk_io.read_bytes - self._prev_disk_io["read"]
                    write_delta = disk_io.write_bytes - self._prev_disk_io["write"]
                    disk_read_rate = (read_delta / (1024 * 1024)) / time_delta  # MB/s
                    disk_write_rate = (write_delta / (1024 * 1024)) / time_delta  # MB/s
            
            # Network I/O
            network_io = psutil.net_io_counters()
            network_sent_rate = 0.0
            network_recv_rate = 0.0
            
            if network_io and self._prev_network_io and self._prev_timestamp:
                time_delta = (current_time - self._prev_timestamp).total_seconds()
                if time_delta > 0:
                    sent_delta = network_io.bytes_sent - self._prev_network_io["sent"]
                    recv_delta = network_io.bytes_recv - self._prev_network_io["recv"]
                    network_sent_rate = (sent_delta / (1024 * 1024)) / time_delta  # MB/s
                    network_recv_rate = (recv_delta / (1024 * 1024)) / time_delta  # MB/s
            
            # Connection count (approximate)
            active_connections = len(psutil.net_connections())
            
            # Process count
            process_count = len(psutil.pids())
            
            # Create resource usage snapshot
            resource_usage = ResourceUsage(
                timestamp=current_time,
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / (1024 * 1024),
                memory_available_mb=memory.available / (1024 * 1024),
                disk_read_mb_per_sec=disk_read_rate,
                disk_write_mb_per_sec=disk_write_rate,
                network_sent_mb_per_sec=network_sent_rate,
                network_recv_mb_per_sec=network_recv_rate,
                active_connections=active_connections,
                process_count=process_count
            )
            
            self._resource_history.append(resource_usage)
            
            # Emit individual metrics
            metrics_to_emit = [
                PerformanceMetric(
                    timestamp=current_time,
                    metric_type=MetricType.CPU_USAGE,
                    value=cpu_percent,
                    unit="percent",
                    session_id=session_id
                ),
                PerformanceMetric(
                    timestamp=current_time,
                    metric_type=MetricType.MEMORY_USAGE,
                    value=memory.percent,
                    unit="percent",
                    session_id=session_id,
                    metadata={"used_mb": memory.used / (1024 * 1024)}
                ),
                PerformanceMetric(
                    timestamp=current_time,
                    metric_type=MetricType.DISK_IO,
                    value=disk_read_rate + disk_write_rate,
                    unit="MB/s",
                    session_id=session_id,
                    metadata={
                        "read_rate": disk_read_rate,
                        "write_rate": disk_write_rate
                    }
                ),
                PerformanceMetric(
                    timestamp=current_time,
                    metric_type=MetricType.NETWORK_IO,
                    value=network_sent_rate + network_recv_rate,
                    unit="MB/s",
                    session_id=session_id,
                    metadata={
                        "sent_rate": network_sent_rate,
                        "recv_rate": network_recv_rate
                    }
                )
            ]
            
            for metric in metrics_to_emit:
                self._emit_metric(metric)
            
            # Update previous values for rate calculations
            if disk_io:
                self._prev_disk_io = {
                    "read": disk_io.read_bytes,
                    "write": disk_io.write_bytes
                }
            
            if network_io:
                self._prev_network_io = {
                    "sent": network_io.bytes_sent,
                    "recv": network_io.bytes_recv
                }
            
            self._prev_timestamp = current_time
            
        except Exception as e:
            print(f"Error collecting system metrics: {e}")
    
    def _emit_metric(self, metric: PerformanceMetric):
        """Emit performance metric to callbacks."""
        for callback in self._callbacks:
            try:
                callback(metric)
            except Exception as e:
                print(f"Performance callback error: {e}")