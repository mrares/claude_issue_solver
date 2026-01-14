"""Configuration management for Claude Issue Solver."""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration container for the issue solver."""

    def __init__(self, dry_run: bool = False):
        """Initialize configuration from environment variables."""
        # Runtime mode
        self.dry_run: bool = dry_run

        # GitHub Configuration - support both token and app authentication
        # GitHub App settings (optional)
        self.github_app_id: Optional[str] = os.getenv("GITHUB_APP_ID")
        self.github_private_key_path: Optional[Path] = None
        self.github_installation_id: Optional[str] = os.getenv("GITHUB_INSTALLATION_ID")

        if os.getenv("GITHUB_PRIVATE_KEY_PATH"):
            self.github_private_key_path = Path(os.getenv("GITHUB_PRIVATE_KEY_PATH"))

        # GitHub Token (optional if using app)
        self.github_token: Optional[str] = None
        try:
            self.github_token = self._get_credential(
                "GITHUB_TOKEN",
                env_vars=["GITHUB_TOKEN", "GH_TOKEN"],
                description="GitHub token"
            )
        except ValueError:
            # Token not found - check if we have app credentials
            if not (self.github_app_id and self.github_private_key_path):
                raise ValueError(
                    "Either GitHub token or GitHub App credentials must be provided.\n"
                    "Token: Set GITHUB_TOKEN or GH_TOKEN\n"
                    "App: Set GITHUB_APP_ID and GITHUB_PRIVATE_KEY_PATH"
                )

        self.github_repo: str = self._get_required("GITHUB_REPO")

        # Claude Configuration - check .env first, then user environment, then CLI config
        self.claude_api_key: Optional[str] = None
        self.claude_credentials_json: Optional[str] = None  # Full OAuth credentials for container mounting
        try:
            self.claude_api_key = self._get_credential(
                "CLAUDE_API_KEY",
                env_vars=["CLAUDE_API_KEY", "ANTHROPIC_API_KEY"],
                description="Claude API key"
            )
        except ValueError:
            # Try to get from Claude CLI config
            self.claude_api_key, self.claude_credentials_json = self._get_claude_cli_credentials()
            if not self.claude_api_key:
                raise ValueError(
                    "No Claude API key found. Please either:\n"
                    "1. Set CLAUDE_API_KEY or ANTHROPIC_API_KEY in .env or environment\n"
                    "2. Run 'claude auth login' to authenticate Claude CLI"
                )

        # Repository configuration - URL or local path
        self.repo_url: Optional[str] = os.getenv("REPO_URL")
        self.repo_path: Optional[Path] = None

        if os.getenv("REPO_PATH"):
            self.repo_path = Path(os.getenv("REPO_PATH"))

        # Must have either URL or path
        if not self.repo_url and not self.repo_path:
            raise ValueError(
                "Either REPO_URL or REPO_PATH must be set. "
                "Use REPO_URL for GitHub repository cloning, or "
                "REPO_PATH for an existing local repository."
            )

        # Paths
        self.worktree_base: Path = Path(
            os.getenv("WORKTREE_BASE", "/tmp/claude-worktrees")
        )
        self.repo_cache: Path = Path(
            os.getenv("REPO_CACHE", "/tmp/claude-repos")
        )

        # Daemon Configuration
        self.poll_interval: int = int(os.getenv("POLL_INTERVAL", "600"))
        self.max_concurrent: int = int(os.getenv("MAX_CONCURRENT", "3"))
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")

        # Runtime files
        self.pid_file: Path = Path(
            os.getenv("PID_FILE", "/tmp/claude-issue-solver.pid")
        )
        self.state_file: Path = Path(
            os.getenv("STATE_FILE", "/tmp/claude-issue-solver-state.json")
        )

        # Validate paths
        self._validate()

    def _get_required(self, key: str) -> str:
        """Get required environment variable or raise error."""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Required environment variable {key} is not set")
        return value

    def _get_credential(self, primary_key: str, env_vars: list[str], description: str) -> str:
        """
        Get credential from environment, checking multiple sources.

        Args:
            primary_key: Primary environment variable name
            env_vars: List of environment variable names to check (in order)
            description: Human-readable description for error messages

        Returns:
            Credential value

        Raises:
            ValueError: If no credential found in any source
        """
        # Check all possible environment variables
        for var in env_vars:
            value = os.getenv(var)
            if value:
                if var != primary_key:
                    import logging
                    logging.getLogger(__name__).info(
                        f"Using {description} from environment variable {var}"
                    )
                return value

        # Not found in any location
        raise ValueError(
            f"No {description} found. Please set one of: {', '.join(env_vars)}\n"
            f"You can set it in .env file or in your shell environment."
        )

    def _get_claude_cli_credentials(self) -> tuple[Optional[str], Optional[str]]:
        """
        Try to get Claude credentials from Claude CLI configuration.

        Returns:
            Tuple of (api_key_or_token, full_credentials_json)
            - api_key_or_token: The API key or OAuth access token
            - full_credentials_json: The full credentials JSON for container mounting (if OAuth)
        """
        import json
        import logging
        import platform

        logger = logging.getLogger(__name__)

        # On macOS, try to get credentials from the Keychain first
        if platform.system() == "Darwin":
            key, creds_json = self._get_claude_keychain_credential()
            if key:
                logger.info("Using Claude credentials from macOS Keychain")
                return key, creds_json

        # Check common Claude CLI config locations (Linux and fallback)
        config_paths = [
            Path.home() / ".claude" / ".credentials.json",  # Claude Code on Linux
            Path.home() / ".config" / "claude" / "config.json",
            Path.home() / ".anthropic" / "config.json",
        ]

        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        content = f.read()
                        config = json.loads(content)
                        # Try different possible key names
                        for key_name in ["api_key", "apiKey", "ANTHROPIC_API_KEY"]:
                            if key_name in config:
                                logger.info(
                                    f"Using Claude API key from CLI config: {config_path}"
                                )
                                return config[key_name], None
                        # Check for OAuth credentials
                        if "claudeAiOauth" in config:
                            oauth_data = config["claudeAiOauth"]
                            if isinstance(oauth_data, dict) and "accessToken" in oauth_data:
                                logger.info(
                                    f"Using Claude OAuth credentials from CLI config: {config_path}"
                                )
                                return oauth_data["accessToken"], content
                except (json.JSONDecodeError, KeyError, IOError):
                    continue

        return None, None

    def _get_claude_keychain_credential(self) -> tuple[Optional[str], Optional[str]]:
        """
        Try to get Claude credentials from macOS Keychain.

        Claude Code stores OAuth credentials in the macOS Keychain under
        the service name 'Claude Code-credentials'. The credential is stored
        as a JSON object containing OAuth tokens.

        Returns:
            Tuple of (api_key_or_token, full_credentials_json)
            - api_key_or_token: The API key or OAuth access token
            - full_credentials_json: The full credentials JSON for container mounting (if OAuth)
        """
        import json
        import logging
        import subprocess

        logger = logging.getLogger(__name__)

        # Claude Code stores credentials under these service names
        service_names = ["Claude Code-credentials", "claude.ai", "Claude", "anthropic.com"]

        for service in service_names:
            try:
                # Use security command to access Keychain
                result = subprocess.run(
                    [
                        "security", "find-generic-password",
                        "-s", service,
                        "-w"  # Output only the password
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode == 0 and result.stdout.strip():
                    credential = result.stdout.strip()
                    # Validate it looks like a credential (not empty)
                    if len(credential) > 10:
                        logger.debug(f"Found Claude credential in Keychain under service: {service}")

                        # The credential might be a JSON object containing OAuth tokens
                        # Try to parse it and extract the actual token
                        try:
                            cred_data = json.loads(credential)
                            # Look for OAuth token in the JSON structure
                            if isinstance(cred_data, dict):
                                # Check for claudeAiOauth which contains the actual tokens
                                if "claudeAiOauth" in cred_data:
                                    oauth_data = cred_data["claudeAiOauth"]
                                    # Return both the access token AND the full credential JSON
                                    # The full JSON is needed for container mounting
                                    if isinstance(oauth_data, dict) and "accessToken" in oauth_data:
                                        logger.debug("Extracted accessToken from Keychain OAuth data")
                                        return oauth_data["accessToken"], credential
                                # Try other common key names
                                for key in ["accessToken", "access_token", "api_key", "apiKey"]:
                                    if key in cred_data:
                                        return cred_data[key], None
                        except json.JSONDecodeError:
                            # Not JSON, return as-is (might be a plain API key)
                            pass

                        return credential, None

            except subprocess.TimeoutExpired:
                logger.warning(f"Timeout accessing Keychain for service: {service}")
            except subprocess.SubprocessError as e:
                logger.debug(f"Could not access Keychain for service {service}: {e}")
            except Exception as e:
                logger.debug(f"Unexpected error accessing Keychain: {e}")

        return None, None

    def _validate(self):
        """Validate configuration."""
        # Validate GitHub App credentials if provided
        if self.github_app_id and self.github_private_key_path:
            if not self.github_private_key_path.exists():
                raise ValueError(
                    f"GitHub App private key not found: {self.github_private_key_path}"
                )

        # If using local path, validate it exists and is a git repo
        if self.repo_path:
            if not self.repo_path.exists():
                raise ValueError(f"Repository path does not exist: {self.repo_path}")

            if not (self.repo_path / ".git").exists():
                raise ValueError(f"Not a git repository: {self.repo_path}")

        # Create directories if they don't exist
        self.worktree_base.mkdir(parents=True, exist_ok=True)

        if self.repo_url:
            self.repo_cache.mkdir(parents=True, exist_ok=True)

        if self.max_concurrent < 1 or self.max_concurrent > 10:
            raise ValueError("MAX_CONCURRENT must be between 1 and 10")

        if self.poll_interval < 60:
            raise ValueError("POLL_INTERVAL must be at least 60 seconds")

    def is_using_github_app(self) -> bool:
        """Check if using GitHub App authentication."""
        return bool(self.github_app_id and self.github_private_key_path)

    def get_repo_path(self) -> Path:
        """
        Get the repository path, whether from URL or local path.

        Returns:
            Path to the repository
        """
        if self.repo_path:
            return self.repo_path

        # Derive path from URL
        if self.repo_url:
            # Extract repo name from URL
            repo_name = self.repo_url.rstrip('/').split('/')[-1]
            if repo_name.endswith('.git'):
                repo_name = repo_name[:-4]
            return self.repo_cache / repo_name

        raise RuntimeError("No repository path or URL configured")

    def __repr__(self) -> str:
        """String representation with sensitive data masked."""
        dry_run_str = " [DRY-RUN]" if self.dry_run else ""
        source = f"url={self.repo_url}" if self.repo_url else f"path={self.repo_path}"
        auth = "app" if self.is_using_github_app() else "token"
        return (
            f"Config(github_repo={self.github_repo}, "
            f"auth={auth}, "
            f"{source}, "
            f"max_concurrent={self.max_concurrent}, "
            f"poll_interval={self.poll_interval}{dry_run_str})"
        )


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_config(config: Config):
    """Set the global configuration instance (used for dry-run mode)."""
    global _config
    _config = config
