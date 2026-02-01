#!/usr/bin/env python3
"""
v2: Streaming & Conversation History - Understanding Event-Driven Multi-turn Dialogue

============================================================
注意：这是【教学演示代码】，不是项目的实际实现
============================================================
本文件用于演示 Claude Agent SDK 的流式输出和对话历史管理。
实际的 Web 应用代码位于 web/ 目录下：
  - 后端: web/backend/main.py
  - 前端: web/frontend/src/
============================================================

This example demonstrates:
1. Real-time streaming of agent responses (event-driven pattern)
2. Multi-turn conversations with automatic context management (stateful)

Goal: Understand streaming messages AND how SDK maintains conversation history.

Run: python src/v2_streaming_and_history.py
"""

import asyncio
from dotenv import load_dotenv
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

load_dotenv()


def format_tool_input(input_data: dict, max_len: int = 100) -> str:
    """Format tool input for display, truncating if needed."""
    text = str(input_data)
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


async def demo_streaming():
    """Demo 1: Streaming - Understanding the event-driven message flow."""
    print("\n" + "=" * 60)
    print("Demo 1: Streaming Output")
    print("=" * 60)
    print("\n[Concept] receive_response() returns an async iterator")
    print("          that yields messages as they arrive.\n")

    options = ClaudeAgentOptions(
        model="sonnet",
        permission_mode="bypassPermissions",
        allowed_tools=["Read", "Glob"],
    )

    prompt = """Please do the following:
1. List the Python files in the src/ directory
2. Read the content of v0_hello.py
3. Summarize what you found in 2-3 sentences"""

    print(f"Prompt: {prompt}")
    print("\n" + "-" * 60)
    print("Streaming Response:")
    print("-" * 60 + "\n")

    # Track statistics
    stats = {
        "text_blocks": 0,
        "tool_calls": 0,
        "messages": 0,
        "cost": 0.0,
    }

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt=prompt)

        # Streaming: receive messages one by one as they arrive
        async for msg in client.receive_response():
            msg_type = type(msg).__name__
            stats["messages"] += 1

            if msg_type == 'AssistantMessage':
                # Process each content block
                for block in msg.content:
                    block_type = type(block).__name__

                    if block_type == 'TextBlock':
                        stats["text_blocks"] += 1
                        # Stream text in real-time
                        print(block.text, end="", flush=True)

                    elif block_type == 'ToolUseBlock':
                        stats["tool_calls"] += 1
                        # Show tool call details
                        print(f"\n\n[Tool Call #{stats['tool_calls']}]")
                        print(f"  Name: {block.name}")
                        print(f"  ID: {block.id[:20]}...")
                        print(f"  Input: {format_tool_input(block.input)}")
                        print()

            elif msg_type == 'ResultMessage':
                # Session complete
                if hasattr(msg, 'total_cost_usd') and msg.total_cost_usd:
                    stats["cost"] = msg.total_cost_usd

    # Print statistics
    print("\n" + "=" * 60)
    print("Streaming Statistics:")
    print("=" * 60)
    print(f"  Total messages received: {stats['messages']}")
    print(f"  Text blocks: {stats['text_blocks']}")
    print(f"  Tool calls: {stats['tool_calls']}")
    print(f"  Total cost: ${stats['cost']:.4f}")
    print("=" * 60)


async def demo_conversation_history():
    """Demo 2: Conversation History - SDK automatically maintains context."""
    print("\n" + "=" * 60)
    print("Demo 2: Multi-turn Conversation (Stateful)")
    print("=" * 60)
    print("\n[Concept] ClaudeSDKClient is stateful - it automatically")
    print("          maintains conversation history across queries.\n")

    options = ClaudeAgentOptions(
        model="sonnet",
        permission_mode="bypassPermissions",
        allowed_tools=[],  # Pure conversation, no tools
    )

    async with ClaudeSDKClient(options=options) as client:
        # Turn 1: Introduce name
        print("👤 User (Turn 1): My name is Alice and I work as a software engineer.")
        await client.query("My name is Alice and I work as a software engineer.")

        assistant_reply = ""
        async for msg in client.receive_response():
            if type(msg).__name__ == 'AssistantMessage':
                for block in msg.content:
                    if type(block).__name__ == 'TextBlock':
                        assistant_reply += block.text

        print(f"🤖 Assistant: {assistant_reply}\n")
        print("-" * 60 + "\n")

        # Turn 2: Ask about name (testing memory)
        print("👤 User (Turn 2): What is my name and occupation?")
        await client.query("What is my name and occupation?")

        assistant_reply = ""
        async for msg in client.receive_response():
            if type(msg).__name__ == 'AssistantMessage':
                for block in msg.content:
                    if type(block).__name__ == 'TextBlock':
                        assistant_reply += block.text

        print(f"🤖 Assistant: {assistant_reply}\n")
        print("-" * 60 + "\n")

        # Turn 3: Continuation
        print("👤 User (Turn 3): What programming language do I prefer?")
        await client.query("What programming language do I prefer?")

        assistant_reply = ""
        async for msg in client.receive_response():
            if type(msg).__name__ == 'AssistantMessage':
                for block in msg.content:
                    if type(block).__name__ == 'TextBlock':
                        assistant_reply += block.text

        print(f"🤖 Assistant: {assistant_reply}\n")

    print("=" * 60)
    print("✅ SDK automatically maintained context across 3 turns")
    print("   No manual message history management needed!")
    print("=" * 60)


async def demo_combined():
    """Demo 3: Streaming + Multi-turn - The complete pattern."""
    print("\n" + "=" * 60)
    print("Demo 3: Streaming Multi-turn Conversation")
    print("=" * 60)
    print("\n[Concept] Combine both: streaming responses in multi-turn dialogue.\n")

    options = ClaudeAgentOptions(
        model="sonnet",
        permission_mode="bypassPermissions",
        allowed_tools=["Glob", "Read"],
    )

    async with ClaudeSDKClient(options=options) as client:
        # Turn 1: Initial request
        print("👤 Turn 1: List all Python files in src/")
        await client.query("List all Python files in src/ directory")

        print("🤖 Assistant: ", end="")
        async for msg in client.receive_response():
            if type(msg).__name__ == 'AssistantMessage':
                for block in msg.content:
                    if type(block).__name__ == 'TextBlock':
                        print(block.text, end="", flush=True)
                    elif type(block).__name__ == 'ToolUseBlock':
                        print(f"\n[Using {block.name}...]", end="", flush=True)

        print("\n\n" + "-" * 60 + "\n")

        # Turn 2: Follow-up (SDK remembers previous context)
        print("👤 Turn 2: How many files did you find?")
        await client.query("How many files did you find?")

        print("🤖 Assistant: ", end="")
        async for msg in client.receive_response():
            if type(msg).__name__ == 'AssistantMessage':
                for block in msg.content:
                    if type(block).__name__ == 'TextBlock':
                        print(block.text, end="", flush=True)

        print("\n")

    print("\n" + "=" * 60)
    print("✅ Multi-turn conversation with streaming output")
    print("   SDK handled both automatically!")
    print("=" * 60)


async def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("v2: Streaming & Conversation History with Claude Agent SDK")
    print("=" * 60)
    print("\nSDK Version: claude-agent-sdk 0.1.27")
    print("\nKey Features:")
    print("  • Streaming: Async iterator for real-time message processing")
    print("  • Stateful: Automatic conversation history management")
    print("  • No manual context handling needed")
    print("=" * 60)

    # Demo 1: Streaming basics
    await demo_streaming()

    input("\n\nPress Enter to continue to Demo 2...")

    # Demo 2: Conversation history
    await demo_conversation_history()

    input("\n\nPress Enter to continue to Demo 3...")

    # Demo 3: Combined pattern
    await demo_combined()

    # Summary
    print("\n" + "=" * 60)
    print("Summary: Two Core Concepts")
    print("=" * 60)
    print("""
1. STREAMING (流式输出)
   - receive_response() returns an AsyncIterator[Message]
   - Yields messages as they arrive: AssistantMessage, ResultMessage, etc.
   - Event-driven pattern for real-time processing

2. CONVERSATION HISTORY (对话历史)
   - ClaudeSDKClient is stateful
   - Automatically maintains conversation context
   - Just call query() multiple times - SDK handles the rest

Key Difference from Anthropic API:
  ❌ Anthropic API: You manually pass messages=[...] history
  ✅ Claude Agent SDK: SDK maintains history automatically

Official Docs:
  client.py:347-386 - receive_response() documentation
  client.py:14-53   - Stateful conversation management
""")
    print("=" * 60)
    print("Next: v3 - Hook Mechanism for controlling Agent behavior")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
