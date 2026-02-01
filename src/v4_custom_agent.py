#!/usr/bin/env python3
"""
v4: Agent Encapsulation - Reusable Agent Components

============================================================
注意：这是【教学演示代码】，不是项目的实际实现
============================================================
本文件用于演示 Claude Agent SDK 的 Agent 封装模式。
实际的 Web 应用代码位于 web/ 目录下：
  - 后端: web/backend/main.py
  - 前端: web/frontend/src/
============================================================

This example demonstrates how to create reusable Agent components through:
- Class-based Agent encapsulation
- Configuration-driven Agent creation
- Factory pattern for Agent instantiation

Goal: Master the pattern of creating reusable, configurable Agent components.

Run: python src/v4_custom_agent.py
"""

import asyncio
import sys
import io

# Fix Windows encoding issue
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from datetime import datetime
from dotenv import load_dotenv
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, HookMatcher

load_dotenv()


# ============================================================
# Agent Configuration
# ============================================================

@dataclass
class AgentConfig:
    """Configuration for an Agent instance."""
    name: str
    description: str
    model: str = "sonnet"
    allowed_tools: list[str] = field(default_factory=list)
    system_prompt: Optional[str] = None
    enable_logging: bool = True
    blocked_patterns: list[str] = field(default_factory=list)


# ============================================================
# Base Agent Class
# ============================================================

class BaseAgent:
    """
    Base class for creating reusable Agent components.

    Features:
    - Automatic logging hooks (optional)
    - Security hooks for blocked patterns
    - Structured response handling
    - Cost tracking
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.total_cost = 0.0
        self.call_count = 0
        self.audit_log = []

    def _create_logging_hooks(self) -> dict:
        """Create logging hooks if enabled."""
        if not self.config.enable_logging:
            return {}

        async def log_pre_hook(hook_input, tool_use_id, context):
            timestamp = datetime.now().strftime("%H:%M:%S")
            tool_name = hook_input['tool_name']

            self.audit_log.append({
                "timestamp": timestamp,
                "agent": self.config.name,
                "event": "tool_call",
                "tool": tool_name,
            })

            print(f"  [{self.config.name}] → {tool_name}")
            return {'continue_': True}

        async def log_post_hook(hook_input, tool_use_id, context):
            return {'continue_': True}

        return {
            'PreToolUse': [HookMatcher(matcher=None, hooks=[log_pre_hook])],
            'PostToolUse': [HookMatcher(matcher=None, hooks=[log_post_hook])]
        }

    def _create_security_hooks(self) -> dict:
        """Create security hooks for blocked patterns."""
        if not self.config.blocked_patterns:
            return {}

        blocked = self.config.blocked_patterns

        async def security_hook(hook_input, tool_use_id, context):
            tool_name = hook_input['tool_name']
            tool_input = hook_input['tool_input']

            # Check Write operations
            if tool_name == "Write":
                file_path = str(tool_input.get('file_path', ''))
                for pattern in blocked:
                    if pattern.lower() in file_path.lower():
                        print(f"  [{self.config.name}] BLOCKED: {file_path}")
                        return {'continue_': False}

            return {'continue_': True}

        return {
            'PreToolUse': [HookMatcher(matcher=None, hooks=[security_hook])]
        }

    def _merge_hooks(self, *hook_dicts) -> dict:
        """Merge multiple hook dictionaries."""
        result = {}
        for hooks in hook_dicts:
            for event_type, matchers in hooks.items():
                if event_type not in result:
                    result[event_type] = []
                result[event_type].extend(matchers)
        return result

    def _build_options(self) -> ClaudeAgentOptions:
        """Build ClaudeAgentOptions from config."""
        hooks = self._merge_hooks(
            self._create_security_hooks(),
            self._create_logging_hooks(),
        )

        return ClaudeAgentOptions(
            model=self.config.model,
            permission_mode="bypassPermissions",
            allowed_tools=self.config.allowed_tools,
            system_prompt=self.config.system_prompt,
            hooks=hooks if hooks else None,
        )

    async def run(self, prompt: str) -> str:
        """
        Run the agent with the given prompt.

        Returns the agent's text response.
        """
        self.call_count += 1
        response_text = []

        options = self._build_options()

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt=prompt)

            async for msg in client.receive_response():
                msg_type = type(msg).__name__

                if msg_type == 'AssistantMessage':
                    for block in msg.content:
                        if type(block).__name__ == 'TextBlock':
                            response_text.append(block.text)

                elif msg_type == 'ResultMessage':
                    if hasattr(msg, 'total_cost_usd') and msg.total_cost_usd:
                        self.total_cost += msg.total_cost_usd

        return ''.join(response_text)

    def get_stats(self) -> dict:
        """Get agent statistics."""
        return {
            "name": self.config.name,
            "calls": self.call_count,
            "total_cost": self.total_cost,
            "audit_entries": len(self.audit_log),
        }


# ============================================================
# Specialized Agent Classes
# ============================================================

class CodeReviewerAgent(BaseAgent):
    """Agent specialized for code review tasks."""

    def __init__(self, strict_mode: bool = False):
        config = AgentConfig(
            name="CodeReviewer",
            description="Reviews code for quality, bugs, and best practices",
            model="sonnet",
            allowed_tools=["Read", "Glob", "Grep"],
            system_prompt=self._get_system_prompt(strict_mode),
            enable_logging=True,
        )
        super().__init__(config)
        self.strict_mode = strict_mode

    def _get_system_prompt(self, strict: bool) -> str:
        base = "You are a code reviewer. Analyze code for bugs, security issues, and best practices."
        if strict:
            return base + " Be very strict and thorough. Point out every potential issue."
        return base + " Focus on major issues and provide constructive feedback."


class FileManagerAgent(BaseAgent):
    """Agent specialized for file management tasks."""

    def __init__(self, read_only: bool = False, blocked_paths: list[str] = None):
        tools = ["Read", "Glob"] if read_only else ["Read", "Write", "Glob"]

        config = AgentConfig(
            name="FileManager",
            description="Manages files and directories",
            model="sonnet",
            allowed_tools=tools,
            system_prompt="You are a file manager assistant. Help users with file operations.",
            enable_logging=True,
            blocked_patterns=blocked_paths or [],
        )
        super().__init__(config)
        self.read_only = read_only


class ConversationAgent(BaseAgent):
    """Agent for pure conversation without tools."""

    def __init__(self, persona: str = "helpful assistant"):
        config = AgentConfig(
            name="Conversationalist",
            description=f"A {persona} for general conversation",
            model="sonnet",
            allowed_tools=[],  # No tools
            system_prompt=f"You are a {persona}. Be helpful and friendly.",
            enable_logging=False,  # No logging for conversation
        )
        super().__init__(config)


# ============================================================
# Agent Factory
# ============================================================

class AgentFactory:
    """Factory for creating agents from configuration."""

    PRESETS = {
        "code-reviewer": {
            "class": CodeReviewerAgent,
            "params": {"strict_mode": False},
        },
        "strict-code-reviewer": {
            "class": CodeReviewerAgent,
            "params": {"strict_mode": True},
        },
        "file-reader": {
            "class": FileManagerAgent,
            "params": {"read_only": True},
        },
        "file-manager": {
            "class": FileManagerAgent,
            "params": {"read_only": False},
        },
        "secure-file-manager": {
            "class": FileManagerAgent,
            "params": {"read_only": False, "blocked_paths": [".env", "secret", "password"]},
        },
        "chat": {
            "class": ConversationAgent,
            "params": {"persona": "helpful assistant"},
        },
    }

    @classmethod
    def create(cls, preset: str) -> BaseAgent:
        """Create an agent from a preset name."""
        if preset not in cls.PRESETS:
            raise ValueError(f"Unknown preset: {preset}. Available: {list(cls.PRESETS.keys())}")

        spec = cls.PRESETS[preset]
        return spec["class"](**spec["params"])

    @classmethod
    def list_presets(cls) -> list[str]:
        """List available presets."""
        return list(cls.PRESETS.keys())


# ============================================================
# Demo Functions
# ============================================================

async def demo_basic_agent():
    """Demo 1: Basic agent usage with custom config."""
    print("\n" + "=" * 60)
    print("Demo 1: Basic Custom Agent")
    print("=" * 60)

    # Create agent with custom config
    config = AgentConfig(
        name="BasicAgent",
        description="A simple demonstration agent",
        model="sonnet",
        allowed_tools=["Read"],
        enable_logging=True,
    )

    agent = BaseAgent(config)

    prompt = "Read the file 'requirements.txt' and tell me what dependencies are listed."
    print(f"\nPrompt: {prompt}")
    print("-" * 60)

    response = await agent.run(prompt)
    print(f"\nResponse:\n{response}")

    stats = agent.get_stats()
    print(f"\n[Stats] Calls: {stats['calls']}, Cost: ${stats['total_cost']:.4f}")


async def demo_specialized_agents():
    """Demo 2: Specialized agent classes."""
    print("\n" + "=" * 60)
    print("Demo 2: Specialized Agent Classes")
    print("=" * 60)

    # Code Reviewer Agent
    print("\n--- CodeReviewerAgent (strict mode) ---")
    reviewer = CodeReviewerAgent(strict_mode=True)

    response = await reviewer.run(
        "Review the code in src/v0_hello.py. Focus on potential improvements."
    )
    print(f"\nReview:\n{response[:500]}...")

    # File Manager Agent (read-only)
    print("\n--- FileManagerAgent (read-only) ---")
    file_mgr = FileManagerAgent(read_only=True)

    response = await file_mgr.run("List all Python files in the src/ directory.")
    print(f"\nFiles:\n{response}")

    # Print combined stats
    print("\n--- Agent Statistics ---")
    for agent in [reviewer, file_mgr]:
        stats = agent.get_stats()
        print(f"  {stats['name']}: {stats['calls']} calls, ${stats['total_cost']:.4f}")


async def demo_factory():
    """Demo 3: Using the Agent Factory."""
    print("\n" + "=" * 60)
    print("Demo 3: Agent Factory Pattern")
    print("=" * 60)

    print("\nAvailable presets:", AgentFactory.list_presets())

    # Create agents from presets
    agents = {
        "chat": AgentFactory.create("chat"),
        "secure-file-manager": AgentFactory.create("secure-file-manager"),
    }

    # Test chat agent
    print("\n--- Chat Agent ---")
    response = await agents["chat"].run("What is 2 + 2? Answer briefly.")
    print(f"Response: {response}")

    # Test secure file manager (will block sensitive paths)
    print("\n--- Secure File Manager ---")
    print("Attempting to write to 'secret_data.txt' (should be blocked)...")
    response = await agents["secure-file-manager"].run(
        "Create a file called 'secret_data.txt' with content 'test'"
    )
    print(f"Response: {response[:200]}...")


async def demo_reusability():
    """Demo 4: Agent reusability - multiple calls to same agent."""
    print("\n" + "=" * 60)
    print("Demo 4: Agent Reusability")
    print("=" * 60)

    agent = ConversationAgent(persona="math tutor")

    questions = [
        "What is 5 * 7?",
        "What is the square root of 144?",
        "What is 15% of 200?",
    ]

    for q in questions:
        print(f"\nQ: {q}")
        response = await agent.run(q)
        print(f"A: {response}")

    stats = agent.get_stats()
    print(f"\n[Total] {stats['calls']} calls, ${stats['total_cost']:.4f}")


async def main():
    # Demo 1: Basic custom agent
    await demo_basic_agent()

    # Demo 2: Specialized agent classes
    await demo_specialized_agents()

    # Demo 3: Factory pattern
    await demo_factory()

    # Demo 4: Reusability
    await demo_reusability()

    print("\n" + "=" * 60)
    print("v4 Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
