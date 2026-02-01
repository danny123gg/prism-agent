#!/usr/bin/env python3
"""
Test Writer Agent - Practical Example

This example demonstrates a test case generator Agent that combines:
- Tool permissions (v1): Read source + Write tests
- Streaming output (v2): Real-time progress
- Hooks (v3): Safety checks for test file locations
- Multi-Agent (v5): Analyzer + Generator pattern

Run: python examples/test_writer.py [source_file]

Example:
    python examples/test_writer.py src/v4_custom_agent.py
    python examples/test_writer.py src/v0_hello.py
"""

import asyncio
import sys
import io
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List
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
class TestConfig:
    """Test generation configuration."""
    source: str = "."
    output_dir: str = "tests/generated"
    framework: str = "pytest"  # pytest, unittest
    coverage_target: str = "functions"  # functions, classes, all
    include_edge_cases: bool = True
    include_mocks: bool = True
    overwrite: bool = False


@dataclass
class TestMetrics:
    """Track generation metrics."""
    files_analyzed: int = 0
    test_files_generated: int = 0
    test_cases_written: int = 0
    functions_covered: int = 0
    classes_covered: int = 0


# ============================================================
# Test Writer Agent
# ============================================================

class TestWriterAgent:
    """
    A test case generator Agent.

    Features:
    - Analyzes source code to identify testable units
    - Generates comprehensive test cases
    - Supports pytest and unittest frameworks
    - Includes edge cases and mock suggestions
    """

    def __init__(self, config: Optional[TestConfig] = None):
        self.config = config or TestConfig()
        self.metrics = TestMetrics()
        self.client = ClaudeSDKClient()

    def _build_options(self) -> ClaudeAgentOptions:
        """Build agent options with appropriate permissions."""

        # Read source, write tests
        allowed_tools = ["Read", "Glob", "Grep", "Write"]

        # Safety hook: only allow writing test files
        async def test_file_hook(hook_input, tool_use_id, context):
            tool_name = hook_input.get("tool_name", "")

            if tool_name == "Write":
                file_path = hook_input.get("tool_input", {}).get("file_path", "")
                target_path = Path(file_path)

                # Only allow writing to tests directory
                output_dir = Path(self.config.output_dir).resolve()
                try:
                    target_path.resolve().relative_to(output_dir)
                except ValueError:
                    print(f"\n  [BLOCKED] Cannot write outside {self.config.output_dir}")
                    return {"continue_": False}

                # Only allow test files
                if not target_path.name.startswith("test_"):
                    print(f"\n  [BLOCKED] Test files must start with 'test_'")
                    return {"continue_": False}

                # Check overwrite
                if not self.config.overwrite and target_path.exists():
                    print(f"\n  [BLOCKED] File exists: {file_path}")
                    return {"continue_": False}

                self.metrics.test_files_generated += 1
                print(f"\n  [Writing] {file_path}")

            return {"continue_": True}

        # Metrics hook
        async def metrics_hook(hook_input, tool_use_id, context):
            tool_name = hook_input.get("tool_name", "")
            if tool_name == "Read":
                self.metrics.files_analyzed += 1
            return {"continue_": True}

        return ClaudeAgentOptions(
            model="sonnet",
            allowed_tools=allowed_tools,
            pre_tool_use_hook=[
                (HookMatcher(matcher="Write"), test_file_hook),
                (HookMatcher(matcher=None), metrics_hook),
            ],
            max_turns=30,
        )

    def _build_prompt(self) -> str:
        """Build the test generation prompt."""

        framework_templates = {
            "pytest": """
Use pytest framework:
- Use `def test_xxx()` function style
- Use `assert` statements
- Use `@pytest.fixture` for setup
- Use `@pytest.mark.parametrize` for multiple inputs
- Import with `import pytest`""",

            "unittest": """
Use unittest framework:
- Use `class TestXxx(unittest.TestCase)` style
- Use `self.assertEqual`, `self.assertTrue`, etc.
- Use `setUp` and `tearDown` methods
- Import with `import unittest`""",
        }

        coverage_instructions = {
            "functions": "Focus on testing all public functions.",
            "classes": "Focus on testing all public classes and their methods.",
            "all": "Test all public functions, classes, methods, and edge cases.",
        }

        prompt = f"""You are a test case generator. Analyze the source code at: {self.config.source}

Output Directory: {self.config.output_dir}
Framework: {self.config.framework}
Coverage Target: {coverage_instructions.get(self.config.coverage_target, coverage_instructions["functions"])}
Include Edge Cases: {self.config.include_edge_cases}
Include Mocks: {self.config.include_mocks}

{framework_templates.get(self.config.framework, framework_templates["pytest"])}

Instructions:
1. First, use Glob to find Python files in the source path
2. Read each file and identify testable units (functions, classes)
3. Generate comprehensive test cases
4. Write test files to the output directory

Test Case Guidelines:
- One test file per source file (test_<source_name>.py)
- Test normal cases first
- Include edge cases: empty inputs, None values, boundary conditions
- Include error cases: invalid inputs, exceptions
- Add docstrings explaining what each test verifies

{"Mock Guidelines:" if self.config.include_mocks else ""}
{"- Use unittest.mock or pytest-mock for external dependencies" if self.config.include_mocks else ""}
{"- Mock file I/O, network calls, and external services" if self.config.include_mocks else ""}
{"- Document what is being mocked and why" if self.config.include_mocks else ""}

IMPORTANT: Only write files to {self.config.output_dir} with names starting with 'test_'
"""
        return prompt

    async def generate(self) -> None:
        """Execute test generation."""

        # Ensure output directory exists
        output_path = Path(self.config.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        options = self._build_options()
        prompt = self._build_prompt()

        print(f"Starting test generation")
        print(f"Source: {self.config.source}")
        print(f"Output: {self.config.output_dir}")
        print(f"Framework: {self.config.framework}")
        print("-" * 60)

        async for message in self.client.process_streaming(prompt, options):
            msg_type = type(message).__name__

            if msg_type == "AssistantMessage":
                for block in message.content:
                    if type(block).__name__ == "TextBlock":
                        print(block.text, end="", flush=True)
                    elif type(block).__name__ == "ToolUseBlock":
                        if block.name != "Write":  # Write is logged by hook
                            print(f"\n  [{block.name}]", flush=True)

        print("\n" + "-" * 60)
        print(f"Test generation complete!")
        print(f"Files analyzed: {self.metrics.files_analyzed}")
        print(f"Test files generated: {self.metrics.test_files_generated}")


# ============================================================
# Quick Generate Function
# ============================================================

async def generate_tests(source: str, output_dir: str = "tests/generated") -> None:
    """
    Convenience function for quick test generation.

    Args:
        source: Source file or directory
        output_dir: Output directory for generated tests
    """
    config = TestConfig(
        source=source,
        output_dir=output_dir,
        framework="pytest",
        include_edge_cases=True,
    )
    agent = TestWriterAgent(config)
    await agent.generate()


# ============================================================
# Main
# ============================================================

async def main():
    print("=" * 60)
    print("Test Writer Agent - Practical Example")
    print("=" * 60)
    print()

    # Get source from command line or use default
    if len(sys.argv) > 1:
        source = sys.argv[1]
    else:
        source = "src/v0_hello.py"  # Default: generate tests for simple file

    # Check if source exists
    if not Path(source).exists():
        print(f"Error: Source not found: {source}")
        print("Usage: python examples/test_writer.py [source_file_or_dir]")
        return

    # Create and run generator
    config = TestConfig(
        source=source,
        output_dir="tests/generated",
        framework="pytest",
        coverage_target="functions",
        include_edge_cases=True,
        include_mocks=True,
        overwrite=True,  # Allow overwriting for demo
    )

    agent = TestWriterAgent(config)
    await agent.generate()

    print(f"\nGenerated tests are in: {config.output_dir}/")
    print("Run tests with: pytest tests/generated/")


if __name__ == "__main__":
    asyncio.run(main())
