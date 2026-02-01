# 05 - Agent 封装模式

> 配套代码：`src/v4_custom_agent.py`
>
> **目标**：学会把配置、Hook、处理逻辑封装成可复用的组件

---

## 为什么要封装？

到目前为止，我们的代码都是"一次性"的——每次使用都要重复配置 options、定义 hooks、处理响应。

这在学习时没问题。但如果你要在实际项目中使用 Agent，这种方式很快就会变得难以维护：

- **重复代码多** — 每次都写一样的配置
- **修改成本高** — 改一个配置要改很多地方
- **难以测试** — 逻辑分散，不好写单元测试

封装解决这些问题。你把配置、Hook、处理逻辑包装成一个类，以后用的时候一行代码就能创建一个功能完整的 Agent。

---

## 封装的基本思路

```
┌─────────────────────────────────────────────────────────┐
│                    AgentConfig                          │
│  - name, description                                    │
│  - model, allowed_tools                                 │
│  - system_prompt, blocked_patterns                      │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                    BaseAgent                             │
│  - _build_options() → ClaudeAgentOptions                │
│  - run(prompt) → response                              │
│  - get_stats() → statistics                            │
└─────────────────────────────────────────────────────────┘
                           ↓
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
    CodeReviewerAgent  FileManagerAgent  ConversationAgent
```

三层结构：

1. **AgentConfig** — 配置数据类，集中管理所有配置项
2. **BaseAgent** — 基础类，封装通用逻辑
3. **专用 Agent** — 继承基类，预设特定配置

---

## AgentConfig

使用 `dataclass` 定义配置：

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class AgentConfig:
    """Agent 配置"""
    name: str                                    # Agent 名称
    description: str                             # 描述
    model: str = "sonnet"                        # 模型
    allowed_tools: list[str] = field(default_factory=list)
    system_prompt: Optional[str] = None
    enable_logging: bool = True
    blocked_patterns: list[str] = field(default_factory=list)
```

好处：

- 类型明确，IDE 有提示
- 默认值减少配置负担
- 配置集中，便于管理

---

## BaseAgent

基类封装通用逻辑：

```python
class BaseAgent:
    """可复用的 Agent 基类"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.total_cost = 0.0
        self.call_count = 0
        self.audit_log = []

    def _build_options(self) -> ClaudeAgentOptions:
        """从配置构建 SDK 选项"""
        hooks = self._create_hooks()
        return ClaudeAgentOptions(
            model=self.config.model,
            permission_mode="bypassPermissions",
            allowed_tools=self.config.allowed_tools,
            system_prompt=self.config.system_prompt,
            hooks=hooks if hooks else None,
        )

    async def run(self, prompt: str) -> str:
        """执行查询，返回文本响应"""
        self.call_count += 1
        response_text = []

        async with ClaudeSDKClient(options=self._build_options()) as client:
            await client.query(prompt=prompt)
            async for msg in client.receive_response():
                # 处理响应，收集文本
                # ...

        return ''.join(response_text)

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "name": self.config.name,
            "calls": self.call_count,
            "total_cost": self.total_cost,
        }
```

关键点：

- 配置和逻辑分离
- 内置统计功能
- `run()` 方法封装完整流程

---

## 专用 Agent

继承基类，预设配置：

```python
class CodeReviewerAgent(BaseAgent):
    """代码审查专用 Agent"""

    def __init__(self, strict_mode: bool = False):
        config = AgentConfig(
            name="CodeReviewer",
            description="Reviews code for quality and best practices",
            model="sonnet",
            allowed_tools=["Read", "Glob", "Grep"],  # 只读
            system_prompt=self._get_prompt(strict_mode),
        )
        super().__init__(config)
        self.strict_mode = strict_mode

    def _get_prompt(self, strict: bool) -> str:
        base = "You are a code reviewer. Focus on code quality, potential bugs, and best practices."
        return base + (" Be very strict and thorough." if strict else "")
```

使用时：

```python
reviewer = CodeReviewerAgent(strict_mode=True)
result = await reviewer.run("Review src/v0_hello.py")
```

一行创建，开箱即用。

---

## 工厂模式

如果你有多种预设配置，可以用工厂模式：

```python
class AgentFactory:
    """Agent 工厂"""

    PRESETS = {
        "code-reviewer": {
            "class": CodeReviewerAgent,
            "params": {"strict_mode": False},
        },
        "strict-reviewer": {
            "class": CodeReviewerAgent,
            "params": {"strict_mode": True},
        },
        "file-manager": {
            "class": FileManagerAgent,
            "params": {"read_only": False},
        },
    }

    @classmethod
    def create(cls, preset: str) -> BaseAgent:
        """从预设创建 Agent"""
        spec = cls.PRESETS[preset]
        return spec["class"](**spec["params"])
```

使用：

```python
reviewer = AgentFactory.create("code-reviewer")
manager = AgentFactory.create("file-manager")
```

好处：

- 预设集中管理
- 一行创建任意类型的 Agent
- 易于扩展新类型

---

## 运行示例

```bash
python src/v4_custom_agent.py
```

你会看到不同类型 Agent 的演示：

```
============================================================
Demo 1: Basic Custom Agent
============================================================
  [BasicAgent] → Read
Response: The requirements.txt file lists...
[Stats] Calls: 1, Cost: $0.0212

============================================================
Demo 2: Specialized Agents
============================================================
--- CodeReviewerAgent (strict mode) ---
  [CodeReviewer] → Read
Review: ## Code Review: src/v0_hello.py...

--- FileManagerAgent (read-only) ---
  [FileManager] → Glob
Files: v0_hello.py, v1_tools.py...

============================================================
Demo 3: Agent Factory
============================================================
Available presets: ['code-reviewer', 'strict-reviewer', 'file-manager']

--- Secure File Manager ---
  [FileManager] BLOCKED: /secret_data.txt

============================================================
Demo 4: Agent Reusability
============================================================
Q: What is 5 * 7?
A: 35

Q: Square root of 144?
A: 12

[Total] 3 calls, $0.0318
```

---

## 什么时候封装？

| 场景 | 选择 |
|------|------|
| 快速原型、一次性脚本 | 直接使用 SDK |
| 需要复用的逻辑 | 封装为类 |
| 生产环境 | 必须封装 |

不需要过早封装。先让代码跑起来，发现有重复了再封装。

---

## 一些问题

**Q: BaseAgent vs 直接用 SDK，性能有差异吗？**

几乎没有。封装只是代码组织方式的变化，不影响运行时性能。

**Q: 如何在多个 Agent 之间共享状态？**

可以通过外部状态对象：

```python
shared = {"context": "..."}
agent1.shared_state = shared
agent2.shared_state = shared
```

**Q: 如何测试封装的 Agent？**

```python
@pytest.mark.asyncio
async def test_code_reviewer():
    agent = CodeReviewerAgent(strict_mode=True)
    response = await agent.run("Review this code...")
    assert "issue" in response.lower() or "improvement" in response.lower()
```

---

## 小结

封装是从"能用"到"好用"的关键一步。

通过封装，你可以：

- 复用配置和逻辑
- 统一行为和接口
- 方便测试和维护

但不要为了封装而封装。先让代码工作，再考虑复用。

---

## 下一步

在 [06-多Agent协作](./06-多Agent协作.md) 中，我们会学习如何让多个 Agent 协作完成复杂任务。

从"单体"到"系统"，从"一个 Agent 做所有事"到"多个 Agent 各司其职"。
