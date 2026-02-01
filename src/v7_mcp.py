#!/usr/bin/env python3
"""
v7: MCP Extension - Connecting to the External World

============================================================
注意：这是【教学演示代码】，不是项目的实际实现
============================================================
本文件用于演示 Claude Agent SDK 的 MCP 扩展能力。
实际的 Web 应用代码位于 web/ 目录下：
  - 后端: web/backend/main.py
  - 前端: web/frontend/src/
============================================================

This example demonstrates the Model Context Protocol (MCP) for:
- Connecting agents to external services
- Extending agent capabilities with custom tools
- Integrating third-party APIs

Goal: Understand how to extend agents beyond built-in tools.

Run: python src/v7_mcp.py

Note: MCP requires external servers. This demo shows configuration patterns
and provides a conceptual example. For real MCP usage, you need to run
actual MCP servers.
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
# MCP Configuration Examples
# ============================================================

def get_mcp_config_examples():
    """Return example MCP server configurations."""
    return {
        # Example 1: Database server
        "database": {
            "command": "python",
            "args": ["-m", "mcp_database_server"],
            "env": {
                "DB_HOST": "localhost",
                "DB_NAME": "mydb",
            }
        },

        # Example 2: Email server
        "email": {
            "command": "node",
            "args": ["email-mcp-server.js"],
            "env": {
                "SMTP_HOST": "smtp.example.com",
                "SMTP_USER": "user@example.com",
            }
        },

        # Example 3: GitHub server
        "github": {
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-github"],
            "env": {
                "GITHUB_TOKEN": "ghp_xxx",
            }
        },

        # Example 4: Filesystem server (official)
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-filesystem", "/allowed/path"],
        },

        # Example 5: Custom Python server
        "custom": {
            "command": "python",
            "args": ["my_mcp_server.py", "--port", "8080"],
            "env": {
                "API_KEY": "xxx",
            }
        },
    }


# ============================================================
# Demo Functions
# ============================================================

async def demo_mcp_concept():
    """Demo 1: Explain MCP concept and configuration."""
    print("\n" + "=" * 60)
    print("Demo 1: MCP Concept and Configuration")
    print("=" * 60)

    print("""
What is MCP (Model Context Protocol)?
-------------------------------------
MCP is a protocol that allows Claude agents to connect to external
services and tools. It extends the agent's capabilities beyond the
built-in tools (Read, Write, Bash, etc.).

Key Benefits:
- Connect to databases, APIs, and external services
- Use custom tools defined by MCP servers
- Maintain security through controlled access
- Share tool implementations across projects

MCP Architecture:

  ┌─────────────────┐      ┌─────────────────┐
  │  Claude Agent   │ MCP  │   MCP Server    │
  │                 │<---->│  (database,     │
  │  ClaudeSDKClient│      │   email, etc.)  │
  └─────────────────┘      └─────────────────┘
         │                        │
         │                        ▼
         │                 ┌─────────────────┐
         │                 │ External Service│
         │                 │ (DB, API, etc.) │
         │                 └─────────────────┘
         ▼
  Built-in Tools
  (Read, Write, Bash)
""")

    print("\nMCP Server Configuration Example:")
    print("-" * 40)

    configs = get_mcp_config_examples()
    for name, config in list(configs.items())[:3]:
        print(f"\n# {name.upper()} Server")
        print(f'mcp_servers={{')
        print(f'    "{name}": {{')
        print(f'        "command": "{config["command"]}",')
        print(f'        "args": {config["args"]},')
        if "env" in config:
            print(f'        "env": {config["env"]}')
        print(f'    }}')
        print(f'}}')


async def demo_mcp_tool_naming():
    """Demo 2: Explain MCP tool naming convention."""
    print("\n" + "=" * 60)
    print("Demo 2: MCP Tool Naming Convention")
    print("=" * 60)

    print("""
MCP Tool Naming Format
----------------------
MCP tools follow this naming convention:

    mcp__{server_name}__{tool_name}

Examples:
    mcp__database__query        - Query database
    mcp__database__insert       - Insert records
    mcp__email__send            - Send email
    mcp__email__search_inbox    - Search inbox
    mcp__github__create_issue   - Create GitHub issue
    mcp__github__list_repos     - List repositories
    mcp__filesystem__read_file  - Read file (via MCP)
    mcp__filesystem__list_dir   - List directory

Configuring Allowed Tools:
--------------------------
""")

    print("""
# Allow specific MCP tools
options = ClaudeAgentOptions(
    allowed_tools=[
        "Read",                      # Built-in tool
        "Write",                     # Built-in tool
        "mcp__database__query",      # MCP database query
        "mcp__email__send",          # MCP email send
    ],
    mcp_servers={
        "database": {...},
        "email": {...},
    }
)

# Or allow all tools from an MCP server (pattern matching)
# Note: This depends on SDK support for wildcards
""")


async def demo_mcp_configuration():
    """Demo 3: Show how to configure MCP in code."""
    print("\n" + "=" * 60)
    print("Demo 3: MCP Configuration in Code")
    print("=" * 60)

    print("""
Complete MCP Configuration Example
----------------------------------
""")

    print('''
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

# Define MCP servers
mcp_servers = {
    # Database server for data operations
    "database": {
        "command": "python",
        "args": ["-m", "mcp_database_server"],
        "env": {
            "DB_HOST": "localhost",
            "DB_PORT": "5432",
            "DB_NAME": "myapp",
            "DB_USER": "agent",
        }
    },

    # Email server for communication
    "email": {
        "command": "node",
        "args": ["./mcp-servers/email-server.js"],
        "env": {
            "SMTP_HOST": "smtp.gmail.com",
            "SMTP_PORT": "587",
            "EMAIL_USER": os.environ.get("EMAIL_USER"),
            "EMAIL_PASS": os.environ.get("EMAIL_PASS"),
        }
    },
}

# Configure agent options
options = ClaudeAgentOptions(
    model="sonnet",
    permission_mode="bypassPermissions",

    # Allow built-in and MCP tools
    allowed_tools=[
        # Built-in tools
        "Read", "Write", "Glob",

        # MCP database tools
        "mcp__database__query",
        "mcp__database__insert",
        "mcp__database__update",

        # MCP email tools
        "mcp__email__send",
        "mcp__email__search",
    ],

    # MCP server definitions
    mcp_servers=mcp_servers,

    system_prompt="""
    You have access to:
    - Database tools (query, insert, update) via mcp__database__*
    - Email tools (send, search) via mcp__email__*
    - File operations via built-in Read/Write
    """,
)

# Use the agent
async with ClaudeSDKClient(options=options) as client:
    await client.query(prompt="Query the users table and send a summary email")
    async for msg in client.receive_response():
        # Handle response...
        pass
''')


async def demo_without_mcp():
    """Demo 4: Run agent without MCP (baseline comparison)."""
    print("\n" + "=" * 60)
    print("Demo 4: Agent Without MCP (Built-in Tools Only)")
    print("=" * 60)

    # Track tool usage
    tool_calls = []

    async def track_hook(hook_input, tool_use_id, context):
        tool_name = hook_input['tool_name']
        tool_calls.append(tool_name)
        print(f"  [Tool] {tool_name}")
        return {'continue_': True}

    hooks = {
        'PreToolUse': [HookMatcher(matcher=None, hooks=[track_hook])]
    }

    options = ClaudeAgentOptions(
        model="sonnet",
        permission_mode="bypassPermissions",
        allowed_tools=["Read", "Glob"],  # Built-in tools only
        hooks=hooks,
    )

    prompt = "List all Python files in src/ directory and count them."

    print(f"\nPrompt: {prompt}")
    print("-" * 40)

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

    print(f"\n--- Tools used: {tool_calls} ---")
    print("\nNote: With MCP, this agent could also query databases, send emails, etc.")


async def demo_mcp_use_cases():
    """Demo 5: Common MCP use cases."""
    print("\n" + "=" * 60)
    print("Demo 5: Common MCP Use Cases")
    print("=" * 60)

    use_cases = [
        {
            "name": "Database Integration",
            "description": "Query and modify databases directly",
            "server": "mcp-database",
            "tools": ["query", "insert", "update", "delete"],
            "example": "Find all users who signed up last month",
        },
        {
            "name": "Email Automation",
            "description": "Send and manage emails programmatically",
            "server": "mcp-email",
            "tools": ["send", "search_inbox", "create_draft", "add_label"],
            "example": "Send weekly report to team@company.com",
        },
        {
            "name": "GitHub Integration",
            "description": "Manage repositories, issues, and PRs",
            "server": "mcp-github",
            "tools": ["create_issue", "list_repos", "create_pr", "search_code"],
            "example": "Create an issue for the bug we discussed",
        },
        {
            "name": "Slack/Discord Bot",
            "description": "Send messages to team channels",
            "server": "mcp-slack",
            "tools": ["send_message", "list_channels", "react_to_message"],
            "example": "Post deployment status to #releases channel",
        },
        {
            "name": "Calendar Management",
            "description": "Schedule and manage calendar events",
            "server": "mcp-calendar",
            "tools": ["create_event", "list_events", "update_event"],
            "example": "Schedule a meeting with the team tomorrow at 3pm",
        },
        {
            "name": "Cloud Services",
            "description": "Manage cloud infrastructure",
            "server": "mcp-aws or mcp-gcp",
            "tools": ["list_instances", "deploy", "get_logs"],
            "example": "Show me the status of our production servers",
        },
    ]

    for i, uc in enumerate(use_cases, 1):
        print(f"\n{i}. {uc['name']}")
        print(f"   Description: {uc['description']}")
        print(f"   Server: {uc['server']}")
        print(f"   Tools: {', '.join(uc['tools'])}")
        print(f"   Example: \"{uc['example']}\"")


async def main():
    print("=" * 60)
    print("v7: MCP Extension Demo")
    print("=" * 60)
    print("\nMCP (Model Context Protocol) extends agent capabilities")
    print("by connecting to external services and custom tools.")
    print("\nNote: This is a conceptual demo. Real MCP usage requires")
    print("running actual MCP servers.")

    # Demo 1: MCP concept
    await demo_mcp_concept()

    # Demo 2: Tool naming
    await demo_mcp_tool_naming()

    # Demo 3: Configuration
    await demo_mcp_configuration()

    # Demo 4: Without MCP (baseline)
    await demo_without_mcp()

    # Demo 5: Use cases
    await demo_mcp_use_cases()

    # Summary
    print("\n" + "=" * 60)
    print("MCP Summary")
    print("=" * 60)
    print("""
Key Points:
-----------
1. MCP connects agents to external services (databases, APIs, etc.)
2. MCP servers run as separate processes
3. Tool naming: mcp__{server}__{tool}
4. Configure via mcp_servers in ClaudeAgentOptions
5. Combine MCP tools with built-in tools

When to Use MCP:
----------------
- Accessing databases
- Sending emails/messages
- Integrating with APIs (GitHub, Slack, etc.)
- Custom business logic
- Services that need credentials

Official MCP Servers:
--------------------
- @anthropic/mcp-filesystem
- @anthropic/mcp-github
- Community servers on npm/PyPI

Resources:
----------
- MCP Specification: https://spec.modelcontextprotocol.io
- Claude MCP Docs: https://docs.anthropic.com/en/docs/claude-code/mcp
""")

    print("=" * 60)
    print("v7 Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
