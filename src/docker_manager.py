"""Docker container management for Claude instances."""

import logging
import subprocess
import shutil
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional, Dict, Any
import docker
from docker.models.containers import Container
from docker.models.images import Image
from docker.errors import DockerException, ImageNotFound, APIError

from .config import get_config
from .repo_manager import RepositoryManager, run_git_command

logger = logging.getLogger(__name__)

CLAUDE_INSTALL_URL = "https://claude.ai/install.sh"


class DockerManager:
    """Manages Docker containers for Claude instances."""

    def __init__(self):
        """Initialize Docker manager."""
        self.config = get_config()
        self.client: Optional[docker.DockerClient] = None
        self.image_name = "claude-issue-solver"
        self.image_tag = "latest"
        self.repo_manager = RepositoryManager()

    def connect(self):
        """Connect to Docker daemon."""
        if self.config.dry_run:
            logger.info("[DRY-RUN] Would connect to Docker daemon")
            return

        try:
            self.client = docker.from_env()
            self.client.ping()
            logger.info("Connected to Docker daemon")
        except DockerException as e:
            logger.error(f"Failed to connect to Docker: {e}")
            raise

    def _download_claude_install_script(self, target_path: Path):
        """
        Download the Claude install script locally.

        Args:
            target_path: Where to save the install script.
        """
        logger.info(f"Downloading Claude install script from {CLAUDE_INSTALL_URL}")
        print(f"  Downloading {CLAUDE_INSTALL_URL}...", flush=True)

        try:
            urllib.request.urlretrieve(CLAUDE_INSTALL_URL, target_path)
            print(f"  Saved to {target_path}", flush=True)
            logger.info(f"Downloaded Claude install script to {target_path}")
        except Exception as e:
            logger.error(f"Failed to download Claude install script: {e}")
            raise RuntimeError(f"Failed to download Claude install script: {e}")

    def _stream_build_output(self, build_logs):
        """
        Stream Docker build logs to stdout.

        Args:
            build_logs: Generator of build log entries.

        Returns:
            The final image from the build.
        """
        image = None
        for log in build_logs:
            if 'stream' in log:
                line = log['stream'].rstrip()
                if line:
                    print(f"  {line}", flush=True)
            elif 'status' in log:
                # Progress updates (e.g., pulling layers)
                status = log.get('status', '')
                progress = log.get('progress', '')
                if progress:
                    print(f"  {status}: {progress}", flush=True)
                elif status:
                    print(f"  {status}", flush=True)
            elif 'error' in log:
                error_msg = log['error']
                print(f"  ERROR: {error_msg}", flush=True)
                raise DockerException(error_msg)

            # Capture the image from the final log entry
            if 'aux' in log and 'ID' in log['aux']:
                image_id = log['aux']['ID']
                try:
                    image = self.client.images.get(image_id)
                except:
                    pass

        return image

    def build_image(self, dev_dockerfile_path: Path) -> str:
        """
        Build Claude-enabled Docker image from development Dockerfile.

        Args:
            dev_dockerfile_path: Path to the development Dockerfile.

        Returns:
            Image ID.
        """
        if self.config.dry_run:
            logger.info(f"[DRY-RUN] Would build development base image from {dev_dockerfile_path}")
            logger.info("[DRY-RUN] Would build Claude-enabled image")
            return "dry-run-image-id"

        if not self.client:
            raise RuntimeError("Not connected to Docker. Call connect() first.")

        if not dev_dockerfile_path.exists():
            raise FileNotFoundError(f"Development Dockerfile not found: {dev_dockerfile_path}")

        try:
            # First, build the development image as a base
            logger.info(f"Building development base image from {dev_dockerfile_path}")
            print(f"\n=== Building base development image ===", flush=True)

            # Build base development image
            dev_context = dev_dockerfile_path.parent

            # Use low-level API for streaming output
            resp = self.client.api.build(
                path=str(dev_context),
                dockerfile=str(dev_dockerfile_path.name),
                tag="dev-base:latest",
                rm=True,
                forcerm=True,
                decode=True,
            )

            self._stream_build_output(resp)

            # Get the built image
            base_image = self.client.images.get("dev-base:latest")
            logger.info(f"Built base development image: {base_image.id[:12]}")
            print(f"\n  Base image built: {base_image.id[:12]}", flush=True)

            # Download Claude install script before building Claude image
            claude_dockerfile_dir = Path(__file__).parent.parent
            install_script_path = claude_dockerfile_dir / "claude-install.sh"
            self._download_claude_install_script(install_script_path)

            # Now build Claude-enabled image
            claude_dockerfile = claude_dockerfile_dir / "Dockerfile.claude"

            logger.info("Building Claude-enabled image")
            print(f"\n=== Building Claude-enabled image ===", flush=True)

            # Use low-level API for streaming output
            resp = self.client.api.build(
                path=str(claude_dockerfile.parent),
                dockerfile=str(claude_dockerfile.name),
                tag=f"{self.image_name}:{self.image_tag}",
                rm=True,
                forcerm=True,
                buildargs={"DEV_DOCKERFILE_PATH": str(dev_dockerfile_path)},
                decode=True,
            )

            self._stream_build_output(resp)

            # Get the built image
            image = self.client.images.get(f"{self.image_name}:{self.image_tag}")
            logger.info(f"Built Claude image: {image.id[:12]}")
            print(f"\n  Claude image built: {image.id[:12]}", flush=True)

            # Cleanup install script
            if install_script_path.exists():
                install_script_path.unlink()

            return image.id

        except DockerException as e:
            logger.error(f"Failed to build Docker image: {e}")
            raise

    def create_worktree(self, issue_number: int) -> Path:
        """
        Create a Git worktree for an issue.

        Args:
            issue_number: GitHub issue number.

        Returns:
            Path to the worktree (absolute).
        """
        # Use absolute path for worktree to avoid issues with relative paths
        worktree_path = (self.config.worktree_base / f"issue-{issue_number}").resolve()

        if self.config.dry_run:
            logger.info(f"[DRY-RUN] Would pull latest from default branch")
            logger.info(f"[DRY-RUN] Would create worktree at: {worktree_path}")
            logger.info(f"[DRY-RUN] Would execute: git worktree add {worktree_path} -b issue-{issue_number}")
            return worktree_path

        # Ensure repository is up to date
        repo_path = self.repo_manager.get_repo_path()
        logger.info("Pulling latest changes before creating worktree...")
        self.repo_manager.pull_latest()

        # Remove if it already exists
        if worktree_path.exists():
            logger.warning(f"Worktree already exists, removing: {worktree_path}")
            self.remove_worktree(issue_number)

        try:
            branch_name = f"issue-{issue_number}"

            # Prune any stale worktree references
            try:
                run_git_command(
                    ["git", "worktree", "prune"],
                    cwd=repo_path,
                    show_output=False,
                )
            except subprocess.CalledProcessError:
                pass

            # Try to delete the branch if it exists (from a previous run)
            try:
                run_git_command(
                    ["git", "branch", "-D", branch_name],
                    cwd=repo_path,
                    show_output=False,
                )
                logger.info(f"Deleted existing branch: {branch_name}")
            except subprocess.CalledProcessError:
                # Branch doesn't exist, that's fine
                pass

            # Create worktree from latest default branch
            run_git_command(
                [
                    "git",
                    "worktree",
                    "add",
                    str(worktree_path),
                    "-b",
                    branch_name,
                ],
                cwd=repo_path,
            )
            logger.info(f"Created worktree: {worktree_path}")
            return worktree_path

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create worktree: {e.output}")
            raise

    def remove_worktree(self, issue_number: int):
        """
        Remove a Git worktree.

        Args:
            issue_number: GitHub issue number.
        """
        # Use absolute path for worktree to match create_worktree
        worktree_path = (self.config.worktree_base / f"issue-{issue_number}").resolve()

        if self.config.dry_run:
            logger.info(f"[DRY-RUN] Would remove worktree: {worktree_path}")
            logger.info(f"[DRY-RUN] Would execute: git worktree remove {worktree_path} --force")
            return

        repo_path = self.repo_manager.get_repo_path()

        try:
            # Remove worktree
            run_git_command(
                ["git", "worktree", "remove", str(worktree_path), "--force"],
                cwd=repo_path,
            )
            logger.info(f"Removed worktree: {worktree_path}")

        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to remove worktree: {e.output}")
            # Try to remove directory manually
            if worktree_path.exists():
                shutil.rmtree(worktree_path, ignore_errors=True)

    def run_claude_container(
        self,
        issue_number: int,
        worktree_path: Path,
        prompt: str,
        keep_container: bool = False,
        github_token: str = None,
    ) -> Container:
        """
        Run a Claude container for an issue.

        Args:
            issue_number: GitHub issue number.
            worktree_path: Path to the Git worktree.
            prompt: Prompt to pass to Claude.
            keep_container: If True, don't auto-remove container (for debugging).
            github_token: GitHub token for gh CLI authentication.

        Returns:
            Docker Container object.
        """
        container_name = f"claude-issue-{issue_number}"

        if self.config.dry_run:
            logger.info(f"[DRY-RUN] Would start Claude container: {container_name}")
            logger.info(f"[DRY-RUN] Image: {self.image_name}:{self.image_tag}")
            logger.info(f"[DRY-RUN] Worktree mount: {worktree_path} -> /workspace")
            logger.info(f"[DRY-RUN] Prompt: {prompt[:100]}...")
            logger.info(f"[DRY-RUN] Privileged: True")
            logger.info(f"[DRY-RUN] Auto-remove: {not keep_container}")
            # Return a mock container object
            class MockContainer:
                def __init__(self):
                    self.id = f"dry-run-{issue_number}"
                    self.status = "running"
                def wait(self):
                    return {"StatusCode": 0}
            return MockContainer()

        if not self.client:
            raise RuntimeError("Not connected to Docker. Call connect() first.")

        try:
            # Check if container already exists
            try:
                existing = self.client.containers.get(container_name)
                logger.warning(f"Container {container_name} already exists, removing")
                existing.remove(force=True)
            except docker.errors.NotFound:
                pass

            # Run container
            logger.info(f"Starting Claude container for issue #{issue_number}")

            # Docker requires absolute paths for volume mounts
            absolute_worktree_path = worktree_path.resolve()

            # Set up volume mounts
            volumes = {
                str(absolute_worktree_path): {
                    "bind": "/workspace",
                    "mode": "rw",
                }
            }

            # Set up environment variables
            environment = {}

            # Pass GitHub token for gh CLI authentication
            if github_token:
                environment["GH_TOKEN"] = github_token
                environment["GITHUB_TOKEN"] = github_token

            # If we have OAuth credentials JSON, write it to a temp file and mount it
            # This allows Claude CLI inside the container to authenticate via OAuth
            credentials_file = None
            if self.config.claude_credentials_json:
                # Create a temporary credentials file that will be mounted
                credentials_file = Path(tempfile.gettempdir()) / f"claude-creds-{issue_number}.json"
                credentials_file.write_text(self.config.claude_credentials_json)
                credentials_file.chmod(0o600)  # Secure permissions
                logger.info(f"Created credentials file for container: {credentials_file}")

                # Mount the credentials file to where Claude CLI expects it
                # Note: Container runs as 'claude' user, so mount to /home/claude/.claude/
                volumes[str(credentials_file)] = {
                    "bind": "/home/claude/.claude/.credentials.json",
                    "mode": "ro",
                }
            else:
                # Fall back to API key environment variable
                environment["ANTHROPIC_API_KEY"] = self.config.claude_api_key
                environment["CLAUDE_API_KEY"] = self.config.claude_api_key

            # Build command with proper flags for non-interactive mode
            # -p (print) mode for non-interactive output
            # --dangerously-skip-permissions to allow autonomous operation (requires non-root user)
            command = [
                "-p",  # Print mode (non-interactive)
                "--dangerously-skip-permissions",  # Allow autonomous operation
                prompt,
            ]

            container = self.client.containers.run(
                f"{self.image_name}:{self.image_tag}",
                name=container_name,
                command=command,
                environment=environment,
                volumes=volumes,
                working_dir="/workspace",
                detach=True,
                remove=not keep_container,  # Auto-remove when done (unless debugging)
                user="claude",  # Run as non-root claude user
                network_mode="bridge",
            )

            logger.info(f"Started container {container_name} ({container.id[:12]})")
            return container

        except DockerException as e:
            logger.error(f"Failed to run container: {e}")
            raise

    def get_container_status(self, issue_number: int) -> Optional[str]:
        """
        Get the status of a container.

        Args:
            issue_number: GitHub issue number.

        Returns:
            Container status or None if not found.
        """
        if not self.client:
            raise RuntimeError("Not connected to Docker. Call connect() first.")

        container_name = f"claude-issue-{issue_number}"

        try:
            container = self.client.containers.get(container_name)
            return container.status
        except docker.errors.NotFound:
            return None

    def get_container_logs(self, issue_number: int) -> Optional[str]:
        """
        Get logs from a container.

        Args:
            issue_number: GitHub issue number.

        Returns:
            Container logs or None if not found.
        """
        if not self.client:
            raise RuntimeError("Not connected to Docker. Call connect() first.")

        container_name = f"claude-issue-{issue_number}"

        try:
            container = self.client.containers.get(container_name)
            return container.logs().decode("utf-8")
        except docker.errors.NotFound:
            return None

    def stop_container(self, issue_number: int):
        """
        Stop a running container.

        Args:
            issue_number: GitHub issue number.
        """
        if not self.client:
            raise RuntimeError("Not connected to Docker. Call connect() first.")

        container_name = f"claude-issue-{issue_number}"

        try:
            container = self.client.containers.get(container_name)
            container.stop(timeout=10)
            logger.info(f"Stopped container {container_name}")
        except docker.errors.NotFound:
            logger.warning(f"Container {container_name} not found")

    def cleanup_image(self, image_id: str):
        """
        Remove a Docker image.

        Args:
            image_id: Image ID to remove.
        """
        if not self.client:
            raise RuntimeError("Not connected to Docker. Call connect() first.")

        try:
            self.client.images.remove(image_id, force=True)
            logger.info(f"Removed image {image_id[:12]}")
        except ImageNotFound:
            logger.warning(f"Image {image_id} not found")
        except APIError as e:
            logger.error(f"Failed to remove image: {e}")

    def close(self):
        """Close Docker connection."""
        if self.client:
            self.client.close()
            logger.info("Closed Docker connection")
