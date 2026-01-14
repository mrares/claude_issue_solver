"""Task queue and scheduler for managing Claude instances."""

import logging
import threading
import queue
import json
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from enum import Enum

from .github_watcher import IssueInfo
from .docker_manager import DockerManager

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    """Represents a task to process an issue."""
    issue_number: int
    issue_title: str
    has_implement_tag: bool
    status: TaskStatus = TaskStatus.PENDING
    container_id: Optional[str] = None
    worktree_path: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['status'] = self.status.value
        return data

    @staticmethod
    def from_dict(data: dict) -> 'Task':
        """Create Task from dictionary."""
        data['status'] = TaskStatus(data['status'])
        return Task(**data)


class TaskQueue:
    """Manages task queue and execution."""

    def __init__(self, max_concurrent: int = 3):
        """
        Initialize task queue.

        Args:
            max_concurrent: Maximum number of concurrent tasks.
        """
        self.max_concurrent = max_concurrent
        self._queue: queue.Queue = queue.Queue()
        self._running: Dict[int, Task] = {}  # issue_number -> Task
        self._completed: List[Task] = []
        self._lock = threading.RLock()
        self._paused = False

    def add_task(self, issue: IssueInfo) -> bool:
        """
        Add a task to the queue.

        Args:
            issue: IssueInfo object.

        Returns:
            True if task was added, False if already exists.
        """
        with self._lock:
            # Check if already running or queued
            if issue.number in self._running:
                logger.info(f"Issue #{issue.number} is already running")
                return False

            # Check if in queue
            for task in list(self._queue.queue):
                if task.issue_number == issue.number:
                    logger.info(f"Issue #{issue.number} is already queued")
                    return False

            task = Task(
                issue_number=issue.number,
                issue_title=issue.title,
                has_implement_tag=issue.has_implement_tag,
            )

            self._queue.put(task)
            logger.info(f"Added task for issue #{issue.number} to queue")
            return True

    def get_next_task(self) -> Optional[Task]:
        """
        Get the next task to execute if capacity allows.

        Returns:
            Task object or None.
        """
        with self._lock:
            if self._paused:
                return None

            if len(self._running) >= self.max_concurrent:
                return None

            try:
                task = self._queue.get_nowait()
                return task
            except queue.Empty:
                return None

    def mark_running(self, task: Task, container_id: str, worktree_path: Path):
        """
        Mark a task as running.

        Args:
            task: Task object.
            container_id: Docker container ID.
            worktree_path: Path to worktree.
        """
        with self._lock:
            task.status = TaskStatus.RUNNING
            task.container_id = container_id
            task.worktree_path = str(worktree_path)
            task.started_at = datetime.now(timezone.utc).isoformat()
            self._running[task.issue_number] = task
            logger.info(f"Marked task #{task.issue_number} as running")

    def mark_completed(self, issue_number: int, error: Optional[str] = None):
        """
        Mark a task as completed.

        Args:
            issue_number: Issue number.
            error: Error message if failed.
        """
        with self._lock:
            if issue_number not in self._running:
                logger.warning(f"Task #{issue_number} not in running tasks")
                return

            task = self._running.pop(issue_number)
            task.completed_at = datetime.now(timezone.utc).isoformat()

            if error:
                task.status = TaskStatus.FAILED
                task.error = error
                logger.error(f"Task #{issue_number} failed: {error}")
            else:
                task.status = TaskStatus.COMPLETED
                logger.info(f"Task #{issue_number} completed successfully")

            self._completed.append(task)

            # Keep only last 100 completed tasks
            if len(self._completed) > 100:
                self._completed = self._completed[-100:]

    def get_running_tasks(self) -> List[Task]:
        """Get list of currently running tasks."""
        with self._lock:
            return list(self._running.values())

    def get_queued_tasks(self) -> List[Task]:
        """Get list of queued tasks."""
        with self._lock:
            return list(self._queue.queue)

    def get_completed_tasks(self, limit: int = 20) -> List[Task]:
        """Get list of completed tasks."""
        with self._lock:
            return self._completed[-limit:]

    def is_running(self, issue_number: int) -> bool:
        """Check if a task is currently running."""
        with self._lock:
            return issue_number in self._running

    def pause(self):
        """Pause task execution."""
        with self._lock:
            self._paused = True
            logger.info("Task queue paused")

    def resume(self):
        """Resume task execution."""
        with self._lock:
            self._paused = False
            logger.info("Task queue resumed")

    def is_paused(self) -> bool:
        """Check if queue is paused."""
        with self._lock:
            return self._paused

    def get_status(self) -> dict:
        """Get queue status."""
        with self._lock:
            return {
                "paused": self._paused,
                "running": len(self._running),
                "queued": self._queue.qsize(),
                "max_concurrent": self.max_concurrent,
            }

    def save_state(self, file_path: Path):
        """
        Save queue state to file.

        Args:
            file_path: Path to save state.
        """
        with self._lock:
            state = {
                "paused": self._paused,
                "running": [task.to_dict() for task in self._running.values()],
                "queued": [task.to_dict() for task in self._queue.queue],
                "completed": [task.to_dict() for task in self._completed[-20:]],
            }

            try:
                with open(file_path, "w") as f:
                    json.dump(state, f, indent=2)
                logger.debug(f"Saved state to {file_path}")
            except Exception as e:
                logger.error(f"Failed to save state: {e}")

    def load_state(self, file_path: Path):
        """
        Load queue state from file.

        Args:
            file_path: Path to load state from.
        """
        if not file_path.exists():
            return

        try:
            with open(file_path, "r") as f:
                state = json.load(f)

            with self._lock:
                self._paused = state.get("paused", False)

                # Load completed tasks
                self._completed = [
                    Task.from_dict(task) for task in state.get("completed", [])
                ]

                logger.info(f"Loaded state from {file_path}")

        except Exception as e:
            logger.error(f"Failed to load state: {e}")
