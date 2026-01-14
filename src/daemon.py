"""Main daemon service for Claude Issue Solver."""

import logging
import signal
import sys
import time
import threading
from pathlib import Path
from typing import Optional

from .config import get_config
from .github_watcher import GitHubWatcher, IssueInfo
from .docker_manager import DockerManager
from .task_queue import TaskQueue, Task

logger = logging.getLogger(__name__)


class IssueSolverDaemon:
    """Main daemon service."""

    def __init__(self):
        """Initialize the daemon."""
        self.config = get_config()
        self.github = GitHubWatcher()
        self.docker = DockerManager()
        self.task_queue = TaskQueue(max_concurrent=self.config.max_concurrent)

        self._running = False
        self._shutdown_event = threading.Event()
        self._threads: list[threading.Thread] = []

        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()

    def _generate_prompt(self, issue: IssueInfo) -> str:
        """
        Generate Claude prompt based on issue tags.

        Args:
            issue: IssueInfo object.

        Returns:
            Prompt string.
        """
        if issue.has_implement_tag:
            # Implementation phase
            prompt = (
                f"Work on github issue {issue.number} following the rules in claude.md "
                f"and the github_issues skill. "
                f"Execute the plan that is provided in the issue, pay special attention "
                f"to any user comments provided in the issue."
            )
        else:
            # Planning phase
            prompt = (
                f"Work on github issue {issue.number} following the rules in claude.md "
                f"and the github_issues skill. "
                f"Check if the issue already contains a plan, if it does and there are "
                f"new user comments review and update the plan as a new comment then end "
                f"your session. "
                f"If there is no plan create one and upload it as a comment to the issue, "
                f"then end your session. "
                f"Ask any questions about the plan as a comment in the issue and exit."
            )

        return prompt

    def _monitor_container(self, task: Task):
        """
        Monitor a container until completion.

        Args:
            task: Task object.
        """
        try:
            if not task.container_id:
                return

            if self.config.dry_run:
                # In dry-run mode, simulate immediate completion
                logger.info(f"[DRY-RUN] Container for issue #{task.issue_number} would complete")
                self.task_queue.mark_completed(task.issue_number)
                return

            # Wait for container to finish
            container = self.docker.client.containers.get(task.container_id)
            result = container.wait()

            exit_code = result.get("StatusCode", -1)

            if exit_code == 0:
                logger.info(f"Container for issue #{task.issue_number} completed successfully")
                self.task_queue.mark_completed(task.issue_number)
            else:
                error = f"Container exited with code {exit_code}"
                logger.error(f"Container for issue #{task.issue_number} failed: {error}")
                self.task_queue.mark_completed(task.issue_number, error=error)

        except Exception as e:
            logger.error(f"Error monitoring container: {e}")
            self.task_queue.mark_completed(task.issue_number, error=str(e))

        finally:
            # Cleanup worktree
            if task.worktree_path:
                try:
                    self.docker.remove_worktree(task.issue_number)
                except Exception as e:
                    logger.error(f"Failed to remove worktree: {e}")

    def _process_tasks(self):
        """Process tasks from the queue."""
        while self._running:
            try:
                # Get next task if capacity allows
                task = self.task_queue.get_next_task()

                if task is None:
                    time.sleep(1)
                    continue

                logger.info(f"Processing task for issue #{task.issue_number}")

                # Create worktree
                worktree_path = self.docker.create_worktree(task.issue_number)

                # Generate prompt
                issue_info = IssueInfo.__new__(IssueInfo)
                issue_info.number = task.issue_number
                issue_info.title = task.issue_title
                issue_info.has_implement_tag = task.has_implement_tag

                prompt = self._generate_prompt(issue_info)

                # Start container
                container = self.docker.run_claude_container(
                    task.issue_number,
                    worktree_path,
                    prompt,
                )

                # Mark as running
                self.task_queue.mark_running(task, container.id, worktree_path)

                # Start monitoring thread
                monitor_thread = threading.Thread(
                    target=self._monitor_container,
                    args=(task,),
                    daemon=True,
                )
                monitor_thread.start()

            except Exception as e:
                logger.error(f"Error processing task: {e}")
                if task:
                    self.task_queue.mark_completed(task.issue_number, error=str(e))

            time.sleep(1)

    def _poll_issues(self):
        """Poll GitHub for new or updated issues."""
        while self._running:
            try:
                logger.info("Polling GitHub for issues...")

                issues = self.github.get_new_or_updated_issues()

                for issue in issues:
                    # Only add if not already running
                    if not self.task_queue.is_running(issue.number):
                        self.task_queue.add_task(issue)

                logger.info(f"Poll complete, found {len(issues)} new/updated issues")

            except Exception as e:
                logger.error(f"Error polling issues: {e}")

            # Wait for next poll interval
            self._shutdown_event.wait(timeout=self.config.poll_interval)

    def _save_state_periodically(self):
        """Periodically save daemon state."""
        while self._running:
            try:
                self.task_queue.save_state(self.config.state_file)
            except Exception as e:
                logger.error(f"Error saving state: {e}")

            # Save every minute
            self._shutdown_event.wait(timeout=60)

    def start(self):
        """Start the daemon."""
        if self.config.dry_run:
            logger.info("Starting Claude Issue Solver daemon in DRY-RUN mode")
        else:
            logger.info("Starting Claude Issue Solver daemon")

        # Write PID file
        self.config.pid_file.write_text(str(sys.modules['os'].getpid()))

        # Ensure repository is ready
        logger.info("Ensuring repository is ready...")
        repo_path = self.docker.repo_manager.ensure_repository()
        logger.info(f"Repository ready at: {repo_path}")

        # Connect to services
        self.github.connect()
        self.docker.connect()

        # Load previous state
        self.task_queue.load_state(self.config.state_file)

        # Build Docker image if needed
        dev_dockerfile = repo_path / "Dockerfile"
        if dev_dockerfile.exists():
            logger.info("Building Docker image...")
            self.docker.build_image(dev_dockerfile)
        else:
            logger.warning(f"Development Dockerfile not found: {dev_dockerfile}")

        # Start background threads
        self._running = True

        poll_thread = threading.Thread(target=self._poll_issues, daemon=True)
        poll_thread.start()
        self._threads.append(poll_thread)

        process_thread = threading.Thread(target=self._process_tasks, daemon=True)
        process_thread.start()
        self._threads.append(process_thread)

        state_thread = threading.Thread(target=self._save_state_periodically, daemon=True)
        state_thread.start()
        self._threads.append(state_thread)

        logger.info("Daemon started successfully")

        # Do initial poll
        try:
            issues = self.github.get_claude_issues()
            for issue in issues:
                self.task_queue.add_task(issue)
        except Exception as e:
            logger.error(f"Error in initial poll: {e}")

        # Wait for shutdown
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def run_once(self):
        """Run through all issues once and exit."""
        if self.config.dry_run:
            logger.info("Running ONE-TIME mode (DRY-RUN)")
        else:
            logger.info("Running ONE-TIME mode")

        # Ensure repository is ready
        logger.info("Ensuring repository is ready...")
        repo_path = self.docker.repo_manager.ensure_repository()
        logger.info(f"Repository ready at: {repo_path}")

        # Connect to services
        self.github.connect()
        self.docker.connect()

        # Build Docker image if needed
        dev_dockerfile = repo_path / "Dockerfile"
        if dev_dockerfile.exists():
            logger.info("Building Docker image...")
            self.docker.build_image(dev_dockerfile)
        else:
            logger.warning(f"Development Dockerfile not found: {dev_dockerfile}")

        # Get all Claude-tagged issues
        logger.info("Fetching Claude-tagged issues...")
        issues = self.github.get_claude_issues()
        logger.info(f"Found {len(issues)} Claude-tagged issues")

        if not issues:
            logger.info("No issues to process")
            self.github.close()
            self.docker.close()
            return

        # Process each issue
        for issue in issues:
            logger.info(f"Processing issue #{issue.number}: {issue.title}")
            logger.info(f"  - Has 'Implement' tag: {issue.has_implement_tag}")
            logger.info(f"  - URL: {issue.url}")

            try:
                # Create worktree
                worktree_path = self.docker.create_worktree(issue.number)
                logger.info(f"  - Worktree: {worktree_path}")

                # Generate prompt
                prompt = self._generate_prompt(issue)
                logger.info(f"  - Prompt: {prompt[:100]}...")

                # Start container (keep it for debugging in one-time mode)
                container = self.docker.run_claude_container(
                    issue.number,
                    worktree_path,
                    prompt,
                    keep_container=True,  # Keep container for debugging
                    github_token=self.github.get_token(),  # Pass GitHub token for gh CLI
                )
                logger.info(f"  - Container ID: {container.id}")
                logger.info(f"  - Container kept for debugging (use 'docker logs {container.id[:12]}' to view output)")

                if not self.config.dry_run:
                    # Wait for container to complete
                    logger.info(f"  - Waiting for container to complete...")
                    result = container.wait()
                    exit_code = result.get("StatusCode", -1)

                    if exit_code == 0:
                        logger.info(f"  - Container completed successfully")
                    else:
                        logger.error(f"  - Container exited with code {exit_code}")

                    # Get container logs (container is kept, so we can get logs)
                    try:
                        logs = container.logs().decode('utf-8', errors='replace')
                        if logs:
                            logger.info(f"  - Container output:\n{logs[-2000:]}")
                    except Exception as e:
                        logger.warning(f"  - Could not get container logs: {e}")

                    # Don't cleanup worktree in one-time mode to allow inspection
                    logger.info(f"  - Worktree kept at: {worktree_path}")
                else:
                    logger.info(f"  - [DRY-RUN] Would wait for container and cleanup")

            except Exception as e:
                logger.error(f"  - Error processing issue #{issue.number}: {e}")

        # Cleanup
        logger.info("One-time run complete")
        self.github.close()
        self.docker.close()

    def stop(self):
        """Stop the daemon."""
        if not self._running:
            return

        logger.info("Stopping daemon...")
        self._running = False
        self._shutdown_event.set()

        # Wait for threads to finish
        for thread in self._threads:
            thread.join(timeout=5)

        # Save final state
        self.task_queue.save_state(self.config.state_file)

        # Cleanup
        self.github.close()
        self.docker.close()

        # Remove PID file
        if self.config.pid_file.exists():
            self.config.pid_file.unlink()

        logger.info("Daemon stopped")

    def get_status(self) -> dict:
        """Get daemon status."""
        return {
            "running": self._running,
            "queue": self.task_queue.get_status(),
            "tasks": {
                "running": [
                    {
                        "issue": t.issue_number,
                        "title": t.issue_title,
                        "started_at": t.started_at,
                    }
                    for t in self.task_queue.get_running_tasks()
                ],
                "queued": [
                    {
                        "issue": t.issue_number,
                        "title": t.issue_title,
                    }
                    for t in self.task_queue.get_queued_tasks()
                ],
                "completed": [
                    {
                        "issue": t.issue_number,
                        "title": t.issue_title,
                        "status": t.status.value,
                        "completed_at": t.completed_at,
                    }
                    for t in self.task_queue.get_completed_tasks()
                ],
            },
        }
