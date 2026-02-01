# Claude Agent SDK 知识库

> **SDK 版本**: claude-agent-sdk >= 0.1.25（本文档基于 0.1.27 编写）
>
> **文档定位说明**
>
> 本文档分为两部分内容：
> 1. **Claude Agent SDK 官方功能**：Anthropic 官方提供的 SDK 能力
> 2. **本项目实现**：基于 SDK 构建的透视化教学应用
>
> 两者的关系：本项目使用 Claude Agent SDK 作为底层，在其基础上实现了可视化界面和教学功能。SDK 的能力是基础，本项目是应用层的封装。

## 目录

1. [概述](#概述)
2. [核心架构](#核心架构)
3. [SDK API 详解](#sdk-api-详解)
4. [Hook 机制](#hook-机制)
5. [子 Agent 系统](#子-agent-系统)
6. [Skills 知识注入](#skills-知识注入)
7. [MCP 扩展](#mcp-扩展)
8. [运行配置](#运行配置)
9. [Extended Thinking](#extended-thinking)
10. [参考资源](#参考资源)

---

## 概述

### SDK 选型说明

Anthropic 提供两个层面的 SDK：

| SDK | 用途 | 特点 | Python 包 |
|-----|------|------|-----------|
| **Claude Agent SDK** | 构建 AI Agent | 内置工具、Hook、子 Agent | `claude-agent-sdk` |
| **Anthropic SDK** | 直接调用 Claude API | 底层 API，需自行实现工具 | `anthropic` |

**Claude Agent SDK 提供的核心能力**：
- 内置工具（Read, Write, Bash, Grep, Glob 等）
- Hook 机制（PreToolUse, PostToolUse）
- 子 Agent 定义（AgentDefinition）
- 会话管理（支持 resume）
- MCP 协议支持

**本项目在 SDK 基础上增加的功能**：
- Web 可视化界面（Playground）
- 工具调用过程的实时展示
- Hook 拦截的交互式演示
- 渐进式学习路径（v0-v7）

### 核心概念

以下是 **Claude Agent SDK 官方提供**的核心概念：

| 概念 | 说明 |
|------|------|
| **ClaudeSDKClient** | SDK 客户端，管理与 Claude 的交互 |
| **ClaudeAgentOptions** | 配置选项：工具、提示词、权限等 |
| **AgentDefinition** | 子 Agent 定义：描述、工具、提示词 |
| **HookMatcher** | Hook 匹配器：拦截特定工具调用 |
| **Session** | 会话管理：支持多轮对话和恢复 |

---

## 核心架构

```
┌─────────────────────────────────────────────────────────────┐
│                     用户代码                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              ClaudeSDKClient                             │   │
│  │  ┌───────────────┐  ┌───────────────┐               │   │
│  │  │ query()       │  │ receive()     │               │   │
│  │  └───────────────┘  └───────────────┘               │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                     SDK 内部                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Hook 系统   │  │ 工具调度器   │  │ 子 Agent 管理器     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                     内置工具层                               │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐ │
│  │ Read   │ │ Write  │ │ Bash   │ │ Grep   │ │ Task     │ │
│  │ Edit   │ │ Glob   │ │ LS     │ │WebFetch│ │ Skill    │ │
│  └────────┘ └────────┘ └────────┘ └────────┘ └──────────┘ │
├─────────────────────────────────────────────────────────────┤
│                     Claude API                              │
└─────────────────────────────────────────────────────────────┘
```

### 数据流

```
用户代码
    │
    ▼
client.query(prompt)     ←── 发送用户消息
    │
    ▼
SDK 内部处理
    │
    ├─ PreToolUse Hook   ←── 可拦截/修改工具调用
    │
    ├─ 执行工具
    │
    ├─ PostToolUse Hook  ←── 可记录/审计工具结果
    │
    ▼
client.receive_response()  ←── 流式接收响应
    │
    ▼
消息类型判断
    ├─ assistant  → 文本响应
    ├─ tool_use   → 工具调用信息
    ├─ tool_result → 工具执行结果
    └─ result     → 最终结果
```

---

## SDK API 详解

### 依赖安装

```bash
pip install claude-agent-sdk
```

### 基础用法

```python
import asyncio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

async def main():
    options = ClaudeAgentOptions(
        model="sonnet",
        allowed_tools=["Read", "Write", "Bash"],
        permission_mode="bypassPermissions"
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt="列出当前目录的文件")

        async for msg in client.receive_response():
            if msg.type == 'assistant':
                # 处理文本响应
                content = msg.message.content
                if isinstance(content, list):
                    for block in content:
                        if block.type == 'text':
                            print(block.text)
            elif msg.type == 'result':
                # 对话结束
                if msg.subtype == 'success':
                    print(f"完成，耗费: ${msg.total_cost_usd:.4f}")

asyncio.run(main())
```

### ClaudeAgentOptions 配置

```python
options = ClaudeAgentOptions(
    # 模型选择
    model="sonnet",  # sonnet | opus | haiku

    # 工具权限
    allowed_tools=["Read", "Write", "Bash", "Grep", "Glob"],

    # 权限模式
    permission_mode="bypassPermissions",  # 跳过权限确认

    # 系统提示词
    system_prompt="你是一个专业的编程助手...",

    # 配置来源
    setting_sources=["project", "local"],  # 加载 .claude 目录配置

    # 子 Agent 定义
    agents={...},

    # Hook 配置
    hooks={...},

    # MCP 服务器
    mcp_servers={...}
)
```

### 消息类型处理

```python
async for msg in client.receive_response():
    match msg.type:
        case 'assistant':
            # Claude 的响应（文本或工具调用）
            handle_assistant_message(msg)

        case 'user':
            # 用户消息回显
            pass

        case 'system':
            # 系统消息
            if msg.subtype == 'init':
                session_id = msg.session_id  # 保存用于 resume

        case 'result':
            # 对话结束
            if msg.subtype == 'success':
                print(f"结果: {msg.result}")
                print(f"耗时: {msg.duration_ms}ms")
                print(f"费用: ${msg.total_cost_usd}")
```

### 多轮对话

```python
async with ClaudeSDKClient(options=options) as client:
    # 第一轮
    await client.query(prompt="创建一个 hello.py 文件")
    async for msg in client.receive_response():
        handle_message(msg)

    # 第二轮（自动保持上下文）
    await client.query(prompt="在文件中添加一个函数")
    async for msg in client.receive_response():
        handle_message(msg)
```

### 会话恢复 (Resume)

```python
# 第一次会话
session_id = None
async with ClaudeSDKClient(options=options) as client:
    await client.query(prompt="记住：我喜欢蓝色")
    async for msg in client.receive_response():
        if msg.type == 'system' and msg.subtype == 'init':
            session_id = msg.session_id
        handle_message(msg)

# 稍后恢复会话
resume_options = ClaudeAgentOptions(
    model="sonnet",
    resume=session_id  # 传入之前的 session_id
)

async with ClaudeSDKClient(options=resume_options) as client:
    await client.query(prompt="我喜欢什么颜色？")
    async for msg in client.receive_response():
        handle_message(msg)  # Claude 会记得是蓝色
```

---

## Hook 机制

Hook 是 **Claude Agent SDK 官方提供**的核心特性之一，用于拦截和审计工具调用。

### Hook 类型

| Hook | 触发时机 | 用途 |
|------|----------|------|
| `PreToolUse` | 工具执行**前** | 拦截、修改、审批 |
| `PostToolUse` | 工具执行**后** | 记录、审计、通知 |

### 基础用法

> **注意**：Hook 返回值使用 `continue_`（带下划线），因为 `continue` 是 Python 保留关键字。

```python
from claude_agent_sdk import HookMatcher

# PreToolUse Hook 函数
async def my_pre_hook(hook_input: dict, tool_use_id: str, context) -> dict:
    tool_name = hook_input.get('tool_name')
    tool_input = hook_input.get('tool_input')

    print(f"[PreHook] 即将调用: {tool_name}")
    print(f"[PreHook] 参数: {tool_input}")

    # 放行
    return {'continue_': True}

    # 或者拦截
    # return {'continue_': False}

# PostToolUse Hook 函数
async def my_post_hook(hook_input: dict, tool_use_id: str, context) -> dict:
    tool_name = hook_input.get('tool_name')
    tool_result = hook_input.get('tool_result')

    print(f"[PostHook] 完成调用: {tool_name}")
    print(f"[PostHook] 结果: {tool_result[:100]}...")

    return {'continue_': True}

# 配置 Hook
hooks = {
    'PreToolUse': [
        HookMatcher(
            matcher="Write|Edit",  # 正则匹配工具名
            hooks=[my_pre_hook]
        )
    ],
    'PostToolUse': [
        HookMatcher(
            matcher=None,  # None 表示匹配所有工具
            hooks=[my_post_hook]
        )
    ]
}

options = ClaudeAgentOptions(
    model="sonnet",
    allowed_tools=["Read", "Write", "Bash"],
    hooks=hooks
)
```

### 实用 Hook 示例

**1. 路径安全检查**

```python
async def path_security_hook(hook_input: dict, tool_use_id: str, context) -> dict:
    tool_name = hook_input.get('tool_name')
    tool_input = hook_input.get('tool_input', {})

    # 检查文件路径
    file_path = tool_input.get('file_path', '')

    # 禁止访问系统目录
    forbidden_paths = ['/etc', '/usr', 'C:\\Windows']
    for forbidden in forbidden_paths:
        if file_path.startswith(forbidden):
            print(f"[BLOCKED] 禁止访问系统目录: {forbidden}")
            return {'continue_': False}

    return {'continue_': True}
```

**2. 操作审计日志**

```python
import json
from datetime import datetime

async def audit_hook(hook_input: dict, tool_use_id: str, context) -> dict:
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "tool": hook_input.get('tool_name'),
        "input": hook_input.get('tool_input')
    }

    with open("audit.jsonl", "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    return {'continue_': True}
```

**3. 危险命令拦截**

```python
DANGEROUS_COMMANDS = ['rm -rf', 'format', 'del /f', 'shutdown']

async def bash_security_hook(hook_input: dict, tool_use_id: str, context) -> dict:
    if hook_input.get('tool_name') != 'Bash':
        return {'continue_': True}

    command = hook_input.get('tool_input', {}).get('command', '')

    for dangerous in DANGEROUS_COMMANDS:
        if dangerous in command.lower():
            print(f"[BLOCKED] 检测到危险命令: {dangerous}")
            return {'continue_': False}

    return {'continue_': True}
```

---

## 子 Agent 系统

子 Agent 是 **Claude Agent SDK 官方提供**的功能，允许将复杂任务分解给专职 Agent 处理。

### AgentDefinition

```python
from claude_agent_sdk import AgentDefinition

agents = {
    "researcher": AgentDefinition(
        description="研究员，负责信息搜集和分析。使用 WebSearch 和 Read 工具。",
        tools=["WebSearch", "Read", "Write"],
        prompt="你是一个专业的研究员，擅长收集和整理信息...",
        model="haiku"  # 可以使用更便宜的模型
    ),

    "writer": AgentDefinition(
        description="写作者，负责生成报告和文档。",
        tools=["Write", "Read", "Glob"],
        prompt="你是一个技术写作专家，擅长将复杂信息整理成清晰的文档...",
        model="sonnet"
    ),

    "reviewer": AgentDefinition(
        description="代码审查员，负责代码质量检查。",
        tools=["Read", "Grep", "Glob"],
        prompt="你是一个资深代码审查员，关注安全性、性能和可维护性...",
        model="sonnet"
    )
}

options = ClaudeAgentOptions(
    model="sonnet",
    allowed_tools=["Task"],  # 主 Agent 只能调度子 Agent
    agents=agents,
    system_prompt="你是一个项目经理，负责协调 researcher、writer、reviewer 完成任务..."
)
```

### 子 Agent 工作流程

```
主 Agent (project-manager)
    │
    ├─ Task(agent="researcher", prompt="调研 React 18 新特性")
    │       │
    │       └─ researcher 使用 WebSearch, Read 收集信息
    │              │
    │              └─ 返回研究结果
    │
    ├─ Task(agent="writer", prompt="基于研究结果写技术报告")
    │       │
    │       └─ writer 使用 Write 生成报告
    │              │
    │              └─ 返回报告路径
    │
    └─ Task(agent="reviewer", prompt="审查生成的报告")
            │
            └─ reviewer 使用 Read 审查报告
                   │
                   └─ 返回审查意见
```

---

## Skills 知识注入

Skills 是 **Claude Agent SDK 官方提供**的机制，允许向 Agent 注入领域专业知识，无需重新训练模型。

### SKILL.md 格式

```markdown
---
name: code-reviewer
description: 代码审查专家，关注安全、性能和可维护性
allowed-tools: Read, Grep, Glob
---

# 代码审查技能

## 审查要点

### 安全性
- 检查 SQL 注入风险
- 检查 XSS 漏洞
- 检查敏感信息泄露

### 性能
- 检查 N+1 查询问题
- 检查不必要的循环
- 检查大对象内存占用

### 可维护性
- 检查函数复杂度
- 检查命名规范
- 检查注释完整性

## 输出格式

请按以下格式输出审查结果：

```
## 审查摘要
- 总体评分: X/10
- 发现问题: X 个

## 详细问题
1. [严重程度] 文件:行号 - 问题描述
   建议: 修复建议
```
```

### 目录结构

```
.claude/
└── skills/
    ├── code-reviewer/
    │   ├── SKILL.md           # 技能定义
    │   └── templates/         # 可选：模板文件
    │       └── review-report.md
    │
    └── doc-generator/
        ├── SKILL.md
        └── references/        # 可选：参考资料
            └── api-spec.md
```

### 使用 Skill

```python
options = ClaudeAgentOptions(
    model="sonnet",
    allowed_tools=["Read", "Grep", "Glob", "Skill"],
    setting_sources=["project"],  # 加载 .claude 目录
)

# Agent 可以通过 Skill 工具加载技能
# Skill(name="code-reviewer") -> 注入 SKILL.md 内容
```

---

## MCP 扩展

Model Context Protocol (MCP) 允许 Agent 连接外部服务和工具。这是 **Claude Agent SDK 官方支持**的扩展机制。

### 配置 MCP 服务器

```python
options = ClaudeAgentOptions(
    model="sonnet",
    allowed_tools=["Read", "Write", "mcp__myserver__my_tool"],
    mcp_servers={
        "myserver": {
            "command": "python",
            "args": ["my_mcp_server.py"],
            "env": {"API_KEY": "xxx"}
        }
    }
)
```

### MCP 工具命名规范

MCP 工具命名格式：`mcp__{server_name}__{tool_name}`

例如：
- `mcp__email__search_inbox`
- `mcp__database__query`
- `mcp__github__create_issue`

### 官方 MCP 服务器

Anthropic 和社区提供了一些常用的 MCP 服务器：

| 服务器 | 功能 | 来源 |
|--------|------|------|
| Filesystem | 文件系统访问 | 官方 |
| GitHub | GitHub 操作 | 官方 |
| Slack | Slack 集成 | 官方 |
| PostgreSQL | 数据库查询 | 官方 |
| Playwright | 浏览器自动化 | 社区 |

> **本项目说明**：本项目的演示环境中未预置 MCP 服务器，如需体验 MCP 功能，请参考官方文档自行配置。

---

## 运行配置

### 环境变量

```bash
# Windows PowerShell
$env:ANTHROPIC_API_KEY = "your-api-key"

# Linux/macOS
export ANTHROPIC_API_KEY="your-api-key"
```

### 可用模型

| 模型标识 | 完整 ID | 说明 |
|----------|---------|------|
| `opus` | `claude-opus-4-5-20251101` | 最强大，适合复杂任务 |
| `sonnet` | `claude-sonnet-4-20250514` | 平衡性能和成本 |
| `haiku` | `claude-haiku-3-5-20241022` | 快速响应，成本最低 |

### 内置工具列表

以下是 **Claude Agent SDK 官方提供**的内置工具：

| 工具 | 功能 | 说明 |
|------|------|------|
| `Read` | 读取文件内容 | 支持文本、图片、PDF、Jupyter Notebook |
| `Write` | 写入文件内容 | 创建或覆盖文件 |
| `Edit` | 精确编辑文件 | 基于字符串替换的编辑 |
| `Bash` | 执行 shell 命令 | 支持超时和后台运行 |
| `Glob` | 文件模式匹配 | 快速查找文件 |
| `Grep` | 内容搜索 | 基于 ripgrep 的正则搜索 |
| `WebFetch` | 获取网页内容 | 抓取并处理网页 |
| `WebSearch` | 网络搜索 | 搜索互联网信息 |
| `Task` | 调度子 Agent | 启动专门的子 Agent |
| `Skill` | 加载技能 | 注入领域知识 |
| `TodoWrite` | 任务列表管理 | 跟踪任务进度 |
| `NotebookEdit` | Jupyter Notebook 编辑 | 编辑 .ipynb 文件单元格 |
| `KillShell` | 终止 Shell 进程 | 停止后台运行的命令 |
| `AskUserQuestion` | 向用户提问 | 交互式获取用户输入 |

> **注意**：本项目的 Playground 演示中，出于安全考虑，默认只启用部分工具。

---

## Extended Thinking

### 概述

Extended Thinking（扩展思考）是 Claude 4 系列模型的高级功能，允许模型在回答前进行更深入的推理。

### SDK 支持情况

**重要**：Claude Agent SDK 目前**不直接暴露** thinking 内容。如需获取完整的思考过程，需要直接调用 Anthropic API。

SDK 内部可能使用了 extended thinking 来提升推理质量，但这对开发者是透明的。

### 使用 Anthropic API 实现

如果你的应用需要展示思考过程，可以直接使用 Anthropic SDK：

```python
from anthropic import Anthropic

client = Anthropic()

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=16000,
    thinking={
        "type": "enabled",
        "budget_tokens": 10000  # 思考过程的 token 预算
    },
    messages=[{"role": "user", "content": "复杂问题..."}]
)

# 解析响应
for block in response.content:
    if block.type == "thinking":
        print("思考过程:", block.thinking)
    elif block.type == "text":
        print("最终回答:", block.text)
```

### 适用场景

- 复杂推理问题
- 数学证明和逻辑推导
- 多步骤规划
- 需要展示推理过程的教学场景

### 本项目的处理

本项目的 `examples/extended_thinking.py` 演示了如何直接调用 Anthropic API 获取思考过程，这是对 SDK 能力的补充。

---

## 参考资源

### 官方文档

- [Claude Agent SDK 文档](https://docs.anthropic.com/en/docs/claude-agent-sdk)
- [claude-agent-sdk (PyPI)](https://pypi.org/project/claude-agent-sdk/)
- [MCP 协议规范](https://spec.modelcontextprotocol.io)
- [Anthropic API 文档](https://docs.anthropic.com/)

### 本项目资源

本项目的学习路径：

| 阶段 | 主题 | 说明 |
|------|------|------|
| v0 | 最简调用 | SDK 基础用法 |
| v1 | 工具权限 | 权限控制机制 |
| v2 | 流式输出 | 实时响应处理 |
| v3 | Hook 机制 | 拦截与审计 |
| v4 | Agent 封装 | 可复用组件 |
| v5 | 多 Agent 协作 | 任务分解与协调 |
| v6 | Skills 注入 | 领域知识增强 |
| v7 | MCP 扩展 | 外部服务集成 |

### 参考代码

| 文件 | 内容 |
|------|------|
| `email-agent/ccsdk/ai-client.ts` | AIClient 封装示例 |
| `email-agent/ccsdk/session.ts` | 会话管理示例 |
| `research-agent/research_agent/agent.py` | Python Agent 完整示例 |
| `hello-world-v2/v2-examples.ts` | V2 API 各种用法 |
