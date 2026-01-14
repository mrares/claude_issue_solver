# Claude Issue Solver

A daemon that monitors GitHub issues tagged with `Claude` and automatically delegates them to Claude AI agents running in isolated Docker containers.

## Features

- Monitors GitHub repository issues for `Claude` tag
- Creates isolated worktrees for each issue
- Launches Claude CLI in Docker containers with dangerous permissions
- Supports planning and implementation workflows
- Concurrent processing (max 3 containers)
- Daemon management via CLI

## Requirements

- Python 3.9+
- Docker
- Git
- Claude CLI authentication
- GitHub Personal Access Token or GitHub App

## Installation

### Quick Install

```bash
./install.sh
```

This will:
- Create a Python virtual environment
- Install all dependencies
- Create a `.env` file from template
- Make scripts executable

### Manual Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
```

## Configuration

Create a `.env` file or set environment variables:

```bash
# GitHub Configuration
# Choose ONE authentication method:

# Option 1: Personal Access Token (simpler)
GITHUB_TOKEN=your_github_token  # Or use GH_TOKEN from environment

# Option 2: GitHub App (more secure, recommended for organizations)
# GITHUB_APP_ID=your_app_id
# GITHUB_PRIVATE_KEY_PATH=./path/to/private-key.pem
# GITHUB_INSTALLATION_ID=your_installation_id  # Optional, auto-detected if not set

# Repository to monitor
GITHUB_REPO=owner/repo

# Claude Configuration
CLAUDE_API_KEY=your_claude_key  # Or use ANTHROPIC_API_KEY from environment

# Repository to track (choose one):
# Option 1: GitHub URL (tool will clone and manage)
REPO_URL=https://github.com/owner/repo.git

# Option 2: Local path (use existing repository)
# REPO_PATH=/path/to/existing/repo

# Optional settings
WORKTREE_BASE=/tmp/claude-worktrees
REPO_CACHE=/tmp/claude-repos  # For cloned repositories
POLL_INTERVAL=600  # seconds (default: 10 minutes)
MAX_CONCURRENT=3   # maximum concurrent containers
```

### GitHub Authentication

The tool supports two authentication methods:

#### Personal Access Token (Simpler)

1. Create a token at https://github.com/settings/tokens
2. Required scopes: `repo`, `read:org`
3. Set in `.env` or environment:
   ```bash
   GITHUB_TOKEN=ghp_your_token_here
   ```

#### GitHub App (More Secure)

Recommended for organizations and better rate limits.

1. Create a GitHub App at https://github.com/settings/apps
2. Required permissions:
   - Repository permissions: `Contents` (Read & Write), `Issues` (Read & Write), `Pull Requests` (Read & Write)
3. Generate and download a private key
4. Install the app on your repository
5. Configure in `.env`:
   ```bash
   GITHUB_APP_ID=123456
   GITHUB_PRIVATE_KEY_PATH=./path/to/private-key.pem
   # GITHUB_INSTALLATION_ID=789012  # Optional, auto-detected
   ```

### Credential Fallback

The tool automatically checks for credentials in multiple locations:

**GitHub Token:**
- `.env` file: `GITHUB_TOKEN`
- Environment: `GITHUB_TOKEN` or `GH_TOKEN`

**Claude API Key:**
- `.env` file: `CLAUDE_API_KEY`
- Environment: `CLAUDE_API_KEY` or `ANTHROPIC_API_KEY`

If credentials are found in your shell environment, you don't need to add them to `.env`.

## Usage

### Start the daemon

```bash
# Start in background
./claude-issue-solver start

# Start in foreground (for debugging)
./claude-issue-solver start --foreground

# Dry-run mode (simulate without executing)
./claude-issue-solver start --dry-run
```

### Stop the daemon

```bash
./claude-issue-solver stop
```

### Check status

```bash
./claude-issue-solver status
```

### View work queue

```bash
./claude-issue-solver queue
```

### View logs for specific issue

```bash
./claude-issue-solver logs <issue_number>
```

### Pause/Resume

```bash
./claude-issue-solver pause
./claude-issue-solver resume
```

### Dry-Run Mode

Test the daemon without making any changes:

```bash
./claude-issue-solver start --dry-run
```

In dry-run mode:
- No worktrees are created
- No Docker containers are built or run
- All actions are logged showing what would happen
- Useful for testing configuration and workflow

## How It Works

1. **Repository Setup**:
   - If `REPO_URL` is set: Clones repository or updates existing clone
   - If `REPO_PATH` is set: Uses existing local repository
2. **Issue Detection**: Scans for issues tagged with `Claude` every 10 minutes
3. **Update & Branch**: Pulls latest default branch before creating worktree
4. **Worktree Creation**: Creates a temporary Git worktree for each issue
5. **Planning Phase**: If no `Implement` tag, Claude creates a plan and posts it as a comment
6. **Implementation Phase**: If `Implement` tag exists, Claude executes the plan
7. **Cleanup**: Removes containers and worktrees after completion

## Docker Environment

The tool builds upon your development Dockerfile and adds:
- Claude CLI installation
- Authentication configuration
- Git worktree mounting
- Dangerous permissions for full control

## Safety Features

- Container isolation
- Automatic cleanup (--rm flag)
- Image deletion after container exit
- Maximum concurrent limit
- Defensive programming practices
