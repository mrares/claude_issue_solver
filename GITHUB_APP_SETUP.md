# GitHub App Setup Guide

This guide explains how to set up GitHub App authentication for Claude Issue Solver, which is recommended for better security and higher rate limits.

## Why Use GitHub App?

**Advantages over Personal Access Tokens:**
- **Better Security**: Fine-grained permissions, no user account dependency
- **Higher Rate Limits**: 5,000 requests/hour vs 1,000 for tokens
- **Organization Control**: Centrally managed, can be restricted by org admins
- **Audit Trail**: Better tracking of automated actions
- **Token Auto-Refresh**: Installation tokens auto-refresh (managed by the tool)

## Step-by-Step Setup

### 1. Create a GitHub App

1. Go to your GitHub account settings:
   - Personal account: https://github.com/settings/apps
   - Organization: https://github.com/organizations/YOUR_ORG/settings/apps

2. Click **"New GitHub App"**

3. Fill in the required fields:
   - **GitHub App name**: `Claude Issue Solver` (or your preferred name)
   - **Homepage URL**: Your repository URL or `https://github.com`
   - **Webhook**: Uncheck "Active" (we don't need webhooks)

### 2. Set Permissions

Under **Repository permissions**, set:

- **Contents**: Read & write
  - _Needed to create branches and worktrees_
- **Issues**: Read & write
  - _Needed to read issues and post comments_
- **Pull requests**: Read & write
  - _Needed to create PRs with solutions_
- **Metadata**: Read-only (automatically set)

### 3. Configure Where to Install

Under **"Where can this GitHub App be installed?"**:
- Choose **"Only on this account"** (recommended)
- Or **"Any account"** if you want to use it across multiple organizations

### 4. Create the App

Click **"Create GitHub App"** at the bottom of the page.

### 5. Generate Private Key

1. After creation, you'll be on the app's settings page
2. Scroll down to **"Private keys"**
3. Click **"Generate a private key"**
4. A `.pem` file will download to your computer
5. Move this file to your Claude Issue Solver directory:
   ```bash
   mv ~/Downloads/your-app-name.*.private-key.pem ./claude-issue-solver-private-key.pem
   ```

### 6. Note Your App ID

On the app settings page, note the **App ID** (shown at the top). You'll need this for configuration.

### 7. Install the App on Your Repository

1. On the app settings page, click **"Install App"** in the left sidebar
2. Select your account/organization
3. Choose either:
   - **All repositories** (if you trust the app completely)
   - **Only select repositories** (recommended - choose your target repo)
4. Click **"Install"**

### 8. Configure Claude Issue Solver

Edit your `.env` file:

```bash
# GitHub App Authentication
GITHUB_APP_ID=123456  # Your App ID from step 6
GITHUB_PRIVATE_KEY_PATH=./claude-issue-solver-private-key.pem
# GITHUB_INSTALLATION_ID is optional - auto-detected if not set

# Remove or comment out GITHUB_TOKEN if you were using it before
# GITHUB_TOKEN=...

# Repository to monitor
GITHUB_REPO=owner/repository
```

**Note:** The installation ID is automatically detected by the tool. You only need to set `GITHUB_INSTALLATION_ID` manually if auto-detection fails.

### 9. Verify Setup

Run the verification script:

```bash
./verify-setup.sh
```

You should see:
```
✓ GitHub App credentials found in .env
```

### 10. Test Connection

Start the tool in dry-run mode to test authentication:

```bash
./claude-issue-solver start --dry-run --foreground
```

Watch the logs for:
```
INFO - Using GitHub App authentication
INFO - GitHub App token obtained, expires at ...
INFO - Connected to repository: owner/repo (via GitHub App)
```

## Troubleshooting

### "Failed to get installation token"

**Possible causes:**
1. App ID is incorrect
   - Check the App ID on your GitHub App settings page
2. Private key path is wrong
   - Verify the file exists: `ls -la claude-issue-solver-private-key.pem`
3. App not installed on repository
   - Go to app settings → Install App → verify repository is selected

### "Failed to connect to GitHub"

**Possible causes:**
1. Repository name format incorrect
   - Must be `owner/repository` (e.g., `octocat/Hello-World`)
2. App doesn't have permission for that repository
   - Check Installation settings, add the repository

### "No module named 'jwt'"

The dependencies aren't installed. Run:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Auto-detection of Installation ID Fails

If you see errors about installation detection, manually set it in `.env`:

1. Go to your app's installation page
2. Look at the URL: `https://github.com/settings/installations/123456`
3. The number at the end is your installation ID
4. Add to `.env`:
   ```bash
   GITHUB_INSTALLATION_ID=123456
   ```

## Security Best Practices

1. **Keep private key secure**:
   ```bash
   chmod 600 claude-issue-solver-private-key.pem
   ```

2. **Add to .gitignore**:
   ```bash
   echo "*.pem" >> .gitignore
   echo ".env" >> .gitignore
   ```

3. **Use organization apps for team use**: Install at org level, not personal account

4. **Review permissions regularly**: GitHub App settings → Permissions → Review

5. **Monitor usage**: GitHub App settings → Advanced → View logs

## Switching Back to Token Authentication

If you need to switch back to token authentication:

1. Edit `.env` and comment out app settings:
   ```bash
   # GitHub App Authentication
   # GITHUB_APP_ID=123456
   # GITHUB_PRIVATE_KEY_PATH=./claude-issue-solver-private-key.pem

   # Use token instead
   GITHUB_TOKEN=ghp_your_token_here
   ```

2. Restart the daemon:
   ```bash
   ./claude-issue-solver stop
   ./claude-issue-solver start
   ```

## Additional Resources

- [GitHub Apps Documentation](https://docs.github.com/en/apps)
- [Authenticating with GitHub Apps](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/about-authentication-with-a-github-app)
- [GitHub API Rate Limits](https://docs.github.com/en/rest/overview/resources-in-the-rest-api#rate-limiting)
