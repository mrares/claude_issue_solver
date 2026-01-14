# Setup Status

## ✅ Completed Configuration

### GitHub Authentication (GitHub App)
- ✅ `GITHUB_APP_ID`: 104229879
- ✅ `GITHUB_PRIVATE_KEY_PATH`: ./claude-issue-solver.2026-01-14.private-key.pem
- ✅ Private key file exists and is readable

### Repository Configuration
- ✅ `GITHUB_REPO`: Relationship-Lab/relab (repository to monitor for issues)
- ✅ `REPO_URL`: https://github.com/Relationship-Lab/relab (will be cloned for worktrees)

### Paths
- ✅ `WORKTREE_BASE`: ./claude-worktrees (relative path)
- ✅ `REPO_CACHE`: ./claude-repos (relative path)
- ✅ `PID_FILE`: ./claude-issue-solver.pid
- ✅ `STATE_FILE`: ./claude-issue-solver-state.json

### Daemon Settings
- ✅ `POLL_INTERVAL`: 600 seconds (10 minutes)
- ✅ `MAX_CONCURRENT`: 3 containers
- ✅ `LOG_LEVEL`: INFO

## ⚠️ Missing Configuration

### Claude API Key
You need to set one of:
- `CLAUDE_API_KEY` in .env file, OR
- `CLAUDE_API_KEY` or `ANTHROPIC_API_KEY` in environment

To add to .env:
```bash
# Uncomment and add your key:
CLAUDE_API_KEY=sk-ant-api03-...
```

Or export as environment variable:
```bash
export ANTHROPIC_API_KEY=sk-ant-api03-...
```

## Verification

Run the setup verification:
```bash
./verify-setup.sh
```

Expected output once Claude API key is set:
```
✓ GitHub App credentials found in .env
✓ GitHub repo configured in .env
✓ Claude API key found
✓ REPO_URL configured
✓ Python dependencies installed
```

## Next Steps

1. **Add Claude API Key** (see above)

2. **Test Configuration** (dry-run mode):
   ```bash
   ./claude-issue-solver start --dry-run --foreground
   ```

3. **Verify GitHub App Permissions**:
   - Go to https://github.com/apps/your-app-name
   - Confirm it has permissions for `Relationship-Lab/relab`:
     - Contents: Read & Write
     - Issues: Read & Write
     - Pull Requests: Read & Write

4. **Test with Real Issue**:
   - Create an issue in `Relationship-Lab/relab`
   - Add the `Claude` label
   - Start the daemon: `./claude-issue-solver start --foreground`
   - Watch for Claude to pick up and process the issue

## Authentication Flow (GitHub App)

With your current setup:
1. ✅ Read private key from `./claude-issue-solver.2026-01-14.private-key.pem`
2. ✅ Generate JWT signed with private key (app ID: 104229879)
3. ✅ Auto-detect installation ID for `Relationship-Lab/relab`
4. ✅ Get installation access token (valid ~1 hour)
5. ✅ Monitor `Relationship-Lab/relab` for issues with `Claude` label
6. ✅ Clone from `https://github.com/Relationship-Lab/relab` for worktrees

## Benefits of Your Setup

✅ **GitHub App Auth**: 5,000 requests/hour (vs 1,000 for tokens)  
✅ **Auto-token refresh**: Managed automatically  
✅ **Relative paths**: Worktrees in project directory (not /tmp)  
✅ **Repository cloning**: Automatic from GitHub URL  

## Troubleshooting

If you see "No module named 'jwt'" when running:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

If private key permissions error:
```bash
chmod 600 ./claude-issue-solver.2026-01-14.private-key.pem
```

For detailed GitHub App setup, see [GITHUB_APP_SETUP.md](GITHUB_APP_SETUP.md)
