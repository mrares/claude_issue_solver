"""Repository management for cloning and updating from GitHub."""

import logging
import subprocess
from pathlib import Path
from typing import Optional, List

from .config import get_config

logger = logging.getLogger(__name__)


def run_git_command(
    args: List[str],
    cwd: Optional[Path] = None,
    show_output: bool = True,
) -> subprocess.CompletedProcess:
    """
    Run a git command with real-time output to stdout.

    Args:
        args: Command arguments (e.g., ["git", "clone", "..."])
        cwd: Working directory for the command
        show_output: Whether to show output in real-time

    Returns:
        CompletedProcess result

    Raises:
        subprocess.CalledProcessError: If command fails
    """
    cmd_str = " ".join(args)
    logger.info(f"Running: {cmd_str}")

    if show_output:
        # Run with real-time output to stdout/stderr
        process = subprocess.Popen(
            args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        output_lines = []
        for line in process.stdout:
            line = line.rstrip()
            print(f"  {line}", flush=True)
            output_lines.append(line)

        process.wait()

        if process.returncode != 0:
            raise subprocess.CalledProcessError(
                process.returncode,
                args,
                output="\n".join(output_lines),
                stderr=None,
            )

        return subprocess.CompletedProcess(
            args,
            process.returncode,
            stdout="\n".join(output_lines),
            stderr=None,
        )
    else:
        # Run with captured output (for commands where we need the result)
        return subprocess.run(
            args,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )


class RepositoryManager:
    """Manages repository cloning and updates."""

    def __init__(self):
        """Initialize repository manager."""
        self.config = get_config()
        self.repo_path: Optional[Path] = None

    def ensure_repository(self) -> Path:
        """
        Ensure repository exists and is up to date.

        If REPO_URL is set, clones or updates from GitHub.
        If REPO_PATH is set, uses existing repository.

        Returns:
            Path to the repository
        """
        if self.config.repo_path:
            # Using existing local repository
            logger.info(f"Using existing repository at: {self.config.repo_path}")
            self.repo_path = self.config.repo_path
            return self.repo_path

        if self.config.repo_url:
            # Using GitHub URL - clone or update
            repo_path = self.config.get_repo_path()

            if repo_path.exists():
                logger.info(f"Repository exists at {repo_path}, updating...")
                self._update_repository(repo_path)
            else:
                logger.info(f"Cloning repository from {self.config.repo_url}...")
                self._clone_repository(repo_path)

            self.repo_path = repo_path
            return repo_path

        raise RuntimeError("No repository configured")

    def _clone_repository(self, target_path: Path):
        """
        Clone repository from GitHub URL.

        Args:
            target_path: Where to clone the repository
        """
        if self.config.dry_run:
            logger.info(f"[DRY-RUN] Would clone {self.config.repo_url} to {target_path}")
            return

        try:
            # Clone with authentication
            clone_url = self._get_authenticated_url(self.config.repo_url)

            run_git_command(
                ["git", "clone", "--progress", clone_url, str(target_path)],
            )

            logger.info(f"Successfully cloned repository to {target_path}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clone repository: {e.output}")
            raise RuntimeError(f"Failed to clone repository: {e.output}")

    def _update_repository(self, repo_path: Path):
        """
        Update repository to latest default branch.

        Args:
            repo_path: Path to the repository
        """
        if self.config.dry_run:
            logger.info(f"[DRY-RUN] Would update repository at {repo_path}")
            logger.info(f"[DRY-RUN] Would execute: git fetch origin")
            logger.info(f"[DRY-RUN] Would execute: git reset --hard origin/<default-branch>")
            return

        try:
            # Get default branch name
            default_branch = self._get_default_branch(repo_path)
            logger.info(f"Default branch: {default_branch}")

            # Update remote URL with fresh authentication token
            # This is necessary because GitHub App installation tokens expire after 1 hour
            if self.config.repo_url:
                authenticated_url = self._get_authenticated_url(self.config.repo_url)
                run_git_command(
                    ["git", "remote", "set-url", "origin", authenticated_url],
                    cwd=repo_path,
                    show_output=False,
                )
                logger.info("Updated remote URL with fresh authentication token")

            # Fetch latest changes
            run_git_command(
                ["git", "fetch", "origin", "--progress"],
                cwd=repo_path,
            )

            # Reset to latest default branch
            run_git_command(
                ["git", "checkout", default_branch],
                cwd=repo_path,
            )

            run_git_command(
                ["git", "reset", "--hard", f"origin/{default_branch}"],
                cwd=repo_path,
            )

            logger.info(f"Updated repository to latest {default_branch}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to update repository: {e.output}")
            raise RuntimeError(f"Failed to update repository: {e.output}")

    def _get_default_branch(self, repo_path: Path) -> str:
        """
        Get the default branch name.

        Args:
            repo_path: Path to the repository

        Returns:
            Default branch name (e.g., 'main' or 'master')
        """
        try:
            # Get symbolic ref for HEAD on remote
            result = subprocess.run(
                ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
            )

            # Parse branch name from refs/remotes/origin/main
            ref = result.stdout.strip()
            branch = ref.split('/')[-1]
            return branch

        except subprocess.CalledProcessError:
            # Fallback: try common branch names
            for branch in ["main", "master"]:
                try:
                    subprocess.run(
                        ["git", "rev-parse", f"origin/{branch}"],
                        cwd=repo_path,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    logger.info(f"Using fallback branch: {branch}")
                    return branch
                except subprocess.CalledProcessError:
                    continue

            raise RuntimeError("Could not determine default branch")

    def _get_authenticated_url(self, url: str) -> str:
        """
        Add GitHub token to URL for authentication.

        Args:
            url: Repository URL

        Returns:
            URL with authentication token
        """
        # If URL already has credentials, return as-is
        if '@' in url:
            return url

        # Get token - either from config or by getting an installation token
        token = self._get_auth_token()
        if not token:
            # No authentication available, return URL as-is
            logger.warning("No GitHub token available for authentication")
            return url

        # Add token for HTTPS URLs
        if url.startswith('https://'):
            # Format: https://x-access-token:token@github.com/owner/repo.git
            # Using x-access-token as username works for both PAT and installation tokens
            return url.replace(
                'https://',
                f'https://x-access-token:{token}@'
            )

        # SSH URLs don't need token
        return url

    def _get_auth_token(self) -> Optional[str]:
        """
        Get authentication token for GitHub operations.

        Returns:
            Token string or None if not available
        """
        # If we have a direct token, use it
        if self.config.github_token:
            return self.config.github_token

        # If using GitHub App, get an installation token
        if self.config.is_using_github_app():
            return self._get_installation_token()

        return None

    def _get_installation_token(self) -> Optional[str]:
        """
        Get GitHub App installation token for git operations.

        Returns:
            Installation token or None
        """
        try:
            from github import Auth, Github

            # Read the private key
            with open(self.config.github_private_key_path, 'r') as key_file:
                private_key = key_file.read()

            # Create App authentication
            app_auth = Auth.AppAuth(self.config.github_app_id, private_key)

            # Get installation ID
            if self.config.github_installation_id:
                installation_id = int(self.config.github_installation_id)
            else:
                # Auto-detect installation using GithubIntegration
                from github import GithubIntegration
                gi = GithubIntegration(auth=app_auth)
                owner, repo_name = self.config.github_repo.split('/')
                installation = gi.get_repo_installation(owner, repo_name)
                installation_id = installation.id
                logger.info(f"Auto-detected installation ID: {installation_id}")

            # Get installation auth - need to create a Github instance first
            # to provide the requester
            installation_auth = app_auth.get_installation_auth(installation_id)
            gh = Github(auth=installation_auth)
            token = installation_auth.token
            gh.close()
            return token

        except Exception as e:
            logger.error(f"Failed to get installation token: {e}")
            return None

    def pull_latest(self):
        """
        Pull latest changes from default branch.

        Should be called before creating new worktrees.
        """
        if not self.repo_path:
            self.repo_path = self.ensure_repository()

        logger.info("Pulling latest changes from default branch...")
        self._update_repository(self.repo_path)

    def get_repo_path(self) -> Path:
        """
        Get the repository path, ensuring it exists.

        Returns:
            Path to the repository
        """
        if not self.repo_path:
            self.repo_path = self.ensure_repository()
        return self.repo_path
