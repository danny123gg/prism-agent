# 04 - Hook 机制详解

> 配套代码：`src/v3_hooks.py`
>
> **目标**：掌握 Hook 机制，实现可观测、可拦截、可审计的 Agent 系统

---

## 转折点

前三个版本（v0-v2）回答的是一个问题：**怎么让 Agent 工作**。

从这一节开始，问题变成了：**怎么让 Agent 可控**。

这是一个重要的转折。

Agent 不是普通程序。普通程序，你写什么它就做什么，行为是确定的。但 Agent 有"自主性"——你给它一个目标，它自己决定怎么实现。你不知道它会调用哪些工具、会采取什么步骤。

这种自主性是 Agent 的价值所在。但它也带来了不确定性。

Hook 是你和 Agent 之间的**约定**。通过 Hook，你可以告诉它：这些事情可以做，那些事情不行。你不是在控制它的每一步，而是在设定边界。

边界之内，你信任它的判断。

---

## Hook 的工作原理

```
用户请求 → Claude 决策 → [PreToolUse Hook] → 工具执行 → [PostToolUse Hook] → 返回结果
                              ↓                              ↓
                        允许/拦截/修改                  记录/处理结果
```

SDK 提供了两种 Hook：

| 类型 | 触发时机 | 典型用途 |
|------|----------|----------|
| `PreToolUse` | 工具执行**之前** | 日志记录、参数验证、访问控制 |
| `PostToolUse` | 工具执行**之后** | 结果记录、错误处理、数据转换 |

---

## Hook 函数签名

> **注意**：Hook 返回值使用 `continue_`（带下划线），因为 `continue` 是 Python 保留关键字。

### PreToolUse Hook

```python
async def pre_hook(hook_input, tool_use_id, context):
    """
    Args:
        hook_input: dict
            - tool_name: str - 工具名称 ("Read", "Write", "Bash" 等)
            - tool_input: dict - 工具参数
        tool_use_id: str - 本次工具调用的唯一 ID
        context: object - 执行上下文

    Returns:
        dict:
            - {'continue_': True} 表示允许执行
            - {'continue_': False} 表示拦截
    """
    return {'continue_': True}  # 允许执行
```

### PostToolUse Hook

```python
async def post_hook(hook_input, tool_use_id, context):
    """
    Args:
        hook_input: dict
            - tool_response: any - 工具执行结果
        tool_use_id: str - 本次工具调用的唯一 ID
        context: object - 执行上下文

    Returns:
        dict:
            - {'continue_': True} 表示继续
    """
    return {'continue_': True}
```

关键点：返回 `{'continue_': True}` 表示"放行"，返回 `{'continue_': False}` 表示"拦截"。

---

## 配置 Hook

使用 `HookMatcher` 配置 Hook：

```python
from claude_agent_sdk import HookMatcher

hooks = {
    'PreToolUse': [
        HookMatcher(matcher=None, hooks=[my_pre_hook])
    ],
    'PostToolUse': [
        HookMatcher(matcher=None, hooks=[my_post_hook])
    ]
}

options = ClaudeAgentOptions(
    # ... 其他配置
    hooks=hooks,
)
```

### matcher 参数

`matcher` 决定这个 Hook 匹配哪些工具：

| 值 | 含义 |
|---|------|
| `None` | 匹配所有工具 |
| `"Write"` | 只匹配 Write 工具 |
| `"Write\|Edit"` | 匹配 Write 或 Edit |

---

## 实战示例

### 示例 1：日志记录

记录每一次工具调用，用于调试和审计：

```python
audit_log = []

async def logging_hook(hook_input, tool_use_id, context):
    tool_name = hook_input.get("tool_name")
    timestamp = datetime.now().strftime("%H:%M:%S")

    # 记录到日志
    audit_log.append({
        "time": timestamp,
        "tool": tool_name,
    })

    # 控制台输出
    print(f"[{timestamp}] → {tool_name}")

    # 允许执行
    return {'continue_': True}
```

### 示例 2：安全拦截

阻止对敏感路径的写入：

```python
async def security_hook(hook_input, tool_use_id, context):
    tool_name = hook_input.get("tool_name")
    tool_input = hook_input.get("tool_input", {})

    if tool_name == "Write":
        file_path = tool_input.get('file_path', '')
        sensitive = ['.env', 'secret', 'password', 'credentials']

        for s in sensitive:
            if s.lower() in file_path.lower():
                print(f"[BLOCKED] Write to sensitive path: {file_path}")
                return {'continue_': False}  # 拦截操作

    return {'continue_': True}
```

当 Agent 尝试写入敏感文件时，操作会被拦截，Agent 会收到失败反馈。

### 示例 3：针对特定工具的 Hook

只监控写操作：

```python
hooks = {
    'PreToolUse': [
        # 只匹配 Write 工具
        HookMatcher(matcher="Write", hooks=[write_monitor_hook]),
        # 匹配所有工具（全局日志）
        HookMatcher(matcher=None, hooks=[logging_hook]),
    ]
}
```

多个 HookMatcher 按顺序执行。如果任一返回 `{'continue_': False}`，后续 Hook 不执行，操作被拦截。

---

## 运行示例

```bash
python src/v3_hooks.py
```

你会看到类似这样的输出：

```
============================================================
Demo: Security Hooks
============================================================

[23:20:38] PRE  → Write
         File: test_normal.txt
[23:20:41] POST ← OK

[BLOCKED] Write to sensitive path: secret_config.txt

============================================================
Audit Summary
============================================================
Total events: 13
  - pre_tool_use: 6
  - post_tool_use: 6
  - blocked: 1

Blocked operations:
  - Write: sensitive path: secret
```

---

## 常见模式

### 速率限制

防止 Agent 过度调用某个工具：

```python
call_count = {}

async def rate_limit_hook(hook_input, tool_use_id, context):
    tool = hook_input.get("tool_name")
    call_count[tool] = call_count.get(tool, 0) + 1

    if call_count[tool] > 10:
        return {'continue_': False}  # 超出限制，拦截
    return {'continue_': True}
```

### 参数清洗

对危险命令做过滤：

```python
async def sanitize_bash_hook(hook_input, tool_use_id, context):
    if hook_input.get("tool_name") == 'Bash':
        cmd = hook_input.get("tool_input", {}).get('command', '')
        # 移除危险字符
        if ';' in cmd or '&&' in cmd:
            return {'continue_': False}  # 拦截链式命令
    return {'continue_': True}
```

### 审计日志持久化

把日志写入文件：

```python
import json

def log_to_file(record):
    with open('audit.jsonl', 'a') as f:
        f.write(json.dumps(record) + '\n')
```

---

## 一些思考

Hook 不只是技术工具，它反映了一种思维方式：**如何在不完全控制的情况下保持信任**。

一开始，我把 Hook 理解成"控制手段"——用来拦截不想要的行为。但后来我觉得这个理解太狭隘了。

Hook 更像是一种**约定**。

你通过 Hook 告诉 Agent：这是边界，在边界之内，我信任你。

好的边界不是越多越好。边界太多，Agent 就没有发挥的空间。边界太少，你又会失去可控性。

关键是想清楚：哪些风险你能承受，哪些不能？哪些决策你愿意交给 Agent，哪些必须自己把控？

这不只是技术问题。它是一个普遍的问题——管理团队、养育孩子、甚至和朋友相处，都会遇到类似的平衡。

---

## 一些问题

**Q: Hook 返回拦截后，Agent 知道吗？**

知道。Agent 会收到工具调用失败的反馈，可能会尝试其他方法。

**Q: 可以在 Hook 中修改参数吗？**

可以，但要谨慎。修改 `hook_input.get("input")` 中的值后返回即可。

**Q: Hook 执行失败会怎样？**

如果 Hook 抛出异常，SDK 会记录错误。建议在 Hook 中做好异常处理。

---

## 小结

Hook 是 SDK 提供的最强大的控制机制。通过它，你可以：

- 记录每一次工具调用（可观测性）
- 拦截危险操作（安全性）
- 保留操作历史（审计性）
- 定制工具行为（灵活性）

更重要的是，Hook 代表了一种思维方式：**在自主性和可控性之间寻找平衡**。

这是 Agent 开发的核心问题之一。

---

## 下一步

在 [05-Agent封装模式](./05-Agent封装模式.md) 中，我们会学习如何把配置、Hook、处理逻辑封装成可复用的组件。

从"能用"到"好用"，从"一次性脚本"到"可维护的系统"。
