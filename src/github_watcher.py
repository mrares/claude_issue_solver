"""GitHub issue watcher for monitoring Claude-tagged issues."""

import logging
import time
import jwt
from typing import List, Set, Optional
from datetime import datetime, timezone, timedelta
from github import Github, GithubException, Auth
from github.Issue import Issue
from github.Repository import Repository

from .config import get_config

logger = logging.getLogger(__name__)


class IssueInfo:
    """Container for issue information."""

    def __init__(self, issue: Issue):
        """Initialize from GitHub issue."""
        self.number: int = issue.number
        self.title: str = issue.title
        self.has_implement_tag: bool = any(
            label.name.lower() == "implement" for label in issue.labels
        )
        self.has_claude_tag: bool = any(
            label.name.lower() == "claude" for label in issue.labels
        )
        self.updated_at: datetime = issue.updated_at
        self.state: str = issue.state
        self.url: str = issue.html_url

    def __hash__(self):
        """Hash based on issue number."""
        return hash(self.number)

    def __eq__(self, other):
        """Equality based on issue number."""
        if isinstance(other, IssueInfo):
            return self.number == other.number
        return False

    def __repr__(self):
        """String representation."""
        return f"IssueInfo(#{self.number}, implement={self.has_implement_tag})"


class GitHubWatcher:
    """Watches GitHub repository for Claude-tagged issues."""

    def __init__(self):
        """Initialize the GitHub watcher."""
        self.config = get_config()
        self.github: Optional[Github] = None
        self.repo: Optional[Repository] = None
        self._last_check: Optional[datetime] = None
        self._known_issues: Set[int] = set()
        self._issue_timestamps: dict[int, datetime] = {}
        self._installation_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    def _generate_jwt(self) -> str:
        """Generate JWT for GitHub App authentication."""
        if not self.config.github_private_key_path:
            raise RuntimeError("No private key path configured")

        # Read private key
        with open(self.config.github_private_key_path, 'r') as key_file:
            private_key = key_file.read()

        # Create JWT
        now = int(time.time())
        payload = {
            'iat': now,
            'exp': now + 600,  # 10 minutes
            'iss': self.config.github_app_id
        }

        return jwt.encode(payload, private_key, algorithm='RS256')

    def _get_installation_token(self) -> str:
        """Get installation access token for GitHub App."""
        # Check if we have a valid cached token
        if self._installation_token and self._token_expires_at:
            if datetime.now(timezone.utc) < self._token_expires_at - timedelta(minutes=5):
                return self._installation_token

        logger.info("Obtaining GitHub App installation token...")

        # Read the private key
        with open(self.config.github_private_key_path, 'r') as key_file:
            private_key = key_file.read()

        # Create App authentication
        app_auth = Auth.AppAuth(self.config.github_app_id, private_key)

        try:
            # Get installation ID if not provided
            if self.config.github_installation_id:
                installation_id = int(self.config.github_installation_id)
            else:
                # Auto-detect installation for the repository using GithubIntegration
                from github import GithubIntegration
                gi = GithubIntegration(auth=app_auth)
                owner, repo_name = self.config.github_repo.split('/')
                installation = gi.get_repo_installation(owner, repo_name)
                installation_id = installation.id
                logger.info(f"Auto-detected installation ID: {installation_id}")

            # Get installation auth (PyGithub handles token refresh automatically)
            installation_auth = app_auth.get_installation_auth(installation_id)

            # Create a temporary Github instance to get the token info
            gh = Github(auth=installation_auth)
            # The token is available from the auth object
            self._installation_token = installation_auth.token
            # Token expires in 1 hour by default for installation tokens
            self._token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            gh.close()

            logger.info(f"GitHub App token obtained, expires at {self._token_expires_at}")
            return self._installation_token

        except GithubException as e:
            logger.error(f"Failed to get installation token: {e}")
            raise

    def _create_github_client(self) -> Github:
        """Create GitHub client with appropriate authentication."""
        if self.config.is_using_github_app():
            logger.info("Using GitHub App authentication")
            token = self._get_installation_token()
            return Github(token)
        else:
            logger.info("Using GitHub token authentication")
            return Github(self.config.github_token)

    def connect(self):
        """Connect to GitHub and validate repository access."""
        try:
            self.github = self._create_github_client()
            self.repo = self.github.get_repo(self.config.github_repo)

            if self.config.is_using_github_app():
                logger.info(f"Connected to repository: {self.config.github_repo} (via GitHub App)")
            else:
                logger.info(f"Connected to repository: {self.config.github_repo} (via token)")

        except GithubException as e:
            logger.error(f"Failed to connect to GitHub: {e}")
            raise

    def _ensure_valid_token(self):
        """Ensure GitHub client has a valid token (refresh if using App auth)."""
        if self.config.is_using_github_app():
            # Check if token needs refresh
            if self._token_expires_at:
                if datetime.now(timezone.utc) >= self._token_expires_at - timedelta(minutes=5):
                    logger.info("GitHub App token expiring soon, refreshing...")
                    self.github.close()
                    self.github = self._create_github_client()
                    self.repo = self.github.get_repo(self.config.github_repo)

    def get_claude_issues(self) -> List[IssueInfo]:
        """
        Get all open issues tagged with 'Claude'.

        Returns:
            List of IssueInfo objects for Claude-tagged issues.
        """
        if not self.repo:
            raise RuntimeError("Not connected to GitHub. Call connect() first.")

        try:
            # Ensure token is valid
            self._ensure_valid_token()

            issues = self.repo.get_issues(state="open", labels=["Claude"])
            issue_list = []

            for issue in issues:
                # Skip pull requests
                if issue.pull_request:
                    continue

                info = IssueInfo(issue)
                issue_list.append(info)

                # Track this issue
                self._known_issues.add(info.number)
                self._issue_timestamps[info.number] = info.updated_at

            self._last_check = datetime.now(timezone.utc)
            logger.info(f"Found {len(issue_list)} Claude-tagged issues")

            return issue_list

        except GithubException as e:
            logger.error(f"Failed to fetch issues: {e}")
            raise

    def get_new_or_updated_issues(self) -> List[IssueInfo]:
        """
        Get issues that are new or have been updated since last check.

        Returns:
            List of IssueInfo objects for new or updated issues.
        """
        all_issues = self.get_claude_issues()
        new_or_updated = []

        for issue in all_issues:
            # New issue
            if issue.number not in self._known_issues:
                logger.info(f"New issue detected: #{issue.number}")
                new_or_updated.append(issue)
                continue

            # Updated issue
            last_known = self._issue_timestamps.get(issue.number)
            if last_known and issue.updated_at > last_known:
                logger.info(f"Updated issue detected: #{issue.number}")
                new_or_updated.append(issue)

        return new_or_updated

    def get_issue_details(self, issue_number: int) -> Optional[Issue]:
        """
        Get full GitHub issue object.

        Args:
            issue_number: Issue number to fetch.

        Returns:
            GitHub Issue object or None if not found.
        """
        if not self.repo:
            raise RuntimeError("Not connected to GitHub. Call connect() first.")

        try:
            # Ensure token is valid
            self._ensure_valid_token()
            return self.repo.get_issue(issue_number)
        except GithubException as e:
            logger.error(f"Failed to fetch issue #{issue_number}: {e}")
            return None

    def post_comment(self, issue_number: int, comment: str) -> bool:
        """
        Post a comment to an issue.

        Args:
            issue_number: Issue number.
            comment: Comment text.

        Returns:
            True if successful, False otherwise.
        """
        issue = self.get_issue_details(issue_number)
        if not issue:
            return False

        try:
            issue.create_comment(comment)
            logger.info(f"Posted comment to issue #{issue_number}")
            return True
        except GithubException as e:
            logger.error(f"Failed to post comment to #{issue_number}: {e}")
            return False

    def get_token(self) -> Optional[str]:
        """
        Get the current GitHub authentication token.

        Returns:
            GitHub token (installation token if using App auth, or PAT).
        """
        if self.config.is_using_github_app():
            return self._get_installation_token()
        return self.config.github_token

    def close(self):
        """Close GitHub connection."""
        if self.github:
            self.github.close()
            logger.info("Closed GitHub connection")
