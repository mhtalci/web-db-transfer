"""
CMS migration performance monitoring and metrics collection.
"""

import time
import psutil
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque


@dataclass
class PerformanceMetric:
    """Represents a performance metric."""
    name: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MigrationMetrics:
    """Collection of migration performance metrics."""
    migration_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_files_processed: int = 0
    total_bytes_processed: int = 0
    database_records_processed: int = 0
    errors_encountered: int = 0
    warnings_encountered: int = 0
    peak_memory_usage: float = 0.0
    peak_cpu_usage: float = 0.0
    average_throughput: float = 0.0  # MB/s
    step_metrics: Dict[str, List[PerformanceMetric]] = field(default_factory=dict)


class CMSPerformanceMonitor:
    """Real-time performance monitoring for CMS migrations."""
    
    def __init__(self, migration_id: str):
        self.migration_id = migration_id
        self.metrics = MigrationMetrics(migration_id, datetime.now())
        self.monitoring_active = False
        self.monitoring_task: Optional[asyncio.Task] = None
        self.metric_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.alert_thresholds = {
            'memory_usage_percent': 85.0,
            'cpu_usage_percent': 90.0,
            'disk_usage_percent': 95.0,
            'error_rate_percent': 5.0
        }
        self.alert_callbacks: List[callable] = []
    
    def add_alert_callback(self, callback: callable):
        """Add callback for performance alerts."""
        self.alert_callbacks.append(callback)
    
    async def start_monitoring(self, interval: float = 5.0):
        """Start real-time performance monitoring."""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop(interval))
    
    async def stop_monitoring(self):
        """Stop performance monitoring."""
        self.monitoring_active = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        self.metrics.end_time = datetime.now()
    
    async def record_step_start(self, step_name: str):
        """Record the start of a migration step."""
        if step_name not in self.metrics.step_metrics:
            self.metrics.step_metrics[step_name] = []
        
        metric = PerformanceMetric(
            name=f"{step_name}_start",
            value=time.time(),
            unit="timestamp"
        )
        self.metrics.step_metrics[step_name].append(metric)
    
    async def record_step_end(self, step_name: str, success: bool = True):
        """Record the end of a migration step."""
        if step_name not in self.metrics.step_metrics:
            self.metrics.step_metrics[step_name] = []
        
        # Find the start metric
        start_metrics = [m for m in self.metrics.step_metrics[step_name] if m.name.endswith('_start')]
        if start_metrics:
            start_time = start_metrics[-1].value
            duration = time.time() - start_time
            
            metric = PerformanceMetric(
                name=f"{step_name}_duration",
                value=duration,
                unit="seconds",
                metadata={'success': success}
            )
            self.metrics.step_metrics[step_name].append(metric)
    
    async def record_file_processed(self, file_path: Path, file_size: int):
        """Record a processed file."""
        self.metrics.total_files_processed += 1
        self.metrics.total_bytes_processed += file_size
        
        # Update throughput calculation
        if self.metrics.start_time:
            elapsed = (datetime.now() - self.metrics.start_time).total_seconds()
            if elapsed > 0:
                self.metrics.average_throughput = (self.metrics.total_bytes_processed / (1024 * 1024)) / elapsed
    
    async def record_database_operation(self, operation: str, records_count: int):
        """Record database operation metrics."""
        self.metrics.database_records_processed += records_count
        
        metric = PerformanceMetric(
            name=f"db_{operation}",
            value=records_count,
            unit="records",
            metadata={'operation': operation}
        )
        
        if 'database' not in self.metrics.step_metrics:
            self.metrics.step_metrics['database'] = []
        self.metrics.step_metrics['database'].append(metric)
    
    async def record_error(self, error_type: str, error_message: str):
        """Record an error occurrence."""
        self.metrics.errors_encountered += 1
        
        metric = PerformanceMetric(
            name="error",
            value=1,
            unit="count",
            metadata={
                'type': error_type,
                'message': error_message[:200]  # Truncate long messages
            }
        )
        
        if 'errors' not in self.metrics.step_metrics:
            self.metrics.step_metrics['errors'] = []
        self.metrics.step_metrics['errors'].append(metric)
    
    async def record_warning(self, warning_type: str, warning_message: str):
        """Record a warning occurrence."""
        self.metrics.warnings_encountered += 1
        
        metric = PerformanceMetric(
            name="warning",
            value=1,
            unit="count",
            metadata={
                'type': warning_type,
                'message': warning_message[:200]
            }
        )
        
        if 'warnings' not in self.metrics.step_metrics:
            self.metrics.step_metrics['warnings'] = []
        self.metrics.step_metrics['warnings'].append(metric)
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics snapshot."""
        current_time = datetime.now()
        elapsed_time = (current_time - self.metrics.start_time).total_seconds()
        
        # Get latest system metrics
        memory_info = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent()
        disk_usage = psutil.disk_usage('/')
        
        return {
            'migration_id': self.migration_id,
            'elapsed_time': elapsed_time,
            'files_processed': self.metrics.total_files_processed,
            'bytes_processed': self.metrics.total_bytes_processed,
            'database_records': self.metrics.database_records_processed,
            'errors': self.metrics.errors_encountered,
            'warnings': self.metrics.warnings_encountered,
            'average_throughput_mbps': self.metrics.average_throughput,
            'system_metrics': {
                'memory_usage_percent': memory_info.percent,
                'memory_available_gb': memory_info.available / (1024**3),
                'cpu_usage_percent': cpu_percent,
                'disk_usage_percent': disk_usage.percent,
                'disk_free_gb': disk_usage.free / (1024**3)
            },
            'peak_usage': {
                'memory_percent': self.metrics.peak_memory_usage,
                'cpu_percent': self.metrics.peak_cpu_usage
            }
        }
    
    def get_step_performance(self, step_name: str) -> Dict[str, Any]:
        """Get performance metrics for a specific step."""
        if step_name not in self.metrics.step_metrics:
            return {}
        
        step_metrics = self.metrics.step_metrics[step_name]
        
        # Calculate step statistics
        duration_metrics = [m for m in step_metrics if m.name.endswith('_duration')]
        error_metrics = [m for m in step_metrics if m.name == 'error']
        
        total_duration = sum(m.value for m in duration_metrics)
        total_errors = len(error_metrics)
        success_rate = 0.0
        
        if duration_metrics:
            successful_runs = sum(1 for m in duration_metrics if m.metadata.get('success', True))
            success_rate = (successful_runs / len(duration_metrics)) * 100
        
        return {
            'step_name': step_name,
            'total_duration': total_duration,
            'average_duration': total_duration / len(duration_metrics) if duration_metrics else 0,
            'execution_count': len(duration_metrics),
            'error_count': total_errors,
            'success_rate_percent': success_rate,
            'metrics': [
                {
                    'name': m.name,
                    'value': m.value,
                    'unit': m.unit,
                    'timestamp': m.timestamp.isoformat(),
                    'metadata': m.metadata
                }
                for m in step_metrics
            ]
        }
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        current_metrics = self.get_current_metrics()
        
        # Calculate overall statistics
        total_time = current_metrics['elapsed_time']
        files_per_second = current_metrics['files_processed'] / total_time if total_time > 0 else 0
        error_rate = (current_metrics['errors'] / max(current_metrics['files_processed'], 1)) * 100
        
        # Get step performance
        step_performance = {}
        for step_name in self.metrics.step_metrics.keys():
            step_performance[step_name] = self.get_step_performance(step_name)
        
        # Performance grade calculation
        performance_grade = self._calculate_performance_grade(current_metrics, error_rate)
        
        return {
            'migration_id': self.migration_id,
            'report_generated': datetime.now().isoformat(),
            'migration_duration': total_time,
            'overall_metrics': current_metrics,
            'performance_statistics': {
                'files_per_second': files_per_second,
                'error_rate_percent': error_rate,
                'throughput_mbps': current_metrics['average_throughput_mbps'],
                'performance_grade': performance_grade
            },
            'step_performance': step_performance,
            'recommendations': self._generate_performance_recommendations(current_metrics, error_rate)
        }
    
    async def _monitoring_loop(self, interval: float):
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                # Collect system metrics
                memory_info = psutil.virtual_memory()
                cpu_percent = psutil.cpu_percent()
                
                # Update peak usage
                self.metrics.peak_memory_usage = max(self.metrics.peak_memory_usage, memory_info.percent)
                self.metrics.peak_cpu_usage = max(self.metrics.peak_cpu_usage, cpu_percent)
                
                # Store metrics history
                self.metric_history['memory_percent'].append((datetime.now(), memory_info.percent))
                self.metric_history['cpu_percent'].append((datetime.now(), cpu_percent))
                
                # Check for alerts
                await self._check_alerts(memory_info.percent, cpu_percent)
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log monitoring error but continue
                await self.record_error("monitoring", str(e))
                await asyncio.sleep(interval)
    
    async def _check_alerts(self, memory_percent: float, cpu_percent: float):
        """Check for performance alerts."""
        alerts = []
        
        if memory_percent > self.alert_thresholds['memory_usage_percent']:
            alerts.append({
                'type': 'memory_high',
                'message': f"Memory usage is {memory_percent:.1f}% (threshold: {self.alert_thresholds['memory_usage_percent']}%)",
                'severity': 'warning' if memory_percent < 95 else 'critical'
            })
        
        if cpu_percent > self.alert_thresholds['cpu_usage_percent']:
            alerts.append({
                'type': 'cpu_high',
                'message': f"CPU usage is {cpu_percent:.1f}% (threshold: {self.alert_thresholds['cpu_usage_percent']}%)",
                'severity': 'warning' if cpu_percent < 95 else 'critical'
            })
        
        # Check error rate
        if self.metrics.total_files_processed > 0:
            error_rate = (self.metrics.errors_encountered / self.metrics.total_files_processed) * 100
            if error_rate > self.alert_thresholds['error_rate_percent']:
                alerts.append({
                    'type': 'error_rate_high',
                    'message': f"Error rate is {error_rate:.1f}% (threshold: {self.alert_thresholds['error_rate_percent']}%)",
                    'severity': 'warning'
                })
        
        # Send alerts
        for alert in alerts:
            for callback in self.alert_callbacks:
                try:
                    await callback(alert)
                except Exception:
                    pass  # Don't let callback errors stop monitoring
    
    def _calculate_performance_grade(self, metrics: Dict[str, Any], error_rate: float) -> str:
        """Calculate overall performance grade."""
        score = 100
        
        # Deduct points for high resource usage
        if metrics['system_metrics']['memory_usage_percent'] > 80:
            score -= 10
        if metrics['system_metrics']['cpu_usage_percent'] > 80:
            score -= 10
        
        # Deduct points for errors
        if error_rate > 1:
            score -= min(error_rate * 5, 30)  # Max 30 points deduction
        
        # Deduct points for low throughput (if applicable)
        if metrics['average_throughput_mbps'] < 1.0 and metrics['bytes_processed'] > 100 * 1024 * 1024:  # 100MB+
            score -= 15
        
        # Grade mapping
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'
    
    def _generate_performance_recommendations(self, metrics: Dict[str, Any], error_rate: float) -> List[str]:
        """Generate performance improvement recommendations."""
        recommendations = []
        
        # Memory recommendations
        if metrics['system_metrics']['memory_usage_percent'] > 80:
            recommendations.append("Consider increasing available memory or reducing concurrent operations")
        
        # CPU recommendations
        if metrics['system_metrics']['cpu_usage_percent'] > 80:
            recommendations.append("High CPU usage detected - consider reducing parallel processing or upgrading hardware")
        
        # Throughput recommendations
        if metrics['average_throughput_mbps'] < 1.0 and metrics['bytes_processed'] > 100 * 1024 * 1024:
            recommendations.append("Low throughput detected - check network connectivity and disk I/O performance")
        
        # Error rate recommendations
        if error_rate > 1:
            recommendations.append(f"Error rate is {error_rate:.1f}% - review error logs and fix underlying issues")
        
        # Disk space recommendations
        if metrics['system_metrics']['disk_free_gb'] < 5:
            recommendations.append("Low disk space - ensure adequate free space for migration operations")
        
        if not recommendations:
            recommendations.append("Performance is optimal - no specific recommendations")
        
        return recommendations


class CMSMetricsCollector:
    """Collect and aggregate metrics across multiple migrations."""
    
    def __init__(self):
        self.migration_metrics: Dict[str, MigrationMetrics] = {}
        self.platform_statistics: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'total_migrations': 0,
            'successful_migrations': 0,
            'total_files_processed': 0,
            'total_bytes_processed': 0,
            'average_duration': 0.0,
            'average_throughput': 0.0
        })
    
    def add_migration_metrics(self, metrics: MigrationMetrics, source_platform: str, success: bool):
        """Add completed migration metrics."""
        self.migration_metrics[metrics.migration_id] = metrics
        
        # Update platform statistics
        stats = self.platform_statistics[source_platform]
        stats['total_migrations'] += 1
        if success:
            stats['successful_migrations'] += 1
        
        stats['total_files_processed'] += metrics.total_files_processed
        stats['total_bytes_processed'] += metrics.total_bytes_processed
        
        # Recalculate averages
        if metrics.end_time:
            duration = (metrics.end_time - metrics.start_time).total_seconds()
            stats['average_duration'] = (stats['average_duration'] * (stats['total_migrations'] - 1) + duration) / stats['total_migrations']
        
        stats['average_throughput'] = (stats['average_throughput'] * (stats['total_migrations'] - 1) + metrics.average_throughput) / stats['total_migrations']
    
    def get_platform_statistics(self) -> Dict[str, Any]:
        """Get aggregated platform statistics."""
        return dict(self.platform_statistics)
    
    def get_global_statistics(self) -> Dict[str, Any]:
        """Get global migration statistics."""
        total_migrations = len(self.migration_metrics)
        successful_migrations = sum(1 for stats in self.platform_statistics.values() 
                                  for _ in range(stats['successful_migrations']))
        
        total_files = sum(stats['total_files_processed'] for stats in self.platform_statistics.values())
        total_bytes = sum(stats['total_bytes_processed'] for stats in self.platform_statistics.values())
        
        success_rate = (successful_migrations / total_migrations * 100) if total_migrations > 0 else 0
        
        return {
            'total_migrations': total_migrations,
            'successful_migrations': successful_migrations,
            'success_rate_percent': success_rate,
            'total_files_processed': total_files,
            'total_bytes_processed': total_bytes,
            'total_data_processed_gb': total_bytes / (1024**3),
            'platform_breakdown': self.get_platform_statistics()
        }