#!/usr/bin/env python3
"""
Database Agent - MCP 实战示例 (数据库集成)

本示例展示 MCP 机制在**数据库操作**场景中的应用：
- 配置 SQLite MCP 服务器进行数据库操作
- 使用 SQL 工具查询和分析数据
- 生成数据分析报告

MCP 让 Agent 能够安全地访问数据库，执行查询并返回结构化结果。

核心概念:
- mcp_servers: 数据库 MCP 服务器配置
- mcp__sqlite__*: SQLite 数据库工具
- 安全查询: 通过 MCP 封装的安全 SQL 执行

Run: python examples/database_agent.py

Note: 这是概念演示。实际 MCP 数据库服务器需要单独部署。
      本示例同时提供一个使用内置工具的模拟版本。
"""

import asyncio
import sys
import io
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

load_dotenv()


# ============================================================
# MCP Configuration
# ============================================================

def get_sqlite_mcp_config(db_path: str) -> Dict[str, Any]:
    """
    获取 SQLite MCP 服务器配置

    SQLite MCP 服务器提供安全的数据库访问，
    Agent 可以执行查询但无法直接访问文件系统。

    工具列表:
    - mcp__sqlite__query: 执行 SELECT 查询
    - mcp__sqlite__execute: 执行 INSERT/UPDATE/DELETE
    - mcp__sqlite__schema: 获取数据库结构
    """
    return {
        "sqlite": {
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-sqlite", db_path],
            "env": {}
        }
    }


def get_postgres_mcp_config() -> Dict[str, Any]:
    """
    获取 PostgreSQL MCP 服务器配置 (示例)

    用于连接 PostgreSQL 数据库的 MCP 配置。

    工具列表:
    - mcp__postgres__query: 执行查询
    - mcp__postgres__schema: 获取表结构
    """
    return {
        "postgres": {
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-postgres"],
            "env": {
                "POSTGRES_HOST": os.environ.get("POSTGRES_HOST", "localhost"),
                "POSTGRES_PORT": os.environ.get("POSTGRES_PORT", "5432"),
                "POSTGRES_DB": os.environ.get("POSTGRES_DB", "mydb"),
                "POSTGRES_USER": os.environ.get("POSTGRES_USER", "user"),
                "POSTGRES_PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            }
        }
    }


# ============================================================
# Sample Database Setup
# ============================================================

def create_sample_database(db_path: str = "sample_data.db"):
    """创建示例数据库"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 创建用户表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE,
            department TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 创建订单表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            product TEXT NOT NULL,
            amount REAL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # 创建产品表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            price REAL,
            stock INTEGER DEFAULT 0
        )
    """)

    # 插入示例数据
    users = [
        ("Alice", "alice@example.com", "Engineering"),
        ("Bob", "bob@example.com", "Sales"),
        ("Charlie", "charlie@example.com", "Engineering"),
        ("Diana", "diana@example.com", "Marketing"),
        ("Eve", "eve@example.com", "Sales"),
    ]

    cursor.executemany(
        "INSERT OR IGNORE INTO users (name, email, department) VALUES (?, ?, ?)",
        users
    )

    products = [
        ("Widget A", "Electronics", 29.99, 100),
        ("Widget B", "Electronics", 49.99, 50),
        ("Gadget X", "Tools", 19.99, 200),
        ("Gadget Y", "Tools", 39.99, 75),
        ("Service Plan", "Services", 99.99, 999),
    ]

    cursor.executemany(
        "INSERT OR IGNORE INTO products (name, category, price, stock) VALUES (?, ?, ?, ?)",
        products
    )

    orders = [
        (1, "Widget A", 29.99, "completed"),
        (1, "Widget B", 49.99, "completed"),
        (2, "Gadget X", 19.99, "pending"),
        (3, "Widget A", 29.99, "completed"),
        (3, "Service Plan", 99.99, "completed"),
        (4, "Gadget Y", 39.99, "cancelled"),
        (5, "Widget B", 49.99, "pending"),
        (5, "Gadget X", 19.99, "completed"),
    ]

    cursor.executemany(
        "INSERT OR IGNORE INTO orders (user_id, product, amount, status) VALUES (?, ?, ?, ?)",
        orders
    )

    conn.commit()
    conn.close()

    print(f"[Database] Sample database created: {db_path}")
    return db_path


# ============================================================
# Local Database Helper (Simulated MCP)
# ============================================================

class LocalDatabaseHelper:
    """
    本地数据库助手

    模拟 MCP 数据库工具的功能，用于演示目的。
    在实际生产环境中，应使用真正的 MCP 服务器。
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def query(self, sql: str) -> List[Dict[str, Any]]:
        """执行 SELECT 查询"""
        cursor = self.conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def execute(self, sql: str) -> int:
        """执行 INSERT/UPDATE/DELETE"""
        cursor = self.conn.cursor()
        cursor.execute(sql)
        self.conn.commit()
        return cursor.rowcount

    def get_schema(self) -> str:
        """获取数据库结构"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()

        schema = []
        for (table_name,) in tables:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()

            col_info = []
            for col in columns:
                col_info.append(f"  {col[1]} {col[2]}")

            schema.append(f"TABLE {table_name}:\n" + "\n".join(col_info))

        return "\n\n".join(schema)

    def close(self):
        self.conn.close()


# ============================================================
# Database Agent (Conceptual + Simulated)
# ============================================================

class DatabaseAgent:
    """
    数据库 Agent

    支持两种模式:
    1. MCP 模式: 使用真正的 MCP 服务器 (需要配置)
    2. 模拟模式: 使用本地数据库助手 (用于演示)
    """

    def __init__(self, db_path: str, use_mcp: bool = False):
        self.db_path = db_path
        self.use_mcp = use_mcp
        self.db_helper = LocalDatabaseHelper(db_path) if not use_mcp else None

    def _build_mcp_options(self):
        """构建 MCP 模式的选项"""
        from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

        mcp_servers = get_sqlite_mcp_config(self.db_path)

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
                "Read", "Write",
                "mcp__sqlite__query",
                "mcp__sqlite__execute",
                "mcp__sqlite__schema",
            ],
            mcp_servers=mcp_servers,
            hooks=hooks,
            max_turns=15,
            system_prompt="""You are a database analyst assistant.

Available tools:
- mcp__sqlite__query: Execute SELECT queries
- mcp__sqlite__execute: Execute INSERT/UPDATE/DELETE
- mcp__sqlite__schema: Get database schema

Guidelines:
1. Always check the schema first to understand table structure
2. Write efficient SQL queries
3. Explain your analysis clearly
4. Format results in readable tables
""",
        )

    def _build_simulated_options(self):
        """构建模拟模式的选项"""
        from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

        # 创建数据库操作 Hook
        async def db_tool_hook(hook_input, tool_use_id, context):
            tool_name = hook_input["tool_name"]
            tool_input = hook_input["tool_input"]

            # 模拟 MCP 数据库工具
            if tool_name == "Bash":
                command = tool_input.get("command", "")

                # 拦截特定的 "db_" 命令并执行数据库操作
                if command.startswith("db_query "):
                    sql = command[9:].strip().strip('"\'')
                    try:
                        results = self.db_helper.query(sql)
                        print(f"  [DB Query] {sql[:50]}...")
                        # 将结果转换为字符串返回
                        return {"continue_": True}
                    except Exception as e:
                        print(f"  [DB Error] {e}")
                        return {"continue_": True}

                elif command.startswith("db_schema"):
                    print("  [DB Schema]")
                    return {"continue_": True}

            print(f"  [Tool] {tool_name}")
            return {"continue_": True}

        hooks = {
            "PreToolUse": [HookMatcher(matcher=None, hooks=[db_tool_hook])]
        }

        # 获取数据库结构供 prompt 使用
        schema = self.db_helper.get_schema()

        return ClaudeAgentOptions(
            model="sonnet",
            permission_mode="bypassPermissions",
            allowed_tools=["Read", "Write", "Bash"],
            hooks=hooks,
            max_turns=15,
            system_prompt=f"""You are a database analyst assistant.

DATABASE SCHEMA:
{schema}

Since MCP is not available, you'll work with pre-queried data.
I will provide you with query results that you can analyze.

Guidelines:
1. Analyze the data I provide
2. Explain your findings clearly
3. Generate insights and recommendations
4. Format results in readable tables
""",
        )

    async def analyze(self, question: str) -> str:
        """执行数据分析"""
        from claude_agent_sdk import ClaudeSDKClient

        if self.use_mcp:
            options = self._build_mcp_options()
        else:
            options = self._build_simulated_options()

            # 在模拟模式下，先执行一些查询并将结果包含在 prompt 中
            sample_data = self._get_sample_data()
            question = f"""{question}

Here is the current data from the database:

{sample_data}

Analyze this data and provide insights."""

        print(f"\n[Database Agent] Analyzing: {question[:60]}...")
        print("-" * 60)

        result_text = ""

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt=question)

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

    def _get_sample_data(self) -> str:
        """获取示例数据"""
        if not self.db_helper:
            return "(No data available)"

        data = []

        # 用户数据
        users = self.db_helper.query("SELECT * FROM users")
        data.append("USERS TABLE:")
        data.append("| id | name | email | department |")
        data.append("|---|---|---|---|")
        for u in users:
            data.append(f"| {u['id']} | {u['name']} | {u['email']} | {u['department']} |")

        data.append("")

        # 订单数据
        orders = self.db_helper.query("""
            SELECT o.id, u.name as user_name, o.product, o.amount, o.status
            FROM orders o
            JOIN users u ON o.user_id = u.id
        """)
        data.append("ORDERS TABLE (with user names):")
        data.append("| id | user | product | amount | status |")
        data.append("|---|---|---|---|---|")
        for o in orders:
            data.append(f"| {o['id']} | {o['user_name']} | {o['product']} | ${o['amount']:.2f} | {o['status']} |")

        data.append("")

        # 产品数据
        products = self.db_helper.query("SELECT * FROM products")
        data.append("PRODUCTS TABLE:")
        data.append("| id | name | category | price | stock |")
        data.append("|---|---|---|---|---|")
        for p in products:
            data.append(f"| {p['id']} | {p['name']} | {p['category']} | ${p['price']:.2f} | {p['stock']} |")

        data.append("")

        # 汇总统计
        stats = self.db_helper.query("""
            SELECT
                COUNT(*) as total_orders,
                SUM(amount) as total_revenue,
                AVG(amount) as avg_order_value
            FROM orders
            WHERE status = 'completed'
        """)[0]

        data.append("SUMMARY STATISTICS:")
        data.append(f"- Total completed orders: {stats['total_orders']}")
        data.append(f"- Total revenue: ${stats['total_revenue']:.2f}")
        data.append(f"- Average order value: ${stats['avg_order_value']:.2f}")

        return "\n".join(data)


# ============================================================
# Demo Functions
# ============================================================

def print_mcp_database_overview():
    """打印 MCP 数据库集成概述"""
    print("""
============================================================
MCP 数据库集成概述
============================================================

什么是 MCP 数据库集成?
---------------------
MCP 允许 Agent 通过安全的接口访问数据库，
无需直接操作数据库文件或连接字符串。

架构:
-----
  ┌─────────────────┐      ┌─────────────────┐
  │  Claude Agent   │ MCP  │  SQLite MCP     │
  │                 │<---->│  Server         │
  │  SDK Client     │      │                 │
  └─────────────────┘      └─────────────────┘
                                  │
                                  ▼
                           ┌─────────────────┐
                           │  SQLite DB      │
                           │  (sample.db)    │
                           └─────────────────┘

优势:
-----
1. 安全: Agent 无法直接访问文件系统
2. 受控: 可以限制 SQL 操作类型 (只读/读写)
3. 审计: 所有查询都经过 MCP 服务器
4. 灵活: 支持多种数据库 (SQLite, PostgreSQL, MySQL)
""")


def print_mcp_config_example():
    """打印 MCP 配置示例"""
    print("""
============================================================
MCP 数据库配置示例
============================================================
""")

    print('''
# SQLite 配置
mcp_servers = {
    "sqlite": {
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-sqlite", "path/to/database.db"],
        "env": {}
    }
}

# PostgreSQL 配置
mcp_servers = {
    "postgres": {
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-postgres"],
        "env": {
            "POSTGRES_HOST": "localhost",
            "POSTGRES_PORT": "5432",
            "POSTGRES_DB": "mydb",
            "POSTGRES_USER": "user",
            "POSTGRES_PASSWORD": "password",
        }
    }
}

# 在选项中启用
options = ClaudeAgentOptions(
    allowed_tools=[
        "mcp__sqlite__query",     # SELECT 查询
        "mcp__sqlite__execute",   # INSERT/UPDATE/DELETE
        "mcp__sqlite__schema",    # 获取表结构
    ],
    mcp_servers=mcp_servers,
)
''')


async def demo_database_analysis():
    """演示数据库分析"""
    print("\n" + "=" * 60)
    print("Demo: Database Analysis (Simulated MCP)")
    print("=" * 60)

    # 创建示例数据库
    db_path = create_sample_database("sample_data.db")

    # 创建 Agent (模拟模式)
    agent = DatabaseAgent(db_path, use_mcp=False)

    # 执行分析
    question = """Analyze the sales data and provide:
1. Which department has the most orders?
2. What is the top-selling product?
3. Who are the most valuable customers?
4. Any recommendations to improve sales?"""

    result = await agent.analyze(question)

    print("\n--- Analysis Result ---")
    print(result if result else "(No output)")

    # 清理
    if agent.db_helper:
        agent.db_helper.close()


# ============================================================
# Main
# ============================================================

async def main():
    print("=" * 60)
    print("Database Agent - MCP 实战示例")
    print("=" * 60)

    # 概述
    print_mcp_database_overview()

    # 配置示例
    print_mcp_config_example()

    # 运行演示
    await demo_database_analysis()

    # 清理测试数据库
    try:
        Path("sample_data.db").unlink()
    except:
        pass

    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)
    print()
    print("Key Takeaways:")
    print("1. MCP 提供安全的数据库访问接口")
    print("2. Agent 可以执行 SQL 查询但无法直接操作文件")
    print("3. 支持多种数据库 (SQLite, PostgreSQL, MySQL)")
    print("4. 所有操作都经过 MCP 服务器，便于审计")


if __name__ == "__main__":
    asyncio.run(main())
