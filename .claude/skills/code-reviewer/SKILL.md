---
name: code-reviewer
description: "Specialized code review skill that provides comprehensive analysis of Python code. Use this skill when reviewing code for quality, bugs, security issues, and best practices. The reviewer examines code structure, identifies potential problems, and suggests improvements."
allowed-tools: Read, Glob, Grep
---

# Code Reviewer Skill

A comprehensive code review skill for Python projects. This skill helps Claude perform thorough, consistent code reviews following industry best practices.

## When to Use This Skill

Use this skill when the user asks to:
- Review Python code for quality issues
- Find potential bugs or security vulnerabilities
- Suggest code improvements and refactoring
- Check adherence to coding standards
- Analyze code complexity and maintainability

## Review Process

### 1. Initial Assessment

First, understand the code's purpose:
- Read the file and any related files
- Identify the main functionality
- Note the coding style and patterns used

### 2. Review Categories

Analyze the code across these dimensions:

#### Code Quality
- [ ] Clear variable and function names
- [ ] Appropriate function length (< 50 lines ideally)
- [ ] Single responsibility principle
- [ ] DRY (Don't Repeat Yourself)
- [ ] Consistent formatting and style

#### Potential Bugs
- [ ] Off-by-one errors
- [ ] Null/None handling
- [ ] Exception handling
- [ ] Edge cases
- [ ] Type mismatches

#### Security Issues
- [ ] Input validation
- [ ] SQL injection risks
- [ ] Command injection risks
- [ ] Sensitive data exposure
- [ ] Insecure defaults

#### Performance
- [ ] Unnecessary loops
- [ ] Inefficient data structures
- [ ] Memory leaks
- [ ] Blocking operations in async code

#### Best Practices
- [ ] Type hints usage
- [ ] Docstrings presence
- [ ] Error messages quality
- [ ] Logging appropriateness
- [ ] Test coverage indicators

### 3. Report Format

Structure your review as follows:

```markdown
## Code Review: [filename]

### Summary
[1-2 sentence overview of the code and overall quality]

### Critical Issues
[Issues that must be fixed - bugs, security problems]

### Improvements
[Suggested improvements for code quality]

### Minor Issues
[Style issues, naming suggestions, etc.]

### Positive Aspects
[What the code does well]
```

## Severity Levels

Use these severity indicators:

| Level | Icon | Description |
|-------|------|-------------|
| Critical | [!] | Must fix - bugs, security issues |
| Warning | [?] | Should fix - code smell, potential issues |
| Info | [i] | Consider - style, minor improvements |
| Good | [+] | Positive feedback - well-done aspects |

## Example Review Output

```markdown
## Code Review: src/v0_hello.py

### Summary
This is a minimal SDK example demonstrating basic Claude Agent SDK usage.
The code is functional but could benefit from better error handling.

### Critical Issues
None identified.

### Improvements

[?] **Add error handling for API failures** (line 27)
The ClaudeSDKClient context manager may raise exceptions on connection failures.
```python
# Before
async with ClaudeSDKClient(options=options) as client:

# After
try:
    async with ClaudeSDKClient(options=options) as client:
        ...
except ConnectionError as e:
    print(f"Failed to connect: {e}")
```

[?] **Consider adding type hints** (lines 19-28)
Adding type hints improves code readability and IDE support.
```python
async def main() -> None:
```

### Minor Issues

[i] **Magic string in permission_mode** (line 23)
Consider using an enum or constant for "bypassPermissions".

### Positive Aspects

[+] Clear file header with docstring explaining purpose
[+] Proper use of async/await pattern
[+] Clean message handling logic
```

## Review Guidelines

### Be Constructive
- Focus on the code, not the author
- Explain why something is an issue
- Provide concrete examples of fixes
- Acknowledge good practices

### Be Specific
- Reference line numbers
- Show before/after code
- Explain the impact of issues

### Be Balanced
- Don't only point out problems
- Recognize well-written code
- Prioritize issues by severity

## Python-Specific Checks

### Import Organization
```python
# Standard library
import asyncio
import os

# Third-party
from dotenv import load_dotenv

# Local
from myproject import utils
```

### Async Best Practices
- Use `async with` for context managers
- Avoid blocking calls in async functions
- Handle cancellation properly

### Error Handling
```python
# Good: Specific exceptions
try:
    result = await client.query(prompt)
except ConnectionError:
    logger.error("Connection failed")
except TimeoutError:
    logger.error("Request timed out")

# Bad: Bare except
try:
    result = await client.query(prompt)
except:
    pass
```

## Common Issues to Flag

1. **Hardcoded credentials or secrets**
2. **Print statements instead of logging**
3. **Missing docstrings on public functions**
4. **Overly complex conditionals**
5. **Unused imports or variables**
6. **Missing input validation**
7. **Inconsistent naming conventions**
8. **Deeply nested code (> 3 levels)**
