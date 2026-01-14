# GitHub App Authentication Support - Changelog

## Overview

Added support for GitHub App authentication as an alternative to Personal Access Tokens. This provides better security, higher rate limits, and improved organization control.

## Changes Made

### 1. Dependencies Added

**requirements.txt:**
- `PyJWT>=2.8.0` - For generating JWTs to authenticate as GitHub App
- `cryptography>=41.0.0` - For signing JWTs with RSA private key

### 2. Configuration Changes

**src/config.py:**
- Added GitHub App configuration fields:
  - `github_app_id` - GitHub App ID
  - `github_private_key_path` - Path to private key file
  - `github_installation_id` - Optional installation ID (auto-detected if not set)
- Made `github_token` optional (was required before)
- Added validation to ensure either token OR app credentials are provided
- Added `is_using_github_app()` helper method
- Private key file existence validation

**\.env.example:**
- Added GitHub App configuration section
- Documented both authentication methods (token vs app)
- Added comments explaining when to use each method

### 3. GitHub API Integration

**src/github_watcher.py (Complete Rewrite):**

New methods for GitHub App authentication:
- `_generate_jwt()` - Generates JWT signed with private key
- `_get_installation_token()` - Retrieves installation access token
  - Caches token to avoid unnecessary API calls
  - Auto-detects installation ID if not configured
  - Refreshes token before expiry (5-minute buffer)
- `_create_github_client()` - Factory method that selects auth type
- `_ensure_valid_token()` - Checks and refreshes tokens before API calls

Enhanced existing methods:
- `connect()` - Now detects and logs auth method being used
- `get_claude_issues()` - Calls `_ensure_valid_token()` before API requests
- `get_issue_details()` - Calls `_ensure_valid_token()` before API requests

### 4. Documentation

**README.md:**
- Updated requirements to include "GitHub App" option
- Added "GitHub Authentication" section explaining both methods
- Step-by-step setup instructions for both token and app
- Added required permissions for GitHub App

**GITHUB_APP_SETUP.md (New):**
- Comprehensive guide for creating and configuring GitHub App
- Troubleshooting section
- Security best practices
- Benefits explanation

**verify-setup.sh:**
- Updated to check for GitHub App credentials in addition to token
- Validates private key file exists
- Shows which authentication method is configured

## Authentication Flow

### GitHub App Flow:
1. Read private key from configured path
2. Generate JWT with app_id, signed with private key (valid 10 minutes)
3. Use JWT to authenticate with GitHub API as the app
4. Get installation token for specific repository installation
5. Cache installation token (valid ~1 hour)
6. Before each API request, check if token needs refresh (5-min buffer)
7. Auto-refresh token when needed

### Token Caching:
- Installation tokens cached in memory
- Automatic refresh 5 minutes before expiry
- Reduces API calls and improves performance

## Configuration Examples

### Using Personal Access Token:
```bash
GITHUB_TOKEN=ghp_your_token_here
GITHUB_REPO=owner/repository
```

### Using GitHub App:
```bash
GITHUB_APP_ID=123456
GITHUB_PRIVATE_KEY_PATH=./private-key.pem
GITHUB_REPO=owner/repository
# GITHUB_INSTALLATION_ID=789012  # Optional, auto-detected
```

## Backward Compatibility

- **Fully backward compatible** - existing token-based setups continue to work
- Tool automatically detects which auth method to use based on configuration
- No changes required to existing .env files using tokens

## Testing

To test the implementation:

1. Set up GitHub App credentials in `.env`
2. Run verification:
   ```bash
   ./verify-setup.sh
   ```
3. Test in dry-run mode:
   ```bash
   ./claude-issue-solver start --dry-run --foreground
   ```
4. Check logs for "Using GitHub App authentication" message

## Security Notes

- Private keys should be kept secure (chmod 600)
- Private keys should never be committed to git
- Installation tokens auto-refresh and are managed by the tool
- JWT tokens are short-lived (10 minutes)
- Fine-grained permissions limit what the app can do

## Rate Limits

- **Token**: 1,000 requests/hour per user
- **GitHub App**: 5,000 requests/hour per installation
- This 5x increase is significant for repositories with many issues

## Future Enhancements

Potential improvements for future versions:
- Support for multiple installations (monitor multiple repos)
- Webhook support for real-time issue notifications
- Better error messages for common setup issues
- Automatic rotation of expired private keys
