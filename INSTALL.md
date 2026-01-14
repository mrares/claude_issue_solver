# Installation Guide

## Prerequisites

1. **Python 3.9+**
   ```bash
   python3 --version
   ```

2. **Docker**
   ```bash
   docker --version
   ```

3. **Git**
   ```bash
   git --version
   ```

4. **Claude CLI** (will be installed in Docker container)

5. **GitHub Personal Access Token**
   - Go to GitHub Settings > Developer settings > Personal access tokens
   - Create a token with `repo` scope
   - Save the token securely

6. **Claude API Key**
   - Get your API key from https://console.anthropic.com/

## Installation Steps

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd claude_issue_solver
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

Or use a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment

Copy the example configuration:

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```bash
# GitHub Configuration
GITHUB_TOKEN=ghp_your_token_here
GITHUB_REPO=owner/repository

# Claude Configuration
CLAUDE_API_KEY=sk-ant-your_key_here

# Paths
WORKTREE_BASE=/tmp/claude-worktrees
REPO_PATH=/path/to/target/repository

# Daemon Configuration (optional, these are defaults)
POLL_INTERVAL=600
MAX_CONCURRENT=3
LOG_LEVEL=INFO
```

### 4. Verify Docker

Ensure Docker is running:

```bash
docker ps
```

### 5. Prepare Target Repository

The target repository (where issues will be processed) should:

1. Have a `Dockerfile` at the root for the development environment
2. Optionally have a `claude.md` file with instructions for Claude
3. Have issues tagged with `Claude` label

### 6. Install the Tool

You can either:

**Option A: Run directly**
```bash
./claude-issue-solver --help
```

**Option B: Install as package**
```bash
pip install -e .
claude-issue-solver --help
```

## Verification

Test the configuration:

```bash
# Check if daemon can start
./claude-issue-solver start --foreground

# In another terminal, check status
./claude-issue-solver status
```

Press Ctrl+C to stop the foreground daemon.

## Usage

See [README.md](README.md) for usage instructions.

## Troubleshooting

### "Failed to connect to Docker"
- Ensure Docker daemon is running: `docker ps`
- Check Docker permissions: `docker run hello-world`

### "Repository path does not exist"
- Verify `REPO_PATH` in `.env` points to a valid git repository
- Ensure the path is absolute, not relative

### "Failed to connect to GitHub"
- Verify `GITHUB_TOKEN` has correct permissions
- Check token hasn't expired
- Ensure `GITHUB_REPO` format is `owner/repo`

### "No Claude-tagged issues found"
- Create a test issue in your repository
- Add a label named `Claude` (case-sensitive)
- Wait for next poll cycle or restart daemon

### Permission Errors
- Ensure the user running the daemon has Docker permissions
- On Linux, add user to docker group: `sudo usermod -aG docker $USER`
