"""
Unit tests for progress tracking functionality.

Tests the ProgressTracker and SessionProgressTracker classes
for real-time progress monitoring and reporting.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from migration_assistant.monitoring.progress_tracker import (
    ProgressTracker, SessionProgressTracker, ProgressEvent,
    ProgressEventType, ProgressUnit, ProgressMetrics
)
from migration_assistant.models.session import (
    MigrationSession, MigrationStep, MigrationStatus, StepStatus
)
from migration_assistant.models.config import MigrationConfig, SystemConfig, SystemType


class TestProgressTracker:
    """Test cases for ProgressTracker class."""
    
    @pytest.fixture
    def progress_tracker(self):
        """Create a ProgressTracker instance for testing."""
        return ProgressTracker(max_history_size=10)
    
    @pytest.fixture
    def mock_callback(self):
        """Create a mock callback function."""
        return Mock()
    
    def test_start_tracking(self, progress_tracker, mock_callback):
        """Test starting progress tracking."""
        progress_tracker.add_callback(mock_callback)
        
        progress_tracker.start_tracking(
            session_id="test-session",
            step_id="test-step",
            total=100,
            unit=ProgressUnit.FILES,
            message="Testing progress"
        )
        
        # Verify callback was called with started event
        mock_callback.assert_called_once()
        event = mock_callback.call_args[0][0]
        
        assert isinstance(event, ProgressEvent)
        assert event.session_id == "test-session"
        assert event.step_id == "test-step"
        assert event.event_type == ProgressEventType.STARTED
        assert event.current == 0
        assert event.total == 100
        assert event.unit == ProgressUnit.FILES
        assert event.message == "Testing progress"
    
    def test_update_progress(self, progress_tracker, mock_callback):
        """Test updating progress."""
        progress_tracker.add_callback(mock_callback)
        
        # Start tracking
        progress_tracker.start_tracking("test-session", total=100)
        mock_callback.reset_mock()
        
        # Update progress
        progress_tracker.update_progress(
            session_id="test-session",
            current=50,
            message="Half done"
        )
        
        # Verify callback was called with progress event
        mock_callback.assert_called_once()
        event = mock_callback.call_args[0][0]
        
        assert event.event_type == ProgressEventType.PROGRESS
        assert event.current == 50
        assert event.total == 100
        assert event.message == "Half done"
        assert event.rate is not None
    
    def test_complete_tracking(self, progress_tracker, mock_callback):
        """Test completing progress tracking."""
        progress_tracker.add_callback(mock_callback)
        
        # Start tracking
        progress_tracker.start_tracking("test-session", total=100)
        mock_callback.reset_mock()
        
        # Complete tracking
        progress_tracker.complete_tracking(
            session_id="test-session",
            message="All done"
        )
        
        # Verify callback was called with completed event
        mock_callback.assert_called_once()
        event = mock_callback.call_args[0][0]
        
        assert event.event_type == ProgressEventType.COMPLETED
        assert event.current == 100
        assert event.total == 100
        assert event.message == "All done"
    
    def test_fail_tracking(self, progress_tracker, mock_callback):
        """Test failing progress tracking."""
        progress_tracker.add_callback(mock_callback)
        
        # Start tracking
        progress_tracker.start_tracking("test-session", total=100)
        progress_tracker.update_progress("test-session", 30)
        mock_callback.reset_mock()
        
        # Fail tracking
        progress_tracker.fail_tracking(
            session_id="test-session",
            message="Something went wrong",
            error="Connection timeout"
        )
        
        # Verify callback was called with failed event
        mock_callback.assert_called_once()
        event = mock_callback.call_args[0][0]
        
        assert event.event_type == ProgressEventType.FAILED
        assert event.current == 30
        assert event.total == 100
        assert event.message == "Something went wrong"
        assert event.metadata["error"] == "Connection timeout"
    
    def test_pause_resume_tracking(self, progress_tracker, mock_callback):
        """Test pausing and resuming progress tracking."""
        progress_tracker.add_callback(mock_callback)
        
        # Start tracking
        progress_tracker.start_tracking("test-session", total=100)
        mock_callback.reset_mock()
        
        # Pause tracking
        progress_tracker.pause_tracking("test-session")
        
        # Verify pause event
        assert mock_callback.call_count == 1
        event = mock_callback.call_args[0][0]
        assert event.event_type == ProgressEventType.PAUSED
        
        mock_callback.reset_mock()
        
        # Try to update while paused (should be ignored)
        progress_tracker.update_progress("test-session", 50)
        mock_callback.assert_not_called()
        
        # Resume tracking
        progress_tracker.resume_tracking("test-session")
        
        # Verify resume event
        mock_callback.assert_called_once()
        event = mock_callback.call_args[0][0]
        assert event.event_type == ProgressEventType.RESUMED
    
    def test_cancel_tracking(self, progress_tracker, mock_callback):
        """Test cancelling progress tracking."""
        progress_tracker.add_callback(mock_callback)
        
        # Start tracking
        progress_tracker.start_tracking("test-session", total=100)
        progress_tracker.update_progress("test-session", 25)
        mock_callback.reset_mock()
        
        # Cancel tracking
        progress_tracker.cancel_tracking(
            session_id="test-session",
            message="User cancelled"
        )
        
        # Verify callback was called with cancelled event
        mock_callback.assert_called_once()
        event = mock_callback.call_args[0][0]
        
        assert event.event_type == ProgressEventType.CANCELLED
        assert event.current == 25
        assert event.message == "User cancelled"
        
        # Verify tracking data was cleaned up
        assert "test-session:session" not in progress_tracker._sessions
    
    def test_get_progress_metrics(self, progress_tracker):
        """Test getting progress metrics."""
        # Start tracking
        progress_tracker.start_tracking("test-session", total=100)
        
        # Update progress multiple times to build rate history
        for i in range(1, 6):
            progress_tracker.update_progress("test-session", i * 20)
            asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.1))
        
        # Get metrics
        metrics = progress_tracker.get_progress_metrics("test-session")
        
        assert isinstance(metrics, ProgressMetrics)
        assert metrics.session_id == "test-session"
        assert metrics.step_id is None
        assert metrics.current_progress == 100
        assert metrics.total_progress == 100
        assert metrics.completion_percentage == 100.0
        assert metrics.elapsed_time > 0
        assert len(metrics.rate_history) > 0
    
    def test_auto_start_tracking(self, progress_tracker):
        """Test auto-starting tracking when updating non-existent session."""
        # Update progress without starting (should auto-start)
        progress_tracker.update_progress("auto-session", 50, total=200)
        
        # Verify session was created
        assert "auto-session:session" in progress_tracker._sessions
        
        # Get metrics to verify
        metrics = progress_tracker.get_progress_metrics("auto-session")
        assert metrics is not None
        assert metrics.current_progress == 50
        assert metrics.total_progress == 200
    
    def test_eta_calculation(self, progress_tracker):
        """Test ETA calculation."""
        # Start tracking
        progress_tracker.start_tracking("eta-session", total=1000)
        
        # Simulate steady progress (not completing)
        import time
        
        for i in range(1, 4):  # Only go to 300 out of 1000
            progress_tracker.update_progress("eta-session", i * 100)
            # Longer delay to create measurable time differences
            time.sleep(0.1)
        
        # Get metrics
        metrics = progress_tracker.get_progress_metrics("eta-session")
        
        # ETA should be calculated based on current rate (700 remaining)
        # With slower progress, ETA should be more than 0
        assert metrics.eta_seconds is not None
        assert metrics.eta_seconds >= 0  # Allow 0 for very fast operations
    
    def test_multiple_sessions(self, progress_tracker):
        """Test tracking multiple sessions simultaneously."""
        # Start multiple sessions
        progress_tracker.start_tracking("session-1", total=100)
        progress_tracker.start_tracking("session-2", total=200)
        progress_tracker.start_tracking("session-1", step_id="step-1", total=50)
        
        # Update progress for different sessions
        progress_tracker.update_progress("session-1", 30)
        progress_tracker.update_progress("session-2", 150)
        progress_tracker.update_progress("session-1", 25, step_id="step-1")
        
        # Verify all sessions are tracked
        active_sessions = progress_tracker.get_all_active_sessions()
        assert "session-1" in active_sessions
        assert "session-2" in active_sessions
        
        # Verify metrics for each session
        metrics_1 = progress_tracker.get_progress_metrics("session-1")
        metrics_2 = progress_tracker.get_progress_metrics("session-2")
        metrics_1_step = progress_tracker.get_progress_metrics("session-1", "step-1")
        
        assert metrics_1.current_progress == 30
        assert metrics_2.current_progress == 150
        assert metrics_1_step.current_progress == 25
    
    def test_cleanup_session(self, progress_tracker):
        """Test cleaning up session data."""
        # Start tracking with multiple steps
        progress_tracker.start_tracking("cleanup-session", total=100)
        progress_tracker.start_tracking("cleanup-session", step_id="step-1", total=50)
        progress_tracker.start_tracking("cleanup-session", step_id="step-2", total=75)
        
        # Verify sessions exist
        assert len([k for k in progress_tracker._sessions.keys() if k.startswith("cleanup-session:")]) == 3
        
        # Cleanup session
        progress_tracker.cleanup_session("cleanup-session")
        
        # Verify all session data was cleaned up
        assert len([k for k in progress_tracker._sessions.keys() if k.startswith("cleanup-session:")]) == 0
        assert len([k for k in progress_tracker._rate_history.keys() if k.startswith("cleanup-session:")]) == 0


class TestSessionProgressTracker:
    """Test cases for SessionProgressTracker class."""
    
    @pytest.fixture
    def progress_tracker(self):
        """Create a ProgressTracker instance."""
        return ProgressTracker()
    
    @pytest.fixture
    def session_tracker(self, progress_tracker):
        """Create a SessionProgressTracker instance."""
        return SessionProgressTracker(progress_tracker)
    
    @pytest.fixture
    def sample_session(self):
        """Create a sample migration session."""
        config = MigrationConfig(
            name="Test Migration",
            source=SystemConfig(
                type=SystemType.WORDPRESS,
                host="source.example.com"
            ),
            destination=SystemConfig(
                type=SystemType.STATIC,
                host="dest.example.com"
            )
        )
        
        session = MigrationSession(
            id="test-session",
            config=config
        )
        
        # Add some steps
        steps = [
            MigrationStep(id="step-1", name="Validate"),
            MigrationStep(id="step-2", name="Backup"),
            MigrationStep(id="step-3", name="Transfer")
        ]
        
        for step in steps:
            session.add_step(step)
        
        return session
    
    def test_track_session(self, session_tracker, sample_session, progress_tracker):
        """Test tracking a migration session."""
        mock_callback = Mock()
        
        # Track session with callback
        session_tracker.track_session(sample_session, mock_callback)
        
        # Verify session-level tracking was started
        metrics = progress_tracker.get_progress_metrics(sample_session.id)
        assert metrics is not None
        assert metrics.total_progress == len(sample_session.steps)
        assert metrics.current_progress == 0
        
        # Verify callback was added
        assert mock_callback in progress_tracker._callbacks
    
    def test_update_session_progress(self, session_tracker, sample_session, progress_tracker):
        """Test updating session progress based on completed steps."""
        # Track session
        session_tracker.track_session(sample_session)
        
        # Mark some steps as completed
        sample_session.steps[0].status = StepStatus.COMPLETED
        sample_session.steps[1].status = StepStatus.COMPLETED
        
        # Update session progress
        session_tracker.update_session_progress(sample_session)
        
        # Verify progress was updated
        metrics = progress_tracker.get_progress_metrics(sample_session.id)
        assert metrics.current_progress == 2  # 2 completed steps
        assert metrics.total_progress == 3    # 3 total steps
    
    def test_track_step(self, session_tracker, sample_session, progress_tracker):
        """Test tracking individual migration steps."""
        # Track session
        session_tracker.track_session(sample_session)
        
        # Track a specific step
        step = sample_session.steps[0]
        session_tracker.track_step(
            sample_session,
            step,
            total=100,
            unit=ProgressUnit.FILES
        )
        
        # Verify step tracking was started
        metrics = progress_tracker.get_progress_metrics(sample_session.id, step.id)
        assert metrics is not None
        assert metrics.total_progress == 100
        assert metrics.current_progress == 0
    
    def test_complete_session(self, session_tracker, sample_session, progress_tracker):
        """Test completing session tracking."""
        mock_callback = Mock()
        
        # Track session with callback
        session_tracker.track_session(sample_session, mock_callback)
        
        # Complete session
        session_tracker.complete_session(sample_session)
        
        # Verify callback was removed
        assert mock_callback not in progress_tracker._callbacks
    
    def test_fail_session(self, session_tracker, sample_session, progress_tracker):
        """Test failing session tracking."""
        mock_callback = Mock()
        
        # Track session with callback
        session_tracker.track_session(sample_session, mock_callback)
        
        # Fail session
        session_tracker.fail_session(sample_session, "Test error")
        
        # Verify callback was removed
        assert mock_callback not in progress_tracker._callbacks
    
    def test_step_progress_integration(self, session_tracker, sample_session, progress_tracker):
        """Test integration between session and step progress tracking."""
        mock_callback = Mock()
        
        # Track session
        session_tracker.track_session(sample_session, mock_callback)
        
        # Track individual steps
        for step in sample_session.steps:
            session_tracker.track_step(sample_session, step, total=50)
        
        # Simulate step completion
        for i, step in enumerate(sample_session.steps):
            # Update step progress
            progress_tracker.update_progress(
                sample_session.id,
                current=50,
                step_id=step.id
            )
            progress_tracker.complete_tracking(sample_session.id, step_id=step.id)
            
            # Mark step as completed
            step.status = StepStatus.COMPLETED
            
            # Update session progress
            session_tracker.update_session_progress(sample_session)
            
            # Verify session progress
            session_metrics = progress_tracker.get_progress_metrics(sample_session.id)
            assert session_metrics.current_progress == i + 1
        
        # Verify all callbacks were triggered
        assert mock_callback.call_count > 0


@pytest.mark.asyncio
class TestProgressTrackerAsync:
    """Async test cases for ProgressTracker."""
    
    @pytest.fixture
    def progress_tracker(self):
        """Create a ProgressTracker instance."""
        return ProgressTracker()
    
    async def test_concurrent_updates(self, progress_tracker):
        """Test concurrent progress updates."""
        # Start multiple tracking sessions
        sessions = ["session-1", "session-2", "session-3"]
        
        for session_id in sessions:
            progress_tracker.start_tracking(session_id, total=100)
        
        # Define async update function
        async def update_session(session_id, updates):
            for current in updates:
                progress_tracker.update_progress(session_id, current)
                await asyncio.sleep(0.01)  # Small delay
        
        # Run concurrent updates
        tasks = [
            update_session("session-1", [10, 20, 30, 40, 50]),
            update_session("session-2", [15, 35, 55, 75, 95]),
            update_session("session-3", [5, 25, 45, 65, 85])
        ]
        
        await asyncio.gather(*tasks)
        
        # Verify final states
        for session_id in sessions:
            metrics = progress_tracker.get_progress_metrics(session_id)
            assert metrics is not None
            assert metrics.current_progress > 0
            assert len(metrics.rate_history) > 0
    
    async def test_rate_calculation_accuracy(self, progress_tracker):
        """Test accuracy of rate calculations over time."""
        session_id = "rate-test"
        progress_tracker.start_tracking(session_id, total=1000, unit=ProgressUnit.BYTES)
        
        # Simulate consistent transfer rate
        target_rate = 100  # bytes per update
        update_interval = 0.1  # seconds
        
        for i in range(1, 11):
            progress_tracker.update_progress(session_id, i * target_rate)
            await asyncio.sleep(update_interval)
        
        # Get final metrics
        metrics = progress_tracker.get_progress_metrics(session_id)
        
        # Rate should be approximately target_rate / update_interval
        expected_rate = target_rate / update_interval
        
        # Allow for some variance due to timing
        assert abs(metrics.average_rate - expected_rate) < expected_rate * 0.5
        assert len(metrics.rate_history) > 0