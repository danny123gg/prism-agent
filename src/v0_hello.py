#!/usr/bin/env python3
"""
v0: Hello Claude - Minimal SDK Example

============================================================
注意：这是【教学演示代码】，不是项目的实际实现
============================================================
本文件用于演示 Claude Agent SDK 的基础用法。
实际的 Web 应用代码位于 web/ 目录下：
  - 后端: web/backend/main.py
  - 前端: web/frontend/src/
============================================================

This is the simplest possible Claude Agent SDK usage.
Goal: Prove that "it just works" with minimal code.

Run: python src/v0_hello.py
"""

import asyncio
import os
from dotenv import load_dotenv
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

# Load .env file
load_dotenv()

async def main():
    # Minimal configuration
    options = ClaudeAgentOptions(
        model="sonnet",
        permission_mode="bypassPermissions"
    )

    # Run a simple query
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt="Hello! Please introduce yourself in one sentence.")

        async for msg in client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == 'AssistantMessage':
                # Extract text from response blocks
                for block in msg.content:
                    if type(block).__name__ == 'TextBlock':
                        print(f"Claude: {block.text}")

            elif msg_type == 'ResultMessage':
                # Show cost info if available
                if hasattr(msg, 'total_cost_usd') and msg.total_cost_usd:
                    print(f"\n[Cost: ${msg.total_cost_usd:.4f}]")

if __name__ == "__main__":
    asyncio.run(main())
