#!/usr/bin/env python3
"""
Web Researcher - MCP 实战示例 (网络搜索)

本示例展示 MCP 机制在**网络研究**场景中的应用：
- 配置 Tavily MCP 服务器进行网络搜索
- 使用搜索工具获取实时信息
- 结合本地文件操作生成研究报告

MCP (Model Context Protocol) 让 Agent 能够连接外部服务，
突破内置工具的限制。

核心概念:
- mcp_servers: MCP 服务器配置
- mcp__{server}__{tool}: MCP 工具命名格式
- 工具组合: MCP 工具 + 内置工具协同工作

Run: python examples/web_researcher.py

Note: 需要配置 TAVILY_API_KEY 环境变量
      获取 API Key: https://tavily.com/
"""

import asyncio
import sys
import io
import os
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

load_dotenv()


# ============================================================
# MCP Configuration
# ============================================================

def get_tavily_mcp_config() -> Dict[str, Any]:
    """
    获取 Tavily MCP 服务器配置

    Tavily 是一个专为 AI Agent 设计的搜索 API，
    提供更结构化、更适合 LLM 处理的搜索结果。

    工具列表:
    - mcp__tavily__tavily_search: 网络搜索
    - mcp__tavily__tavily_extract: 提取网页内容
    - mcp__tavily__tavily_crawl: 爬取网站
    """
    api_key = os.environ.get("TAVILY_API_KEY", "")

    if not api_key:
        print("[Warning] TAVILY_API_KEY not set. MCP features will not work.")
        print("         Get your API key at: https://tavily.com/")

    return {
        "tavily": {
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-tavily"],
            "env": {
                "TAVILY_API_KEY": api_key,
            }
        }
    }


def get_serpapi_mcp_config() -> Dict[str, Any]:
    """
    获取 SerpAPI MCP 服务器配置 (备选)

    SerpAPI 提供 Google 搜索结果的结构化 API。

    工具列表:
    - mcp__serpapi__google: Google 搜索
    - mcp__serpapi__google_news: 新闻搜索
    - mcp__serpapi__google_images: 图片搜索
    """
    api_key = os.environ.get("SERPAPI_API_KEY", "")

    return {
        "serpapi": {
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-serpapi"],
            "env": {
                "SERPAPI_API_KEY": api_key,
            }
        }
    }


# ============================================================
# Research Configuration
# ============================================================

@dataclass
class ResearchConfig:
    """研究任务配置"""
    topic: str
    search_depth: str = "basic"  # basic, advanced
    max_results: int = 5
    output_format: str = "markdown"  # markdown, json
    save_to_file: bool = True
    output_dir: str = "research_output"


# ============================================================
# Web Researcher Agent (Conceptual Demo)
# ============================================================

class WebResearcherAgent:
    """
    网络研究助手 Agent

    使用 MCP 连接搜索服务，进行网络研究并生成报告。

    Note: 这是一个概念演示。实际运行需要:
    1. 配置 TAVILY_API_KEY 环境变量
    2. 安装 Node.js (用于运行 npx)
    3. 网络连接正常
    """

    def __init__(self, config: ResearchConfig):
        self.config = config

    def _build_options(self):
        """构建 Agent 选项 (包含 MCP 配置)"""
        from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

        # MCP 服务器配置
        mcp_servers = get_tavily_mcp_config()

        # 日志 Hook
        async def log_hook(hook_input, tool_use_id, context):
            tool_name = hook_input["tool_name"]
            print(f"  [Tool] {tool_name}")
            return {"continue_": True}

        hooks = {
            "PreToolUse": [HookMatcher(matcher=None, hooks=[log_hook])]
        }

        return ClaudeAgentOptions(
            model="sonnet",
            permission_mode="bypassPermissions",
            allowed_tools=[
                # 内置工具
                "Read", "Write", "Glob",
                # MCP 工具 (Tavily)
                "mcp__tavily__tavily_search",
                "mcp__tavily__tavily_extract",
            ],
            mcp_servers=mcp_servers,
            hooks=hooks,
            max_turns=20,
            system_prompt=f"""You are a web research assistant.

Your task is to research topics using web search tools and compile findings into reports.

Available tools:
- mcp__tavily__tavily_search: Search the web for information
- mcp__tavily__tavily_extract: Extract content from specific URLs
- Write: Save reports to files

Research guidelines:
1. Start with a broad search to understand the topic
2. Extract key information from relevant sources
3. Synthesize findings into a coherent report
4. Include source citations

Output format: {self.config.output_format}
""",
        )

    async def research(self) -> str:
        """执行研究任务"""
        from claude_agent_sdk import ClaudeSDKClient

        # 确保输出目录存在
        if self.config.save_to_file:
            Path(self.config.output_dir).mkdir(parents=True, exist_ok=True)

        options = self._build_options()

        prompt = f"""Research the following topic and create a comprehensive report:

Topic: {self.config.topic}

Instructions:
1. Use mcp__tavily__tavily_search to find relevant information
2. Search for at least {self.config.max_results} different aspects of the topic
3. Compile findings into a well-structured report
4. Include source URLs for all information
{"5. Save the report to " + self.config.output_dir + "/report.md" if self.config.save_to_file else ""}

Report structure:
- Executive Summary
- Key Findings
- Detailed Analysis
- Sources
"""

        print(f"\n[Research] Starting research on: {self.config.topic}")
        print("-" * 60)

        result_text = ""

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt=prompt)

            async for msg in client.receive_response():
                msg_type = type(msg).__name__

                if msg_type == "AssistantMessage":
                    for block in msg.content:
                        if type(block).__name__ == "TextBlock":
                            result_text += block.text

                elif msg_type == "ResultMessage":
                    if hasattr(msg, "total_cost_usd") and msg.total_cost_usd:
                        print(f"\n[Cost: ${msg.total_cost_usd:.4f}]")

        return result_text


# ============================================================
# Demo: Conceptual Overview
# ============================================================

def print_mcp_overview():
    """打印 MCP 概念说明"""
    print("""
============================================================
MCP (Model Context Protocol) 网络搜索集成
============================================================

什么是 MCP?
-----------
MCP 是一个协议，让 Claude Agent 能够连接外部服务。
通过 MCP，Agent 可以执行网络搜索、数据库查询、API 调用等操作。

MCP 架构:
---------
  ┌─────────────────┐      ┌─────────────────┐
  │  Claude Agent   │ MCP  │   MCP Server    │
  │                 │<---->│   (Tavily)      │
  │  SDK Client     │      │                 │
  └─────────────────┘      └─────────────────┘
                                  │
                                  ▼
                           ┌─────────────────┐
                           │  Tavily API     │
                           │  (Web Search)   │
                           └─────────────────┘

配置方式:
---------
""")

    print('''
# 1. 定义 MCP 服务器
mcp_servers = {
    "tavily": {
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-tavily"],
        "env": {
            "TAVILY_API_KEY": os.environ.get("TAVILY_API_KEY"),
        }
    }
}

# 2. 在选项中启用 MCP 工具
options = ClaudeAgentOptions(
    allowed_tools=[
        "Read", "Write",  # 内置工具
        "mcp__tavily__tavily_search",  # MCP 工具
        "mcp__tavily__tavily_extract",
    ],
    mcp_servers=mcp_servers,
)

# 3. Agent 现在可以使用搜索功能
prompt = "Search for the latest news about AI"
''')


def print_tool_reference():
    """打印 MCP 工具参考"""
    print("""
============================================================
MCP 搜索工具参考
============================================================

Tavily Tools:
-------------
mcp__tavily__tavily_search
  - 功能: 网络搜索
  - 参数:
    - query: 搜索查询
    - search_depth: "basic" | "advanced"
    - max_results: 结果数量 (1-10)
  - 返回: 搜索结果列表 (标题、URL、摘要)

mcp__tavily__tavily_extract
  - 功能: 提取网页内容
  - 参数:
    - urls: 要提取的 URL 列表
  - 返回: 网页的清理后文本内容

mcp__tavily__tavily_crawl
  - 功能: 爬取网站
  - 参数:
    - url: 起始 URL
    - max_pages: 最大页面数
  - 返回: 多个页面的内容

SerpAPI Tools (备选):
--------------------
mcp__serpapi__google
  - 功能: Google 搜索
  - 参数: q (查询), location (位置)
  - 返回: Google 搜索结果

mcp__serpapi__google_news
  - 功能: Google 新闻搜索
  - 参数: q (查询)
  - 返回: 新闻文章列表
""")


def print_example_prompt():
    """打印示例 Prompt"""
    print("""
============================================================
示例 Prompt
============================================================

研究任务示例:
-------------
prompt = '''
Research the topic "Large Language Model Agents" and create a report.

Use mcp__tavily__tavily_search to:
1. Search for "LLM agent frameworks 2024"
2. Search for "AI agent best practices"
3. Search for "Claude agent SDK examples"

Then compile the findings into a markdown report saved to research_output/llm_agents.md

Include:
- Executive summary
- Key frameworks and tools
- Best practices
- Challenges and solutions
- Source URLs
'''
""")


def print_setup_instructions():
    """打印环境配置说明"""
    print("""
============================================================
环境配置说明
============================================================

要运行 MCP 搜索功能，需要:

1. 获取 Tavily API Key:
   - 访问 https://tavily.com/
   - 注册账号并获取 API Key
   - 设置环境变量: TAVILY_API_KEY=your_key

2. 安装 Node.js:
   - MCP 服务器通过 npx 运行
   - 下载: https://nodejs.org/

3. 配置 .env 文件:
   ```
   ANTHROPIC_API_KEY=your_anthropic_key
   TAVILY_API_KEY=your_tavily_key
   ```

4. 运行示例:
   ```
   python examples/web_researcher.py --demo
   ```

当前环境状态:
""")
    # 检查环境变量
    tavily_key = os.environ.get("TAVILY_API_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

    print(f"  ANTHROPIC_API_KEY: {'[Set]' if anthropic_key else '[Not Set]'}")
    print(f"  TAVILY_API_KEY: {'[Set]' if tavily_key else '[Not Set]'}")

    # 检查 Node.js
    try:
        import subprocess
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        node_version = result.stdout.strip() if result.returncode == 0 else "Not Found"
    except:
        node_version = "Not Found"

    print(f"  Node.js: {node_version}")


# ============================================================
# Demo with Real MCP (if configured)
# ============================================================

async def demo_with_mcp():
    """尝试运行实际的 MCP 演示"""
    tavily_key = os.environ.get("TAVILY_API_KEY", "")

    if not tavily_key:
        print("\n[Skip] TAVILY_API_KEY not configured, skipping live demo.")
        print("       Set the environment variable to enable web search.")
        return

    print("\n" + "=" * 60)
    print("Live Demo: Web Research with MCP")
    print("=" * 60)

    config = ResearchConfig(
        topic="Claude Agent SDK best practices",
        search_depth="basic",
        max_results=3,
        save_to_file=True,
        output_dir="research_output",
    )

    try:
        agent = WebResearcherAgent(config)
        result = await agent.research()

        print("\n--- Research Result ---")
        print(result[:1000] if result else "(No output)")

    except Exception as e:
        print(f"\n[Error] MCP demo failed: {e}")
        print("        This might be due to missing dependencies or network issues.")


# ============================================================
# Main
# ============================================================

async def main():
    import sys

    print("=" * 60)
    print("Web Researcher - MCP 实战示例")
    print("=" * 60)

    # 打印概念说明
    print_mcp_overview()

    # 打印工具参考
    print_tool_reference()

    # 打印示例 Prompt
    print_example_prompt()

    # 打印配置说明
    print_setup_instructions()

    # 尝试运行实际演示
    if "--demo" in sys.argv:
        await demo_with_mcp()
    else:
        print("\n" + "-" * 60)
        print("使用 --demo 参数运行实际的 MCP 搜索演示:")
        print("  python examples/web_researcher.py --demo")

    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)
    print()
    print("Key Takeaways:")
    print("1. MCP 让 Agent 能够连接外部服务 (搜索、API 等)")
    print("2. 工具命名格式: mcp__{server}__{tool}")
    print("3. 通过 mcp_servers 配置定义服务器")
    print("4. MCP 工具和内置工具可以组合使用")


if __name__ == "__main__":
    asyncio.run(main())
