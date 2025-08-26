"""
Progress tracking system for migration operations.

This module provides real-time progress monitoring with estimated time remaining,
transfer rate tracking, and performance metrics collection.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable, Union
from enum import Enum
from dataclasses import dataclass, field
from collections import deque

from pydantic import BaseModel

from migration_assistant.models.session import MigrationSession, MigrationStep, LogLevel


class ProgressEventType(str, Enum):
    """Types of progress events."""
    STARTED = "started"
    PROGRESS = "progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    RESUMED = "resumed"
    CANCELLED = "cancelled"


class ProgressUnit(str, Enum):
    """Units for progress measurement."""
    ITEMS = "items"
    BYTES = "bytes"
    FILES = "files"
    RECORDS = "records"
    PERCENT = "percent"
    OPERATIONS = "operations"


@dataclass
class ProgressEvent:
    """Progress event data structure."""
    session_id: str
    step_id: Optional[str]
    event_type: ProgressEventType
    timestamp: datetime
    current: int
    total: int
    unit: ProgressUnit
    rate: Optional[float] = None  # units per second
    eta: Optional[int] = None  # seconds remaining
    message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProgressMetrics:
    """Progress metrics for performance analysis."""
    session_id: str
    step_id: Optional[str]
    start_time: datetime
    current_time: datetime
    elapsed_time: float  # seconds
    current_progress: int
    total_progress: int
    completion_percentage: float
    average_rate: float  # units per second
    current_rate: float  # units per second
    eta_seconds: Optional[int]
    peak_rate: float
    min_rate: float
    rate_history: List[float] = field(default_factory=list)
    throughput_history: List[Dict[str, Any]] = field(default_factory=list)


class ProgressTracker:
    """
    Real-time progress tracker for migration operations.
    
    Provides progress monitoring with ETA calculation, rate tracking,
    and performance metrics collection.
    """
    
    def __init__(self, max_history_size: int = 100):
        """
        Initialize progress tracker.
        
        Args:
            max_history_size: Maximum number of rate samples to keep for calculations
        """
        self.max_history_size = max_history_size
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._callbacks: List[Callable[[ProgressEvent], None]] = []
        self._rate_history: Dict[str, deque] = {}
        self._last_update: Dict[str, float] = {}
        self._paused_sessions: Dict[str, float] = {}  # session_id -> pause_time
        
    def add_callback(self, callback: Callable[[ProgressEvent], None]):
        """Add a progress callback function."""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[ProgressEvent], None]):
        """Remove a progress callback function."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def start_tracking(
        self,
        session_id: str,
        step_id: Optional[str] = None,
        total: int = 100,
        unit: ProgressUnit = ProgressUnit.ITEMS,
        message: Optional[str] = None
    ):
        """
        Start tracking progress for a session/step.
        
        Args:
            session_id: Migration session ID
            step_id: Optional step ID for step-level tracking
            total: Total number of units to process
            unit: Unit of measurement
            message: Optional descriptive message
        """
        tracking_key = f"{session_id}:{step_id or 'session'}"
        
        self._sessions[tracking_key] = {
            "session_id": session_id,
            "step_id": step_id,
            "start_time": time.time(),
            "current": 0,
            "total": total,
            "unit": unit,
            "paused_time": 0.0,
            "is_paused": False,
            "message": message
        }
        
        self._rate_history[tracking_key] = deque(maxlen=self.max_history_size)
        self._last_update[tracking_key] = time.time()
        
        # Emit started event
        event = ProgressEvent(
            session_id=session_id,
            step_id=step_id,
            event_type=ProgressEventType.STARTED,
            timestamp=datetime.utcnow(),
            current=0,
            total=total,
            unit=unit,
            message=message
        )
        
        self._emit_event(event)
    
    def update_progress(
        self,
        session_id: str,
        current: int,
        step_id: Optional[str] = None,
        total: Optional[int] = None,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Update progress for a session/step.
        
        Args:
            session_id: Migration session ID
            current: Current progress value
            step_id: Optional step ID
            total: Optional updated total (if changed)
            message: Optional progress message
            metadata: Optional additional metadata
        """
        tracking_key = f"{session_id}:{step_id or 'session'}"
        
        if tracking_key not in self._sessions:
            # Auto-start tracking if not already started
            self.start_tracking(session_id, step_id, total or 100)
        
        session_data = self._sessions[tracking_key]
        
        # Skip update if paused
        if session_data.get("is_paused", False):
            return
        
        # Update values
        old_current = session_data["current"]
        session_data["current"] = current
        if total is not None:
            session_data["total"] = total
        if message is not None:
            session_data["message"] = message
        
        # Calculate rate
        current_time = time.time()
        time_delta = current_time - self._last_update[tracking_key]
        
        if time_delta > 0 and current > old_current:
            rate = (current - old_current) / time_delta
            self._rate_history[tracking_key].append(rate)
        else:
            rate = 0.0
        
        self._last_update[tracking_key] = current_time
        
        # Calculate ETA
        eta = self._calculate_eta(tracking_key)
        
        # Emit progress event
        event = ProgressEvent(
            session_id=session_id,
            step_id=step_id,
            event_type=ProgressEventType.PROGRESS,
            timestamp=datetime.utcnow(),
            current=current,
            total=session_data["total"],
            unit=session_data["unit"],
            rate=rate,
            eta=eta,
            message=message,
            metadata=metadata or {}
        )
        
        self._emit_event(event)
    
    def complete_tracking(
        self,
        session_id: str,
        step_id: Optional[str] = None,
        message: Optional[str] = None
    ):
        """
        Mark tracking as completed.
        
        Args:
            session_id: Migration session ID
            step_id: Optional step ID
            message: Optional completion message
        """
        tracking_key = f"{session_id}:{step_id or 'session'}"
        
        if tracking_key not in self._sessions:
            return
        
        session_data = self._sessions[tracking_key]
        session_data["current"] = session_data["total"]
        
        # Emit completed event
        event = ProgressEvent(
            session_id=session_id,
            step_id=step_id,
            event_type=ProgressEventType.COMPLETED,
            timestamp=datetime.utcnow(),
            current=session_data["total"],
            total=session_data["total"],
            unit=session_data["unit"],
            message=message
        )
        
        self._emit_event(event)
    
    def fail_tracking(
        self,
        session_id: str,
        step_id: Optional[str] = None,
        message: Optional[str] = None,
        error: Optional[str] = None
    ):
        """
        Mark tracking as failed.
        
        Args:
            session_id: Migration session ID
            step_id: Optional step ID
            message: Optional failure message
            error: Optional error details
        """
        tracking_key = f"{session_id}:{step_id or 'session'}"
        
        if tracking_key not in self._sessions:
            return
        
        session_data = self._sessions[tracking_key]
        
        # Emit failed event
        event = ProgressEvent(
            session_id=session_id,
            step_id=step_id,
            event_type=ProgressEventType.FAILED,
            timestamp=datetime.utcnow(),
            current=session_data["current"],
            total=session_data["total"],
            unit=session_data["unit"],
            message=message,
            metadata={"error": error} if error else {}
        )
        
        self._emit_event(event)
    
    def pause_tracking(
        self,
        session_id: str,
        step_id: Optional[str] = None
    ):
        """
        Pause progress tracking.
        
        Args:
            session_id: Migration session ID
            step_id: Optional step ID
        """
        tracking_key = f"{session_id}:{step_id or 'session'}"
        
        if tracking_key not in self._sessions:
            return
        
        session_data = self._sessions[tracking_key]
        session_data["is_paused"] = True
        self._paused_sessions[tracking_key] = time.time()
        
        # Emit paused event
        event = ProgressEvent(
            session_id=session_id,
            step_id=step_id,
            event_type=ProgressEventType.PAUSED,
            timestamp=datetime.utcnow(),
            current=session_data["current"],
            total=session_data["total"],
            unit=session_data["unit"]
        )
        
        self._emit_event(event)
    
    def resume_tracking(
        self,
        session_id: str,
        step_id: Optional[str] = None
    ):
        """
        Resume paused progress tracking.
        
        Args:
            session_id: Migration session ID
            step_id: Optional step ID
        """
        tracking_key = f"{session_id}:{step_id or 'session'}"
        
        if tracking_key not in self._sessions:
            return
        
        session_data = self._sessions[tracking_key]
        
        if session_data.get("is_paused", False):
            # Add paused time to total paused time
            pause_duration = time.time() - self._paused_sessions.get(tracking_key, time.time())
            session_data["paused_time"] += pause_duration
            session_data["is_paused"] = False
            
            if tracking_key in self._paused_sessions:
                del self._paused_sessions[tracking_key]
            
            # Reset last update time
            self._last_update[tracking_key] = time.time()
            
            # Emit resumed event
            event = ProgressEvent(
                session_id=session_id,
                step_id=step_id,
                event_type=ProgressEventType.RESUMED,
                timestamp=datetime.utcnow(),
                current=session_data["current"],
                total=session_data["total"],
                unit=session_data["unit"]
            )
            
            self._emit_event(event)
    
    def cancel_tracking(
        self,
        session_id: str,
        step_id: Optional[str] = None,
        message: Optional[str] = None
    ):
        """
        Cancel progress tracking.
        
        Args:
            session_id: Migration session ID
            step_id: Optional step ID
            message: Optional cancellation message
        """
        tracking_key = f"{session_id}:{step_id or 'session'}"
        
        if tracking_key not in self._sessions:
            return
        
        session_data = self._sessions[tracking_key]
        
        # Emit cancelled event
        event = ProgressEvent(
            session_id=session_id,
            step_id=step_id,
            event_type=ProgressEventType.CANCELLED,
            timestamp=datetime.utcnow(),
            current=session_data["current"],
            total=session_data["total"],
            unit=session_data["unit"],
            message=message
        )
        
        self._emit_event(event)
        
        # Clean up tracking data
        self._cleanup_tracking(tracking_key)
    
    def get_progress_metrics(
        self,
        session_id: str,
        step_id: Optional[str] = None
    ) -> Optional[ProgressMetrics]:
        """
        Get current progress metrics.
        
        Args:
            session_id: Migration session ID
            step_id: Optional step ID
            
        Returns:
            Progress metrics or None if not found
        """
        tracking_key = f"{session_id}:{step_id or 'session'}"
        
        if tracking_key not in self._sessions:
            return None
        
        session_data = self._sessions[tracking_key]
        current_time = time.time()
        
        # Calculate elapsed time (excluding paused time)
        elapsed_time = current_time - session_data["start_time"] - session_data["paused_time"]
        if session_data.get("is_paused", False):
            pause_start = self._paused_sessions.get(tracking_key, current_time)
            elapsed_time -= (current_time - pause_start)
        
        # Calculate completion percentage
        completion_percentage = 0.0
        if session_data["total"] > 0:
            completion_percentage = (session_data["current"] / session_data["total"]) * 100
        
        # Calculate rates
        rate_history = list(self._rate_history.get(tracking_key, []))
        average_rate = sum(rate_history) / len(rate_history) if rate_history else 0.0
        current_rate = rate_history[-1] if rate_history else 0.0
        peak_rate = max(rate_history) if rate_history else 0.0
        min_rate = min(rate_history) if rate_history else 0.0
        
        # Calculate ETA
        eta_seconds = self._calculate_eta(tracking_key)
        
        return ProgressMetrics(
            session_id=session_id,
            step_id=step_id,
            start_time=datetime.fromtimestamp(session_data["start_time"]),
            current_time=datetime.fromtimestamp(current_time),
            elapsed_time=elapsed_time,
            current_progress=session_data["current"],
            total_progress=session_data["total"],
            completion_percentage=completion_percentage,
            average_rate=average_rate,
            current_rate=current_rate,
            eta_seconds=eta_seconds,
            peak_rate=peak_rate,
            min_rate=min_rate,
            rate_history=rate_history,
            throughput_history=self._get_throughput_history(tracking_key)
        )
    
    def get_all_active_sessions(self) -> List[str]:
        """Get list of all active session IDs."""
        session_ids = set()
        for tracking_key in self._sessions.keys():
            session_id = tracking_key.split(":")[0]
            session_ids.add(session_id)
        return list(session_ids)
    
    def cleanup_session(self, session_id: str):
        """Clean up all tracking data for a session."""
        keys_to_remove = [key for key in self._sessions.keys() if key.startswith(f"{session_id}:")]
        
        for key in keys_to_remove:
            self._cleanup_tracking(key)
    
    def _calculate_eta(self, tracking_key: str) -> Optional[int]:
        """Calculate estimated time to completion."""
        session_data = self._sessions[tracking_key]
        rate_history = self._rate_history.get(tracking_key, deque())
        
        if not rate_history or session_data["current"] >= session_data["total"]:
            return None
        
        remaining = session_data["total"] - session_data["current"]
        
        # Use average of recent rates for ETA calculation
        recent_rates = list(rate_history)[-10:]  # Last 10 samples
        if not recent_rates:
            return None
        
        avg_rate = sum(recent_rates) / len(recent_rates)
        if avg_rate <= 0:
            return None
        
        eta_seconds = remaining / avg_rate
        return int(eta_seconds)
    
    def _get_throughput_history(self, tracking_key: str) -> List[Dict[str, Any]]:
        """Get throughput history for analysis."""
        session_data = self._sessions[tracking_key]
        rate_history = list(self._rate_history.get(tracking_key, []))
        
        history = []
        current_time = time.time()
        
        for i, rate in enumerate(rate_history):
            timestamp = current_time - (len(rate_history) - i - 1)
            history.append({
                "timestamp": datetime.fromtimestamp(timestamp).isoformat(),
                "rate": rate,
                "unit": session_data["unit"].value
            })
        
        return history
    
    def _emit_event(self, event: ProgressEvent):
        """Emit progress event to all callbacks."""
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                # Log callback errors but don't fail the tracking
                print(f"Progress callback error: {e}")
    
    def _cleanup_tracking(self, tracking_key: str):
        """Clean up tracking data for a specific key."""
        if tracking_key in self._sessions:
            del self._sessions[tracking_key]
        if tracking_key in self._rate_history:
            del self._rate_history[tracking_key]
        if tracking_key in self._last_update:
            del self._last_update[tracking_key]
        if tracking_key in self._paused_sessions:
            del self._paused_sessions[tracking_key]


class SessionProgressTracker:
    """
    High-level progress tracker for migration sessions.
    
    Integrates with MigrationSession objects to provide automatic
    progress tracking and reporting.
    """
    
    def __init__(self, progress_tracker: ProgressTracker):
        """
        Initialize session progress tracker.
        
        Args:
            progress_tracker: Underlying progress tracker instance
        """
        self.progress_tracker = progress_tracker
        self._session_callbacks: Dict[str, List[Callable]] = {}
    
    def track_session(
        self,
        session: MigrationSession,
        callback: Optional[Callable[[ProgressEvent], None]] = None
    ):
        """
        Start tracking a migration session.
        
        Args:
            session: Migration session to track
            callback: Optional progress callback
        """
        # Start session-level tracking
        total_steps = len(session.steps)
        self.progress_tracker.start_tracking(
            session.id,
            total=total_steps,
            unit=ProgressUnit.OPERATIONS,
            message=f"Migration: {session.config.name}"
        )
        
        # Add callback if provided
        if callback:
            if session.id not in self._session_callbacks:
                self._session_callbacks[session.id] = []
            self._session_callbacks[session.id].append(callback)
            self.progress_tracker.add_callback(callback)
    
    def update_session_progress(self, session: MigrationSession):
        """Update session progress based on completed steps."""
        completed_steps = sum(
            1 for step in session.steps 
            if step.status.value in ["completed", "skipped"]
        )
        
        self.progress_tracker.update_progress(
            session.id,
            current=completed_steps,
            message=f"Completed {completed_steps}/{len(session.steps)} steps"
        )
    
    def track_step(
        self,
        session: MigrationSession,
        step: MigrationStep,
        total: int = 100,
        unit: ProgressUnit = ProgressUnit.ITEMS
    ):
        """
        Start tracking a migration step.
        
        Args:
            session: Migration session
            step: Migration step to track
            total: Total units for the step
            unit: Unit of measurement
        """
        self.progress_tracker.start_tracking(
            session.id,
            step_id=step.id,
            total=total,
            unit=unit,
            message=step.name
        )
    
    def complete_session(self, session: MigrationSession):
        """Mark session tracking as completed."""
        self.progress_tracker.complete_tracking(
            session.id,
            message=f"Migration completed: {session.config.name}"
        )
        
        # Clean up callbacks
        if session.id in self._session_callbacks:
            for callback in self._session_callbacks[session.id]:
                self.progress_tracker.remove_callback(callback)
            del self._session_callbacks[session.id]
        
        # Clean up session tracking data
        self.progress_tracker.cleanup_session(session.id)
    
    def fail_session(self, session: MigrationSession, error: str):
        """Mark session tracking as failed."""
        self.progress_tracker.fail_tracking(
            session.id,
            message=f"Migration failed: {session.config.name}",
            error=error
        )
        
        # Clean up callbacks
        if session.id in self._session_callbacks:
            for callback in self._session_callbacks[session.id]:
                self.progress_tracker.remove_callback(callback)
            del self._session_callbacks[session.id]
        
        # Clean up session tracking data
        self.progress_tracker.cleanup_session(session.id)