# Verification Script Updates

## Summary

Updated `verify-setup.sh` to properly support:
1. GitHub App authentication
2. Repository URL configuration  
3. Claude CLI authentication detection
4. Virtual environment dependency checking

## Changes Made

### 1. Fixed Script Execution (Line 5)
Changed from `set -e` to `set +e` to prevent early exit on errors. The script now shows ALL issues instead of stopping at the first failure.

### 2. GitHub Authentication (Lines 103-145)
**Now detects both authentication methods:**
- ✅ GitHub Personal Access Token (from .env or environment)
- ✅ GitHub App credentials (App ID + private key file)

**Features:**
- Validates private key file exists
- Shows which authentication method is configured
- Only requires ONE method (not both)

### 3. GitHub Repository Detection (Lines 147-166)  
**Flexible repository configuration:**
- Checks both `.env` file AND environment variables
- Accepts `GITHUB_REPO` from either source
- No longer requires it to be in .env specifically

### 4. Claude API Key Detection (Lines 169-211)
**Now checks THREE sources:**
1. `.env` file: `CLAUDE_API_KEY`
2. Environment: `CLAUDE_API_KEY` or `ANTHROPIC_API_KEY`
3. Claude CLI: `~/.config/claude/config.json` or `~/.anthropic/config.json`

**Benefits:**
- Users who ran `claude auth login` don't need to set API key again
- Detects existing Claude CLI authentication
- Shows helpful error messages with both options

### 5. Python Dependencies (Lines 231-252)
**Intelligent dependency checking:**
- Automatically uses venv if available
- Falls back to system Python if no venv
- Checks for all required packages including PyJWT and cryptography
- Shows whether it's using venv or system Python

## Verification Script Output

### Successful Check:
```
✓ GitHub App credentials found in .env
✓ GitHub repo configured in .env
✓ Claude CLI is authenticated (using profile credentials)
✓ REPO_URL configured: https://github.com/Relationship-Lab/relab
✓ Python dependencies installed (Using virtual environment)
```

### Missing Credentials:
```
✗ Claude API key not found
   Option 1: Set CLAUDE_API_KEY or ANTHROPIC_API_KEY in .env or environment
   Option 2: Run 'claude auth login' to authenticate Claude CLI
```

## Configuration Updates

### config.py Changes

Added `_get_claude_cli_key()` method to read Claude API key from CLI config:

```python
def _get_claude_cli_key(self) -> Optional[str]:
    """Try to get Claude API key from Claude CLI configuration."""
    config_paths = [
        Path.home() / ".config" / "claude" / "config.json",
        Path.home() / ".anthropic" / "config.json",
    ]
    
    for config_path in config_paths:
        if config_path.exists():
            # Read and parse config.json
            # Return API key if found
```

**Fallback order:**
1. Check `CLAUDE_API_KEY` in .env
2. Check `CLAUDE_API_KEY` or `ANTHROPIC_API_KEY` in environment
3. Check Claude CLI config files
4. Raise error if none found

## Usage

### Run Verification:
```bash
./verify-setup.sh
```

### Expected Output (All Pass):
```
=== Claude Issue Solver Setup Verification ===

1. Checking Python...
✓ Python 3.9.6 (>= 3.9 required)

2. Checking Docker...
✓ Docker is running

3. Checking Git...
✓ git is installed

4. Checking credentials...
✓ .env file exists
  ✓ GitHub App credentials found in .env
  ✓ GitHub repo configured in .env
  ✓ Claude CLI is authenticated (using profile credentials)

5. Checking repository configuration...
✓ REPO_URL configured: https://github.com/Relationship-Lab/relab

6. Checking Python dependencies...
✓ Python dependencies installed
  Using virtual environment
```

## Testing

The script now properly handles all credential scenarios:

| Scenario | Detection | Result |
|----------|-----------|--------|
| API key in .env | ✅ Detects | Shows "found in .env" |
| API key in env var | ✅ Detects | Shows "found in environment" |
| Claude CLI auth | ✅ Detects | Shows "using profile credentials" |
| No credentials | ✅ Detects | Shows helpful error with options |
| GitHub App + key | ✅ Detects | Shows app credentials |
| GitHub token | ✅ Detects | Shows token found |
| Missing GITHUB_REPO | ✅ Detects | Shows error to set it |

## Benefits

1. **User-Friendly**: Detects credentials from multiple sources automatically
2. **Flexible**: Works with .env, environment variables, OR Claude CLI
3. **Informative**: Shows exactly where each credential was found
4. **Complete**: No longer exits early, shows all issues at once
5. **Smart**: Uses venv automatically if available
