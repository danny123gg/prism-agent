# 01 - 从这里开始

> 配套代码：`src/v0_hello.py`
>
> **目标**：让 Agent 跑起来，看到它的回复，建立第一个确定感

---

## 什么是 Claude Agent SDK？

> **SDK 版本**: claude-agent-sdk 0.1.27

在开始写代码之前，我们先聊聊 SDK 是什么。

Anthropic 提供了两种方式和 Claude 交互：

**原始 API** — 你需要自己管理对话历史、处理工具调用、编排多轮交互。灵活，但繁琐。

**Claude Agent SDK** — 在 API 之上做了一层封装。它帮你处理了 Agent Loop、内置了常用工具、提供了权限控制和 Hook 机制。你可以专注于"让 Agent 做什么"，而不是"怎么让 Agent 跑起来"。

简单说：**SDK 让你用更少的代码，做更复杂的事情**。

如果你只是想做一个简单的问答机器人，用 API 就够了。但如果你想让 AI 读文件、写代码、执行命令——也就是真正的"Agent"——SDK 会帮你省很多事。

---

## 核心概念

在开始写代码之前，有几个概念需要理解。不需要记住所有细节，先有个印象就好。

### ClaudeSDKClient

这是 SDK 的主入口。你通过它发送请求、接收响应。

```python
async with ClaudeSDKClient(options=options) as client:
    await client.query(prompt="你好")
    async for msg in client.receive_response():
        # 处理响应
        pass
```

### ClaudeAgentOptions

这是配置类。你用它告诉 SDK：用什么模型、允许什么工具、采用什么权限模式。

```python
options = ClaudeAgentOptions(
    model="sonnet",                      # 使用的模型
    permission_mode="bypassPermissions", # 权限模式（后面会详细讲）
    allowed_tools=["Read", "Write"],     # 允许使用的工具
)
```

### 消息类型

SDK 返回的是一个消息流。你会收到几种不同类型的消息：

- **AssistantMessage** — Claude 的回复，包含文本或工具调用
- **ResultMessage** — 会话结束，包含费用等信息
- **SystemMessage** — 系统消息

每个 `AssistantMessage` 的内容是一个"块"列表。块有两种：

- **TextBlock** — 文本，通过 `block.text` 获取
- **ToolUseBlock** — 工具调用，包含 `name`（工具名）、`input`（参数）、`id`

---

## API 支持与限制

在使用 Claude Agent SDK 之前，你需要了解它支持哪些 API 提供商。

### 支持的 API

| 提供商 | 支持状态 | 配置方式 |
|--------|----------|----------|
| Anthropic API | ✅ 原生支持 | 默认，设置 `ANTHROPIC_API_KEY` |
| API 代理 | ✅ 支持 | 设置 `ANTHROPIC_BASE_URL` |
| AWS Bedrock | ❌ 不直接支持 | — |
| Google Vertex AI | ❌ 不直接支持 | — |
| OpenAI | ❌ 不支持 | — |
| Gemini | ❌ 不支持 | — |
| 通义千问等 | ❌ 不支持 | — |

### 为什么只支持 Claude？

Claude Agent SDK 是专门为 Claude 模型设计的 Agent 框架，它依赖于：

1. **Anthropic 特定的 API 格式** — 请求/响应结构与 OpenAI、Gemini 完全不同
2. **Claude 特有的功能** — 如工具调用格式（`tool_use` block）、扩展思考模式（extended thinking）
3. **SDK 的底层实现** — 整个 Agent 逻辑是围绕 Claude 能力构建的

不同模型的 API 格式差异示例：

```
# Anthropic: 工具调用返回 tool_use block
# OpenAI: 工具调用返回 function_call
# Gemini: 工具调用返回 function_declarations
```

### 使用 API 代理

如果你需要通过代理访问 Claude API，可以设置 `ANTHROPIC_BASE_URL`：

```bash
# .env 文件
ANTHROPIC_API_KEY=your-api-key
ANTHROPIC_BASE_URL=https://your-proxy.com
```

代理服务需要兼容 Anthropic API 格式。这种方式可以用于：
- 企业内网代理
- 区域访问限制绕过
- 自建的 API 网关

### 如果需要其他模型

如果你的场景需要使用 OpenAI、Gemini 或其他模型，Claude Agent SDK 不是合适的选择。你可以考虑：

- **LangChain** — 支持多种模型的通用框架
- **OpenAI Assistants API** — OpenAI 的 Agent 方案
- **AutoGen** — 微软的多 Agent 框架

选择 Claude Agent SDK 意味着选择 Claude 生态。这是一个权衡：你获得了与 Claude 深度集成的能力，但放弃了模型切换的灵活性。

---

## v0 代码详解

让我们看看最简单的示例代码。

```python
#!/usr/bin/env python3
"""
v0: Hello Claude - 最简示例
"""

import asyncio
from dotenv import load_dotenv
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

# 加载环境变量
load_dotenv()

async def main():
    # 最简配置
    options = ClaudeAgentOptions(
        model="sonnet",
        permission_mode="bypassPermissions"
    )

    # 运行查询
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt="Hello! Please introduce yourself in one sentence.")

        async for msg in client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == 'AssistantMessage':
                for block in msg.content:
                    if type(block).__name__ == 'TextBlock':
                        print(f"Claude: {block.text}")

            elif msg_type == 'ResultMessage':
                if hasattr(msg, 'total_cost_usd') and msg.total_cost_usd:
                    print(f"\n[Cost: ${msg.total_cost_usd:.4f}]")

if __name__ == "__main__":
    asyncio.run(main())
```

代码不长，但每一行都有它的意义。让我逐个解释：

### 环境准备

```python
from dotenv import load_dotenv
load_dotenv()
```

从 `.env` 文件加载环境变量，主要是 `ANTHROPIC_API_KEY`。

### 配置

```python
options = ClaudeAgentOptions(
    model="sonnet",
    permission_mode="bypassPermissions"
)
```

- `model="sonnet"` — 使用 Claude Sonnet 模型
- `permission_mode="bypassPermissions"` — 跳过权限确认。这只是为了学习方便，生产环境不要这样用

### 创建客户端并查询

```python
async with ClaudeSDKClient(options=options) as client:
    await client.query(prompt="...")
```

使用异步上下文管理器（`async with`）确保连接正确关闭。

### 处理响应

```python
async for msg in client.receive_response():
    msg_type = type(msg).__name__
```

**注意**：我们用 `type(msg).__name__` 来判断消息类型。这是 SDK 的设计，消息对象是 Python 类实例，类型信息在类名中。

### 提取文本

```python
for block in msg.content:
    if type(block).__name__ == 'TextBlock':
        print(f"Claude: {block.text}")
```

遍历内容块，找到 TextBlock，打印它的文本。

---

## 运行

确保你已经：
1. 安装了依赖：`pip install -r requirements.txt`
2. 配置了 `.env` 文件
3. 验证了环境：`python scripts/verify_setup.py`

然后运行：

```bash
python src/v0_hello.py
```

你应该会看到类似这样的输出：

```
Claude: Hello! I'm Claude, an AI assistant made by Anthropic...

[Cost: $0.0855]
```

如果你看到了 Claude 的回复，恭喜——你的第一个 Agent 跑起来了。

这个"跑起来"的感觉很重要。它是你后续学习的锚点。

---

## 一些问题

**Q: 为什么用 `type(msg).__name__` 而不是 `msg.type`？**

SDK 的消息对象是 Python 类实例，类型信息在类名中，不是属性。这是 SDK 的设计选择。

**Q: `bypassPermissions` 安全吗？**

不安全。仅在学习和开发时使用。生产环境应该使用更严格的权限模式，后面会详细讲。

**Q: 费用怎么算的？**

`total_cost_usd` 是整个会话的 API 调用费用，根据 token 用量计算。

---

## 小结

这一节我们做了一件简单的事：让 Agent 跑起来。

代码很简单，概念也不多。但这个简单很重要——它给了你一个确定感：SDK 的基本用法，我懂了。

有了这个确定感，我们才能往下走。

---

## 下一步

在 [02-工具权限设计](./02-工具权限设计.md) 中，我们会讨论一个重要的问题：如何控制 Agent 能做什么、不能做什么。
