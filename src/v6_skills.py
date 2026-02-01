#!/usr/bin/env python3
"""
v6: Skills Knowledge Injection - Making Agents Domain Experts

============================================================
注意：这是【教学演示代码】，不是项目的实际实现
============================================================
本文件用于演示 Claude Agent SDK 的 Skills 知识注入。
实际的 Web 应用代码位于 web/ 目录下：
  - 后端: web/backend/main.py
  - 前端: web/frontend/src/
============================================================

This example demonstrates how to use Skills to inject domain knowledge:
- Loading skills from .claude/skills/ directory
- Using the Skill tool to invoke specialized knowledge
- Creating domain-expert agents

Goal: Master the pattern of knowledge injection for specialized agents.

Run: python src/v6_skills.py
"""

import asyncio
import sys
import io
from dotenv import load_dotenv
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, HookMatcher

# Fix Windows encoding issue
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

load_dotenv()


# ============================================================
# Skills Demo Functions
# ============================================================

async def demo_skill_loading():
    """Demo 1: Load and use skills from project directory."""
    print("\n" + "=" * 60)
    print("Demo 1: Loading Skills from Project Directory")
    print("=" * 60)

    # Track skill usage
    skill_calls = []

    async def track_skill_hook(hook_input, tool_use_id, context):
        tool_name = hook_input['tool_name']
        if tool_name == "Skill":
            skill_name = hook_input['tool_input'].get('skill', 'unknown')
            skill_calls.append(skill_name)
            print(f"\n  [Skill Invoked] {skill_name}")
        return {'continue_': True}

    hooks = {
        'PreToolUse': [HookMatcher(matcher=None, hooks=[track_skill_hook])]
    }

    options = ClaudeAgentOptions(
        model="sonnet",
        permission_mode="bypassPermissions",
        setting_sources=["project"],  # Load skills from .claude/skills/
        allowed_tools=["Skill", "Read", "Glob", "Grep"],
        hooks=hooks,
        system_prompt=(
            "You have access to specialized skills. "
            "Use the 'code-reviewer' skill when reviewing code. "
            "The skill provides detailed guidelines for thorough code reviews."
        ),
    )

    prompt = """Please review the code in src/v0_hello.py using your code-reviewer skill.
Focus on:
1. Code quality
2. Potential issues
3. Suggestions for improvement"""

    print(f"\nPrompt: {prompt}")
    print("-" * 60)

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt=prompt)

        async for msg in client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == 'AssistantMessage':
                for block in msg.content:
                    block_type = type(block).__name__
                    if block_type == 'TextBlock':
                        print(block.text, end="")
                    elif block_type == 'ToolUseBlock':
                        if block.name != "Skill":
                            print(f"\n  [Tool: {block.name}]")

            elif msg_type == 'ResultMessage':
                if hasattr(msg, 'total_cost_usd') and msg.total_cost_usd:
                    print(f"\n\n[Cost: ${msg.total_cost_usd:.4f}]")

    print(f"\n--- Skills used: {skill_calls if skill_calls else 'None'} ---")


async def demo_skill_based_agent():
    """Demo 2: Create an agent that primarily uses skills."""
    print("\n" + "=" * 60)
    print("Demo 2: Skill-Based Agent")
    print("=" * 60)

    options = ClaudeAgentOptions(
        model="sonnet",
        permission_mode="bypassPermissions",
        setting_sources=["project"],
        allowed_tools=["Skill", "Read", "Glob"],
        system_prompt=(
            "You are a code quality specialist. "
            "Your primary tool is the 'code-reviewer' skill which provides "
            "comprehensive code review guidelines. "
            "Always use this skill when analyzing code."
        ),
    )

    prompt = "List all Python files in src/ and give me a quick assessment of the project structure."

    print(f"\nPrompt: {prompt}")
    print("-" * 60)

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt=prompt)

        async for msg in client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == 'AssistantMessage':
                for block in msg.content:
                    if type(block).__name__ == 'TextBlock':
                        print(block.text, end="")

            elif msg_type == 'ResultMessage':
                if hasattr(msg, 'total_cost_usd') and msg.total_cost_usd:
                    print(f"\n\n[Cost: ${msg.total_cost_usd:.4f}]")


async def demo_without_skills():
    """Demo 3: Compare behavior without skills."""
    print("\n" + "=" * 60)
    print("Demo 3: Agent Without Skills (Comparison)")
    print("=" * 60)

    options = ClaudeAgentOptions(
        model="sonnet",
        permission_mode="bypassPermissions",
        # No setting_sources - skills not loaded
        allowed_tools=["Read"],
        system_prompt="You are a helpful assistant.",
    )

    prompt = "Read src/v0_hello.py and give a brief code review."

    print(f"\nPrompt: {prompt}")
    print("-" * 60)

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt=prompt)

        async for msg in client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == 'AssistantMessage':
                for block in msg.content:
                    if type(block).__name__ == 'TextBlock':
                        print(block.text, end="")

            elif msg_type == 'ResultMessage':
                if hasattr(msg, 'total_cost_usd') and msg.total_cost_usd:
                    print(f"\n\n[Cost: ${msg.total_cost_usd:.4f}]")


async def main():
    print("=" * 60)
    print("v6: Skills Knowledge Injection Demo")
    print("=" * 60)
    print("\nSkills allow you to inject domain expertise into agents.")
    print("Skills are defined in .claude/skills/<skill-name>/SKILL.md")
    print("\nThis project has the following skills:")
    print("  - code-reviewer: Comprehensive Python code review guidelines")

    # Demo 3: Without skills (baseline)
    await demo_without_skills()

    # Demo 2: Skill-based agent
    await demo_skill_based_agent()

    # Demo 1: Explicit skill loading
    await demo_skill_loading()

    print("\n" + "=" * 60)
    print("Skills Comparison Summary")
    print("=" * 60)
    print("""
Without Skills:
  - Agent uses general knowledge
  - Reviews may be inconsistent
  - No structured methodology

With Skills:
  - Agent follows defined guidelines
  - Consistent review format
  - Domain expertise injected
  - Structured checklists and categories
""")

    print("=" * 60)
    print("v6 Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
