# Claude Issue Solver Instructions

This file provides instructions for Claude AI agents working on GitHub issues.

## Workflow

### Planning Phase (No `Implement` tag)

When an issue has the `Claude` tag but NOT the `Implement` tag:

1. **Read the Issue**
   - Understand the problem or feature request
   - Review all comments and context
   - Check if a plan already exists

2. **Check for Existing Plan**
   - If a plan exists and there are new user comments:
     - Review the feedback
     - Update the plan accordingly
     - Post updated plan as a new comment
     - End session

3. **Create a Plan**
   - If no plan exists:
     - Design a clear implementation approach
     - Break down into specific steps
     - Identify files that need changes
     - Consider edge cases and testing
     - Post the plan as a comment
     - End session

4. **Ask Questions**
   - If requirements are unclear, ask questions as comments
   - Wait for user clarification
   - End session after posting questions

### Implementation Phase (Has `Implement` tag)

When an issue has both `Claude` and `Implement` tags:

1. **Review the Plan**
   - Read the approved plan from issue comments
   - Review any additional user feedback
   - Understand the expected outcome

2. **Execute the Plan**
   - Follow the plan step by step
   - Make necessary code changes
   - Ensure code quality and style consistency
   - Add appropriate tests if needed
   - Follow coding best practices

3. **Create Pull Request**
   - Commit changes with descriptive messages
   - Create a pull request referencing the issue
   - Summarize changes in PR description
   - End session

4. **Handle Issues**
   - If blocked, post a comment explaining the blocker
   - If requirements conflict, ask for clarification
   - If tests fail, fix and retry

## Best Practices

### Code Quality
- Follow existing code style and patterns
- Write clear, self-documenting code
- Add comments only where logic is complex
- Ensure backwards compatibility
- Handle error cases properly

### Testing
- Run existing tests before changes
- Add tests for new functionality
- Ensure all tests pass before committing
- Test edge cases

### Git Workflow
- Use descriptive commit messages
- Keep commits focused and atomic
- Create branches named `issue-<number>`
- Reference issue number in commits

### Communication
- Post clear, concise comments
- Update issue status as you progress
- Ask questions when blocked
- Summarize work completed

## Example Plan Format

```markdown
## Implementation Plan for Issue #123

### Overview
Brief description of what needs to be done.

### Files to Change
- `src/module.py` - Add new function
- `tests/test_module.py` - Add tests
- `README.md` - Update documentation

### Steps
1. Create new function `doSomething()` in `src/module.py`
2. Add input validation
3. Implement core logic
4. Add error handling
5. Write unit tests
6. Update documentation
7. Run full test suite

### Considerations
- Ensure backwards compatibility
- Handle edge case where X happens
- Performance impact should be minimal

### Testing
- Unit tests for happy path
- Tests for error conditions
- Integration test with existing feature Y
```

## Issue Labels

- `Claude` - Issue should be processed by Claude
- `Implement` - Plan is approved, proceed with implementation
- Additional labels may provide context (e.g., `bug`, `feature`, `high-priority`)

## Session Ending

Always end your session cleanly:

1. Post final status comment
2. If planning phase: Wait for user approval
3. If implementation phase: Create PR and link to issue
4. Exit gracefully

## Troubleshooting

### Can't Find Files
- Check if repository structure matches plan
- Ask user for clarification

### Tests Failing
- Fix the failing tests
- Don't commit broken code
- If stuck, post comment with error details

### Conflicting Requirements
- Post comment asking for clarification
- Don't make assumptions
- Wait for user guidance

## Remember

- You have full git access within the worktree
- You can commit changes
- You are isolated from other issues
- Your work is in a branch named `issue-<number>`
- The container has dangerous permissions - use carefully
- Always follow security best practices
