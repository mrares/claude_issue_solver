# Architecture Overview

## System Components

### 1. Configuration (`src/config.py`)
- Loads environment variables from `.env` file
- Validates configuration
- Provides global config instance
- Manages paths and limits

### 2. GitHub Watcher (`src/github_watcher.py`)
- Connects to GitHub API using PyGithub
- Monitors issues tagged with `Claude`
- Detects new and updated issues
- Posts comments back to issues
- Tracks issue state and timestamps

### 3. Docker Manager (`src/docker_manager.py`)
- Manages Docker client connection
- Builds Claude-enabled Docker images
- Creates and manages Git worktrees
- Runs containers with Claude CLI
- Monitors container lifecycle
- Handles cleanup (containers, images, worktrees)

### 4. Task Queue (`src/task_queue.py`)
- Thread-safe task queue implementation
- Enforces max concurrent task limit (3 by default)
- Tracks task states: pending, running, completed, failed
- Provides pause/resume functionality
- Persists state to JSON file
- Maintains task history

### 5. Daemon Service (`src/daemon.py`)
- Main orchestration service
- Runs background threads:
  - Issue polling thread (every 10 minutes)
  - Task processing thread (continuous)
  - State persistence thread (every minute)
- Generates prompts based on issue tags
- Monitors container completion
- Handles graceful shutdown
- Signal handling (SIGINT, SIGTERM)

### 6. CLI Interface (`src/cli.py`)
- Command-line interface using Click
- Daemon control commands:
  - start/stop/restart
  - status/queue
  - pause/resume
  - logs
- PID file management
- Foreground/background execution modes

## Data Flow

```
┌─────────────────┐
│  GitHub Issues  │
│  (Claude tag)   │
└────────┬────────┘
         │
         │ Poll (every 10 min)
         ▼
┌─────────────────┐
│ GitHub Watcher  │
│  - Detect new   │
│  - Track updates│
└────────┬────────┘
         │
         │ New/Updated Issue
         ▼
┌─────────────────┐
│   Task Queue    │
│  - Queue tasks  │
│  - Limit to 3   │
└────────┬────────┘
         │
         │ Next task
         ▼
┌─────────────────┐
│ Docker Manager  │
│  - Create tree  │
│  - Build image  │
│  - Run container│
└────────┬────────┘
         │
         │ Container running
         ▼
┌─────────────────┐
│  Claude Agent   │
│  - Plan/Execute │
│  - Post comments│
└────────┬────────┘
         │
         │ Complete
         ▼
┌─────────────────┐
│    Cleanup      │
│  - Remove tree  │
│  - Mark complete│
└─────────────────┘
```

## Threading Model

### Main Thread
- Initializes daemon
- Handles signals
- Waits for shutdown

### Polling Thread
- Runs every `POLL_INTERVAL` seconds (default: 600)
- Fetches issues from GitHub
- Adds new/updated issues to queue
- Uses shutdown event for graceful termination

### Processing Thread
- Continuously processes task queue
- Respects `MAX_CONCURRENT` limit
- Creates worktrees
- Starts containers
- Spawns monitor threads

### Monitor Threads (per container)
- One thread per running container
- Waits for container completion
- Handles success/failure
- Triggers cleanup
- Updates task status

### State Persistence Thread
- Runs every 60 seconds
- Saves queue state to JSON
- Ensures state survives restarts

## File Structure

```
claude_issue_solver/
├── src/
│   ├── __init__.py          # Package init
│   ├── config.py            # Configuration
│   ├── github_watcher.py    # GitHub integration
│   ├── docker_manager.py    # Docker management
│   ├── task_queue.py        # Queue & scheduling
│   ├── daemon.py            # Main service
│   └── cli.py               # CLI interface
├── claude-issue-solver      # Main executable
├── Dockerfile.claude        # Claude-enabled Docker image
├── requirements.txt         # Python dependencies
├── setup.py                 # Package setup
├── .env.example             # Config template
├── README.md                # User documentation
├── INSTALL.md               # Installation guide
└── ARCHITECTURE.md          # This file
```

## State Persistence

### PID File (`/tmp/claude-issue-solver.pid`)
- Contains daemon process ID
- Used to check if daemon is running
- Removed on clean shutdown

### State File (`/tmp/claude-issue-solver-state.json`)
- JSON format
- Contains:
  - Queue state (paused/running)
  - Running tasks
  - Queued tasks
  - Recent completed tasks (last 100)
- Updated every minute
- Loaded on daemon startup

## Docker Integration

### Image Building

1. **Base Development Image**
   - Built from target repo's `Dockerfile`
   - Tagged as `dev-base:latest`

2. **Claude-Enabled Image**
   - Extends base development image
   - Installs Claude CLI
   - Adds git configuration
   - Tagged as `claude-issue-solver:latest`

### Container Execution

- **Volumes**: Worktree mounted at `/workspace`
- **Environment**: Claude API key passed via env vars
- **Networking**: Bridge mode
- **Privileges**: Runs with `--privileged` flag
- **Lifecycle**: Auto-removed with `--rm` flag
- **Working Dir**: `/workspace`

## Security Considerations

### Dangerous Permissions
- Containers run with `--privileged` flag
- Full access to worktree filesystem
- Can make git commits and push changes

### Isolation
- Each issue gets isolated worktree
- Containers are removed after completion
- Worktrees cleaned up automatically

### Credentials
- GitHub token stored in environment
- Claude API key passed to containers
- Both should be kept secure

## Scalability Limits

- **Max Concurrent**: 3 containers (configurable)
- **Poll Interval**: 10 minutes minimum
- **Task History**: Last 100 completed tasks
- **State Updates**: Every 60 seconds

## Error Handling

### Container Failures
- Non-zero exit codes logged as failures
- Task marked as failed with error message
- Worktree still cleaned up

### Network Errors
- GitHub API failures logged but don't crash daemon
- Retried on next poll cycle

### Docker Errors
- Build failures prevent daemon start
- Container start failures mark task as failed

### Graceful Shutdown
- Signal handlers for SIGINT/SIGTERM
- Waits for threads to finish (5s timeout)
- Saves final state before exit
- Removes PID file
