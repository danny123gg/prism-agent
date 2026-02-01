#!/usr/bin/env python3
"""
Documentation Generator Agent - Practical Example

This example demonstrates a documentation generator Agent that combines:
- Tool permissions (v1): Read + Write for doc generation
- Streaming output (v2): Real-time progress
- Hooks (v3): Safety checks before writing
- Agent patterns (v4): Configurable generation

Run: python examples/doc_generator.py [source_file]

Example:
    python examples/doc_generator.py src/v4_custom_agent.py
    python examples/doc_generator.py src/
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
class DocConfig:
    """Documentation generation configuration."""
    source: str = "."
    output_dir: str = "docs/generated"
    doc_type: str = "api"  # api, readme, tutorial
    format: str = "markdown"  # markdown, rst
    include_examples: bool = True
    overwrite: bool = False


@dataclass
class DocMetrics:
    """Track generation metrics."""
    files_analyzed: int = 0
    docs_generated: int = 0
    functions_documented: int = 0
    classes_documented: int = 0


# ============================================================
# Documentation Generator Agent
# ============================================================

class DocGeneratorAgent:
    """
    A documentation generator Agent.

    Features:
    - Analyzes source code structure
    - Generates formatted documentation
    - Safety hooks to prevent overwriting
    - Multiple output formats
    """

    def __init__(self, config: Optional[DocConfig] = None):
        self.config = config or DocConfig()
        self.metrics = DocMetrics()
        self.client = ClaudeSDKClient()

    def _build_options(self) -> ClaudeAgentOptions:
        """Build agent options with appropriate permissions."""

        # Read source, write docs
        allowed_tools = ["Read", "Glob", "Grep", "Write"]

        # Safety hook: confirm before writing
        async def write_safety_hook(hook_input, tool_use_id, context):
            tool_name = hook_input.get("tool_name", "")

            if tool_name == "Write":
                file_path = hook_input.get("tool_input", {}).get("file_path", "")

                # Only allow writing to output directory
                output_dir = Path(self.config.output_dir).resolve()
                target_path = Path(file_path).resolve()

                # Check if target is within output directory
                try:
                    target_path.relative_to(output_dir)
                except ValueError:
                    print(f"\n  [BLOCKED] Cannot write outside {self.config.output_dir}")
                    return {"continue_": False}

                # Check overwrite protection
                if not self.config.overwrite and target_path.exists():
                    print(f"\n  [BLOCKED] File exists (overwrite=False): {file_path}")
                    return {"continue_": False}

                self.metrics.docs_generated += 1
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
                (HookMatcher(matcher="Write"), write_safety_hook),
                (HookMatcher(matcher=None), metrics_hook),
            ],
            max_turns=30,
        )

    def _build_prompt(self) -> str:
        """Build the generation prompt based on configuration."""

        doc_type_instructions = {
            "api": """Generate API documentation including:
- Module overview
- Class documentation with attributes and methods
- Function signatures with parameters and return types
- Usage examples for key functions""",

            "readme": """Generate a README.md including:
- Project title and description
- Installation instructions
- Quick start example
- API overview
- License section""",

            "tutorial": """Generate a tutorial document including:
- Introduction and goals
- Prerequisites
- Step-by-step instructions with code examples
- Common pitfalls and solutions
- Next steps""",
        }

        prompt = f"""You are a documentation generator. Analyze the source code at: {self.config.source}

Task: {doc_type_instructions.get(self.config.doc_type, doc_type_instructions["api"])}

Output Directory: {self.config.output_dir}
Format: {self.config.format}
Include Examples: {self.config.include_examples}

Instructions:
1. First, use Glob to find Python files in the source path
2. Read each file and analyze its structure
3. Generate documentation in the specified format
4. Write the documentation to the output directory

Documentation Structure:
- One doc file per module (for API docs)
- Clear headings and sections
- Code examples in fenced blocks
- Cross-references where appropriate

IMPORTANT: Only write files to {self.config.output_dir}
"""
        return prompt

    async def generate(self) -> None:
        """Execute documentation generation."""

        # Ensure output directory exists
        output_path = Path(self.config.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        options = self._build_options()
        prompt = self._build_prompt()

        print(f"Starting documentation generation")
        print(f"Source: {self.config.source}")
        print(f"Output: {self.config.output_dir}")
        print(f"Type: {self.config.doc_type}")
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
        print(f"Generation complete!")
        print(f"Files analyzed: {self.metrics.files_analyzed}")
        print(f"Docs generated: {self.metrics.docs_generated}")


# ============================================================
# Quick Generate Function
# ============================================================

async def generate_api_docs(source: str, output_dir: str = "docs/generated") -> None:
    """
    Convenience function for quick API doc generation.

    Args:
        source: Source file or directory
        output_dir: Output directory for generated docs
    """
    config = DocConfig(
        source=source,
        output_dir=output_dir,
        doc_type="api",
        include_examples=True,
    )
    agent = DocGeneratorAgent(config)
    await agent.generate()


# ============================================================
# Main
# ============================================================

async def main():
    print("=" * 60)
    print("Documentation Generator Agent - Practical Example")
    print("=" * 60)
    print()

    # Get source from command line or use default
    if len(sys.argv) > 1:
        source = sys.argv[1]
    else:
        source = "src/v4_custom_agent.py"  # Default: document a single file

    # Check if source exists
    if not Path(source).exists():
        print(f"Error: Source not found: {source}")
        print("Usage: python examples/doc_generator.py [source_file_or_dir]")
        return

    # Create and run generator
    config = DocConfig(
        source=source,
        output_dir="docs/generated",
        doc_type="api",
        format="markdown",
        include_examples=True,
        overwrite=True,  # Allow overwriting for demo
    )

    agent = DocGeneratorAgent(config)
    await agent.generate()

    print(f"\nGenerated docs are in: {config.output_dir}/")


if __name__ == "__main__":
    asyncio.run(main())
