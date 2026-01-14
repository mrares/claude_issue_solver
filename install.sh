#!/bin/bash
# Installation script for Claude Issue Solver

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        Claude Issue Solver - Installation Script        ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo

# Check Python version
echo -e "${YELLOW}[1/5]${NC} Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 not found${NC}"
    echo "Please install Python 3.9 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 9 ]); then
    echo -e "${RED}Error: Python 3.9+ required, found $PYTHON_VERSION${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION found"
echo

# Create virtual environment
echo -e "${YELLOW}[2/5]${NC} Creating virtual environment..."
if [ -d "venv" ]; then
    echo -e "${YELLOW}!${NC} Virtual environment already exists"
    read -p "Remove and recreate? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf venv
        python3 -m venv venv
        echo -e "${GREEN}✓${NC} Virtual environment recreated"
    else
        echo -e "${YELLOW}!${NC} Using existing virtual environment"
    fi
else
    python3 -m venv venv
    echo -e "${GREEN}✓${NC} Virtual environment created"
fi
echo

# Activate virtual environment
echo -e "${YELLOW}[3/5]${NC} Activating virtual environment..."
source venv/bin/activate
echo -e "${GREEN}✓${NC} Virtual environment activated"
echo

# Upgrade pip
echo -e "${YELLOW}[4/5]${NC} Upgrading pip..."
pip install --upgrade pip --quiet
echo -e "${GREEN}✓${NC} pip upgraded"
echo

# Install dependencies
echo -e "${YELLOW}[5/5]${NC} Installing dependencies..."
pip install -r requirements.txt --quiet
echo -e "${GREEN}✓${NC} Dependencies installed"
echo

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}!${NC} Creating .env file from template..."
    cp .env.example .env
    echo -e "${GREEN}✓${NC} .env file created"
    echo -e "${YELLOW}⚠${NC}  Please edit .env and add your credentials:"
    echo "   - GITHUB_TOKEN"
    echo "   - GITHUB_REPO"
    echo "   - CLAUDE_API_KEY"
    echo "   - REPO_PATH"
    echo
else
    echo -e "${GREEN}✓${NC} .env file already exists"
    echo
fi

# Make scripts executable
chmod +x claude-issue-solver
chmod +x verify-setup.sh

echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Installation Complete! ✓                    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo
echo -e "${BLUE}Next steps:${NC}"
echo
echo -e "1. ${YELLOW}Configure environment:${NC}"
echo -e "   ${BLUE}nano .env${NC}"
echo
echo -e "2. ${YELLOW}Verify setup:${NC}"
echo -e "   ${BLUE}./verify-setup.sh${NC}"
echo
echo -e "3. ${YELLOW}Activate virtual environment:${NC}"
echo -e "   ${BLUE}source venv/bin/activate${NC}"
echo
echo -e "4. ${YELLOW}Start the daemon:${NC}"
echo -e "   ${BLUE}./claude-issue-solver start --foreground${NC}"
echo
echo -e "${GREEN}For more information, see QUICKSTART.md${NC}"
echo
