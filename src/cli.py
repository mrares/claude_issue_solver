"""Command-line interface for Claude Issue Solver daemon."""

import sys
import json
import logging
import signal
import time
from pathlib import Path
import click

from .config import get_config, set_config, Config
from .daemon import IssueSolverDaemon


def setup_logging(level: str = "INFO"):
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("/tmp/claude-issue-solver.log"),
        ],
    )


def get_daemon_pid() -> int:
    """Get the PID of the running daemon."""
    config = get_config()
    if not config.pid_file.exists():
        return None

    try:
        return int(config.pid_file.read_text().strip())
    except (ValueError, IOError):
        return None


def is_daemon_running() -> bool:
    """Check if daemon is running."""
    pid = get_daemon_pid()
    if pid is None:
        return False

    try:
        # Send signal 0 to check if process exists
        import os
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


@click.group()
@click.option("--log-level", default="INFO", help="Logging level")
def cli(log_level):
    """Claude Issue Solver - Automated GitHub issue resolution."""
    setup_logging(log_level)


@cli.command()
@click.option("--foreground", "-f", is_flag=True, help="Run in foreground")
@click.option("--dry-run", is_flag=True, help="Simulate actions without executing them")
@click.option("--one-time", is_flag=True, help="Run once through all issues and exit")
def start(foreground, dry_run, one_time):
    """Start the daemon."""
    if is_daemon_running() and not dry_run and not one_time:
        click.echo("Daemon is already running")
        sys.exit(1)

    if one_time:
        click.echo("Running Claude Issue Solver in ONE-TIME mode...")
        if dry_run:
            click.echo("(DRY-RUN: No actual changes will be made)\n")
    elif dry_run:
        click.echo("Starting Claude Issue Solver daemon in DRY-RUN mode...")
        click.echo("No worktrees will be created, no Docker containers will run.")
        click.echo("Actions will be logged to show what would happen.\n")
    else:
        click.echo("Starting Claude Issue Solver daemon...")

    try:
        # Set up config with dry-run mode if needed
        if dry_run:
            config = Config(dry_run=True)
            set_config(config)

        daemon = IssueSolverDaemon()

        if one_time:
            # Run once and exit
            daemon.run_once()
        elif foreground or dry_run:
            # Run in foreground (always foreground for dry-run)
            daemon.start()
        else:
            # Fork to background
            import os

            pid = os.fork()
            if pid > 0:
                # Parent process
                click.echo(f"Daemon started with PID {pid}")
                sys.exit(0)

            # Child process
            os.setsid()
            daemon.start()

    except Exception as e:
        click.echo(f"Failed to start daemon: {e}", err=True)
        sys.exit(1)


@cli.command()
def stop():
    """Stop the daemon."""
    if not is_daemon_running():
        click.echo("Daemon is not running")
        sys.exit(1)

    pid = get_daemon_pid()
    click.echo(f"Stopping daemon (PID {pid})...")

    try:
        import os
        os.kill(pid, signal.SIGTERM)

        # Wait for daemon to stop
        for _ in range(30):
            if not is_daemon_running():
                click.echo("Daemon stopped successfully")
                return
            time.sleep(0.5)

        # Force kill if still running
        click.echo("Daemon did not stop gracefully, forcing...")
        os.kill(pid, signal.SIGKILL)
        click.echo("Daemon killed")

    except Exception as e:
        click.echo(f"Failed to stop daemon: {e}", err=True)
        sys.exit(1)


@cli.command()
def restart():
    """Restart the daemon."""
    if is_daemon_running():
        click.echo("Stopping daemon...")
        ctx = click.get_current_context()
        ctx.invoke(stop)
        time.sleep(2)

    click.echo("Starting daemon...")
    ctx = click.get_current_context()
    ctx.invoke(start)


@cli.command()
def status():
    """Show daemon status."""
    if not is_daemon_running():
        click.echo("Daemon is not running")
        sys.exit(1)

    config = get_config()

    # Load state file
    if not config.state_file.exists():
        click.echo("No state file found")
        sys.exit(1)

    try:
        with open(config.state_file) as f:
            state = json.load(f)

        click.echo("=== Claude Issue Solver Status ===\n")
        click.echo(f"PID: {get_daemon_pid()}")
        click.echo(f"Paused: {state.get('paused', False)}")
        click.echo(f"Running tasks: {len(state.get('running', []))}/{config.max_concurrent}")
        click.echo(f"Queued tasks: {len(state.get('queued', []))}")
        click.echo()

        # Running tasks
        running = state.get("running", [])
        if running:
            click.echo("Running Tasks:")
            for task in running:
                click.echo(f"  - Issue #{task['issue_number']}: {task['issue_title']}")
                click.echo(f"    Started: {task.get('started_at', 'N/A')}")
            click.echo()

        # Queued tasks
        queued = state.get("queued", [])
        if queued:
            click.echo("Queued Tasks:")
            for task in queued:
                click.echo(f"  - Issue #{task['issue_number']}: {task['issue_title']}")
            click.echo()

        # Recent completed
        completed = state.get("completed", [])
        if completed:
            click.echo("Recent Completed Tasks:")
            for task in completed[-5:]:
                status_icon = "✓" if task['status'] == "completed" else "✗"
                click.echo(f"  {status_icon} Issue #{task['issue_number']}: {task['issue_title']}")
                click.echo(f"    Status: {task['status']}")
                if task.get('error'):
                    click.echo(f"    Error: {task['error']}")

    except Exception as e:
        click.echo(f"Failed to read status: {e}", err=True)
        sys.exit(1)


@cli.command()
def queue():
    """Show work queue."""
    if not is_daemon_running():
        click.echo("Daemon is not running")
        sys.exit(1)

    config = get_config()

    try:
        with open(config.state_file) as f:
            state = json.load(f)

        click.echo("=== Work Queue ===\n")

        # Running
        running = state.get("running", [])
        click.echo(f"Running ({len(running)}):")
        for task in running:
            click.echo(f"  #{task['issue_number']}: {task['issue_title']}")

        # Queued
        queued = state.get("queued", [])
        click.echo(f"\nQueued ({len(queued)}):")
        for task in queued:
            impl_tag = " [IMPLEMENT]" if task.get('has_implement_tag') else ""
            click.echo(f"  #{task['issue_number']}: {task['issue_title']}{impl_tag}")

    except Exception as e:
        click.echo(f"Failed to read queue: {e}", err=True)
        sys.exit(1)


@cli.command()
def pause():
    """Pause task execution."""
    if not is_daemon_running():
        click.echo("Daemon is not running")
        sys.exit(1)

    config = get_config()

    try:
        with open(config.state_file) as f:
            state = json.load(f)

        state["paused"] = True

        with open(config.state_file, "w") as f:
            json.dump(state, f, indent=2)

        click.echo("Daemon paused (currently running tasks will complete)")

    except Exception as e:
        click.echo(f"Failed to pause daemon: {e}", err=True)
        sys.exit(1)


@cli.command()
def resume():
    """Resume task execution."""
    if not is_daemon_running():
        click.echo("Daemon is not running")
        sys.exit(1)

    config = get_config()

    try:
        with open(config.state_file) as f:
            state = json.load(f)

        state["paused"] = False

        with open(config.state_file, "w") as f:
            json.dump(state, f, indent=2)

        click.echo("Daemon resumed")

    except Exception as e:
        click.echo(f"Failed to resume daemon: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("issue_number", type=int)
def logs(issue_number):
    """Show logs for a specific issue."""
    if not is_daemon_running():
        click.echo("Daemon is not running")
        sys.exit(1)

    try:
        from .docker_manager import DockerManager

        docker = DockerManager()
        docker.connect()

        logs = docker.get_container_logs(issue_number)

        if logs:
            click.echo(f"=== Logs for Issue #{issue_number} ===\n")
            click.echo(logs)
        else:
            click.echo(f"No container found for issue #{issue_number}")

    except Exception as e:
        click.echo(f"Failed to get logs: {e}", err=True)
        sys.exit(1)


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
