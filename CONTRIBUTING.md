# Contributing to Claude Issue Solver

## Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/yourusername/claude-issue-solver.git
   cd claude-issue-solver
   ```

2. **Create Virtual Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -e .  # Install in development mode
   ```

4. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

## Testing

### Manual Testing

1. **Start in Foreground**
   ```bash
   ./claude-issue-solver start --foreground
   ```

2. **Create Test Issue**
   - Create an issue in your test repository
   - Add `Claude` label
   - Wait for daemon to detect it

3. **Check Status**
   ```bash
   ./claude-issue-solver status
   ./claude-issue-solver queue
   ```

### Automated Tests

(To be added)

## Code Style

- Follow PEP 8
- Use type hints
- Add docstrings to all functions
- Keep functions focused and small
- Use descriptive variable names

## Adding Features

### New Configuration Options

1. Add to `src/config.py`
2. Update `.env.example`
3. Add validation
4. Document in README.md

### New CLI Commands

1. Add command to `src/cli.py`
2. Follow Click conventions
3. Update help text
4. Document in README.md

### New Docker Features

1. Modify `src/docker_manager.py`
2. Update `Dockerfile.claude` if needed
3. Test thoroughly
4. Document any new requirements

## Pull Request Process

1. Create feature branch
   ```bash
   git checkout -b feature/my-feature
   ```

2. Make changes and commit
   ```bash
   git add .
   git commit -m "feat: add my feature"
   ```

3. Push and create PR
   ```bash
   git push origin feature/my-feature
   ```

4. Ensure PR description includes:
   - What changed
   - Why it changed
   - How to test
   - Any breaking changes

## Commit Message Format

Use conventional commits:

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `refactor:` - Code refactoring
- `test:` - Test additions/changes
- `chore:` - Build/tool changes

Example: `feat: add pause/resume functionality`

## Questions?

Open an issue for discussion!
