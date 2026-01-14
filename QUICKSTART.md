# Quick Start Guide

Get Claude Issue Solver running in 5 minutes!

## Prerequisites Check

```bash
# Check Python version (need 3.9+)
python3 --version

# Check Docker is running
docker ps

# Check Git
git --version
```

## Installation

### 1. Get API Keys

- **GitHub Token**: https://github.com/settings/tokens (need `repo` scope)
- **Claude API Key**: https://console.anthropic.com/

### 2. Quick Install

```bash
# Run the install script
./install.sh
```

This will:
- Create a virtual environment
- Install all dependencies
- Create `.env` from template
- Make scripts executable

### 3. Configure

```bash
# Edit .env and configure:
nano .env
```

**Required:**
- `GITHUB_TOKEN` (or use `GH_TOKEN` from environment)
- `GITHUB_REPO` (e.g., `owner/repository`)
- `CLAUDE_API_KEY` (or use `ANTHROPIC_API_KEY` from environment)

**Choose repository source:**
- `REPO_URL` - GitHub URL to clone (recommended)
  - Example: `https://github.com/owner/repo.git`
  - Tool will clone and keep updated
- OR `REPO_PATH` - Path to existing local repo
  - Example: `/path/to/existing/repo`

**Note:** Credentials can be in `.env` file OR your shell environment.

### 4. Verify Setup

```bash
./verify-setup.sh
```

## First Run

### Test with Dry-Run Mode

Before running for real, test with dry-run mode:

```bash
# Activate virtual environment
source venv/bin/activate

# Run in dry-run mode
./claude-issue-solver start --dry-run
```

This will:
- Check GitHub for issues
- Show what actions would be taken
- NOT create worktrees or run containers
- Log everything to console

### Start the Daemon

```bash
# Test in foreground first
./claude-issue-solver start --foreground
```

You should see:
```
Starting Claude Issue Solver daemon...
Connected to repository: owner/repo
Connected to Docker daemon
Building Docker image...
Daemon started successfully
```

### Create a Test Issue

1. Go to your GitHub repository
2. Create a new issue: "Test Claude Issue Solver"
3. Add label: `Claude`
4. Wait ~30 seconds

### Check Status

In another terminal:

```bash
./claude-issue-solver status
```

You should see your issue being processed!

### Stop the Daemon

Press `Ctrl+C` in the foreground terminal, or:

```bash
./claude-issue-solver stop
```

## Running in Background

```bash
# Start as daemon
./claude-issue-solver start

# Check status
./claude-issue-solver status

# View queue
./claude-issue-solver queue

# View logs for specific issue
./claude-issue-solver logs 123

# Stop
./claude-issue-solver stop
```

## Workflow Example

### Planning Phase

1. **Create Issue**
   - Title: "Add user authentication"
   - Label: `Claude`
   - Description: Detailed requirements

2. **Claude Creates Plan**
   - Daemon detects issue
   - Claude analyzes requirements
   - Posts implementation plan as comment
   - Waits for approval

3. **Review Plan**
   - Read Claude's plan
   - Add comments/feedback if needed
   - Remove `Claude` label temporarily if major changes needed

### Implementation Phase

4. **Approve Implementation**
   - Add `Implement` label to issue
   - Daemon detects update
   - Claude executes plan

5. **Claude Creates PR**
   - Makes code changes
   - Runs tests
   - Creates pull request
   - Links PR to issue

6. **Review & Merge**
   - Review the PR
   - Request changes if needed
   - Merge when satisfied

## Common Commands

```bash
# Install and setup
./install.sh                     # One-time setup
source venv/bin/activate         # Activate environment

# Testing
./verify-setup.sh                # Verify configuration
./claude-issue-solver start --dry-run  # Test without executing

# Running
./claude-issue-solver start      # Start in background
./claude-issue-solver start -f   # Start in foreground

# Monitoring
./claude-issue-solver status     # Check daemon status
./claude-issue-solver queue      # View work queue
./claude-issue-solver logs 42    # View logs for issue #42

# Control
./claude-issue-solver pause      # Pause new tasks
./claude-issue-solver resume     # Resume processing
./claude-issue-solver restart    # Restart daemon
./claude-issue-solver stop       # Stop daemon
```

## Troubleshooting

### "Daemon is already running"
```bash
./claude-issue-solver stop
./claude-issue-solver start
```

### "Failed to connect to Docker"
```bash
# Check Docker is running
docker ps

# Try starting Docker Desktop
```

### "Repository path does not exist"
```bash
# Make sure REPO_PATH in .env is correct and absolute
echo $REPO_PATH  # Should show full path like /home/user/myrepo
```

### "No issues found"
```bash
# Check:
# 1. Issue has "Claude" label (exact spelling, case-sensitive)
# 2. Issue is open (not closed)
# 3. GITHUB_REPO in .env matches your repository
```

### View Logs
```bash
# Daemon logs
tail -f /tmp/claude-issue-solver.log

# Container logs for specific issue
./claude-issue-solver logs <issue_number>
```

## What's Next?

- Read [README.md](README.md) for detailed usage
- See [ARCHITECTURE.md](ARCHITECTURE.md) to understand how it works
- Check [CONTRIBUTING.md](CONTRIBUTING.md) to contribute
- Read [claude.md](claude.md) to understand Claude's workflow

## Need Help?

1. Check logs: `tail -f /tmp/claude-issue-solver.log`
2. Check status: `./claude-issue-solver status`
3. View queue: `./claude-issue-solver queue`
4. Open an issue on GitHub

## Tips

- Start with simple issues to test the system
- Review plans before adding `Implement` label
- Keep issues focused and well-defined
- Monitor the first few runs in foreground mode
- Check Docker container logs if issues fail
- The daemon polls every 10 minutes - be patient!

Happy automated issue solving! 🚀
