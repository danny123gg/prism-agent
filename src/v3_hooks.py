#!/usr/bin/env python3
"""
v3: Hook Mechanism - Observable, Interceptable, Auditable

============================================================
注意：这是【教学演示代码】，不是项目的实际实现
============================================================
本文件用于演示 Claude Agent SDK 的 Hook 机制。
实际的 Web 应用代码位于 web/ 目录下：
  - 后端: web/backend/main.py
  - 前端: web/frontend/src/
============================================================

This example demonstrates the Hook mechanism for:
- Logging all tool calls (observability)
- Blocking dangerous operations (security)
- Recording execution history (audit trail)

Goal: Master the core engineering deployment pattern.

Run: python src/v3_hooks.py
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, HookMatcher

load_dotenv()

# Global audit log
audit_log = []


# ============================================================
# Hook Functions
# ============================================================

async def logging_pre_hook(hook_input, tool_use_id, context):
    """
    PreToolUse Hook: Log every tool call before execution.

    This is the most common use case - observability.
    """
    tool_name = hook_input['tool_name']
    tool_input = hook_input['tool_input']
    timestamp = datetime.now().strftime("%H:%M:%S")

    # Create audit record
    record = {
        "timestamp": timestamp,
        "event": "pre_tool_use",
        "tool_name": tool_name,
        "tool_use_id": tool_use_id[:12] + "...",
        "input_preview": str(tool_input)[:80],
    }
    audit_log.append(record)

    # Visual output
    print(f"\n[{timestamp}] PRE  → {tool_name}")

    # Show relevant input based on tool type
    if tool_name == "Read":
        print(f"         File: {tool_input.get('file_path', 'N/A')}")
    elif tool_name == "Write":
        path = tool_input.get('file_path', 'N/A')
        content_len = len(tool_input.get('content', ''))
        print(f"         File: {path} ({content_len} chars)")
    elif tool_name == "Bash":
        cmd = tool_input.get('command', 'N/A')[:60]
        print(f"         Command: {cmd}")
    elif tool_name == "Glob":
        print(f"         Pattern: {tool_input.get('pattern', 'N/A')}")

    # Always allow - this is just logging
    return {'continue_': True}


async def logging_post_hook(hook_input, tool_use_id, context):
    """
    PostToolUse Hook: Log the result after execution.
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    tool_response = hook_input.get('tool_response', {})

    # Check for errors
    is_error = False
    if isinstance(tool_response, dict):
        is_error = 'error' in tool_response

    status = "ERROR" if is_error else "OK"

    record = {
        "timestamp": timestamp,
        "event": "post_tool_use",
        "tool_use_id": tool_use_id[:12] + "...",
        "status": status,
    }
    audit_log.append(record)

    print(f"[{timestamp}] POST ← {status}")

    return {'continue_': True}


async def security_pre_hook(hook_input, tool_use_id, context):
    """
    Security Hook: Block dangerous operations.

    This demonstrates how to use hooks for access control.
    """
    tool_name = hook_input['tool_name']
    tool_input = hook_input['tool_input']

    # Rule 1: Block writes to sensitive directories
    if tool_name == "Write":
        file_path = tool_input.get('file_path', '')
        sensitive_paths = ['.env', 'credentials', 'secret', 'password']

        for sensitive in sensitive_paths:
            if sensitive.lower() in file_path.lower():
                print(f"\n[BLOCKED] Write to sensitive path: {file_path}")
                audit_log.append({
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "event": "blocked",
                    "tool_name": tool_name,
                    "reason": f"sensitive path: {sensitive}",
                })
                return {'continue_': False}  # Block the operation

    # Rule 2: Block dangerous bash commands
    if tool_name == "Bash":
        command = tool_input.get('command', '')
        dangerous_patterns = ['rm -rf', 'format', 'del /f', 'shutdown']

        for pattern in dangerous_patterns:
            if pattern.lower() in command.lower():
                print(f"\n[BLOCKED] Dangerous command: {command[:50]}")
                audit_log.append({
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "event": "blocked",
                    "tool_name": tool_name,
                    "reason": f"dangerous pattern: {pattern}",
                })
                return {'continue_': False}

    # Allow all other operations
    return {'continue_': True}


# ============================================================
# Demo Functions
# ============================================================

async def demo_logging_hooks():
    """Demo 1: Pure logging hooks - observe without interfering."""
    print("\n" + "=" * 60)
    print("Demo 1: Logging Hooks (Observability)")
    print("=" * 60)

    hooks = {
        'PreToolUse': [
            HookMatcher(matcher=None, hooks=[logging_pre_hook])
        ],
        'PostToolUse': [
            HookMatcher(matcher=None, hooks=[logging_post_hook])
        ]
    }

    options = ClaudeAgentOptions(
        model="sonnet",
        permission_mode="bypassPermissions",
        allowed_tools=["Read", "Glob"],
        hooks=hooks,
    )

    prompt = "List Python files in src/ directory, then read the first few lines of v0_hello.py"
    print(f"\nPrompt: {prompt}")
    print("-" * 60)

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt=prompt)

        async for msg in client.receive_response():
            if type(msg).__name__ == 'AssistantMessage':
                for block in msg.content:
                    if type(block).__name__ == 'TextBlock':
                        print(f"\n{block.text}")

            elif type(msg).__name__ == 'ResultMessage':
                if hasattr(msg, 'total_cost_usd') and msg.total_cost_usd:
                    print(f"\n[Cost: ${msg.total_cost_usd:.4f}]")


async def demo_security_hooks():
    """Demo 2: Security hooks - block dangerous operations."""
    print("\n" + "=" * 60)
    print("Demo 2: Security Hooks (Access Control)")
    print("=" * 60)

    hooks = {
        'PreToolUse': [
            HookMatcher(matcher=None, hooks=[security_pre_hook, logging_pre_hook])
        ],
        'PostToolUse': [
            HookMatcher(matcher=None, hooks=[logging_post_hook])
        ]
    }

    options = ClaudeAgentOptions(
        model="sonnet",
        permission_mode="bypassPermissions",
        allowed_tools=["Read", "Write"],
        hooks=hooks,
    )

    # This prompt tries to write to a "sensitive" path
    prompt = """Please do these two tasks:
1. Write a file called 'test_normal.txt' with content 'Hello World'
2. Write a file called 'secret_config.txt' with content 'should be blocked'"""

    print(f"\nPrompt: {prompt}")
    print("-" * 60)

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt=prompt)

        async for msg in client.receive_response():
            if type(msg).__name__ == 'AssistantMessage':
                for block in msg.content:
                    if type(block).__name__ == 'TextBlock':
                        print(f"\n{block.text}")

            elif type(msg).__name__ == 'ResultMessage':
                if hasattr(msg, 'total_cost_usd') and msg.total_cost_usd:
                    print(f"\n[Cost: ${msg.total_cost_usd:.4f}]")


async def demo_selective_hooks():
    """Demo 3: Selective hooks - only match specific tools."""
    print("\n" + "=" * 60)
    print("Demo 3: Selective Hooks (Tool-Specific)")
    print("=" * 60)

    async def write_only_hook(hook_input, tool_use_id, context):
        """This hook only fires for Write operations."""
        print(f"\n[WRITE HOOK] Intercepted write operation")
        print(f"         Target: {hook_input['tool_input'].get('file_path', 'N/A')}")
        return {'continue_': True}

    hooks = {
        'PreToolUse': [
            # Only match Write tool using regex pattern
            HookMatcher(matcher="Write", hooks=[write_only_hook]),
            # Match all tools for general logging
            HookMatcher(matcher=None, hooks=[logging_pre_hook]),
        ],
        'PostToolUse': [
            HookMatcher(matcher=None, hooks=[logging_post_hook])
        ]
    }

    options = ClaudeAgentOptions(
        model="sonnet",
        permission_mode="bypassPermissions",
        allowed_tools=["Read", "Write", "Glob"],
        hooks=hooks,
    )

    prompt = """Do these tasks:
1. List files in current directory
2. Write 'test content' to 'demo_selective.txt'"""

    print(f"\nPrompt: {prompt}")
    print("-" * 60)

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt=prompt)

        async for msg in client.receive_response():
            if type(msg).__name__ == 'AssistantMessage':
                for block in msg.content:
                    if type(block).__name__ == 'TextBlock':
                        print(f"\n{block.text}")

            elif type(msg).__name__ == 'ResultMessage':
                if hasattr(msg, 'total_cost_usd') and msg.total_cost_usd:
                    print(f"\n[Cost: ${msg.total_cost_usd:.4f}]")


def print_audit_summary():
    """Print the collected audit log."""
    print("\n" + "=" * 60)
    print("Audit Log Summary")
    print("=" * 60)

    if not audit_log:
        print("No events recorded.")
        return

    # Count by event type
    events = {}
    blocked = 0
    for record in audit_log:
        event = record.get('event', 'unknown')
        events[event] = events.get(event, 0) + 1
        if event == 'blocked':
            blocked += 1

    print(f"Total events: {len(audit_log)}")
    for event, count in events.items():
        print(f"  - {event}: {count}")

    if blocked > 0:
        print(f"\n[!] {blocked} operation(s) were blocked by security hooks")

    # Show blocked operations
    blocked_records = [r for r in audit_log if r.get('event') == 'blocked']
    if blocked_records:
        print("\nBlocked operations:")
        for r in blocked_records:
            print(f"  - {r['tool_name']}: {r['reason']}")


async def main():
    global audit_log

    # Demo 1: Logging hooks
    await demo_logging_hooks()

    # Demo 2: Security hooks
    await demo_security_hooks()

    # Demo 3: Selective hooks
    await demo_selective_hooks()

    # Print audit summary
    print_audit_summary()

    # Cleanup test files
    for f in ['test_normal.txt', 'demo_selective.txt']:
        try:
            Path(f).unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
