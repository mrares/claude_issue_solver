#!/bin/bash
# Setup verification script for Claude Issue Solver

# Don't exit on errors - we want to show all issues
set +e

echo "=== Claude Issue Solver Setup Verification ==="
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check functions
check_command() {
    if command -v $1 &> /dev/null; then
        echo -e "${GREEN}✓${NC} $1 is installed"
        $1 --version 2>&1 | head -n1 | sed 's/^/  /'
        return 0
    else
        echo -e "${RED}✗${NC} $1 is not installed"
        return 1
    fi
}

check_python_version() {
    if command -v python3 &> /dev/null; then
        VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        MAJOR=$(echo $VERSION | cut -d. -f1)
        MINOR=$(echo $VERSION | cut -d. -f2)

        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 9 ]; then
            echo -e "${GREEN}✓${NC} Python $VERSION (>= 3.9 required)"
            return 0
        else
            echo -e "${RED}✗${NC} Python $VERSION (>= 3.9 required)"
            return 1
        fi
    else
        echo -e "${RED}✗${NC} Python 3 is not installed"
        return 1
    fi
}

check_docker_running() {
    if docker ps &> /dev/null; then
        echo -e "${GREEN}✓${NC} Docker is running"
        docker --version | sed 's/^/  /'
        return 0
    else
        echo -e "${RED}✗${NC} Docker is not running or not accessible"
        return 1
    fi
}

check_credential() {
    local var_name=$1
    local alt_vars=$2
    local description=$3

    # Check .env file first
    if [ -f ".env" ]; then
        if grep -q "^${var_name}=" .env && ! grep -q "^${var_name}=$\|^${var_name}=your_" .env; then
            echo -e "  ${GREEN}✓${NC} ${description} found in .env"
            return 0
        fi
    fi

    # Check environment variables
    if [ -n "${!var_name}" ]; then
        echo -e "  ${GREEN}✓${NC} ${description} found in environment (${var_name})"
        return 0
    fi

    # Check alternative environment variables
    for alt in $alt_vars; do
        if [ -n "${!alt}" ]; then
            echo -e "  ${GREEN}✓${NC} ${description} found in environment (${alt})"
            return 0
        fi
    done

    # Not found anywhere
    echo -e "  ${RED}✗${NC} ${description} not found"
    echo -e "     Set in .env or environment (${var_name})"
    [ -n "$alt_vars" ] && echo -e "     Alternative vars: ${alt_vars}"
    return 1
}

check_env_file() {
    if [ -f ".env" ]; then
        echo -e "${GREEN}✓${NC} .env file exists"
    else
        echo -e "${YELLOW}!${NC} .env file not found (will use environment variables)"
    fi

    echo
    echo "Checking credentials (checks .env and environment):"

    local all_ok=0

    # Check GitHub authentication (token OR app)
    local has_token=0
    local has_app=0

    # Check for GitHub token (but don't fail if not found - app might be used)
    if [ -f ".env" ]; then
        if grep -q "^GITHUB_TOKEN=" .env && ! grep -q "^GITHUB_TOKEN=$\|^GITHUB_TOKEN=your_" .env; then
            echo -e "  ${GREEN}✓${NC} GitHub token found in .env"
            has_token=1
        fi
    fi

    if [ $has_token -eq 0 ]; then
        if [ -n "$GITHUB_TOKEN" ]; then
            echo -e "  ${GREEN}✓${NC} GitHub token found in environment (GITHUB_TOKEN)"
            has_token=1
        elif [ -n "$GH_TOKEN" ]; then
            echo -e "  ${GREEN}✓${NC} GitHub token found in environment (GH_TOKEN)"
            has_token=1
        fi
    fi

    # Check for GitHub App credentials
    if [ -f ".env" ]; then
        if grep -q "^GITHUB_APP_ID=" .env && ! grep -q "^GITHUB_APP_ID=$\|^GITHUB_APP_ID=your_" .env; then
            if grep -q "^GITHUB_PRIVATE_KEY_PATH=" .env && ! grep -q "^GITHUB_PRIVATE_KEY_PATH=$\|^GITHUB_PRIVATE_KEY_PATH=./path" .env; then
                PRIVATE_KEY_PATH=$(grep "^GITHUB_PRIVATE_KEY_PATH=" .env | cut -d= -f2)
                if [ -f "$PRIVATE_KEY_PATH" ]; then
                    echo -e "  ${GREEN}✓${NC} GitHub App credentials found in .env"
                    has_app=1
                else
                    echo -e "  ${RED}✗${NC} GitHub App private key not found: $PRIVATE_KEY_PATH"
                fi
            fi
        fi
    fi

    # Must have either token or app
    if [ $has_token -eq 0 ] && [ $has_app -eq 0 ]; then
        echo -e "  ${RED}✗${NC} No GitHub authentication found"
        echo -e "     Provide either GITHUB_TOKEN or GitHub App credentials"
        all_ok=1
    fi

    # Check GitHub repo (can be in .env or environment)
    local has_repo=0

    if [ -f ".env" ]; then
        if grep -q "^GITHUB_REPO=" .env && ! grep -q "^GITHUB_REPO=$\|^GITHUB_REPO=owner" .env; then
            echo -e "  ${GREEN}✓${NC} GitHub repo configured in .env"
            has_repo=1
        fi
    fi

    if [ $has_repo -eq 0 ] && [ -n "$GITHUB_REPO" ]; then
        echo -e "  ${GREEN}✓${NC} GitHub repo found in environment"
        has_repo=1
    fi

    if [ $has_repo -eq 0 ]; then
        echo -e "  ${RED}✗${NC} GitHub repo not found"
        echo -e "     Set GITHUB_REPO in .env or environment"
        all_ok=1
    fi

    # Check Claude API key (CLAUDE_API_KEY, ANTHROPIC_API_KEY, or CLI auth)
    local has_claude_key=0

    # Check .env file
    if [ -f ".env" ]; then
        if grep -q "^CLAUDE_API_KEY=" .env && ! grep -q "^CLAUDE_API_KEY=$\|^CLAUDE_API_KEY=your_" .env; then
            echo -e "  ${GREEN}✓${NC} Claude API key found in .env"
            has_claude_key=1
        fi
    fi

    # Check environment variables
    if [ $has_claude_key -eq 0 ]; then
        if [ -n "$CLAUDE_API_KEY" ]; then
            echo -e "  ${GREEN}✓${NC} Claude API key found in environment (CLAUDE_API_KEY)"
            has_claude_key=1
        elif [ -n "$ANTHROPIC_API_KEY" ]; then
            echo -e "  ${GREEN}✓${NC} Claude API key found in environment (ANTHROPIC_API_KEY)"
            has_claude_key=1
        fi
    fi

    # Check Claude CLI authentication
    if [ $has_claude_key -eq 0 ]; then
        # On macOS, check the Keychain for Claude credentials
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # Try to find Claude credentials in Keychain
            for service in "Claude Code-credentials" "claude.ai" "Claude" "anthropic.com"; do
                if security find-generic-password -s "$service" -w &> /dev/null; then
                    echo -e "  ${GREEN}✓${NC} Claude credentials found in macOS Keychain (service: $service)"
                    has_claude_key=1
                    break
                fi
            done
        fi

        # Check for credentials file (Linux) or config files
        if [ $has_claude_key -eq 0 ]; then
            if [ -f "$HOME/.claude/.credentials.json" ]; then
                echo -e "  ${GREEN}✓${NC} Claude credentials found in ~/.claude/.credentials.json"
                has_claude_key=1
            elif [ -f "$HOME/.config/claude/config.json" ] || [ -f "$HOME/.anthropic/config.json" ]; then
                echo -e "  ${GREEN}✓${NC} Claude CLI is authenticated (using profile credentials)"
                has_claude_key=1
            fi
        fi
    fi

    # If still not found, report error
    if [ $has_claude_key -eq 0 ]; then
        echo -e "  ${RED}✗${NC} Claude API key not found"
        echo -e "     Option 1: Set CLAUDE_API_KEY or ANTHROPIC_API_KEY in .env or environment"
        echo -e "     Option 2: Run 'claude auth login' to authenticate Claude CLI (stores in Keychain on macOS)"
        all_ok=1
    fi

    return $all_ok
}

check_repo_config() {
    local has_url=0
    local has_path=0

    # Check for REPO_URL
    if [ -f ".env" ]; then
        if grep -q "^REPO_URL=" .env && ! grep -q "^REPO_URL=$\|^REPO_URL=https://github.com/owner" .env; then
            REPO_URL=$(grep "^REPO_URL=" .env | cut -d= -f2)
            echo -e "${GREEN}✓${NC} REPO_URL configured: $REPO_URL"
            echo -e "  ${YELLOW}→${NC} Repository will be cloned automatically"
            has_url=1
        fi

        # Check for REPO_PATH
        if grep -q "^REPO_PATH=" .env && ! grep -q "^REPO_PATH=$\|^REPO_PATH=/path/to" .env; then
            REPO_PATH=$(grep "^REPO_PATH=" .env | cut -d= -f2)
            if [ -d "$REPO_PATH" ]; then
                if [ -d "$REPO_PATH/.git" ]; then
                    echo -e "${GREEN}✓${NC} REPO_PATH is valid git repo: $REPO_PATH"
                    has_path=1
                else
                    echo -e "${RED}✗${NC} REPO_PATH is not a git repo: $REPO_PATH"
                    return 1
                fi
            else
                echo -e "${RED}✗${NC} REPO_PATH does not exist: $REPO_PATH"
                return 1
            fi
        fi
    fi

    # Check environment
    if [ -n "$REPO_URL" ] && [ $has_url -eq 0 ]; then
        echo -e "${GREEN}✓${NC} REPO_URL in environment: $REPO_URL"
        has_url=1
    fi

    if [ -n "$REPO_PATH" ] && [ $has_path -eq 0 ]; then
        if [ -d "$REPO_PATH" ] && [ -d "$REPO_PATH/.git" ]; then
            echo -e "${GREEN}✓${NC} REPO_PATH in environment: $REPO_PATH"
            has_path=1
        fi
    fi

    # Must have at least one
    if [ $has_url -eq 0 ] && [ $has_path -eq 0 ]; then
        echo -e "${RED}✗${NC} Neither REPO_URL nor REPO_PATH configured"
        echo -e "  ${YELLOW}→${NC} Set REPO_URL (recommended) or REPO_PATH in .env"
        return 1
    fi

    return 0
}

check_python_deps() {
    # Use venv python if available, otherwise system python
    local python_cmd="python3"
    if [ -f "venv/bin/python" ]; then
        python_cmd="venv/bin/python"
    fi

    if $python_cmd -c "import click, github, docker, dotenv, psutil, jwt, cryptography" 2> /dev/null; then
        echo -e "${GREEN}✓${NC} Python dependencies installed"
        if [ "$python_cmd" = "venv/bin/python" ]; then
            echo "  Using virtual environment"
        fi
        return 0
    else
        echo -e "${RED}✗${NC} Python dependencies not installed"
        if [ -d "venv" ]; then
            echo "  Run: source venv/bin/activate && pip install -r requirements.txt"
        else
            echo "  Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
        fi
        return 1
    fi
}

# Run checks
echo "1. Checking Python..."
check_python_version
echo

echo "2. Checking Docker..."
check_docker_running
echo

echo "3. Checking Git..."
check_command git
echo

echo "4. Checking credentials..."
check_env_file
echo

echo "5. Checking repository configuration..."
check_repo_config
echo

echo "6. Checking Python dependencies..."
check_python_deps
echo

echo "=== Summary ==="
echo
echo "If all checks pass, you can start the daemon with:"
echo
echo "Test first with dry-run mode:"
echo "  ./claude-issue-solver start --dry-run"
echo
echo "Then run in foreground for first-time use:"
echo "  ./claude-issue-solver start --foreground"
echo
echo "Or start in background:"
echo "  ./claude-issue-solver start"
echo
echo -e "${YELLOW}Note:${NC} Credentials can be in .env file OR environment variables"
echo "  GitHub: GITHUB_TOKEN/GH_TOKEN OR GitHub App (GITHUB_APP_ID + private key)"
echo "  Claude: CLAUDE_API_KEY, ANTHROPIC_API_KEY, or macOS Keychain (via 'claude auth login')"
echo "  Repo: GITHUB_REPO in .env or environment"
echo
echo "For GitHub App setup, see GITHUB_APP_SETUP.md"
echo "For general instructions, see QUICKSTART.md"
