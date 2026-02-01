#!/usr/bin/env python3
"""
Code Reviewer Agent - Practical Example

This example demonstrates a production-ready code review Agent that combines:
- Tool permissions (v1): Read-only access for safety
- Streaming output (v2): Real-time feedback
- Hooks (v3): Logging and metrics
- Agent patterns (v4): Reusable configuration
- Skills (v6): Domain expertise from SKILL.md

Run: python examples/code_reviewer.py [file_or_directory]

Example:
    python examples/code_reviewer.py src/v0_hello.py
    python examples/code_reviewer.py src/
"""

import asyncio
import sys
import io
import os
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, HookMatcher

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

load_dotenv()


# ============================================================
# Configuration
# ============================================================

@dataclass
class ReviewConfig:
    """Code review configuration."""
    target: str = "."
    focus: str = "all"  # all, security, performance, style
    severity: str = "medium"  # low, medium, high (minimum to report)
    max_files: int = 10
    use_skill: bool = True


@dataclass
class ReviewMetrics:
    """Track review metrics."""
    files_reviewed: int = 0
    issues_found: int = 0
    tools_used: list = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

    @property
    def duration(self) -> float:
        return time.time() - self.start_time


# ============================================================
# Code Review Agent
# ============================================================

class CodeReviewAgent:
    """
    A reusable code review Agent.

    Features:
    - Read-only access (safe for CI/CD)
    - Streaming output for real-time feedback
    - Metrics collection via hooks
    - Optional Skill-based expertise
    """

    def __init__(self, config: Optional[ReviewConfig] = None):
        self.config = config or ReviewConfig()
        self.metrics = ReviewMetrics()
        self.client = ClaudeSDKClient()

    def _build_options(self) -> ClaudeAgentOptions:
        """Build agent options with appropriate permissions."""

        # Read-only tools for safety
        allowed_tools = ["Read", "Glob", "Grep"]

        # Add Skill tool if enabled
        if self.config.use_skill:
            allowed_tools.append("Skill")

        # Create metrics hook
        async def metrics_hook(hook_input, tool_use_id, context):
            tool_name = hook_input.get("tool_name", "unknown")
            if tool_name not in self.metrics.tools_used:
                self.metrics.tools_used.append(tool_name)

            # Count file reads
            if tool_name == "Read":
                self.metrics.files_reviewed += 1

            return {"continue_": True}

        return ClaudeAgentOptions(
            model="sonnet",
            allowed_tools=allowed_tools,
            setting_sources=["project"] if self.config.use_skill else [],
            pre_tool_use_hook=[(HookMatcher(matcher=None), metrics_hook)],
            max_turns=20,
        )

    def _build_prompt(self) -> str:
        """Build the review prompt based on configuration."""

        focus_instructions = {
            "all": "Review for bugs, security issues, performance problems, and code style.",
            "security": "Focus on security vulnerabilities: injection, auth, data exposure, etc.",
            "performance": "Focus on performance issues: memory leaks, inefficient algorithms, etc.",
            "style": "Focus on code style: naming, structure, documentation, best practices.",
        }

        severity_levels = {
            "low": "Report all issues including minor suggestions.",
            "medium": "Report medium and high severity issues.",
            "high": "Only report critical issues that could cause bugs or security problems.",
        }

        prompt = f"""You are a code reviewer. Review the code at: {self.config.target}

{focus_instructions.get(self.config.focus, focus_instructions["all"])}
{severity_levels.get(self.config.severity, severity_levels["medium"])}

Instructions:
1. First, use Glob to find relevant files (max {self.config.max_files} files)
2. Read each file and analyze the code
3. Provide a structured review report

Output Format:
## Summary
Brief overview of the code quality.

## Issues Found
For each issue:
- **[SEVERITY]** File:line - Description
- Suggestion for fix

## Positive Observations
Good practices observed.

## Recommendations
Top 3 actionable improvements.
"""

        # Add Skill instruction if enabled
        if self.config.use_skill:
            prompt += """
Note: If a code-reviewer Skill is available, use it for expert guidance.
"""

        return prompt

    async def review(self) -> str:
        """Execute the code review and return the report."""

        options = self._build_options()
        prompt = self._build_prompt()

        print(f"Starting code review: {self.config.target}")
        print(f"Focus: {self.config.focus}, Min severity: {self.config.severity}")
        print("-" * 60)

        result_text = ""

        async for message in self.client.process_streaming(prompt, options):
            msg_type = type(message).__name__

            if msg_type == "AssistantMessage":
                for block in message.content:
                    if type(block).__name__ == "TextBlock":
                        print(block.text, end="", flush=True)
                        result_text += block.text
                    elif type(block).__name__ == "ToolUseBlock":
                        print(f"\n  [Analyzing: {block.name}]", flush=True)

        print("\n" + "-" * 60)
        print(f"Review completed in {self.metrics.duration:.1f}s")
        print(f"Files reviewed: {self.metrics.files_reviewed}")
        print(f"Tools used: {self.metrics.tools_used}")

        return result_text


# ============================================================
# Quick Review Function
# ============================================================

async def quick_review(target: str, focus: str = "all") -> str:
    """
    Convenience function for quick code reviews.

    Args:
        target: File or directory to review
        focus: Review focus (all, security, performance, style)

    Returns:
        Review report as string
    """
    config = ReviewConfig(target=target, focus=focus)
    agent = CodeReviewAgent(config)
    return await agent.review()


# ============================================================
# Main
# ============================================================

async def main():
    print("=" * 60)
    print("Code Reviewer Agent - Practical Example")
    print("=" * 60)
    print()

    # Get target from command line or use default
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = "src/v0_hello.py"  # Default: review a simple file

    # Check if target exists
    if not Path(target).exists():
        print(f"Error: Target not found: {target}")
        print("Usage: python examples/code_reviewer.py [file_or_directory]")
        return

    # Create and run review
    config = ReviewConfig(
        target=target,
        focus="all",
        severity="medium",
        max_files=5,
        use_skill=True,
    )

    agent = CodeReviewAgent(config)
    report = await agent.review()

    # Optional: Save report
    # with open("review_report.md", "w", encoding="utf-8") as f:
    #     f.write(report)
    # print("\nReport saved to: review_report.md")


if __name__ == "__main__":
    asyncio.run(main())
