#!/usr/bin/env python3
"""
v5: Multi-Agent Collaboration - Division of Labor, Coordination, and Orchestration

============================================================
注意：这是【教学演示代码】，不是项目的实际实现
============================================================
本文件用于演示 Claude Agent SDK 的多 Agent 协作。
实际的 Web 应用代码位于 web/ 目录下：
  - 后端: web/backend/main.py
  - 前端: web/frontend/src/
============================================================

This example demonstrates multi-agent systems using the SDK's AgentDefinition:
- Defining specialized sub-agents
- Main agent delegating tasks to sub-agents
- Coordinated task execution

Goal: Master the pattern of building multi-agent systems.

Run: python src/v5_multi_agent.py
"""

import asyncio
import sys
import io
from datetime import datetime
from dotenv import load_dotenv
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AgentDefinition,
    HookMatcher,
)

# Fix Windows encoding issue
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

load_dotenv()


# ============================================================
# Tracking System
# ============================================================

class AgentTracker:
    """Track agent activities and sub-agent spawns."""

    def __init__(self):
        self.events = []
        self.subagent_count = 0

    def log(self, agent: str, event: str, details: str = ""):
        """Log an event."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.events.append({
            "time": timestamp,
            "agent": agent,
            "event": event,
            "details": details,
        })
        print(f"  [{timestamp}] [{agent}] {event}" + (f": {details}" if details else ""))

    async def pre_hook(self, hook_input, tool_use_id, context):
        """Hook to track tool usage."""
        tool_name = hook_input['tool_name']
        tool_input = hook_input['tool_input']

        if tool_name == "Task":
            # Sub-agent spawn
            self.subagent_count += 1
            subagent_type = tool_input.get('subagent_type', 'unknown')
            description = tool_input.get('description', 'no description')
            self.log("MAIN", f"Spawning sub-agent #{self.subagent_count}", f"{subagent_type}: {description}")
        else:
            # Regular tool use
            self.log("AGENT", f"Tool: {tool_name}")

        return {'continue_': True}

    def summary(self):
        """Print summary."""
        print(f"\n--- Tracking Summary ---")
        print(f"Total events: {len(self.events)}")
        print(f"Sub-agents spawned: {self.subagent_count}")


# ============================================================
# Sub-Agent Definitions
# ============================================================

def create_researcher_agent() -> AgentDefinition:
    """Create a researcher sub-agent."""
    return AgentDefinition(
        description=(
            "Use this agent when you need to search or read files to gather information. "
            "The researcher can read files, search patterns, and summarize findings. "
            "Ideal for understanding code structure, finding specific content, or exploring directories."
        ),
        tools=["Read", "Glob", "Grep"],
        prompt=(
            "You are a research assistant. Your job is to gather information by reading files "
            "and searching for patterns. Be thorough and report your findings clearly. "
            "Always provide specific file paths and line numbers when relevant."
        ),
        model="haiku"  # Use faster model for sub-agents
    )


def create_writer_agent() -> AgentDefinition:
    """Create a writer sub-agent."""
    return AgentDefinition(
        description=(
            "Use this agent when you need to create or modify files. "
            "The writer can create new files, update existing content, and organize documentation. "
            "Ideal for generating reports, creating summaries, or writing code."
        ),
        tools=["Write", "Read"],
        prompt=(
            "You are a technical writer. Your job is to create clear, well-organized documents. "
            "When writing, use proper formatting (markdown when appropriate). "
            "Be concise but comprehensive."
        ),
        model="haiku"
    )


def create_analyzer_agent() -> AgentDefinition:
    """Create an analyzer sub-agent."""
    return AgentDefinition(
        description=(
            "Use this agent when you need to analyze code or data patterns. "
            "The analyzer examines files to identify issues, patterns, or improvements. "
            "Ideal for code review, pattern detection, or quality analysis."
        ),
        tools=["Read", "Glob", "Grep"],
        prompt=(
            "You are a code analyst. Your job is to examine code and identify patterns, "
            "potential issues, and areas for improvement. Provide specific, actionable feedback. "
            "Focus on code quality, best practices, and potential bugs."
        ),
        model="haiku"
    )


# ============================================================
# Main Agent Configuration
# ============================================================

def create_orchestrator_options(tracker: AgentTracker) -> ClaudeAgentOptions:
    """Create options for the main orchestrator agent."""

    # Define sub-agents
    agents = {
        "researcher": create_researcher_agent(),
        "writer": create_writer_agent(),
        "analyzer": create_analyzer_agent(),
    }

    # Create hooks for tracking
    hooks = {
        'PreToolUse': [
            HookMatcher(matcher=None, hooks=[tracker.pre_hook])
        ]
    }

    return ClaudeAgentOptions(
        model="sonnet",  # Main agent uses more capable model
        permission_mode="bypassPermissions",
        allowed_tools=["Task"],  # Main agent can ONLY spawn sub-agents
        agents=agents,
        hooks=hooks,
        system_prompt=(
            "You are a project coordinator. Your role is to delegate tasks to specialized agents:\n"
            "- 'researcher': For reading files and gathering information\n"
            "- 'writer': For creating and modifying files\n"
            "- 'analyzer': For code analysis and review\n\n"
            "Always delegate work to the appropriate sub-agent. "
            "Coordinate their efforts and synthesize their findings. "
            "You should NOT try to do tasks directly - use the sub-agents."
        ),
    )


# ============================================================
# Demo Functions
# ============================================================

async def demo_research_task():
    """Demo 1: Multi-agent research task."""
    print("\n" + "=" * 60)
    print("Demo 1: Multi-Agent Research Task")
    print("=" * 60)

    tracker = AgentTracker()
    options = create_orchestrator_options(tracker)

    prompt = """Please analyze the project structure:
1. Use the researcher to find all Python files and understand the project layout
2. Summarize what you learned about the project structure"""

    print(f"\nPrompt: {prompt}")
    print("-" * 60)

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt=prompt)

        async for msg in client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == 'AssistantMessage':
                for block in msg.content:
                    if type(block).__name__ == 'TextBlock':
                        print(f"\n{block.text}")

            elif msg_type == 'ResultMessage':
                if hasattr(msg, 'total_cost_usd') and msg.total_cost_usd:
                    print(f"\n[Total Cost: ${msg.total_cost_usd:.4f}]")

    tracker.summary()


async def demo_coordinated_task():
    """Demo 2: Coordinated multi-step task."""
    print("\n" + "=" * 60)
    print("Demo 2: Coordinated Multi-Step Task")
    print("=" * 60)

    tracker = AgentTracker()
    options = create_orchestrator_options(tracker)

    prompt = """Complete this multi-step task:
1. First, use the researcher to read src/v0_hello.py and understand its structure
2. Then, use the analyzer to review the code and identify any improvements
3. Finally, summarize the findings from both agents"""

    print(f"\nPrompt: {prompt}")
    print("-" * 60)

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt=prompt)

        async for msg in client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == 'AssistantMessage':
                for block in msg.content:
                    if type(block).__name__ == 'TextBlock':
                        print(f"\n{block.text}")

            elif msg_type == 'ResultMessage':
                if hasattr(msg, 'total_cost_usd') and msg.total_cost_usd:
                    print(f"\n[Total Cost: ${msg.total_cost_usd:.4f}]")

    tracker.summary()


async def demo_simple_delegation():
    """Demo 3: Simple single delegation."""
    print("\n" + "=" * 60)
    print("Demo 3: Simple Delegation")
    print("=" * 60)

    tracker = AgentTracker()
    options = create_orchestrator_options(tracker)

    prompt = "Use the researcher to list all markdown files (*.md) in the docs/ directory."

    print(f"\nPrompt: {prompt}")
    print("-" * 60)

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt=prompt)

        async for msg in client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == 'AssistantMessage':
                for block in msg.content:
                    if type(block).__name__ == 'TextBlock':
                        print(f"\n{block.text}")

            elif msg_type == 'ResultMessage':
                if hasattr(msg, 'total_cost_usd') and msg.total_cost_usd:
                    print(f"\n[Total Cost: ${msg.total_cost_usd:.4f}]")

    tracker.summary()


# ============================================================
# Alternative Pattern: Direct Sub-Agent Usage
# ============================================================

async def demo_direct_subagent():
    """Demo 4: Direct sub-agent usage (without orchestrator)."""
    print("\n" + "=" * 60)
    print("Demo 4: Direct Sub-Agent Usage (Alternative Pattern)")
    print("=" * 60)

    print("\nThis demo shows how to use sub-agents directly without an orchestrator.")
    print("Useful when you know exactly which specialist you need.\n")

    # Create a single sub-agent configuration directly
    researcher_def = create_researcher_agent()

    options = ClaudeAgentOptions(
        model=researcher_def.model,
        permission_mode="bypassPermissions",
        allowed_tools=researcher_def.tools,
        system_prompt=researcher_def.prompt,
    )

    prompt = "Find and list all Python files in the src/ directory. Show their names only."

    print(f"Prompt: {prompt}")
    print("-" * 60)

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt=prompt)

        async for msg in client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == 'AssistantMessage':
                for block in msg.content:
                    if type(block).__name__ == 'TextBlock':
                        print(f"\n{block.text}")

            elif msg_type == 'ResultMessage':
                if hasattr(msg, 'total_cost_usd') and msg.total_cost_usd:
                    print(f"\n[Cost: ${msg.total_cost_usd:.4f}]")


async def main():
    print("=" * 60)
    print("v5: Multi-Agent Collaboration Demo")
    print("=" * 60)
    print("\nThis demo shows how multiple agents can work together:")
    print("- MAIN (Orchestrator): Coordinates and delegates tasks")
    print("- researcher: Gathers information by reading files")
    print("- writer: Creates and modifies content")
    print("- analyzer: Reviews and analyzes code")

    # Demo 3: Simple delegation (fastest, good for testing)
    await demo_simple_delegation()

    # Demo 1: Research task
    await demo_research_task()

    # Demo 2: Coordinated multi-step task
    await demo_coordinated_task()

    # Demo 4: Direct sub-agent usage
    await demo_direct_subagent()

    print("\n" + "=" * 60)
    print("v5 Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
