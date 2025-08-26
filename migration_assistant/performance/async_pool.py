"""Async connection pooling and resource management."""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from abc import ABC, abstractmethod
import weakref
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar('T')

class PoolState(Enum):
    """Connection pool states."""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    DRAINING = "draining"
    CLOSED = "closed"

@dataclass
class PoolStats:
    """Connection pool statistics."""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    pending_requests: int = 0
    total_created: int = 0
    total_destroyed: int = 0
    total_requests: int = 0
    total_errors: int = 0
    avg_wait_time_ms: float = 0.0
    max_wait_time_ms: float = 0.0

@dataclass
class ConnectionInfo:
    """Information about a pooled connection."""
    connection: Any
    created_at: float
    last_used: float
    use_count: int = 0
    is_healthy: bool = True
    in_use: bool = False

class PooledConnection(Generic[T]):
    """Wrapper for pooled connections."""
    
    def __init__(self, connection: T, pool: 'AsyncConnectionPool', info: ConnectionInfo):
        self.connection = connection
        self._pool = pool
        self._info = info
        self._returned = False
    
    async def __aenter__(self) -> T:
        return self.connection
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if not self._returned:
            await self._pool._return_connection(self._info)
            self._returned = True
    
    def __getattr__(self, name):
        """Delegate attribute access to the underlying connection."""
        return getattr(self.connection, name)

class AsyncConnectionPool(Generic[T]):
    """Generic async connection pool with health checking and monitoring."""
    
    def __init__(
        self,
        connection_factory: Callable[[], Any],
        min_size: int = 1,
        max_size: int = 10,
        max_idle_time: float = 300.0,  # 5 minutes
        health_check_interval: float = 60.0,  # 1 minute
        connection_timeout: float = 30.0,
        health_check_func: Optional[Callable[[Any], bool]] = None,
        cleanup_func: Optional[Callable[[Any], None]] = None
    ):
        """Initialize connection pool.
        
        Args:
            connection_factory: Function to create new connections
            min_size: Minimum number of connections to maintain
            max_size: Maximum number of connections allowed
            max_idle_time: Maximum time a connection can be idle (seconds)
            health_check_interval: Interval between health checks (seconds)
            connection_timeout: Timeout for creating new connections (seconds)
            health_check_func: Function to check connection health
            cleanup_func: Function to cleanup connections
        """
        self.connection_factory = connection_factory
        self.min_size = min_size
        self.max_size = max_size
        self.max_idle_time = max_idle_time
        self.health_check_interval = health_check_interval
        self.connection_timeout = connection_timeout
        self.health_check_func = health_check_func
        self.cleanup_func = cleanup_func
        
        self._connections: Dict[int, ConnectionInfo] = {}
        self._available: asyncio.Queue = asyncio.Queue()
        self._pending_requests: List[asyncio.Future] = []
        self._state = PoolState.INITIALIZING
        self._stats = PoolStats()
        self._lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Weak reference to track pool instances for cleanup
        self._instances = weakref.WeakSet()
        self._instances.add(self)
    
    async def initialize(self):
        """Initialize the connection pool."""
        async with self._lock:
            if self._state != PoolState.INITIALIZING:
                return
            
            logger.info(f"Initializing connection pool (min={self.min_size}, max={self.max_size})")
            
            # Create minimum number of connections
            for _ in range(self.min_size):
                try:
                    await self._create_connection()
                except Exception as e:
                    logger.error(f"Failed to create initial connection: {e}")
            
            self._state = PoolState.ACTIVE
            
            # Start background tasks
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            
            logger.info(f"Connection pool initialized with {len(self._connections)} connections")
    
    async def _create_connection(self) -> ConnectionInfo:
        """Create a new connection."""
        if len(self._connections) >= self.max_size:
            raise RuntimeError("Maximum pool size reached")
        
        try:
            # Create connection with timeout
            connection = await asyncio.wait_for(
                asyncio.to_thread(self.connection_factory),
                timeout=self.connection_timeout
            )
            
            now = time.time()
            info = ConnectionInfo(
                connection=connection,
                created_at=now,
                last_used=now
            )
            
            connection_id = id(connection)
            self._connections[connection_id] = info
            self._stats.total_created += 1
            
            # Add to available queue
            await self._available.put(info)
            
            logger.debug(f"Created new connection {connection_id}")
            return info
            
        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            self._stats.total_errors += 1
            raise
    
    async def _destroy_connection(self, info: ConnectionInfo):
        """Destroy a connection."""
        connection_id = id(info.connection)
        
        try:
            if self.cleanup_func:
                await asyncio.to_thread(self.cleanup_func, info.connection)
            
            if connection_id in self._connections:
                del self._connections[connection_id]
                self._stats.total_destroyed += 1
                
            logger.debug(f"Destroyed connection {connection_id}")
            
        except Exception as e:
            logger.error(f"Error destroying connection {connection_id}: {e}")
    
    async def acquire(self, timeout: Optional[float] = None) -> PooledConnection[T]:
        """Acquire a connection from the pool.
        
        Args:
            timeout: Maximum time to wait for a connection
            
        Returns:
            PooledConnection wrapper
        """
        if self._state != PoolState.ACTIVE:
            if self._state == PoolState.INITIALIZING:
                await self.initialize()
            else:
                raise RuntimeError(f"Pool is {self._state.value}")
        
        start_time = time.time()
        self._stats.total_requests += 1
        
        try:
            # Try to get an available connection
            try:
                info = await asyncio.wait_for(
                    self._available.get(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                # Try to create a new connection if under max size
                async with self._lock:
                    if len(self._connections) < self.max_size:
                        info = await self._create_connection()
                        # Remove from available queue since we're using it
                        try:
                            self._available.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                    else:
                        raise asyncio.TimeoutError("No connections available and pool is at maximum size")
            
            # Mark connection as in use
            info.in_use = True
            info.last_used = time.time()
            info.use_count += 1
            
            # Update stats
            wait_time = (time.time() - start_time) * 1000
            self._stats.avg_wait_time_ms = (
                (self._stats.avg_wait_time_ms * (self._stats.total_requests - 1) + wait_time) /
                self._stats.total_requests
            )
            self._stats.max_wait_time_ms = max(self._stats.max_wait_time_ms, wait_time)
            
            return PooledConnection(info.connection, self, info)
            
        except Exception as e:
            self._stats.total_errors += 1
            logger.error(f"Failed to acquire connection: {e}")
            raise
    
    async def _return_connection(self, info: ConnectionInfo):
        """Return a connection to the pool."""
        info.in_use = False
        info.last_used = time.time()
        
        # Check if connection is still healthy
        if await self._check_connection_health(info):
            await self._available.put(info)
        else:
            # Destroy unhealthy connection
            await self._destroy_connection(info)
            
            # Create replacement if below minimum
            async with self._lock:
                if len(self._connections) < self.min_size and self._state == PoolState.ACTIVE:
                    try:
                        await self._create_connection()
                    except Exception as e:
                        logger.error(f"Failed to create replacement connection: {e}")
    
    async def _check_connection_health(self, info: ConnectionInfo) -> bool:
        """Check if a connection is healthy."""
        if not self.health_check_func:
            return True
        
        try:
            return await asyncio.to_thread(self.health_check_func, info.connection)
        except Exception as e:
            logger.warning(f"Health check failed for connection {id(info.connection)}: {e}")
            return False
    
    async def _health_check_loop(self):
        """Background task to check connection health."""
        while self._state == PoolState.ACTIVE:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                # Check all connections
                unhealthy_connections = []
                
                for connection_id, info in list(self._connections.items()):
                    if not info.in_use and not await self._check_connection_health(info):
                        unhealthy_connections.append(info)
                
                # Remove unhealthy connections
                for info in unhealthy_connections:
                    await self._destroy_connection(info)
                
                # Ensure minimum connections
                async with self._lock:
                    while len(self._connections) < self.min_size and self._state == PoolState.ACTIVE:
                        try:
                            await self._create_connection()
                        except Exception as e:
                            logger.error(f"Failed to create connection during health check: {e}")
                            break
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
    
    async def _cleanup_loop(self):
        """Background task to cleanup idle connections."""
        while self._state == PoolState.ACTIVE:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                now = time.time()
                idle_connections = []
                
                # Find idle connections
                for connection_id, info in list(self._connections.items()):
                    if (not info.in_use and 
                        now - info.last_used > self.max_idle_time and
                        len(self._connections) > self.min_size):
                        idle_connections.append(info)
                
                # Remove idle connections
                for info in idle_connections:
                    await self._destroy_connection(info)
                    logger.debug(f"Removed idle connection {id(info.connection)}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def close(self):
        """Close the connection pool."""
        logger.info("Closing connection pool")
        
        async with self._lock:
            self._state = PoolState.DRAINING
        
        # Cancel background tasks
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        for info in list(self._connections.values()):
            await self._destroy_connection(info)
        
        self._state = PoolState.CLOSED
        logger.info("Connection pool closed")
    
    def get_stats(self) -> PoolStats:
        """Get current pool statistics."""
        active_count = sum(1 for info in self._connections.values() if info.in_use)
        idle_count = len(self._connections) - active_count
        
        self._stats.total_connections = len(self._connections)
        self._stats.active_connections = active_count
        self._stats.idle_connections = idle_count
        self._stats.pending_requests = len(self._pending_requests)
        
        return self._stats
    
    @property
    def state(self) -> PoolState:
        """Get current pool state."""
        return self._state

class DatabaseConnectionPool(AsyncConnectionPool):
    """Specialized connection pool for database connections."""
    
    def __init__(self, connection_string: str, **kwargs):
        """Initialize database connection pool.
        
        Args:
            connection_string: Database connection string
            **kwargs: Additional pool configuration
        """
        self.connection_string = connection_string
        
        # Default database-specific settings
        kwargs.setdefault('min_size', 2)
        kwargs.setdefault('max_size', 20)
        kwargs.setdefault('max_idle_time', 600.0)  # 10 minutes
        kwargs.setdefault('health_check_interval', 30.0)  # 30 seconds
        
        super().__init__(
            connection_factory=self._create_db_connection,
            health_check_func=self._check_db_health,
            cleanup_func=self._cleanup_db_connection,
            **kwargs
        )
    
    def _create_db_connection(self):
        """Create database connection - to be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _create_db_connection")
    
    def _check_db_health(self, connection) -> bool:
        """Check database connection health - to be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _check_db_health")
    
    def _cleanup_db_connection(self, connection):
        """Cleanup database connection - to be implemented by subclasses."""
        try:
            if hasattr(connection, 'close'):
                connection.close()
        except Exception as e:
            logger.warning(f"Error closing database connection: {e}")

class ResourceMonitor:
    """Monitor resource usage for connection pools and async operations."""
    
    def __init__(self):
        """Initialize resource monitor."""
        self.pools: Dict[str, AsyncConnectionPool] = {}
        self.metrics: Dict[str, List[Dict[str, Any]]] = {}
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
    
    def register_pool(self, name: str, pool: AsyncConnectionPool):
        """Register a connection pool for monitoring.
        
        Args:
            name: Pool name
            pool: Connection pool instance
        """
        self.pools[name] = pool
        self.metrics[name] = []
        logger.info(f"Registered pool '{name}' for monitoring")
    
    def unregister_pool(self, name: str):
        """Unregister a connection pool.
        
        Args:
            name: Pool name
        """
        if name in self.pools:
            del self.pools[name]
            del self.metrics[name]
            logger.info(f"Unregistered pool '{name}' from monitoring")
    
    async def start_monitoring(self, interval: float = 30.0):
        """Start resource monitoring.
        
        Args:
            interval: Monitoring interval in seconds
        """
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop(interval))
        logger.info(f"Started resource monitoring with {interval}s interval")
    
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
    
    async def _monitor_loop(self, interval: float):
        """Background monitoring loop."""
        try:
            import psutil
        except ImportError:
            logger.warning("psutil not available, system metrics will be limited")
            psutil = None
        
        while self._monitoring:
            try:
                timestamp = time.time()
                
                # Collect system metrics
                system_metrics = {}
                if psutil:
                    system_metrics = {
                        'cpu_percent': psutil.cpu_percent(interval=1),
                        'memory_percent': psutil.virtual_memory().percent,
                        'disk_usage': psutil.disk_usage('/').percent,
                        'network_io': psutil.net_io_counters()._asdict() if psutil.net_io_counters() else {},
                        'process_count': len(psutil.pids())
                    }
                
                # Collect pool metrics
                for pool_name, pool in self.pools.items():
                    stats = pool.get_stats()
                    
                    metric = {
                        'timestamp': timestamp,
                        'pool_state': pool.state.value,
                        'total_connections': stats.total_connections,
                        'active_connections': stats.active_connections,
                        'idle_connections': stats.idle_connections,
                        'pending_requests': stats.pending_requests,
                        'total_created': stats.total_created,
                        'total_destroyed': stats.total_destroyed,
                        'total_requests': stats.total_requests,
                        'total_errors': stats.total_errors,
                        'avg_wait_time_ms': stats.avg_wait_time_ms,
                        'max_wait_time_ms': stats.max_wait_time_ms,
                        'system_metrics': system_metrics
                    }
                    
                    self.metrics[pool_name].append(metric)
                    
                    # Keep only last 1000 metrics per pool
                    if len(self.metrics[pool_name]) > 1000:
                        self.metrics[pool_name] = self.metrics[pool_name][-1000:]
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(interval)
    
    def get_pool_metrics(self, pool_name: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get metrics for a specific pool.
        
        Args:
            pool_name: Pool name
            limit: Maximum number of metrics to return
            
        Returns:
            List of metric dictionaries
        """
        metrics = self.metrics.get(pool_name, [])
        if limit:
            return metrics[-limit:]
        return metrics
    
    def get_all_metrics(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all collected metrics.
        
        Returns:
            Dictionary mapping pool names to metrics
        """
        return self.metrics.copy()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all monitored pools.
        
        Returns:
            Summary dictionary
        """
        summary = {
            'pools': {},
            'total_pools': len(self.pools),
            'monitoring': self._monitoring
        }
        
        for pool_name, pool in self.pools.items():
            stats = pool.get_stats()
            recent_metrics = self.metrics.get(pool_name, [])[-10:]  # Last 10 metrics
            
            avg_cpu = 0
            avg_memory = 0
            if recent_metrics:
                cpu_values = [m['system_metrics'].get('cpu_percent', 0) for m in recent_metrics if 'system_metrics' in m]
                memory_values = [m['system_metrics'].get('memory_percent', 0) for m in recent_metrics if 'system_metrics' in m]
                
                avg_cpu = sum(cpu_values) / len(cpu_values) if cpu_values else 0
                avg_memory = sum(memory_values) / len(memory_values) if memory_values else 0
            
            summary['pools'][pool_name] = {
                'state': pool.state.value,
                'connections': {
                    'total': stats.total_connections,
                    'active': stats.active_connections,
                    'idle': stats.idle_connections
                },
                'requests': {
                    'total': stats.total_requests,
                    'errors': stats.total_errors,
                    'error_rate': stats.total_errors / stats.total_requests * 100 if stats.total_requests > 0 else 0
                },
                'performance': {
                    'avg_wait_time_ms': stats.avg_wait_time_ms,
                    'max_wait_time_ms': stats.max_wait_time_ms
                },
                'system': {
                    'avg_cpu_percent': avg_cpu,
                    'avg_memory_percent': avg_memory
                }
            }
        
        return summary

# Global resource monitor instance
resource_monitor = ResourceMonitor()