#!/usr/bin/env python3
"""
v1: Tool Permissions - Understanding Minimal Permissions

============================================================
注意：这是【教学演示代码】，不是项目的实际实现
============================================================
本文件用于演示 Claude Agent SDK 的工具权限控制。
实际的 Web 应用代码位于 web/ 目录下：
  - 后端: web/backend/main.py
  - 前端: web/frontend/src/
============================================================

This example demonstrates how to control which tools an Agent can use.
Goal: Understand the principle of minimal permissions.

Run: python src/v1_tools.py
"""

import asyncio
from dotenv import load_dotenv
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

load_dotenv()


async def run_with_tools(name: str, allowed_tools: list[str], prompt: str):
    """Run a query with specific tool permissions."""
    print(f"\n{'='*50}")
    print(f"Mode: {name}")
    print(f"Allowed tools: {allowed_tools}")
    print(f"Prompt: {prompt}")
    print("-" * 50)

    options = ClaudeAgentOptions(
        model="sonnet",
        permission_mode="bypassPermissions",
        allowed_tools=allowed_tools,
    )

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
                        print(f"\n[Tool: {block.name}]")

            elif msg_type == 'ResultMessage':
                if hasattr(msg, 'total_cost_usd') and msg.total_cost_usd:
                    print(f"\n[Cost: ${msg.total_cost_usd:.4f}]")


async def main():
    # Demo 1: Read-only mode - can only read files
    await run_with_tools(
        name="Read-Only",
        allowed_tools=["Read"],
        prompt="Read the file requirements.txt and tell me what dependencies are listed."
    )

    # Demo 2: Read-Write mode - can read and write files
    await run_with_tools(
        name="Read-Write",
        allowed_tools=["Read", "Write"],
        prompt="Create a file called 'test_output.txt' with content 'Hello from v1!' in the current directory."
    )

    # Demo 3: No tools - pure conversation
    await run_with_tools(
        name="No Tools (Conversation Only)",
        allowed_tools=[],
        prompt="What is 2 + 2? Just answer, no tools needed."
    )

    print("\n" + "=" * 50)
    print("Summary:")
    print("- Read-Only: Can inspect but not modify")
    print("- Read-Write: Full file access")
    print("- No Tools: Pure conversation, maximum safety")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
