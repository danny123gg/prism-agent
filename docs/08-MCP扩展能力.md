# 08 - MCP 扩展能力

> 配套代码：`src/v7_mcp.py`
>
> **目标**：理解 MCP 协议，学会连接外部服务扩展 Agent 能力

---

## 边界的扩展

到目前为止，我们的 Agent 能做的事情是有限的：

- 读写本地文件
- 执行命令
- 搜索代码

这些是 SDK 内置的工具。但如果你想让 Agent 做更多——查询数据库、发送邮件、调用第三方 API——内置工具就不够用了。

MCP（Model Context Protocol）解决的就是这个问题。

它是一个扩展协议，让 Agent 可以连接到任何外部服务。只要有对应的 MCP Server，Agent 就能获得新的能力。

**从封闭到开放，从有限到无限。**

---

## MCP 是什么

```
┌─────────────────┐      ┌─────────────────┐
│  Claude Agent   │ MCP  │   MCP Server    │
│                 │<---->│  (database,     │
│                 │      │   email, etc.)  │
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
```

MCP Server 是一个独立的进程，它实现了特定的功能（比如查询数据库），并通过 MCP 协议暴露给 Agent。

Agent 可以像使用内置工具一样使用 MCP 提供的工具。

---

## 配置 MCP

```python
options = ClaudeAgentOptions(
    model="sonnet",
    allowed_tools=[
        "Read",                      # 内置工具
        "mcp__database__query",      # MCP 工具
        "mcp__database__insert",     # MCP 工具
    ],
    mcp_servers={
        "database": {
            "command": "python",
            "args": ["-m", "mcp_database_server"],
            "env": {
                "DB_HOST": "localhost",
                "DB_NAME": "mydb",
            }
        }
    }
)
```

### 配置项说明

| 项目 | 说明 |
|------|------|
| `command` | 启动 MCP Server 的命令 |
| `args` | 命令参数 |
| `env` | 环境变量（用于传递配置和凭证） |

### 工具命名

MCP 工具的命名格式：

```
mcp__{server_name}__{tool_name}
```

例如：
- `mcp__database__query` — database server 的 query 工具
- `mcp__email__send` — email server 的 send 工具
- `mcp__github__create_issue` — github server 的 create_issue 工具

---

## 常见 MCP Server

### 数据库

```python
"database": {
    "command": "python",
    "args": ["-m", "mcp_database_server"],
    "env": {
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "myapp",
        "DB_USER": "agent",
        "DB_PASS": os.environ.get("DB_PASS"),
    }
}
```

### 邮件

```python
"email": {
    "command": "node",
    "args": ["email-mcp-server.js"],
    "env": {
        "SMTP_HOST": "smtp.gmail.com",
        "EMAIL_USER": os.environ.get("EMAIL_USER"),
        "EMAIL_PASS": os.environ.get("EMAIL_PASS"),
    }
}
```

### GitHub（官方）

```python
"github": {
    "command": "npx",
    "args": ["-y", "@anthropic/mcp-github"],
    "env": {
        "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN"),
    }
}
```

### 文件系统（官方）

```python
"filesystem": {
    "command": "npx",
    "args": ["-y", "@anthropic/mcp-filesystem", "/allowed/path"],
}
```

---

## 安全考虑

MCP 扩展了 Agent 的能力，但也扩展了风险面。

### 凭证管理

```python
# 好：从环境变量读取
"env": {
    "API_KEY": os.environ.get("API_KEY"),
}

# 差：硬编码
"env": {
    "API_KEY": "sk-xxx",  # 危险！
}
```

### 最小权限

```python
# 只允许需要的 MCP 工具
allowed_tools=[
    "mcp__database__query",   # 只读查询
    # "mcp__database__delete", # 不允许删除
]
```

### 路径限制

```python
# 限制文件系统访问范围
"filesystem": {
    "args": ["-y", "@anthropic/mcp-filesystem", "/safe/path/only"],
}
```

---

## 运行示例

```bash
python src/v7_mcp.py
```

由于 MCP 需要实际运行的外部服务器，v7 主要是概念演示，展示配置方法和用例。

---

## MCP vs 内置工具

| 方面 | 内置工具 | MCP 工具 |
|------|----------|----------|
| 运行位置 | SDK 内部 | 独立进程 |
| 扩展性 | 固定 | 可自定义 |
| 外部服务 | 不支持 | 支持 |
| 凭证管理 | 无 | 通过 env 配置 |
| 适用场景 | 文件操作 | 任意服务集成 |

简单来说：内置工具处理本地操作，MCP 处理外部集成。

---

## 一些问题

**Q: MCP Server 从哪里获取？**

三个来源：
1. **官方服务器** — `@anthropic/mcp-*` 系列（npm）
2. **社区服务器** — npm/PyPI 上的第三方包
3. **自定义开发** — 按 MCP 规范编写

**Q: MCP Server 需要一直运行吗？**

不需要。SDK 会在需要时自动启动 MCP Server，使用完毕后可以关闭。

**Q: MCP 工具调用失败怎么办？**

Agent 会收到错误信息，可能会重试、使用替代方法、或报告给用户。

---

## 小结

MCP 是 Agent 能力的扩展机制。

通过 MCP，你可以：

- 连接数据库
- 发送邮件
- 调用第三方 API
- 集成任何外部服务

这意味着 Agent 的能力边界，理论上是无限的。

---

## 旅程的终点

恭喜！你已经完成了 Claude Agent SDK 的全部核心教学内容。

回顾一下我们走过的路：

| 阶段 | 版本 | 学到了什么 |
|------|------|-----------|
| **基础** | v0-v2 | 让 Agent 跑起来，理解权限和消息流 |
| **工程** | v3-v5 | Hook 机制、Agent 封装、多 Agent 协作 |
| **扩展** | v6-v7 | Skills 知识注入、MCP 外部服务 |

现在你掌握了：

- SDK 的基本用法
- 权限控制原则
- 流式消息处理
- Hook 机制
- Agent 封装模式
- 多 Agent 协作
- Skills 领域知识
- MCP 能力扩展

这些是构建 Agent 应用的核心技能。

---

## 接下来呢？

学习只是开始。

真正的理解来自实践。尝试用你学到的东西构建一些小项目：

- 一个代码审查助手
- 一个文档生成器
- 一个简单的任务自动化工具

在实践中，你会遇到各种问题。解决这些问题的过程，就是深度学习的过程。

`examples/` 目录下有一些实战案例，可以作为参考。

---

## 资源

- [MCP 规范](https://spec.modelcontextprotocol.io)
- [Claude Agent SDK 文档](https://docs.anthropic.com/en/docs/claude-code/sdk)
- [官方 MCP Server](https://github.com/anthropics)

---

感谢你读到这里。

希望这个项目对你有所帮助。

学习的路上，我们都是同行者。
