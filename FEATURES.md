# Feature Overview

## Core Features

### 1. GitHub Issue Monitoring
- Automatically scans repository for issues tagged with `Claude`
- Polls every 10 minutes (configurable)
- Detects new issues and updates to existing issues
- Ignores pull requests (only processes issues)

### 2. Two-Phase Workflow

#### Planning Phase (No `Implement` Tag)
- Creates isolated git worktree for the issue
- Launches Claude in Docker container
- Claude analyzes the issue
- Claude creates implementation plan
- Posts plan as comment on the issue
- Waits for user approval

#### Implementation Phase (Has `Implement` Tag)
- Creates isolated git worktree
- Launches Claude in Docker container  
- Claude reads approved plan from issue
- Claude executes the plan
- Makes code changes
- Creates pull request
- Links PR to original issue

### 3. Docker Integration

#### Automatic Image Building
- Extends your development Dockerfile
- Adds Claude CLI
- Configures git for commits
- Tags as `claude-issue-solver:latest`

#### Secure Container Execution
- Each issue runs in isolated container
- Worktree mounted at `/workspace`
- Claude API key passed via environment
- Runs with privileged mode for full git access
- Auto-removed after completion (`--rm` flag)
- Images cleaned up after container exits

### 4. Concurrent Task Management
- Runs up to 3 containers in parallel (configurable)
- Thread-safe task queue
- Fair scheduling (FIFO)
- Prevents duplicate processing
- Tracks task status throughout lifecycle

### 5. Daemon Operation

#### Background Service
- Runs as system daemon
- PID file tracking
- Signal handling (SIGINT, SIGTERM)
- Graceful shutdown
- State persistence

#### Worker Threads
- **Poll Thread**: Checks GitHub every 10 minutes
- **Process Thread**: Manages task queue and containers
- **Monitor Threads**: One per running container
- **State Thread**: Saves state every minute

### 6. CLI Interface

#### Daemon Control
```bash
claude-issue-solver start         # Start daemon
claude-issue-solver start -f      # Start in foreground
claude-issue-solver stop          # Stop daemon
claude-issue-solver restart       # Restart daemon
claude-issue-solver status        # Show status
```

#### Work Management
```bash
claude-issue-solver queue         # View work queue
claude-issue-solver pause         # Pause new tasks
claude-issue-solver resume        # Resume processing
claude-issue-solver logs 123      # View logs for issue #123
```

### 7. State Persistence

#### What's Saved
- Queue state (paused/running)
- Running tasks with progress
- Queued tasks waiting to start
- Recently completed tasks (last 100)
- Task metadata (started/completed times, errors)

#### When It's Saved
- Every 60 seconds automatically
- On daemon shutdown
- Can be loaded on restart

### 8. Resource Management

#### Automatic Cleanup
- Worktrees removed after task completion
- Docker containers auto-removed (`--rm`)
- Docker images cleaned up
- Old task history pruned (keeps last 100)

#### Resource Limits
- Max 3 concurrent containers
- Configurable worktree base directory
- Configurable poll interval (min 60s)

## Safety Features

### Isolation
- Each issue gets separate git worktree
- Containers don't interfere with each other
- Main repository unaffected by task failures

### Error Handling
- Comprehensive exception handling
- Failed tasks marked and logged
- Errors don't crash daemon
- Automatic retry on next poll

### Defensive Programming
- Type hints throughout
- Input validation
- Path existence checks
- Process lifecycle management
- Thread safety with locks

## Configuration

### Required Settings
- `GITHUB_TOKEN` - GitHub personal access token
- `GITHUB_REPO` - Repository in owner/repo format
- `CLAUDE_API_KEY` - Claude API key
- `REPO_PATH` - Path to target repository

### Optional Settings
- `WORKTREE_BASE` - Where to create worktrees
- `POLL_INTERVAL` - How often to check GitHub (seconds)
- `MAX_CONCURRENT` - Max parallel containers
- `LOG_LEVEL` - Logging verbosity
- `PID_FILE` - Daemon PID file location
- `STATE_FILE` - State persistence file location

## Limitations

### By Design
- Polling-based (not webhooks)
- Single machine operation
- Maximum 3 concurrent tasks (configurable up to 10)
- 10 minute minimum poll interval (60s configurable minimum)

### Current Version
- No webhook support
- No multi-repository support
- No web UI (CLI only)
- No metrics dashboard
- No notification integrations

## Dependencies

### Python Packages (Minimal)
- `PyGithub` - GitHub API client
- `python-dotenv` - Environment config
- `docker` - Docker API client
- `psutil` - Process utilities
- `click` - CLI framework
- `pyyaml` - YAML support

### System Requirements
- Python 3.9+
- Docker
- Git
- Linux/macOS (Windows with WSL2)

## Use Cases

### Perfect For
- Automating routine issue resolution
- Standardized bug fixes
- Feature implementation with clear specs
- Maintenance tasks
- Documentation updates
- Test case additions

### Not Ideal For
- Issues requiring human judgment
- Complex architectural decisions
- Security-critical changes
- Emergency hotfixes (10 min polling delay)

## Performance

### Scalability
- Handles hundreds of issues efficiently
- Low memory footprint
- Minimal CPU usage (mostly waiting)
- Docker containers run on demand

### Response Time
- New issue detected: 0-10 minutes (polling)
- Task start: Immediate (if < 3 running)
- Task complete: Depends on issue complexity

## Security Considerations

### Credentials
- API keys in environment variables only
- Never logged or exposed
- Passed to containers via environment

### Container Security
- Runs with privileged mode (needed for git)
- Isolated filesystem per worktree
- No network restrictions (needed for git/API)
- Containers auto-removed (no persistence)

### Code Safety
- Claude has full git access within worktree
- Can commit and push changes
- Cannot affect other worktrees
- Cannot access host system (except worktree)

## Monitoring & Debugging

### Logs
- Main log: `/tmp/claude-issue-solver.log`
- Structured logging with levels
- Per-container logs via CLI
- Thread-safe logging

### Status Checking
- Running tasks count
- Queued tasks list
- Recent completed tasks
- Pause/resume state
- Container status per issue

### Troubleshooting
- Foreground mode for debugging
- Detailed error messages
- Container logs accessible
- State file inspection
- PID file verification
