 """Background task management for long-running NEURON simulations."""
from asyncio import Task, CancelledError
from typing import Dict, Optional, Any, Union
import asyncio
import time
import logging

# Configure logging
logger = logging.getLogger(__name__)

class SimulationTaskManager:
    """Manages long-running simulation tasks."""
    
    def __init__(self, default_timeout: float = 3600):  # 1 hour default timeout
        self._tasks: Dict[str, Task] = {}
        self._progress: Dict[str, float] = {}
        self._cancel_events: Dict[str, asyncio.Event] = {}
        self._start_times: Dict[str, float] = {}
        self._timeouts: Dict[str, float] = {}
        self._results: Dict[str, any] = {}
        self._errors: Dict[str, str] = {}
        self.default_timeout = default_timeout
        
    def register_task(self, sim_id: str, task: Task, timeout: Optional[float] = None) -> None:
        """Register a new simulation task with optional timeout in seconds."""
        self._tasks[sim_id] = task
        self._progress[sim_id] = 0.0
        self._cancel_events[sim_id] = asyncio.Event()
        self._start_times[sim_id] = time.time()
        self._timeouts[sim_id] = timeout or self.default_timeout
        
    def update_progress(self, sim_id: str, progress: float) -> None:
        """Update simulation progress (0-100)."""
        self._progress[sim_id] = min(max(progress, 0.0), 100.0)  # Clamp between 0-100
        
    def get_progress(self, sim_id: str) -> float:
        """Get current simulation progress."""
        return self._progress.get(sim_id, 0.0)
        
    def get_elapsed_time(self, sim_id: str) -> Optional[float]:
        """Get elapsed time in seconds for a task."""
        start_time = self._start_times.get(sim_id)
        if start_time is None:
            return None
        return time.time() - start_time
        
    def is_timed_out(self, sim_id: str) -> bool:
        """Check if task has exceeded its timeout."""
        elapsed = self.get_elapsed_time(sim_id)
        if elapsed is None:
            return False
        return elapsed > self._timeouts.get(sim_id, self.default_timeout)
        
    def store_result(self, sim_id: str, result: any) -> None:
        """Store task result."""
        self._results[sim_id] = result
        
    def get_result(self, sim_id: str) -> Optional[any]:
        """Get stored task result."""
        return self._results.get(sim_id)
        
    def store_error(self, sim_id: str, error: str) -> None:
        """Store task error."""
        self._errors[sim_id] = error
        
    def get_error(self, sim_id: str) -> Optional[str]:
        """Get stored task error."""
        return self._errors.get(sim_id)
        
    async def cancel_task(self, sim_id: str) -> bool:
        """Cancel a running simulation."""
        if sim_id not in self._tasks:
            return False
            
        self._cancel_events[sim_id].set()
        task = self._tasks[sim_id]
        
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                self.store_error(sim_id, "Task cancelled by user")
            except Exception as e:
                self.store_error(sim_id, f"Error during cancellation: {str(e)}")
        
        self.cleanup_task(sim_id)
        return True
        
    def should_cancel(self, sim_id: str) -> bool:
        """Check if simulation should be cancelled."""
        # Check both explicit cancellation and timeout
        event = self._cancel_events.get(sim_id)
        is_cancelled = event and event.is_set()
        is_timeout = self.is_timed_out(sim_id)
        
        if is_timeout and not is_cancelled:
            # If timed out but not yet cancelled, mark for cancellation
            self._cancel_events[sim_id].set()
            self.store_error(sim_id, "Task timed out")
            
        return is_cancelled or is_timeout
        
    def cleanup_task(self, sim_id: str) -> None:
        """Clean up task resources."""
        try:
            # Store final progress before cleanup
            final_progress = self.get_progress(sim_id)
            
            # Clean up all task-related resources
            self._tasks.pop(sim_id, None)
            self._progress.pop(sim_id, None)
            self._cancel_events.pop(sim_id, None)
            self._start_times.pop(sim_id, None)
            self._timeouts.pop(sim_id, None)
            
            # Keep results and errors for history
            if sim_id in self._errors:
                # If there was an error, ensure progress reflects failure
                self._progress[sim_id] = final_progress
                
        except Exception as e:
            # Log cleanup error but don't raise
            print(f"Error during task cleanup for {sim_id}: {str(e)}")
            
    async def wait_for_task(self, sim_id: str, timeout: Optional[float] = None) -> bool:
        """Wait for task to complete with timeout."""
        if sim_id not in self._tasks:
            return False
            
        task = self._tasks[sim_id]
        try:
            if timeout is None:
                timeout = self._timeouts.get(sim_id, self.default_timeout)
                
            await asyncio.wait_for(task, timeout=timeout)
            return True
            
        except asyncio.TimeoutError:
            self.store_error(sim_id, f"Task timed out after {timeout} seconds")
            await self.cancel_task(sim_id)
            return False
            
        except Exception as e:
            self.store_error(sim_id, f"Task failed: {str(e)}")
            return False
