# 06 - 多 Agent 协作

> 配套代码：`src/v5_multi_agent.py`
>
> **目标**：掌握多 Agent 系统的设计模式，让不同 Agent 各司其职

---

## 为什么需要多 Agent？

单个 Agent 什么都能做，但这不一定是好事。

想象一个什么都会的员工：你让他写代码，他可以；让他审查代码，他也可以；让他写文档，他还是可以。听起来很方便？

问题在于：一个"万能"的人，往往每件事都做得不够专业。而且你不知道他在用什么标准做决策——写代码时会不会偷懒？审查时会不会放水？

多 Agent 的思路是：**让专业的 Agent 做专业的事**。

- 一个 Agent 专门做研究，只能读文件，不能修改
- 一个 Agent 专门写代码，只能写指定目录
- 一个 Agent 专门做审查，只能读不能写

职责清晰，权限最小，各司其职。

---

## 核心概念

### AgentDefinition

定义一个子 Agent 的能力和行为：

```python
from claude_agent_sdk import AgentDefinition

researcher = AgentDefinition(
    description="Use this agent when you need to search or read files.",
    tools=["Read", "Glob", "Grep"],
    prompt="You are a research assistant. Gather information thoroughly.",
    model="haiku"  # 用快速便宜的模型
)
```

| 属性 | 说明 |
|------|------|
| `description` | 告诉主 Agent 什么时候应该使用这个子 Agent |
| `tools` | 子 Agent 可用的工具 |
| `prompt` | 子 Agent 的系统提示 |
| `model` | 子 Agent 使用的模型 |

### Task 工具

主 Agent 通过 `Task` 工具调度子 Agent：

```python
options = ClaudeAgentOptions(
    model="sonnet",               # 主 Agent 用强模型
    allowed_tools=["Task"],       # 主 Agent 只能调度
    agents={
        "researcher": researcher,
        "writer": writer,
    },
)
```

主 Agent 会看到可用的子 Agent 列表，并决定什么时候调用哪一个。

---

## 协调者模式

最常见的多 Agent 模式是**协调者模式**：

```
┌─────────────────────────────────────────────────────────┐
│                   Orchestrator (协调者)                  │
│                  Model: sonnet (强模型)                  │
│                  Tools: [Task] (只能调度)                │
└─────────────────────────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ Researcher│    │  Writer  │    │ Analyzer │
    │   haiku   │    │  haiku   │    │  haiku   │
    │ Read,Glob │    │  Write   │    │ Read,Grep│
    └──────────┘    └──────────┘    └──────────┘
```

协调者负责：
- 理解用户意图
- 拆解任务
- 调度合适的子 Agent
- 汇总结果

子 Agent 负责：
- 执行具体任务
- 返回结果

这种分工让系统更可控：协调者负责"想"，子 Agent 负责"做"。

---

## 定义子 Agent

```python
def create_researcher_agent() -> AgentDefinition:
    return AgentDefinition(
        description="Use when you need to search or read files.",
        tools=["Read", "Glob", "Grep"],
        prompt="You are a research assistant. Gather information thoroughly and summarize clearly.",
        model="haiku"
    )

def create_writer_agent() -> AgentDefinition:
    return AgentDefinition(
        description="Use when you need to create or modify files.",
        tools=["Write", "Read"],
        prompt="You are a technical writer. Create clear, well-structured content.",
        model="haiku"
    )

def create_analyzer_agent() -> AgentDefinition:
    return AgentDefinition(
        description="Use for code analysis and review.",
        tools=["Read", "Glob", "Grep"],
        prompt="You are a code analyst. Identify issues and suggest improvements.",
        model="haiku"
    )
```

注意：每个子 Agent 都只有它需要的工具。Researcher 只能读，Writer 可以写但不能执行命令。

---

## 配置协调者

```python
options = ClaudeAgentOptions(
    model="sonnet",
    permission_mode="bypassPermissions",
    allowed_tools=["Task"],  # 协调者只能调度
    agents={
        "researcher": create_researcher_agent(),
        "writer": create_writer_agent(),
        "analyzer": create_analyzer_agent(),
    },
    system_prompt="""
You are a project coordinator. Delegate tasks to specialized agents:
- 'researcher': For reading files and gathering information
- 'writer': For creating and modifying files
- 'analyzer': For code analysis and review

Always delegate work to the appropriate sub-agent.
Do NOT try to do tasks directly - use the sub-agents.
""",
)
```

关键点：协调者的 `allowed_tools` 只有 `["Task"]`。它自己不能读文件、不能写代码，只能调度子 Agent。

---

## 运行示例

```bash
python src/v5_multi_agent.py
```

```
============================================================
Demo: Multi-Agent Coordination
============================================================

Prompt: First use researcher to read v0_hello.py, then use analyzer to review it

  [12:00:10] MAIN → Spawning sub-agent: researcher
  [12:00:20] MAIN → Spawning sub-agent: analyzer

## Research Findings
The file v0_hello.py contains a minimal SDK example...

## Analysis Results
Code quality is good. Suggested improvements:
1. Add error handling for API failures
2. Consider adding type hints
...

--- Tracking Summary ---
Sub-agents spawned: 2
Total cost: $0.1700
```

你可以看到：

1. 协调者收到任务后，先调用 researcher
2. researcher 完成后，协调者调用 analyzer
3. 协调者汇总两个子 Agent 的结果

---

## 一个有趣的发现

设计多 Agent 系统时，你会发现自己在做的事情，和**管理一个团队**很像。

你要想清楚：
- 每个 Agent 的职责是什么？
- 它需要什么权限？
- 它和其他 Agent 怎么配合？
- 出了问题谁负责？

这不是纯技术问题，这是**组织问题**。

而且你会发现，"小而专"的 Agent 往往比"大而全"的 Agent 好用。一个什么都能做的 Agent，反而什么都做不好——它的上下文太分散，不知道在具体场景下应该优先考虑什么。

这和人的团队是一样的道理。

---

## 成本优化

多 Agent 系统天然支持成本优化：

| Agent 类型 | 推荐模型 | 说明 |
|------------|----------|------|
| 协调者 | sonnet | 需要高级推理 |
| 子 Agent | haiku | 执行具体任务，快速便宜 |

主 Agent 用贵的模型做决策，子 Agent 用便宜的模型执行。这样既保证质量，又控制成本。

---

## 一些问题

**Q: 子 Agent 之间可以直接通信吗？**

不能。子 Agent 之间通过协调者传递信息。协调者收到一个子 Agent 的结果后，可以将其传递给另一个。

**Q: 子 Agent 可以再启动子 Agent 吗？**

技术上可以，但不推荐。建议保持扁平结构（一层子 Agent），简化调试。

**Q: 如何处理子 Agent 失败？**

协调者会收到失败信息，可以决定重试、换一个子 Agent、或报告给用户。

---

## 小结

多 Agent 系统的核心思想是：**让专业的 Agent 做专业的事**。

通过职责分离和最小权限，你可以构建更可控、更安全、更高效的系统。

设计多 Agent 系统，本质上是在做组织设计。想清楚每个角色的职责和边界，是成功的关键。

---

## 下一步

在 [07-Skills知识注入](./07-Skills知识注入.md) 中，我们会学习如何给 Agent 注入领域知识，让它从"通用助手"变成"领域专家"。
