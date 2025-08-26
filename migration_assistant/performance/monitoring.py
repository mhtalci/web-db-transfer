"""Advanced resource monitoring with psutil integration."""

import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import threading
from collections import deque, defaultdict

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class MetricType(Enum):
    """Types of metrics."""
    GAUGE = "gauge"  # Point-in-time value
    COUNTER = "counter"  # Monotonically increasing
    HISTOGRAM = "histogram"  # Distribution of values
    RATE = "rate"  # Rate of change

@dataclass
class SystemMetrics:
    """System-wide metrics."""
    timestamp: float
    cpu_percent: float
    cpu_count: int
    cpu_freq: Optional[Dict[str, float]]
    memory_total: int
    memory_available: int
    memory_percent: float
    memory_used: int
    memory_free: int
    swap_total: int
    swap_used: int
    swap_percent: float
    disk_usage: Dict[str, Dict[str, Union[int, float]]]
    network_io: Dict[str, int]
    boot_time: float
    load_avg: Optional[List[float]]
    process_count: int

@dataclass
class ProcessMetrics:
    """Process-specific metrics."""
    timestamp: float
    pid: int
    name: str
    status: str
    cpu_percent: float
    memory_percent: float
    memory_rss: int
    memory_vms: int
    num_threads: int
    num_fds: Optional[int]
    io_read_count: Optional[int]
    io_write_count: Optional[int]
    io_read_bytes: Optional[int]
    io_write_bytes: Optional[int]
    create_time: float

@dataclass
class Alert:
    """System alert."""
    timestamp: float
    level: AlertLevel
    metric: str
    value: float
    threshold: float
    message: str
    resolved: bool = False
    resolved_at: Optional[float] = None

@dataclass
class Threshold:
    """Metric threshold configuration."""
    metric: str
    warning_value: Optional[float] = None
    critical_value: Optional[float] = None
    comparison: str = "greater"  # "greater", "less", "equal"
    duration: float = 0.0  # Seconds threshold must be exceeded
    enabled: bool = True

class MetricCollector:
    """Collects system and process metrics."""
    
    def __init__(self):
        """Initialize metric collector."""
        self.enabled = PSUTIL_AVAILABLE
        if not self.enabled:
            logger.warning("psutil not available, metrics collection will be limited")
    
    def collect_system_metrics(self) -> Optional[SystemMetrics]:
        """Collect system-wide metrics."""
        if not self.enabled:
            return None
        
        try:
            timestamp = time.time()
            
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            cpu_freq = None
            try:
                freq = psutil.cpu_freq()
                if freq:
                    cpu_freq = {
                        'current': freq.current,
                        'min': freq.min,
                        'max': freq.max
                    }
            except (AttributeError, OSError):
                pass
            
            # Memory metrics
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Disk usage for all mounted filesystems
            disk_usage = {}
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_usage[partition.mountpoint] = {
                        'total': usage.total,
                        'used': usage.used,
                        'free': usage.free,
                        'percent': usage.percent
                    }
                except (PermissionError, OSError):
                    continue
            
            # Network I/O
            network_io = {}
            try:
                net_io = psutil.net_io_counters()
                if net_io:
                    network_io = {
                        'bytes_sent': net_io.bytes_sent,
                        'bytes_recv': net_io.bytes_recv,
                        'packets_sent': net_io.packets_sent,
                        'packets_recv': net_io.packets_recv,
                        'errin': net_io.errin,
                        'errout': net_io.errout,
                        'dropin': net_io.dropin,
                        'dropout': net_io.dropout
                    }
            except AttributeError:
                pass
            
            # System info
            boot_time = psutil.boot_time()
            process_count = len(psutil.pids())
            
            # Load average (Unix-like systems only)
            load_avg = None
            try:
                load_avg = list(psutil.getloadavg())
            except (AttributeError, OSError):
                pass
            
            return SystemMetrics(
                timestamp=timestamp,
                cpu_percent=cpu_percent,
                cpu_count=cpu_count,
                cpu_freq=cpu_freq,
                memory_total=memory.total,
                memory_available=memory.available,
                memory_percent=memory.percent,
                memory_used=memory.used,
                memory_free=memory.free,
                swap_total=swap.total,
                swap_used=swap.used,
                swap_percent=swap.percent,
                disk_usage=disk_usage,
                network_io=network_io,
                boot_time=boot_time,
                load_avg=load_avg,
                process_count=process_count
            )
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return None
    
    def collect_process_metrics(self, pid: Optional[int] = None) -> Optional[ProcessMetrics]:
        """Collect metrics for a specific process.
        
        Args:
            pid: Process ID (current process if None)
            
        Returns:
            ProcessMetrics or None if failed
        """
        if not self.enabled:
            return None
        
        try:
            process = psutil.Process(pid)
            timestamp = time.time()
            
            # Basic process info
            name = process.name()
            status = process.status()
            create_time = process.create_time()
            
            # CPU and memory
            cpu_percent = process.cpu_percent()
            memory_percent = process.memory_percent()
            memory_info = process.memory_info()
            
            # Thread count
            num_threads = process.num_threads()
            
            # File descriptors (Unix-like systems)
            num_fds = None
            try:
                num_fds = process.num_fds()
            except (AttributeError, OSError):
                pass
            
            # I/O counters
            io_read_count = None
            io_write_count = None
            io_read_bytes = None
            io_write_bytes = None
            try:
                io_counters = process.io_counters()
                io_read_count = io_counters.read_count
                io_write_count = io_counters.write_count
                io_read_bytes = io_counters.read_bytes
                io_write_bytes = io_counters.write_bytes
            except (AttributeError, OSError):
                pass
            
            return ProcessMetrics(
                timestamp=timestamp,
                pid=process.pid,
                name=name,
                status=status,
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_rss=memory_info.rss,
                memory_vms=memory_info.vms,
                num_threads=num_threads,
                num_fds=num_fds,
                io_read_count=io_read_count,
                io_write_count=io_write_count,
                io_read_bytes=io_read_bytes,
                io_write_bytes=io_write_bytes,
                create_time=create_time
            )
            
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception) as e:
            logger.error(f"Failed to collect process metrics for PID {pid}: {e}")
            return None
    
    def collect_top_processes(self, limit: int = 10, sort_by: str = 'cpu_percent') -> List[ProcessMetrics]:
        """Collect metrics for top processes.
        
        Args:
            limit: Maximum number of processes to return
            sort_by: Sort criteria ('cpu_percent', 'memory_percent', 'memory_rss')
            
        Returns:
            List of ProcessMetrics sorted by specified criteria
        """
        if not self.enabled:
            return []
        
        try:
            processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    metrics = self.collect_process_metrics(proc.info['pid'])
                    if metrics:
                        processes.append(metrics)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Sort processes
            reverse = True  # Higher values first for most metrics
            if sort_by == 'name':
                reverse = False
            
            processes.sort(key=lambda p: getattr(p, sort_by, 0), reverse=reverse)
            
            return processes[:limit]
            
        except Exception as e:
            logger.error(f"Failed to collect top processes: {e}")
            return []

class ResourceMonitor:
    """Advanced resource monitoring with alerting and historical data."""
    
    def __init__(
        self,
        collection_interval: float = 30.0,
        history_size: int = 1000,
        enable_alerts: bool = True
    ):
        """Initialize resource monitor.
        
        Args:
            collection_interval: Seconds between metric collections
            history_size: Maximum number of historical metrics to keep
            enable_alerts: Whether to enable alerting
        """
        self.collection_interval = collection_interval
        self.history_size = history_size
        self.enable_alerts = enable_alerts
        
        self.collector = MetricCollector()
        self.system_metrics: deque = deque(maxlen=history_size)
        self.process_metrics: Dict[int, deque] = defaultdict(lambda: deque(maxlen=history_size))
        self.alerts: List[Alert] = []
        self.thresholds: List[Threshold] = []
        
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
        # Default thresholds
        self._setup_default_thresholds()
    
    def _setup_default_thresholds(self):
        """Setup default monitoring thresholds."""
        self.thresholds = [
            Threshold("cpu_percent", warning_value=80.0, critical_value=95.0),
            Threshold("memory_percent", warning_value=85.0, critical_value=95.0),
            Threshold("swap_percent", warning_value=50.0, critical_value=80.0),
            Threshold("disk_percent", warning_value=85.0, critical_value=95.0),
        ]
    
    async def start_monitoring(self):
        """Start resource monitoring."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Started resource monitoring with {self.collection_interval}s interval")
    
    async def stop_monitoring(self):
        """Stop resource monitoring."""
        self._monitoring = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped resource monitoring")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._monitoring:
            try:
                # Collect system metrics
                system_metrics = self.collector.collect_system_metrics()
                if system_metrics:
                    async with self._lock:
                        self.system_metrics.append(system_metrics)
                    
                    # Check thresholds
                    if self.enable_alerts:
                        await self._check_thresholds(system_metrics)
                
                # Collect process metrics for current process
                process_metrics = self.collector.collect_process_metrics()
                if process_metrics:
                    async with self._lock:
                        self.process_metrics[process_metrics.pid].append(process_metrics)
                
                await asyncio.sleep(self.collection_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.collection_interval)
    
    async def _check_thresholds(self, metrics: SystemMetrics):
        """Check metrics against configured thresholds."""
        current_time = time.time()
        
        for threshold in self.thresholds:
            if not threshold.enabled:
                continue
            
            value = self._get_metric_value(metrics, threshold.metric)
            if value is None:
                continue
            
            # Check warning threshold
            if (threshold.warning_value is not None and
                self._compare_value(value, threshold.warning_value, threshold.comparison)):
                
                await self._create_alert(
                    AlertLevel.WARNING,
                    threshold.metric,
                    value,
                    threshold.warning_value,
                    f"{threshold.metric} is {value:.1f}% (warning threshold: {threshold.warning_value:.1f}%)"
                )
            
            # Check critical threshold
            if (threshold.critical_value is not None and
                self._compare_value(value, threshold.critical_value, threshold.comparison)):
                
                await self._create_alert(
                    AlertLevel.CRITICAL,
                    threshold.metric,
                    value,
                    threshold.critical_value,
                    f"{threshold.metric} is {value:.1f}% (critical threshold: {threshold.critical_value:.1f}%)"
                )
    
    def _get_metric_value(self, metrics: SystemMetrics, metric_name: str) -> Optional[float]:
        """Extract metric value from SystemMetrics."""
        if metric_name == "cpu_percent":
            return metrics.cpu_percent
        elif metric_name == "memory_percent":
            return metrics.memory_percent
        elif metric_name == "swap_percent":
            return metrics.swap_percent
        elif metric_name == "disk_percent":
            # Return highest disk usage percentage
            if metrics.disk_usage:
                return max(disk['percent'] for disk in metrics.disk_usage.values())
        
        return None
    
    def _compare_value(self, value: float, threshold: float, comparison: str) -> bool:
        """Compare value against threshold."""
        if comparison == "greater":
            return value > threshold
        elif comparison == "less":
            return value < threshold
        elif comparison == "equal":
            return abs(value - threshold) < 0.01
        
        return False
    
    async def _create_alert(
        self,
        level: AlertLevel,
        metric: str,
        value: float,
        threshold: float,
        message: str
    ):
        """Create a new alert."""
        # Check if similar alert already exists and is not resolved
        for alert in self.alerts:
            if (alert.metric == metric and 
                alert.level == level and 
                not alert.resolved and
                time.time() - alert.timestamp < 300):  # 5 minutes
                return  # Don't create duplicate alerts
        
        alert = Alert(
            timestamp=time.time(),
            level=level,
            metric=metric,
            value=value,
            threshold=threshold,
            message=message
        )
        
        self.alerts.append(alert)
        logger.log(
            logging.WARNING if level == AlertLevel.WARNING else logging.ERROR,
            f"Alert: {message}"
        )
    
    def add_threshold(self, threshold: Threshold):
        """Add a monitoring threshold."""
        self.thresholds.append(threshold)
        logger.info(f"Added threshold for {threshold.metric}")
    
    def remove_threshold(self, metric: str):
        """Remove thresholds for a specific metric."""
        self.thresholds = [t for t in self.thresholds if t.metric != metric]
        logger.info(f"Removed thresholds for {metric}")
    
    def get_current_metrics(self) -> Optional[SystemMetrics]:
        """Get the most recent system metrics."""
        if self.system_metrics:
            return self.system_metrics[-1]
        return None
    
    def get_historical_metrics(self, limit: Optional[int] = None) -> List[SystemMetrics]:
        """Get historical system metrics.
        
        Args:
            limit: Maximum number of metrics to return
            
        Returns:
            List of SystemMetrics
        """
        metrics = list(self.system_metrics)
        if limit:
            return metrics[-limit:]
        return metrics
    
    def get_process_metrics(self, pid: int, limit: Optional[int] = None) -> List[ProcessMetrics]:
        """Get historical metrics for a specific process.
        
        Args:
            pid: Process ID
            limit: Maximum number of metrics to return
            
        Returns:
            List of ProcessMetrics
        """
        if pid not in self.process_metrics:
            return []
        
        metrics = list(self.process_metrics[pid])
        if limit:
            return metrics[-limit:]
        return metrics
    
    def get_alerts(self, resolved: Optional[bool] = None) -> List[Alert]:
        """Get alerts.
        
        Args:
            resolved: Filter by resolved status (None for all)
            
        Returns:
            List of Alert objects
        """
        if resolved is None:
            return self.alerts.copy()
        
        return [alert for alert in self.alerts if alert.resolved == resolved]
    
    def resolve_alert(self, alert_index: int):
        """Mark an alert as resolved."""
        if 0 <= alert_index < len(self.alerts):
            self.alerts[alert_index].resolved = True
            self.alerts[alert_index].resolved_at = time.time()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get monitoring summary."""
        current_metrics = self.get_current_metrics()
        unresolved_alerts = self.get_alerts(resolved=False)
        
        summary = {
            'monitoring_active': self._monitoring,
            'collection_interval': self.collection_interval,
            'metrics_collected': len(self.system_metrics),
            'processes_monitored': len(self.process_metrics),
            'total_alerts': len(self.alerts),
            'unresolved_alerts': len(unresolved_alerts),
            'thresholds_configured': len(self.thresholds)
        }
        
        if current_metrics:
            summary['current_metrics'] = {
                'timestamp': current_metrics.timestamp,
                'cpu_percent': current_metrics.cpu_percent,
                'memory_percent': current_metrics.memory_percent,
                'swap_percent': current_metrics.swap_percent,
                'process_count': current_metrics.process_count,
                'uptime_hours': (time.time() - current_metrics.boot_time) / 3600
            }
        
        if unresolved_alerts:
            summary['recent_alerts'] = [
                {
                    'level': alert.level.value,
                    'metric': alert.metric,
                    'message': alert.message,
                    'timestamp': alert.timestamp
                }
                for alert in unresolved_alerts[-5:]  # Last 5 alerts
            ]
        
        return summary
    
    def export_metrics(self, format: str = 'json') -> str:
        """Export metrics in specified format.
        
        Args:
            format: Export format ('json', 'csv')
            
        Returns:
            Formatted metrics data
        """
        if format == 'json':
            data = {
                'system_metrics': [asdict(m) for m in self.system_metrics],
                'process_metrics': {
                    str(pid): [asdict(m) for m in metrics]
                    for pid, metrics in self.process_metrics.items()
                },
                'alerts': [asdict(alert) for alert in self.alerts],
                'thresholds': [asdict(threshold) for threshold in self.thresholds]
            }
            return json.dumps(data, indent=2)
        
        elif format == 'csv':
            # Simple CSV export for system metrics
            lines = ['timestamp,cpu_percent,memory_percent,swap_percent,process_count']
            for metrics in self.system_metrics:
                lines.append(
                    f"{metrics.timestamp},{metrics.cpu_percent},{metrics.memory_percent},"
                    f"{metrics.swap_percent},{metrics.process_count}"
                )
            return '\n'.join(lines)
        
        else:
            raise ValueError(f"Unsupported export format: {format}")

# Global resource monitor instance
resource_monitor = ResourceMonitor()