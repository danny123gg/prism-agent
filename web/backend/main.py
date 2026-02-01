"""
FastAPI Backend for Agent Trace Visualization.

启动方式: python main.py
服务地址: http://localhost:8000

Trace 日志目录: ./traces/
"""

# === API 配置（必须在最开始设置，让子进程能继承）===
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 临时：直接从 .env 读取并硬编码设置（验证流程）
from config import load_config
config_obj = load_config()
os.environ['ANTHROPIC_API_KEY'] = config_obj.anthropic_api_key
os.environ['ANTHROPIC_BASE_URL'] = config_obj.anthropic_base_url
os.environ['ANTHROPIC_MODEL'] = config_obj.anthropic_model
# 注意：ANTHROPIC_MODEL_THINKING 已在 config.py 的 load_config() 中设置到 os.environ
print(f"[启动] API 配置已设置:")
print(f"  API Key: {config_obj.anthropic_api_key[:20]}...")
print(f"  Base URL: {config_obj.anthropic_base_url}")
print(f"  Model (Normal): {config_obj.anthropic_model}")
print(f"  Model (Thinking): {config_obj.anthropic_model_thinking}")

import io
import json
import uuid
import asyncio
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator
from urllib.parse import quote


# === 重试配置 ===
MAX_RETRIES = 3  # 最大重试次数
INITIAL_RETRY_DELAY = 1.0  # 初始重试延迟（秒）
MAX_RETRY_DELAY = 10.0  # 最大重试延迟（秒）

# 可重试的错误类型
RETRYABLE_ERRORS = (
    ConnectionError,
    TimeoutError,
    OSError,  # 包含网络相关错误
)

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from anthropic import Anthropic


# === Windows UTF-8 编码修复 ===
def setup_windows_encoding():
    """
    配置 Windows 系统的 UTF-8 编码支持。

    Windows 默认使用 GBK/CP936 编码，导致中文输出乱码。
    此函数将 stdout/stderr 包装为 UTF-8 编码输出。
    """
    if sys.platform == 'win32':
        # 设置 Windows 控制台代码页为 UTF-8
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleOutputCP(65001)  # UTF-8
            kernel32.SetConsoleCP(65001)
        except Exception:
            pass

        # 包装 stdout/stderr 为 UTF-8 编码
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer,
                encoding='utf-8',
                errors='replace',
                line_buffering=True
            )
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer,
                encoding='utf-8',
                errors='replace',
                line_buffering=True
            )


def safe_print(*args, **kwargs):
    """
    安全的打印函数，处理编码错误。

    在 Windows 环境下，某些字符可能无法直接输出，
    此函数会自动替换无法编码的字符。
    """
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # 如果编码失败，尝试替换无法编码的字符
        safe_args = []
        for arg in args:
            if isinstance(arg, str):
                safe_args.append(arg.encode('utf-8', errors='replace').decode('utf-8'))
            else:
                safe_args.append(arg)
        print(*safe_args, **kwargs)


# 在导入时设置编码
setup_windows_encoding()
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from claude_agent_sdk import query, ClaudeAgentOptions, Message
from claude_agent_sdk.types import (
    HookMatcher, HookContext,
    PermissionResultAllow, PermissionResultDeny, ToolPermissionContext
)
from config import get_config

from models import (
    SSEEventType,
    ToolStatus,
    ChatRequest,
    SessionInfo,
    HealthResponse,
)


# === 安全沙箱配置 ===
# 专门的沙箱目录 - Agent 只能在此目录中操作文件
BACKEND_ROOT = Path(__file__).parent.resolve()  # web/backend 目录
SANDBOX_ROOT = BACKEND_ROOT / "sandbox"  # 专门的沙箱目录
SANDBOX_ROOT.mkdir(exist_ok=True)  # 确保沙箱目录存在

ALLOWED_DIRS = [
    SANDBOX_ROOT,  # 沙箱目录 - Agent 的工作空间
]

# === Trace 日志系统 ===
TRACE_DIR = Path(__file__).parent / "traces"
TRACE_DIR.mkdir(exist_ok=True)


# === 共享 System Prompt 生成函数 ===
def generate_system_prompt() -> str:
    """
    生成 Normal 和 Thinking 模式共享的 system prompt。
    包含 CLAUDE.md 中定义的完整行为准则。
    """
    from datetime import datetime
    now = datetime.now()
    current_date = now.strftime("%Y年%m月%d日")
    current_year = now.year

    return f"""你是 Prism，一个用 Claude Agent SDK 构建的透视化教学助手。

你的名字来自棱镜——它能把一束白光分解成七彩光谱，让不可见的变得可见。你的设计理念是：把 Claude Agent SDK 内部的工具调用、Hook 机制、子 Agent 等运作方式外显出来，让用户不只是"用" Agent，而是"看见" Agent 如何工作。

**不要在普通对话中主动自我介绍**，只在用户明确询问"你是谁"时才使用上述介绍。

## ⚠️ 核心要求：透视解读（每次回复必须包含）

**你必须在每次回复的末尾添加「透视解读」区块。这是 Prism 最重要的特性，绝对不能省略。**

### 什么是透视解读？

Prism（棱镜）的本质是**让不可见的变得可见**。透视解读不是简单地复述"我用了什么工具"，而是：

1. **揭示机制**：让用户看见 Agent 内部的决策流程
2. **提炼洞察**：从具体操作中抽象出通用的理解
3. **启发思考**：用类比或总结帮助用户建立心智模型

透视解读是一种**元思考**——不仅完成任务，还要反思"这个过程本身说明了什么"。

### 格式模板

```
---

### 🔍 **透视解读**

[开篇：点明这次交互的核心机制或模式]

[中段：用结构化的方式展示过程，可以是：]
- 编号列表展示步骤流程
- 要点列表总结关键机制
- 对比说明不同方案的选择

[收尾：一句启发性的总结，帮助用户建立更深的理解]
```

### 示例

**示例 1（工具调用 - 展示 Agent 能力边界）**：
```
---

### 🔍 **透视解读**

这次交互展示了 Agent 如何通过**工具扩展**突破自身能力边界：

1. 作为语言模型，我本身无法"看到"文件系统
2. 通过调用 `Bash` 工具，我获得了与操作系统交互的能力
3. SDK 负责权限控制、结果传递，让这个过程安全可控

这就是 Agent 的核心范式：**语言理解 + 工具调用 = 能力扩展**。你在界面上看到的工具卡片，正是这个"能力借用"过程的可视化 🔧
```

**示例 2（Hook 拦截 - 展示安全机制）**：
```
---

### 🔍 **透视解读**

刚才发生了一个值得关注的**安全降级**过程：

1. **意图识别**：我判断需要获取外部信息
2. **首选方案被拦截**：尝试 `curl` 时，PreToolUse Hook 检测到这是未授权的网络请求
3. **自动降级**：改用已授权的 `mcp__tavily__tavily_search` 工具
4. **任务完成**：最终成功获取了需要的信息

这个过程揭示了一个设计哲学：**安全不是阻止，而是引导**。Hook 机制不是简单地说"不行"，而是把 Agent 引导到安全的路径上 🛡️
```

**示例 3（多轮迭代 - 展示推理过程）**：
```
---

### 🔍 **透视解读**

注意到这次对话经历了 **3 轮迭代**吗？这展示了 Agent 的渐进式推理：

- **第 1 轮**：读取文件，理解上下文
- **第 2 轮**：发现缺少关键信息，主动搜索补充
- **第 3 轮**：整合所有信息，生成最终回答

这不是"一次性输出"，而是**思考-行动-观察**的循环。每一轮迭代都基于上一轮的结果调整策略——这正是 Agent 区别于普通 LLM 的关键特征 🔄
```

**示例 4（纯对话 - 反向说明）**：
```
---

### 🔍 **透视解读**

这次是纯文本对话，没有调用任何工具。

这本身就是一个有趣的观察：Agent 的智能不仅体现在"会用工具"，也体现在**知道何时不需要工具**。当知识库足以回答问题时，直接响应比调用工具更高效。

判断"要不要用工具"本身，就是一种元认知能力 💬
```

### 写作原则

- **有深度**：不只是描述"做了什么"，要解释"这说明什么"
- **有结构**：适当使用列表、加粗、换行，让层次清晰
- **有启发**：结尾给一个"原来如此"的洞察
- **有温度**：可以用 emoji，可以有一点个人风格
- **适度篇幅**：5-10 行为宜，不要过短（没有深度）也不要过长（变成说教）

## 项目定位

**这是一个透视化教学应用，不是知识库问答系统。**

- 用户通过前台界面**体验** Agent 的运作过程（可视化工具调用、思考过程等）
- 用户主要通过操作、观察来学习，不是通过问答来学习项目内容
- 项目包含 v0-v8 示例代码和详细文档，但这些是给开发者在 GitHub 上学习的，不是给你在对话中讲解的

**你的角色**：
- ✅ 技术助手：回答通用问题，执行任务
- ❌ 项目讲师：不需要讲解"v0 是什么"、"为什么这个学习路径"

## 系统信息
- 当前日期: {current_date}
- 工作目录: {SANDBOX_ROOT}
- 所有文件操作都在沙箱目录内进行
- 操作系统：Windows (win32)

## 搜索工具配置

**重要：禁止使用内置的 WebSearch 工具**（在中国大陆无法使用）

已配置的 MCP 搜索工具（按场景选择）：

| 场景 | 使用工具 |
|------|----------|
| 技术文档、API 文档、编程问题 | `mcp__serpapi__google` (Google 搜索，技术内容更精准) |
| 通用搜索、新闻、综合信息 | `mcp__tavily__tavily_search` (支持 time_range 参数) |
| 提取特定网页内容 | `mcp__tavily__tavily_extract` |
| 深度研究任务 | `mcp__tavily__tavily_research` |

## 时效性处理
- 你的知识截止于 2025 年 5 月，对于此后的事件、新闻、技术动态等问题，必须使用搜索工具获取最新信息
- 搜索时效性内容时，在查询中加入年份（如 "{current_year}年 AI 热点"）以获得更准确的结果
- 使用 Tavily 搜索时，可通过 time_range 参数限定时间范围（可选值: day/week/month/year）
- 对于历史内容查询，保持原始查询即可，无需添加当前年份

## 信息溯源规则（重要）

**使用搜索工具获取信息后，必须提供来源链接，确保信息可追溯、可验证。**

### 必须标注来源的情况
- 具体数据、统计数字、排名
- 事件细节、时间线、事实陈述
- 技术文档、API 说明、配置方法
- 专家观点、研究结论、分析判断
- 新闻热点、最新动态、行业趋势

### 权威来源优先级

**优先使用（第一梯队）**：
1. **官方来源**：官网、官方文档、官方博客、GitHub 官方仓库
   - 例：anthropic.com、docs.anthropic.com、github.com/anthropics
2. **权威媒体**：知名科技媒体、主流新闻机构
   - 例：TechCrunch、The Verge、Wired、Ars Technica、MIT Technology Review
3. **学术机构**：论文库、大学研究机构
   - 例：arXiv、IEEE、ACM、Nature、Science

**谨慎使用（第二梯队）**：
4. **专业社区**：Stack Overflow、Hacker News
5. **知名博客**：仅限有明确专业背景的作者

**避免使用**：
- ❌ 内容农场、营销网站
- ❌ 无法验证作者身份的个人博客
- ❌ 社交媒体截图（除非是官方账号公告）
- ❌ 二手转载（尽量找原始来源）

### 标注格式

**内联引用**（主要方式）：
```
根据 [Anthropic 官方文档](https://docs.anthropic.com/...) 的说明...
[TechCrunch 报道](https://techcrunch.com/...) 显示...
```

**格式要求**：
- ✅ 链接文本清晰描述来源类型和名称
- ✅ 在首次提及信息时标注链接
- ❌ 不使用"这里"、"来源"、"链接"等模糊表述
- ❌ 不使用裸 URL

**文末汇总**（引用多个来源时）：
```
[回答内容]

**参考来源**：
- [标题](URL) - 官方文档
- [标题](URL) - TechCrunch 2026年1月报道
```

### 搜索策略

1. **关键词优化**：加上 "official"、"documentation"、"announcement"；使用英文关键词搜索技术内容
2. **限定域名**：使用 site: 语法（如 site:anthropic.com Claude Agent SDK）
3. **对比验证**：搜索到信息后，对比 2-3 个来源，选择最权威、最原始的来源
4. **追溯原始来源**：如果搜到二手报道，尽量找到原始出处

## 回复风格

**简洁、技术性、聚焦问题**

- 使用简体中文进行思考和回复
- 不要重复文档中的教学内容（"锚点"、"学习路径"、"为什么这样设计"）
- 不要主动引导用户"接下来看什么"
- 保持技术性说明，2-3 句话足够

### 具体场景处理

**用户问"什么是 v0？"**：
回复："v0 是项目中最基础的 SDK 调用示例，演示如何初始化 Agent、发送请求、接收响应。详细说明可以查看项目 README 或 docs/。"

**用户问"你能做什么？"**：
回复："我可以帮你执行技术任务（代码分析、文件操作、信息搜索等）、调用工具完成复杂工作流、解答技术问题。这个应用的特点是你可以看到我的工作过程——每次工具调用、每个决策步骤都会可视化展示。"

## 边界说明

**在你能力范围内**：
- Claude Agent SDK 的基本用法
- Python 异步编程
- Agent 开发的一般性问题
- 通用技术任务

**超出范围的问题**：
- 礼貌说明超出范围
- 如果知道相关资源，指向官方文档或项目文档
- 不要假装知道不知道的事情

## 透视解读（核心功能）

**这是 Prism 的标志性功能，必须在每次回复末尾添加。**

当你完成任务后，在回复的最后添加一个「透视解读」区块，从 Prism（棱镜）的视角解释刚才发生了什么。这让用户不仅得到答案，还能"看见" Agent 内部的运作机制。

### 格式模板

```
---

### 🔍 **透视解读**

[用 2-4 句话解释刚才发生了什么，包括：]
- 使用了哪些工具、为什么选择这些工具
- 如果有多轮迭代，解释迭代的原因
- 如果有 Hook 拦截，解释拦截原因和降级策略
- 如果有子 Agent，解释任务委派的逻辑

[可选：用简短的类比或总结帮助用户理解 Agent 机制]
```

### 示例

**示例 1（工具调用）**：
```
---

### 🔍 **透视解读**

刚才我使用了 `Bash` 工具执行 `ls -lah` 命令来列出目录内容。这是 Claude Agent SDK 提供的工具之一，让我能够与文件系统交互。你在界面上看到的工具调用卡片，就是这个过程的可视化呈现。
```

**示例 2（Hook 拦截）**：
```
---

### 🔍 **透视解读**

这次交互展示了 Hook 机制的实际应用：
1. 我尝试使用 `curl` 访问外部 API
2. PreToolUse Hook 检测到这是沙箱外的网络请求，进行了拦截
3. 我改用 `mcp__tavily__tavily_search` 工具（已授权的 MCP 搜索服务）
4. 成功获取了需要的信息

这就是"安全降级"策略——当首选方案被拦截时，自动切换到允许的替代方案。
```

**示例 3（简单对话）**：
```
---

### 🔍 **透视解读**

这次是纯文本对话，没有调用任何工具。并非所有问题都需要工具——当我的知识库足以回答时，直接响应是最高效的方式。
```

### 注意事项

- **始终添加**：即使是简单对话也要添加透视解读（可以说明"这次没有使用工具"）
- **简洁为主**：2-4 句话足够，不要写成长篇教程
- **聚焦机制**：重点解释"发生了什么"和"为什么"，而不是重复任务结果
- **使用分隔线**：用 `---` 将透视解读与主要回复内容分隔开"""


def is_path_in_sandbox(file_path: str) -> bool:
    """检查路径是否在沙箱目录内"""
    try:
        path = Path(file_path).resolve()
        # 检查是否在允许的目录内
        for allowed_dir in ALLOWED_DIRS:
            try:
                path.relative_to(allowed_dir)
                return True
            except ValueError:
                continue
        return False
    except Exception:
        return False


def sandbox_check_tool(tool_name: str, tool_input: dict) -> tuple[bool, str]:
    """
    沙箱检查函数 - 检查工具调用是否允许

    返回: (是否允许, 拒绝原因)
    """
    # 只读工具 - 允许访问大部分路径，但敏感文件除外
    # Read, Glob, Grep 是安全的只读操作，但需要检查敏感文件
    if tool_name in ["Read", "Glob", "Grep"]:
        # 检查是否访问敏感文件 (黑名单)
        file_path = tool_input.get("file_path", "") or tool_input.get("path", "")
        pattern = tool_input.get("pattern", "")

        # 敏感文件黑名单
        sensitive_patterns = [".env", ".env.local", ".env.production", "credentials", "secrets"]

        # 检查文件路径
        if file_path:
            file_name = file_path.replace("\\", "/").split("/")[-1].lower()
            for sensitive in sensitive_patterns:
                if sensitive.lower() in file_name:
                    return False, f"拒绝读取: {file_name} 是敏感文件 (黑名单: {sensitive})"

        # 检查 glob pattern
        if pattern:
            for sensitive in sensitive_patterns:
                if sensitive.lower() in pattern.lower():
                    return False, f"拒绝搜索: pattern '{pattern}' 可能匹配敏感文件"

        return True, ""

    # 文件写入工具 - 检查路径，必须在沙箱内
    if tool_name in ["Write", "Edit"]:
        file_path = tool_input.get("file_path", "")
        if not file_path:
            return False, "文件路径为空"
        if not is_path_in_sandbox(file_path):
            return False, f"拒绝写入: {file_path} 不在允许的目录内 (沙箱: {SANDBOX_ROOT})"
        return True, ""

    # Bash 命令 - 允许所有命令，但路径操作必须在沙箱内
    if tool_name == "Bash":
        command = tool_input.get("command", "")

        # 禁止路径穿越
        if "../" in command or "..\\" in command:
            return False, "拒绝执行: 禁止路径穿越 (../)"

        # 检查命令中的绝对路径是否在沙箱内
        # 提取可能的路径（简单检测绝对路径）
        import re
        # Windows 绝对路径: C:\... 或 /c/...
        # Unix 绝对路径: /...
        path_patterns = [
            r'[A-Za-z]:[\\\/][^\s"\']+',  # Windows: C:\path or C:/path
            r'\/[a-z]\/[^\s"\']+',  # Git Bash: /c/path
            r'(?<![a-zA-Z0-9_])\/(?!dev\/|proc\/|sys\/)[a-zA-Z][^\s"\']*',  # Unix: /path (exclude /dev, /proc, /sys)
        ]

        for pattern in path_patterns:
            matches = re.findall(pattern, command, re.IGNORECASE)
            for path_str in matches:
                # 规范化路径
                try:
                    # 转换 /c/... 格式为 C:\...
                    if path_str.startswith('/') and len(path_str) > 2 and path_str[2] == '/':
                        path_str = path_str[1].upper() + ':' + path_str[2:].replace('/', '\\')

                    if not is_path_in_sandbox(path_str):
                        return False, f"拒绝执行: 路径 {path_str} 不在沙箱目录内 (沙箱: {SANDBOX_ROOT})"
                except Exception:
                    pass  # 无法解析的路径忽略

        return True, ""

    # Task (子代理) - 允许，但子代理也会受到沙箱限制
    if tool_name == "Task":
        return True, ""

    # 其他工具 - 默认允许 (如 WebSearch, WebFetch, Skill 等)
    # 只有涉及文件操作的工具需要沙箱检查
    return True, ""


# === 沙箱权限回调 (can_use_tool) ===
async def sandbox_can_use_tool(
    tool_name: str,
    tool_input: dict,
    context: ToolPermissionContext
) -> PermissionResultAllow | PermissionResultDeny:
    """
    can_use_tool 回调 - SDK 内置的权限检查机制

    这是 SDK 推荐的权限控制方式，比 hooks 更可靠。

    Args:
        tool_name: 工具名称
        tool_input: 工具输入参数
        context: 权限上下文

    Returns:
        PermissionResultAllow: 允许执行
        PermissionResultDeny: 拒绝执行
    """
    safe_print(f"[SANDBOX] 检查工具权限: {tool_name}")

    # 检查沙箱权限
    is_allowed, reason = sandbox_check_tool(tool_name, tool_input)

    if not is_allowed:
        safe_print(f"[SANDBOX] 拦截 {tool_name}: {reason}")
        return PermissionResultDeny(
            message=f"沙箱安全限制: {reason}",
            interrupt=False  # 不中断整个会话，只拒绝这个工具调用
        )

    safe_print(f"[SANDBOX] 允许 {tool_name}")
    return PermissionResultAllow()


# === Hooks 机制 (#23) ===
# 用于在工具调用前后插入自定义逻辑，支持观测、拦截和审计

# 注意: Hook 事件队列现在是每请求独立的，避免多浏览器/多标签页并发问题


def create_keep_stream_open_hook(tracer: 'TraceLogger'):
    """创建 keep_stream_open_hook 工厂函数

    Workaround: 保持 stream 打开以启用 can_use_tool 回调

    官方文档说明 (Issue #48):
    In Python, can_use_tool requires streaming mode and a PreToolUse hook
    that returns {"continue_": True} to keep the stream open.

    参考: https://platform.claude.com/docs/en/agent-sdk/user-input

    Args:
        tracer: Trace 日志记录器
    """
    async def keep_stream_open_hook(hook_input: dict, tool_use_id: str | None, context: dict) -> dict:
        """
        KeepStreamOpen Hook - 保持 stream 打开以支持 can_use_tool

        Returns:
            {"continue_": True} - 允许执行并保持 stream 打开
        """
        tracer.log("hook_keep_stream", {
            "hook_type": "KeepStreamOpen",
            "tool_use_id": tool_use_id,
            "action": "continue"
        })
        # 返回 continue_: True 保持 stream 打开
        # 注意：v0.1.3 已修复 field conversion bug，continue_ 会被正确转换为 continue
        return {"continue_": True}

    return keep_stream_open_hook


def create_pre_tool_hook(tracer: 'TraceLogger', hook_events_queue: list, pending_html_files: dict):
    """创建 PreToolUse Hook 工厂函数

    SDK HookCallback 签名: (input: dict, tool_use_id: str | None, context: dict) -> dict
    参见: claude_agent_sdk/types.py HookCallback 定义

    Args:
        tracer: Trace 日志记录器
        hook_events_queue: 此请求专属的事件队列（每个 SSE 流独立）
        pending_html_files: 存储待处理的 HTML 文件信息（key: tool_use_id, value: file_path）
    """
    async def pre_tool_hook(hook_input: dict, tool_use_id: str | None, context: dict) -> dict:
        """
        PreToolUse Hook - 在工具执行前触发

        Args:
            hook_input: 包含 toolName, input 等信息的字典
            tool_use_id: 工具调用 ID
            context: 上下文信息 (包含 signal)

        Returns:
            {} - 允许执行
            {"decision": "block"} - 拦截
        """
        # 从 hook_input 中提取工具信息
        # SDK v0.1.27 格式 (snake_case):
        # {
        #   'session_id': '...',
        #   'hook_event_name': 'PreToolUse',
        #   'tool_name': 'Write',
        #   'tool_input': {...},
        #   'tool_use_id': '...'
        # }
        tool_name = hook_input.get("tool_name", "unknown")
        tool_input = hook_input.get("tool_input", {})

        safe_print(f"[HOOK] PreToolUse: {tool_name} (id: {tool_use_id})")

        # 🔒 沙箱权限检查 - 在 hook 中实现，因为 can_use_tool 回调不会被触发
        is_allowed, reason = sandbox_check_tool(tool_name, tool_input)

        if not is_allowed:
            safe_print(f"[SANDBOX] 🚫 拦截 {tool_name}: {reason}")
            # 记录沙箱拦截事件 - 使用专门的 sandbox_block 事件类型
            tracer.log("sandbox_block", {
                "tool_name": tool_name,
                "tool_use_id": tool_use_id,
                "tool_input_summary": _summarize_input(tool_name, tool_input),
                "reason": reason,
                "blocked_path": tool_input.get("file_path") or tool_input.get("path") or tool_input.get("command", "")[:100]
            })
            # 添加拦截事件到队列
            hook_events_queue.append({
                "type": "pre_tool",
                "tool_name": tool_name,
                "action": "block",
                "message": f"沙箱安全限制: {reason}"
            })
            # 返回 block 决定 - SDK 会阻止工具执行
            return {"decision": "block", "reason": f"沙箱安全限制: {reason}"}

        # 记录到 trace (允许执行)
        tracer.log("hook_pre_tool", {
            "tool_name": tool_name,
            "tool_use_id": tool_use_id,
            "tool_input_summary": _summarize_input(tool_name, tool_input),
            "action": "allow"
        })

        # 检测 HTML 文件创建 - 记录到字典供 PostToolUse 使用
        if tool_name == "Write" and isinstance(tool_input, dict) and tool_use_id:
            file_path = tool_input.get("file_path", "")
            if file_path.lower().endswith('.html'):
                # 将文件路径存储到字典，key 是 tool_use_id
                pending_html_files[tool_use_id] = file_path
                safe_print(f"[HOOK] 检测到 HTML 文件写入: {file_path}")

        # 添加事件到此请求专属的队列（线程安全）
        hook_events_queue.append({
            "type": "pre_tool",
            "tool_name": tool_name,
            "action": "allow",
            "message": f"Hook 允许执行 {tool_name}"
        })

        # 返回空字典表示允许执行
        return {}

    return pre_tool_hook


def create_post_tool_hook(tracer: 'TraceLogger', hook_events_queue: list, pending_html_files: dict):
    """创建 PostToolUse Hook 工厂函数

    SDK HookCallback 签名: (input: dict, tool_use_id: str | None, context: dict) -> dict

    Args:
        tracer: Trace 日志记录器
        hook_events_queue: 此请求专属的事件队列（每个 SSE 流独立）
        pending_html_files: 存储待处理的 HTML 文件信息（key: tool_use_id, value: file_path）
    """
    async def post_tool_hook(hook_input: dict, tool_use_id: str | None, context: dict) -> dict:
        """
        PostToolUse Hook - 在工具执行后触发

        Args:
            hook_input: 包含 toolName, toolResult 等信息的字典
            tool_use_id: 工具调用 ID
            context: 上下文信息

        Returns:
            {} - 继续执行
        """
        # 从 hook_input 中提取工具信息
        # SDK v0.1.27 格式 (snake_case):
        # {
        #   'hook_event_name': 'PostToolUse',
        #   'tool_name': 'Write',
        #   'tool_result': {...},
        #   'tool_use_id': '...'
        # }
        tool_name = hook_input.get("tool_name", "unknown")
        tool_result = hook_input.get("tool_result")

        safe_print(f"[HOOK] PostToolUse: {tool_name} (id: {tool_use_id})")

        # 记录到 trace - 包含结果摘要
        tracer.log("hook_post_tool", {
            "tool_name": tool_name,
            "tool_use_id": tool_use_id,
            "has_result": tool_result is not None,
            "result_summary": _summarize_output(tool_name, tool_result) if tool_result else None
        })

        # 检测 HTML 文件创建 - 从字典查找
        if tool_name == "Write" and tool_use_id and tool_use_id in pending_html_files:
            # 如果工具执行成功，推送访问链接
            if tool_result:
                file_path = pending_html_files[tool_use_id]
                filename = Path(file_path).name
                access_url = f"http://localhost:8000/sandbox/{filename}"

                # 添加特殊事件到队列，包含访问链接
                hook_events_queue.append({
                    "type": "html_created",
                    "tool_name": tool_name,
                    "filename": filename,
                    "url": access_url,
                    "message": f"✨ HTML 文件已创建，可通过以下链接访问：\n{access_url}"
                })

                safe_print(f"[HOOK] HTML 文件创建成功: {filename} -> {access_url}")

            # 从字典中移除已处理的条目
            del pending_html_files[tool_use_id]

        # 添加事件到此请求专属的队列
        hook_events_queue.append({
            "type": "post_tool",
            "tool_name": tool_name,
            "message": f"Hook 记录 {tool_name} 执行完成"
        })

        return {}

    return post_tool_hook


class TraceLogger:
    """Trace 日志记录器 - 增强版"""

    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.start_time = datetime.now()
        self.log_file = TRACE_DIR / f"{trace_id}.json"
        self.events = []
        self.metadata = {
            "trace_id": trace_id,
            "start_time": self.start_time.isoformat(),
            "status": "running",
            "version": "2.0"  # Trace 格式版本
        }
        self.stats = {
            "tool_calls": 0,
            "iterations": 0,
            "sub_agents": 0,
            "errors": 0,
            "hooks_triggered": 0,
            "sandbox_blocks": 0,
            "thinking_blocks": 0,
            "thinking_chars": 0
        }

    def log(self, event_type: str, data: dict, raw_msg: any = None):
        """记录事件，添加 human_readable 摘要"""
        # 生成人类可读的摘要
        summary = self._generate_summary(event_type, data)

        event = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_ms": int((datetime.now() - self.start_time).total_seconds() * 1000),
            "event_type": event_type,
            "summary": summary,  # 人类可读摘要
            "data": data
        }

        # 更新统计信息
        if event_type == "tool_start":
            self.stats["tool_calls"] += 1
            if data.get("name") == "Task":
                self.stats["sub_agents"] += 1
            iteration = data.get("iteration", 0)
            if iteration > self.stats["iterations"]:
                self.stats["iterations"] = iteration
        elif event_type == "error":
            self.stats["errors"] += 1
        elif event_type == "sandbox_block":
            self.stats["sandbox_blocks"] += 1
        elif event_type in ("hook_pre_tool", "hook_post_tool"):
            self.stats["hooks_triggered"] += 1
        elif event_type == "thinking":
            self.stats["thinking_blocks"] += 1
            thinking_text = data.get("thinking", "")
            self.stats["thinking_chars"] += len(thinking_text)

        if raw_msg is not None:
            # 尝试序列化原始消息
            try:
                if hasattr(raw_msg, '__dict__'):
                    event["raw"] = str(raw_msg.__dict__)
                else:
                    event["raw"] = str(raw_msg)
            except Exception:
                event["raw"] = repr(raw_msg)

        self.events.append(event)
        self._save()

    def _generate_summary(self, event_type: str, data: dict) -> str:
        """生成人类可读的事件摘要"""
        summaries = {
            "request": lambda d: f"用户请求: {d.get('message', '')[:50]}...",
            "config": lambda d: f"配置 Agent (沙箱: {d.get('sandbox_root', 'N/A')})",
            "text_delta": lambda d: f"输出文本 ({len(d.get('delta', ''))} 字符)",
            "thinking": lambda d: f"💭 思考中 ({len(d.get('thinking', ''))} 字符, ~{len(d.get('thinking', ''))//4} tokens)",
            "tool_start": lambda d: f"调用工具 [{d.get('name')}] (迭代 #{d.get('iteration', 1)})",
            "tool_result": lambda d: f"工具 [{d.get('tool_name', '?')}] 完成 (状态: {d.get('status')}, 耗时: {d.get('duration_ms', '?')}ms)",
            "usage": lambda d: f"Token: {d.get('input_tokens', 0)}入/{d.get('output_tokens', 0)}出 | API延迟: {d.get('duration_api_ms', '?')}ms | 缓存: {d.get('cache_read_tokens', 0)}读",
            "complete": lambda d: f"完成 (工具调用: {len(d.get('tools_used', []))}个)",
            "error": lambda d: f"错误: {d.get('type', 'Unknown')} - {d.get('error', '')[:50]}",
            "raw_message": lambda d: f"SDK 消息 (subtype: {d.get('subtype', 'N/A')})",
            # Hook 相关事件
            "sandbox_block": lambda d: f"🚫 沙箱拦截 [{d.get('tool_name')}]: {d.get('reason', '')[:40]}",
            "hook_pre_tool": lambda d: f"Hook 预检 [{d.get('tool_name')}] -> {d.get('action', 'allow')}",
            "hook_post_tool": lambda d: f"Hook 后处理 [{d.get('tool_name')}] (有结果: {d.get('has_result', False)})",
            # 重试和代理事件
            "retry": lambda d: f"⚠️ 重试 #{d.get('attempt')}/{d.get('max_retries')} ({d.get('error_type')})",
            "agent_complete": lambda d: f"✅ 子代理完成 (深度: {d.get('new_depth')})",
        }
        generator = summaries.get(event_type, lambda d: event_type)
        try:
            return generator(data)
        except Exception:
            return event_type

    def log_error(self, error: Exception):
        """记录错误"""
        self.metadata["status"] = "error"
        self.metadata["error"] = {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc()
        }
        self.log("error", {
            "error": str(error),
            "type": type(error).__name__,
            "traceback": traceback.format_exc()
        })

    def complete(self):
        """标记完成"""
        self.metadata["status"] = "completed"
        self.metadata["end_time"] = datetime.now().isoformat()
        self.metadata["duration_ms"] = int((datetime.now() - self.start_time).total_seconds() * 1000)
        self.metadata["stats"] = self.stats  # 添加统计信息
        self._save()

    def _save(self):
        """保存到文件"""
        output = {
            "metadata": self.metadata,
            "events": self.events
        }
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    @property
    def file_path(self) -> str:
        return str(self.log_file.absolute())


# === 性能指标收集器 (#62) ===
class MetricsCollector:
    """
    收集和聚合 Agent 性能指标

    指标包括：
    - 请求统计：总数、成功、失败
    - 延迟指标：首字节时间、总响应时间
    - Token 吞吐量
    - 工具调用统计
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """重置所有指标"""
        self._requests = {
            "total": 0,
            "success": 0,
            "error": 0,
        }
        self._latencies = []  # 总响应时间列表 (ms)
        self._ttft = []  # Time to first token 列表 (ms)
        self._tokens = {
            "total_input": 0,
            "total_output": 0,
        }
        self._tool_calls = {}  # 工具名 -> 调用次数
        self._errors = {}  # 错误类型 -> 次数
        self._start_time = datetime.now()

    def record_request_start(self) -> float:
        """记录请求开始，返回开始时间戳"""
        self._requests["total"] += 1
        return datetime.now().timestamp() * 1000  # ms

    def record_first_token(self, start_time: float):
        """记录首字节时间"""
        ttft = datetime.now().timestamp() * 1000 - start_time
        self._ttft.append(ttft)

    def record_request_complete(self, start_time: float, success: bool = True):
        """记录请求完成"""
        latency = datetime.now().timestamp() * 1000 - start_time
        self._latencies.append(latency)
        if success:
            self._requests["success"] += 1
        else:
            self._requests["error"] += 1

    def record_tokens(self, input_tokens: int, output_tokens: int):
        """记录 token 使用量"""
        self._tokens["total_input"] += input_tokens
        self._tokens["total_output"] += output_tokens

    def record_tool_call(self, tool_name: str):
        """记录工具调用"""
        self._tool_calls[tool_name] = self._tool_calls.get(tool_name, 0) + 1

    def record_error(self, error_type: str):
        """记录错误"""
        self._errors[error_type] = self._errors.get(error_type, 0) + 1

    def _percentile(self, data: list, p: float) -> float:
        """计算百分位数"""
        if not data:
            return 0
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * p / 100
        f = int(k)
        c = f + 1 if f + 1 < len(sorted_data) else f
        return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)

    def get_metrics(self) -> dict:
        """获取当前指标快照"""
        uptime_seconds = (datetime.now() - self._start_time).total_seconds()

        # 计算延迟统计
        latency_stats = {
            "avg": sum(self._latencies) / len(self._latencies) if self._latencies else 0,
            "min": min(self._latencies) if self._latencies else 0,
            "max": max(self._latencies) if self._latencies else 0,
            "p50": self._percentile(self._latencies, 50),
            "p95": self._percentile(self._latencies, 95),
            "p99": self._percentile(self._latencies, 99),
        }

        # 计算 TTFT 统计
        ttft_stats = {
            "avg": sum(self._ttft) / len(self._ttft) if self._ttft else 0,
            "min": min(self._ttft) if self._ttft else 0,
            "max": max(self._ttft) if self._ttft else 0,
            "p50": self._percentile(self._ttft, 50),
            "p95": self._percentile(self._ttft, 95),
        }

        # 计算吞吐量
        total_tokens = self._tokens["total_input"] + self._tokens["total_output"]
        throughput = total_tokens / uptime_seconds if uptime_seconds > 0 else 0

        # 计算成功率
        success_rate = (
            self._requests["success"] / self._requests["total"] * 100
            if self._requests["total"] > 0 else 100
        )

        return {
            "uptime_seconds": round(uptime_seconds, 2),
            "requests": {
                **self._requests,
                "success_rate": round(success_rate, 2),
            },
            "latency_ms": {k: round(v, 2) for k, v in latency_stats.items()},
            "ttft_ms": {k: round(v, 2) for k, v in ttft_stats.items()},
            "tokens": {
                **self._tokens,
                "throughput_per_second": round(throughput, 2),
            },
            "tool_calls": dict(sorted(
                self._tool_calls.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]),  # Top 10 工具
            "errors": dict(self._errors),
        }


# 全局指标收集器实例
metrics_collector = MetricsCollector()


# === 会话存储 (内存，仅用于演示) ===
sessions: dict[str, dict] = {}


# === UTF-8 乱码修复 ===
def sanitize_utf8_text(text: str) -> str:
    """
    清理 UTF-8 文本中的 Unicode 替换字符 (U+FFFD)

    问题原因：Claude SDK 在流式传输时可能在 UTF-8 多字节字符的中间分块，
    导致字节序列不完整。当使用 errors='replace' 解码时，
    这些不完整的字节会被替换为 U+FFFD (�)。

    例如："审" (UTF-8: E5 AE A1) 可能被截断为 E5 AE，
    解码后变成 "�" 或 "��"。

    解决方案：移除连续的替换字符序列（通常表示被截断的中文字符）
    """
    if not text:
        return text

    # Unicode 替换字符
    REPLACEMENT_CHAR = '\ufffd'

    if REPLACEMENT_CHAR not in text:
        return text

    # 策略：移除替换字符序列
    # 连续的 1-4 个 U+FFFD 通常表示一个被截断的多字节字符
    import re
    # 移除 1-4 个连续的替换字符（对应 UTF-8 的 1-4 字节字符）
    cleaned = re.sub(r'\ufffd{1,4}', '', text)

    return cleaned


# === SSE 事件格式化 ===
def format_sse(event_type: SSEEventType, data: dict) -> str:
    """格式化 SSE 事件"""
    return f"event: {event_type.value}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# === Claude SDK 流式处理 ===

async def create_message_stream(message: str, history: list = None):
    """
    创建 AsyncIterable 消息流

    SDK 在流模式下才会正确初始化 hooks，字符串模式下 hooks 不工作。
    参考 SDK client.py: is_streaming = not isinstance(prompt, str)

    CLI 流模式期望的消息格式:
    {"type": "user", "message": {"role": "user", "content": "..."}}

    Args:
        message: 用户消息字符串
        history: 对话历史（可选），格式为 [{"role": "user"/"assistant", "content": "..."}]

    Yields:
        dict: CLI 期望的消息格式
    """
    # SDK 流模式只接受 'user' 类型消息，不能发送 'assistant' 类型
    # 解决方案：将对话历史摘要作为上下文注入到系统提示中

    # 构建历史上下文摘要
    history_context = ""
    if history and len(history) > 0:
        # 将历史消息转换为上下文摘要
        history_lines = []
        for hist_msg in history:
            role = hist_msg.get("role", "unknown")
            content = hist_msg.get("content", "")
            # 截断过长的内容
            if len(content) > 500:
                content = content[:500] + "..."
            role_label = "用户" if role == "user" else "助手"
            history_lines.append(f"[{role_label}]: {content}")

        if history_lines:
            history_context = "\n\n[对话历史摘要]\n" + "\n".join(history_lines) + "\n\n请基于以上对话历史继续回答。\n"

    # 如果没有历史消息，当前消息需要注入系统上下文
    if not history:
        from datetime import datetime
        now = datetime.now()
        current_date = now.strftime("%Y年%m月%d日")
        current_year = now.year

        date_context = f"""你是 Prism，一个用 Claude Agent SDK 构建的透视化教学助手。

你的名字来自棱镜——它能把一束白光分解成七彩光谱，让不可见的变得可见。你的设计理念是：把 Claude Agent SDK 内部的工具调用、Hook 机制、子 Agent 等运作方式外显出来，让用户不只是"用" Agent，而是"看见" Agent 如何工作。

[系统信息]
当前日期: {current_date}

重要提示:
- 你的知识截止于 2025 年 5 月，对于此后的事件、新闻、技术动态等问题，必须使用搜索工具获取最新信息
- 搜索时效性内容时，建议在查询中加入年份（如 "{current_year}年 AI 热点"）以获得更准确的结果
- 使用 Tavily 搜索时，可通过 time_range 参数限定时间范围（可选值: day/week/month/year）
- 对于历史内容查询，保持原始查询即可，无需添加当前年份

"""
        yield {
            "type": "user",
            "message": {
                "role": "user",
                "content": date_context + message
            }
        }
    else:
        # 有历史消息时，将历史摘要和当前消息合并发送
        from datetime import datetime
        now = datetime.now()
        current_date = now.strftime("%Y年%m月%d日")
        current_year = now.year

        date_context = f"""你是 Prism，一个用 Claude Agent SDK 构建的透视化教学助手。

[系统信息]
当前日期: {current_date}

重要提示:
- 你的知识截止于 2025 年 5 月，对于此后的事件请使用搜索工具
- 搜索时效性内容时，建议在查询中加入年份（如 "{current_year}年 AI 热点"）
"""
        yield {
            "type": "user",
            "message": {
                "role": "user",
                "content": date_context + history_context + "\n[当前用户消息]\n" + message
            }
        }


async def process_agent_stream(
    message: str,
    session_id: str,
    trace_id: str,
    history: list = None
) -> AsyncGenerator[str, None]:
    """
    处理 Claude Agent 流式响应，转换为 SSE 事件。

    Args:
        message: 当前用户消息
        session_id: 会话 ID
        trace_id: 追踪 ID
        history: 对话历史（可选）
    """
    # 创建 Trace 记录器
    tracer = TraceLogger(trace_id)
    tracer.log("request", {
        "message": message,
        "session_id": session_id,
        "history_length": len(history) if history else 0
    })

    # 性能指标：记录请求开始
    request_start_time = metrics_collector.record_request_start()
    first_token_recorded = False

    # 配置常量
    MAX_TURNS = 30  # 最大迭代轮次

    # 发送会话配置信息给前端
    yield format_sse(SSEEventType.SESSION_CONFIG, {
        "max_turns": MAX_TURNS,
        "permission_mode": "default",  # 匹配 ClaudeAgentOptions 中的设置
        "sandbox_enabled": True,
        "sandbox_root": str(SANDBOX_ROOT)
    })

    # 追踪状态
    current_text = ""
    tools_used = []
    total_input_tokens = 0
    total_output_tokens = 0
    tool_states: dict[str, dict] = {}  # tool_use_id -> tool info
    current_iteration = 0  # 当前迭代轮次
    current_depth = 0  # 当前子代理深度 (0 = 主代理)
    last_tool_batch_id = None  # 用于检测新一轮迭代
    stop_reason = None  # 停止原因 (#34)

    try:
        # 配置 Claude Agent
        # SDK v0.1.25+ 已修复 system_prompt 问题
        # 如需自定义 system_prompt，可使用:
        #   system_prompt={"type": "preset", "preset": "claude_code"}  # 预设
        #   system_prompt="Your custom prompt here"  # 自定义

        # 完整的工具列表
        # can_use_tool 回调已启用 (#48)
        # 通过 keep_stream_open_hook 保持 stream 打开，使 can_use_tool 正常工作
        # 参考: https://platform.claude.com/docs/en/agent-sdk/user-input
        #
        # WebSearch 替代方案 (#6):
        # SDK 内置的 WebSearch 在某些环境下会失败 (exit code 1)
        # 提供 /api/search 端点作为备用方案，用户可通过 WebFetch 调用
        # 注意: 不能在 prompt 中注入复杂提示，会导致 SDK 命令行解析失败

        # 创建此请求专属的 hook 事件队列（解决多浏览器并发问题）
        hook_events_queue = []
        # 创建待处理的 HTML 文件字典（用于 Hook 之间传递信息）
        pending_html_files = {}

        # 配置 Hooks (#23)
        # PreToolUse: 工具执行前触发
        # PostToolUse: 工具执行后触发
        #
        # 重要 (#48): keep_stream_open_hook 必须在 PreToolUse 中第一个执行
        # 它返回 {"continue_": True} 以保持 stream 打开，使 can_use_tool 回调能正常工作
        hooks_config = {
            'PreToolUse': [
                # 第一个 Hook: 保持 stream 打开（can_use_tool 依赖此机制）
                HookMatcher(
                    matcher=None,
                    hooks=[create_keep_stream_open_hook(tracer)]
                ),
                # 第二个 Hook: 原有的 PreToolUse 逻辑
                HookMatcher(
                    matcher=None,  # None 匹配所有工具
                    hooks=[create_pre_tool_hook(tracer, hook_events_queue, pending_html_files)]
                )
            ],
            'PostToolUse': [
                HookMatcher(
                    matcher=None,
                    hooks=[create_post_tool_hook(tracer, hook_events_queue, pending_html_files)]
                )
            ]
        }

        # 构建 SDK 选项
        # 注意：API Key 已在启动时设置到 os.environ，子进程会自动继承
        # env 参数只需要传递必要的编码配置，避免环境变量冲突

        # MCP 服务器配置
        # 包名和参数格式来自用户的 Claude Code 配置 (~/.claude.json)
        # tavily-mcp: 使用环境变量传递 API Key
        # mcp-serpapi: 使用 -k 参数传递 API Key
        tavily_key = os.environ.get("TAVILY_API_KEY", "")
        serpapi_key = os.environ.get("SERPAPI_API_KEY", "")

        mcp_servers_config = {
            "tavily": {
                "command": "npx",
                "args": ["-y", "tavily-mcp"],
                "env": {
                    "TAVILY_API_KEY": tavily_key
                }
            },
            "serpapi": {
                "command": "npx",
                "args": ["-y", "mcp-serpapi", "-k", serpapi_key],
                "env": {}
            }
        }

        options = ClaudeAgentOptions(
            model=config_obj.anthropic_model,  # 使用配置文件中的完整模型ID
            # 使用共享的 system prompt（包含 CLAUDE.md 中的完整行为准则）
            system_prompt=generate_system_prompt(),
            allowed_tools=[
                "Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task",
                "WebFetch",
                # 搜索策略: 专业知识用 Google，非专业知识用 Tavily
                "mcp__tavily__tavily_search",
                "mcp__tavily__tavily_extract",
                "mcp__serpapi__google",
                "mcp__serpapi__bing",
            ],
            # 明确禁用 SDK 内置的 WebSearch（在中国大陆无法使用）
            disallowed_tools=["WebSearch"],
            # MCP 服务器配置
            mcp_servers=mcp_servers_config,
            permission_mode="default",  # 必须为 default 才能触发 can_use_tool 回调
            max_turns=MAX_TURNS,  # 使用配置常量，避免复杂任务被截断
            cwd=str(project_root),  # 项目根目录，便于读取；写入受 sandbox_check_tool 限制
            can_use_tool=sandbox_can_use_tool,  # ✅ 已启用 - 沙箱权限检查 (#48)
            hooks=hooks_config,  # Hooks 机制 (#23) - 已启用
            env={
                # 只传递编码配置，避免环境变量冲突
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1",
                "PYTHONLEGACYWINDOWSSTDIO": "0",
            },
        )
        tracer.log("config", {
            "options": str(options),
            "sandbox_root": str(SANDBOX_ROOT),
            "can_use_tool_enabled": True,  # ✅ 已启用沙箱权限检查
            "hooks_enabled": True,  # (#23) Hooks 机制已配置
            "note": "can_use_tool 实现沙箱权限控制，hooks 实现观测和审计"
        })

        # 搜索指引移除说明 (#6)
        # 原先每条消息都注入 search_hint 导致 Agent 只回复"了解规则"而不执行任务
        # WebSearch 替代方案: 用户可手动使用 WebFetch 调用 /api/search
        # 或通过 MCP 工具 (tavily/serpapi) 进行搜索

        # 流式处理消息
        # 使用 AsyncIterable 流模式，hooks 才能正确注册和触发
        # 参考 SDK client.py: is_streaming = not isinstance(prompt, str)

        # 使用重试机制处理连接错误
        retry_count = 0
        last_error = None
        stream = None

        while retry_count <= MAX_RETRIES:
            try:
                # 使用 AsyncIterable 流模式，让 hooks 正常工作
                # 每次重试需要创建新的生成器（AsyncIterable 只能消费一次）
                stream = query(prompt=create_message_stream(message, history), options=options)
                break  # 成功获取流
            except RETRYABLE_ERRORS as e:
                retry_count += 1
                last_error = e
                if retry_count <= MAX_RETRIES:
                    delay = min(INITIAL_RETRY_DELAY * (2 ** (retry_count - 1)), MAX_RETRY_DELAY)
                    tracer.log("retry", {
                        "attempt": retry_count,
                        "max_retries": MAX_RETRIES,
                        "delay_seconds": delay,
                        "error": str(e),
                        "error_type": type(e).__name__
                    })
                    yield format_sse(SSEEventType.TEXT_DELTA, {
                        "text": f"\n[连接重试 {retry_count}/{MAX_RETRIES}，等待 {delay:.1f}s...]\n"
                    })
                    await asyncio.sleep(delay)
                else:
                    raise last_error

        if stream is None:
            raise last_error or RuntimeError("Failed to create stream")

        async for msg in stream:
            # 记录原始消息
            msg_subtype = getattr(msg, 'subtype', None)
            tracer.log("raw_message", {"subtype": msg_subtype}, raw_msg=msg)

            # 跳过初始化消息
            if msg_subtype == 'init':
                continue

            # 处理完成消息 (subtype='success')
            if msg_subtype == 'success':
                result_text = getattr(msg, 'result', None)
                usage = getattr(msg, 'usage', None)
                # 推断停止原因 (#34)
                # SDK 不直接暴露 stop_reason，从可用数据推断
                is_error = getattr(msg, 'is_error', False)
                num_turns = getattr(msg, 'num_turns', 0)
                if is_error:
                    stop_reason = "error"
                elif num_turns >= MAX_TURNS:
                    stop_reason = "max_turns"
                else:
                    stop_reason = "end_turn"
                if result_text and result_text != current_text:
                    delta = result_text[len(current_text):]
                    # 清理 UTF-8 乱码 (U+FFFD 替换字符)
                    delta = sanitize_utf8_text(delta)
                    if delta:  # 只在有有效内容时发送
                        current_text = result_text
                        tracer.log("text_delta", {"delta": delta})
                        yield format_sse(SSEEventType.TEXT_DELTA, {"text": delta})

                if usage:
                    total_input_tokens = usage.get('input_tokens', 0)
                    total_output_tokens = usage.get('output_tokens', 0)
                    cost = getattr(msg, 'total_cost_usd', 0) or 0

                    # 提取 API 延迟数据
                    duration_ms = getattr(msg, 'duration_ms', None)
                    duration_api_ms = getattr(msg, 'duration_api_ms', None)
                    num_turns = getattr(msg, 'num_turns', 0)

                    # 计算缓存命中信息
                    cache_read_tokens = usage.get('cache_read_input_tokens', 0)
                    cache_creation_tokens = usage.get('cache_creation_input_tokens', 0)

                    # 性能指标：记录 token 使用量
                    metrics_collector.record_tokens(total_input_tokens, total_output_tokens)

                    # 计算上下文占用情况
                    # Claude Opus 4.5 上下文窗口: 200K tokens
                    context_max = 200000
                    context_used = total_input_tokens + total_output_tokens
                    context_percent = round((context_used / context_max) * 100, 2)

                    tracer.log("usage", {
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                        "cost": cost,
                        "context_used": context_used,
                        "context_max": context_max,
                        "context_percent": context_percent,
                        # API 延迟追踪
                        "duration_ms": duration_ms,
                        "duration_api_ms": duration_api_ms,
                        "sdk_overhead_ms": (duration_ms - duration_api_ms) if duration_ms and duration_api_ms else None,
                        "num_turns": num_turns,
                        # 缓存信息
                        "cache_read_tokens": cache_read_tokens,
                        "cache_creation_tokens": cache_creation_tokens
                    })
                    yield format_sse(SSEEventType.COST_UPDATE, {
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                        "cost": round(cost, 6),
                        "total_cost": round(cost, 6),
                        "context_used": context_used,
                        "context_max": context_max,
                        "context_percent": context_percent
                    })
                continue

            # 处理助手消息 (有 content 属性)
            content = getattr(msg, 'content', None)
            if content and isinstance(content, list):
                # 预先检测并行工具调用：统计此消息中的工具数量
                tool_blocks = [b for b in content if hasattr(b, 'name') and hasattr(b, 'id') and hasattr(b, 'input')]
                is_parallel_batch = len(tool_blocks) > 1
                parallel_group_id = str(uuid.uuid4())[:8] if is_parallel_batch else None

                for block in content:
                    # 处理思考内容 (ThinkingBlock)
                    block_type = getattr(block, 'type', None)
                    if block_type == 'thinking' or hasattr(block, 'thinking'):
                        thinking_text = getattr(block, 'thinking', None) or getattr(block, 'text', None)
                        if thinking_text:
                            # 清理 UTF-8 乱码 (U+FFFD 替换字符)
                            thinking_text = sanitize_utf8_text(thinking_text)
                            if thinking_text:
                                # 增强的 thinking 记录：包含长度和估算 token 数
                                tracer.log("thinking", {
                                    "thinking": thinking_text,
                                    "length": len(thinking_text),
                                    "estimated_tokens": len(thinking_text) // 4  # 粗略估算
                                })
                                yield format_sse(SSEEventType.THINKING_DELTA, {"thinking": thinking_text})

                    elif hasattr(block, 'text') and not block_type:
                        # 文本内容
                        text = block.text
                        if text and text != current_text:
                            delta = text[len(current_text):]
                            # 清理 UTF-8 乱码 (U+FFFD 替换字符)
                            delta = sanitize_utf8_text(delta)
                            if delta:  # 只在有有效内容时发送
                                current_text = text
                                tracer.log("text_delta", {"delta": delta})
                                yield format_sse(SSEEventType.TEXT_DELTA, {"text": delta})
                            # 性能指标：记录首字节时间
                            if not first_token_recorded:
                                metrics_collector.record_first_token(request_start_time)
                                first_token_recorded = True

                    elif hasattr(block, 'name') and hasattr(block, 'id') and hasattr(block, 'input'):
                        # 工具调用开始 (ToolUseBlock 有 name, id, input 属性)
                        tool_id = block.id
                        tool_name = block.name
                        tool_input = getattr(block, 'input', {}) or {}

                        # 检测新一轮迭代（当收到新的工具调用批次时）
                        # 通过检查是否是第一个工具或与上一批次不同来判断
                        if not tool_states or current_text:
                            current_iteration += 1
                            current_text = ""  # 重置文本，准备下一轮

                        tool_states[tool_id] = {
                            "name": tool_name,
                            "input": tool_input,
                            "status": ToolStatus.RUNNING,
                            "iteration": current_iteration,
                            "parallel_group": parallel_group_id,
                            "is_parallel": is_parallel_batch,
                            "start_time": datetime.now()  # 记录开始时间用于计算耗时
                        }
                        tools_used.append(tool_name)

                        # 性能指标：记录工具调用
                        metrics_collector.record_tool_call(tool_name)

                        # 完整输入内容（限制大小）
                        full_input = None
                        input_truncated = False
                        if tool_input:
                            input_str = json.dumps(tool_input, ensure_ascii=False, default=str)
                            if len(input_str) > 5000:
                                full_input = input_str[:5000]
                                input_truncated = True
                            else:
                                full_input = input_str

                        tracer.log("tool_start", {
                            "tool_id": tool_id,
                            "name": tool_name,
                            "input_summary": _summarize_input(tool_name, tool_input),
                            "full_input": full_input,
                            "input_truncated": input_truncated,
                            "input_length": len(json.dumps(tool_input, ensure_ascii=False, default=str)) if tool_input else 0,
                            "iteration": current_iteration,
                            "parallel_group": parallel_group_id,
                            "parallel_count": len(tool_blocks) if is_parallel_batch else 1,
                            "is_mcp": tool_name.startswith("mcp__")
                        })

                        # 检查是否是 Task 工具 (子代理)
                        if tool_name == "Task":
                            current_depth += 1  # 进入子代理，深度增加
                            agent_type = tool_input.get("subagent_type", "unknown")
                            description = tool_input.get("description", "")
                            yield format_sse(SSEEventType.AGENT_SPAWN, {
                                "agent_id": tool_id,
                                "agent_type": agent_type,
                                "description": description,
                                "parent_tool_id": tool_id,
                                "iteration": current_iteration,
                                "depth": current_depth
                            })
                        else:
                            # 发送 hook 事件队列中的 pre_tool 事件 (#23)
                            while hook_events_queue:
                                hook_event = hook_events_queue.pop(0)
                                if hook_event["type"] == "pre_tool":
                                    yield format_sse(SSEEventType.HOOK_PRE_TOOL, {
                                        "hook_type": "PreToolUse",
                                        "tool_name": hook_event["tool_name"],
                                        "action": hook_event.get("action", "allow"),
                                        "message": hook_event.get("message", "")
                                    })
                                elif hook_event["type"] == "post_tool":
                                    yield format_sse(SSEEventType.HOOK_POST_TOOL, {
                                        "hook_type": "PostToolUse",
                                        "tool_name": hook_event["tool_name"],
                                        "message": hook_event.get("message", "")
                                    })

                            yield format_sse(SSEEventType.TOOL_START, {
                                "tool_id": tool_id,
                                "name": tool_name,
                                "input": _summarize_input(tool_name, tool_input),
                                "iteration": current_iteration
                            })

                    elif hasattr(block, 'tool_use_id') and hasattr(block, 'content'):
                        # 工具调用结果 (ToolResultBlock 有 tool_use_id, content 属性)
                        tool_id = block.tool_use_id
                        is_error = getattr(block, 'is_error', False)
                        result_content = block.content

                        status = ToolStatus.ERROR if is_error else ToolStatus.COMPLETED
                        tool_info = tool_states.get(tool_id, {})
                        tool_name = tool_info.get("name", "")

                        # 计算工具执行耗时
                        tool_start_time = tool_info.get("start_time")
                        duration_ms = None
                        if tool_start_time:
                            duration_ms = int((datetime.now() - tool_start_time).total_seconds() * 1000)

                        # 完整输出内容（限制大小以避免 Trace 文件过大）
                        full_output = None
                        output_truncated = False
                        if result_content:
                            content_str = str(result_content)
                            if len(content_str) > 5000:
                                full_output = content_str[:5000]
                                output_truncated = True
                            else:
                                full_output = content_str

                        tracer.log("tool_result", {
                            "tool_id": tool_id,
                            "tool_name": tool_name,
                            "status": status.value,
                            "is_error": is_error,
                            "output_summary": _summarize_output(tool_name, result_content),
                            "full_output": full_output,
                            "output_truncated": output_truncated,
                            "output_length": len(str(result_content)) if result_content else 0,
                            "duration_ms": duration_ms,
                            "iteration": tool_info.get("iteration"),
                            "parallel_group": tool_info.get("parallel_group")
                        })

                        yield format_sse(SSEEventType.TOOL_RESULT, {
                            "tool_id": tool_id,
                            "status": status.value,
                            "output": _summarize_output(tool_name, result_content),
                            "error": str(result_content) if is_error else None
                        })

                        # 如果是 Task 工具完成，递减深度并发送 AGENT_COMPLETE 事件
                        if tool_name == "Task" and current_depth > 0:
                            yield format_sse(SSEEventType.AGENT_COMPLETE, {
                                "agent_id": tool_id
                            })
                            current_depth -= 1
                            tracer.log("agent_complete", {
                                "agent_id": tool_id,
                                "new_depth": current_depth
                            })

        # 消息完成
        tracer.log("complete", {
            "tools_used": list(set(tools_used)),
            "total_tokens": total_input_tokens + total_output_tokens
        })
        tracer.complete()

        # 性能指标：记录请求成功完成
        metrics_collector.record_request_complete(request_start_time, success=True)

        yield format_sse(SSEEventType.MESSAGE_COMPLETE, {
            "tools_used": list(set(tools_used)),
            "total_tokens": total_input_tokens + total_output_tokens,
            "trace_file": tracer.file_path,
            "stop_reason": stop_reason  # (#34)
        })

        # 保存会话
        if session_id not in sessions:
            sessions[session_id] = {
                "created_at": datetime.now().isoformat(),
                "messages": []
            }
        sessions[session_id]["messages"].append({
            "role": "user",
            "content": message
        })
        sessions[session_id]["messages"].append({
            "role": "assistant",
            "content": current_text,
            "tools_used": tools_used,
            "trace_id": trace_id
        })

    except Exception as e:
        tracer.log_error(e)
        # 性能指标：记录错误
        metrics_collector.record_error(type(e).__name__)
        metrics_collector.record_request_complete(request_start_time, success=False)
        yield format_sse(SSEEventType.ERROR, {
            "error": str(e),
            "details": type(e).__name__,
            "trace_file": tracer.file_path
        })


def _summarize_input(tool_name: str, input_data: dict) -> dict:
    """简化工具输入用于显示"""
    if tool_name == "Read":
        return {"file_path": input_data.get("file_path", "")}
    elif tool_name == "Write":
        content = input_data.get("content", "")
        return {
            "file_path": input_data.get("file_path", ""),
            "content_length": len(content),
            "content_preview": content[:100] + "..." if len(content) > 100 else content
        }
    elif tool_name == "Edit":
        return {
            "file_path": input_data.get("file_path", ""),
            "old_string_preview": (input_data.get("old_string", ""))[:50],
            "new_string_preview": (input_data.get("new_string", ""))[:50]
        }
    elif tool_name == "Bash":
        cmd = input_data.get("command", "")
        return {
            "command": cmd[:100] + "..." if len(cmd) > 100 else cmd,
            "description": input_data.get("description", "")
        }
    elif tool_name in ["Glob", "Grep"]:
        return {
            "pattern": input_data.get("pattern", ""),
            "path": input_data.get("path", ".")
        }
    elif tool_name == "Task":
        return {
            "subagent_type": input_data.get("subagent_type", ""),
            "description": input_data.get("description", ""),
            "prompt_preview": (input_data.get("prompt", ""))[:100]
        }
    return input_data


def _summarize_output(tool_name: str, output) -> dict:
    """简化工具输出用于显示"""
    if output is None:
        return {"result": None}

    output_str = str(output)
    if len(output_str) > 500:
        return {
            "preview": output_str[:500] + "...",
            "full_length": len(output_str)
        }
    return {"result": output_str}


# === FastAPI 应用 ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    safe_print("[INFO] Agent Trace Server starting...")
    safe_print(f"[INFO] Trace logs directory: {TRACE_DIR.absolute()}")
    yield
    safe_print("[INFO] Agent Trace Server shutting down...")


app = FastAPI(
    title="Agent Trace Visualization API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置 - 允许前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载沙箱静态文件服务 - 让 Agent 创建的 HTML 文件可以通过 HTTP 访问
app.mount("/sandbox", StaticFiles(directory=str(SANDBOX_ROOT)), name="sandbox")


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    return HealthResponse(status="ok", version="1.0.0")


# === 性能指标 API (#62) ===
@app.get("/api/metrics")
async def get_metrics():
    """获取性能指标"""
    return metrics_collector.get_metrics()


@app.post("/api/metrics/reset")
async def reset_metrics():
    """重置性能指标"""
    metrics_collector.reset()
    return {"status": "reset", "message": "Metrics have been reset"}


# === 预热机制 ===
# 使用 asyncio.Lock 避免多浏览器/多标签页并发预热的竞态条件
_warmup_lock = asyncio.Lock()
warmup_status = {"ready": False, "warming_up": False}


@app.post("/api/warmup")
async def warmup():
    """
    预热 SDK - 临时禁用，直接返回就绪状态。

    原因：Windows 环境下 SDK 子进程可能无法正确继承环境变量，
    导致预热失败。禁用预热不影响核心功能，只是首次响应会慢一些。
    """
    global warmup_status

    # 直接标记为就绪，跳过预热
    warmup_status["ready"] = True
    warmup_status["warming_up"] = False
    safe_print("[INFO] SDK warmup skipped (直接就绪)")
    return {"status": "ready"}


@app.get("/api/warmup/status")
async def warmup_status_check():
    """检查预热状态"""
    return warmup_status


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    发送消息并返回 SSE 流。

    每次请求会生成一个 trace_id，日志保存在 ./traces/{trace_id}.json

    支持对话历史：前端可传递 history 字段来维护多轮对话上下文。
    """
    session_id = request.session_id or str(uuid.uuid4())
    trace_id = f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    # 将 history 转换为字典列表
    history = None
    if request.history:
        history = [{"role": msg.role, "content": msg.content} for msg in request.history]

    return StreamingResponse(
        process_agent_stream(request.message, session_id, trace_id, history),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream; charset=utf-8",
            "X-Session-Id": quote(session_id, safe=''),  # URL 编码以支持非 ASCII 字符
            "X-Trace-Id": trace_id
        }
    )


# === Extended Thinking API (使用 Anthropic API) ===
# Claude Agent SDK 不暴露 thinking 内容，因此使用 Anthropic API 直接调用

# === Think 模式工具定义 ===
THINKING_MODE_TOOLS = [
    {
        "name": "Bash",
        "description": "Execute a bash/shell command. Use for running scripts, git operations, npm commands, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to execute"
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "Read",
        "description": "Read the contents of a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The absolute path to the file to read"
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "Write",
        "description": "Write content to a file. Creates the file if it doesn't exist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The absolute path to the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file"
                }
            },
            "required": ["file_path", "content"]
        }
    },
    {
        "name": "Glob",
        "description": "Find files matching a glob pattern.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "The glob pattern to match files (e.g., '**/*.py')"
                },
                "path": {
                    "type": "string",
                    "description": "The directory to search in (defaults to sandbox root)"
                }
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "WebSearch",
        "description": "Search the web for information. Use this tool when you need to find current information, news, or data from the internet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "WebFetch",
        "description": "Fetch and read the content of a web page. Use this to retrieve specific information from a URL.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch content from"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "TavilySearch",
        "description": "Search the web using Tavily API. Returns comprehensive search results with snippets.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                }
            },
            "required": ["query"]
        }
    }
]


import subprocess
import glob as glob_module


def execute_thinking_tool(tool_name: str, tool_input: dict) -> str:
    """
    执行 Think 模式的工具调用。

    Returns:
        工具执行结果字符串
    """
    # 沙箱检查
    is_allowed, reason = sandbox_check_tool(tool_name, tool_input)
    if not is_allowed:
        return f"[SANDBOX ERROR] {reason}"

    try:
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            # 在沙箱目录中执行命令
            # 设置环境变量确保 Python 输出使用 UTF-8 编码
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(SANDBOX_ROOT),
                capture_output=True,
                text=True,
                timeout=60,
                encoding='utf-8',
                errors='replace',
                env=env
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[STDERR]\n{result.stderr}"
            if result.returncode != 0:
                output += f"\n[Exit code: {result.returncode}]"
            return output or "(no output)"

        elif tool_name == "Read":
            file_path = tool_input.get("file_path", "")
            # 处理相对路径
            if not Path(file_path).is_absolute():
                file_path = str(SANDBOX_ROOT / file_path)

            path = Path(file_path)
            if not path.exists():
                return f"[ERROR] File not found: {file_path}"
            if not path.is_file():
                return f"[ERROR] Not a file: {file_path}"

            content = path.read_text(encoding='utf-8', errors='replace')
            # 限制返回内容长度
            if len(content) > 50000:
                content = content[:50000] + f"\n\n[... truncated, {len(content)} total chars]"
            return content

        elif tool_name == "Write":
            file_path = tool_input.get("file_path", "")
            content = tool_input.get("content", "")

            # 处理相对路径
            if not Path(file_path).is_absolute():
                file_path = str(SANDBOX_ROOT / file_path)

            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
            return f"Successfully wrote {len(content)} characters to {file_path}"

        elif tool_name == "Glob":
            pattern = tool_input.get("pattern", "")
            search_path = tool_input.get("path", "")

            # 处理搜索路径
            if not search_path or not Path(search_path).is_absolute():
                search_path = str(SANDBOX_ROOT / (search_path or ""))

            full_pattern = str(Path(search_path) / pattern)
            matches = glob_module.glob(full_pattern, recursive=True)

            if not matches:
                return "No files found matching the pattern."

            # 限制返回数量
            if len(matches) > 100:
                matches = matches[:100]
                return "\n".join(matches) + f"\n\n[... and more, showing first 100]"
            return "\n".join(matches)

        elif tool_name == "WebSearch":
            query = tool_input.get("query", "")
            if not query:
                return "[ERROR] WebSearch requires a query parameter"

            # 使用已有的 serpapi_search 函数
            result = serpapi_search(query, max_results=10)

            if result.get("error"):
                return f"[ERROR] Search failed: {result['error']}"

            # 格式化搜索结果
            results = result.get("results", [])
            if not results:
                return "No search results found."

            output = []
            for item in results:
                title = item.get("title", "No title")
                url = item.get("url", "")
                snippet = item.get("snippet", "")
                output.append(f"**{title}**\n{url}\n{snippet}\n")

            return "\n".join(output)

        elif tool_name == "WebFetch":
            url = tool_input.get("url", "")
            if not url:
                return "[ERROR] WebFetch requires a url parameter"

            import urllib.request
            import urllib.error

            try:
                # 设置请求头模拟浏览器
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as response:
                    content = response.read().decode('utf-8', errors='replace')

                # 简单的 HTML 清理：移除脚本和样式
                import re
                content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
                content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
                content = re.sub(r'<[^>]+>', ' ', content)  # 移除 HTML 标签
                content = re.sub(r'\s+', ' ', content).strip()  # 压缩空白

                # 限制长度
                if len(content) > 30000:
                    content = content[:30000] + "\n\n[... truncated]"

                return content

            except urllib.error.HTTPError as e:
                return f"[ERROR] HTTP {e.code}: {e.reason}"
            except urllib.error.URLError as e:
                return f"[ERROR] URL Error: {str(e.reason)}"
            except Exception as e:
                return f"[ERROR] Failed to fetch URL: {str(e)}"

        elif tool_name == "TavilySearch":
            query = tool_input.get("query", "")
            if not query:
                return "[ERROR] TavilySearch requires a query parameter"

            import urllib.request
            import urllib.error

            # Tavily API key（从环境变量或硬编码）
            import os
            tavily_key = os.environ.get("TAVILY_API_KEY", "")

            if not tavily_key:
                # 回退到 SerpAPI
                return execute_thinking_tool("WebSearch", {"query": query})

            try:
                api_url = "https://api.tavily.com/search"
                data = json.dumps({
                    "api_key": tavily_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": 10
                }).encode('utf-8')

                req = urllib.request.Request(
                    api_url,
                    data=data,
                    headers={"Content-Type": "application/json"}
                )

                with urllib.request.urlopen(req, timeout=30) as response:
                    result = json.loads(response.read().decode('utf-8'))

                results = result.get("results", [])
                if not results:
                    return "No search results found."

                output = []
                for item in results:
                    title = item.get("title", "No title")
                    url = item.get("url", "")
                    content = item.get("content", "")[:500]  # 限制摘要长度
                    output.append(f"**{title}**\n{url}\n{content}\n")

                return "\n".join(output)

            except Exception as e:
                # 回退到 SerpAPI
                return execute_thinking_tool("WebSearch", {"query": query})

        else:
            return f"[ERROR] Unknown tool: {tool_name}"

    except subprocess.TimeoutExpired:
        return "[ERROR] Command timed out after 60 seconds"
    except Exception as e:
        return f"[ERROR] {type(e).__name__}: {str(e)}"


async def process_thinking_stream(
    message: str,
    thinking_budget: int = 10000,
    enable_tools: bool = True,
    tracer: TraceLogger = None,
    history: list = None
) -> AsyncGenerator[str, None]:
    """
    使用 Anthropic API 处理 Extended Thinking 请求，返回 SSE 流。

    支持工具调用循环：thinking + tools 组合使用。

    Args:
        message: 当前用户消息
        thinking_budget: 思考 token 预算
        enable_tools: 是否启用工具
        tracer: 日志记录器
        history: 对话历史（可选）
    """
    client = Anthropic()

    # 构建消息列表，包含历史对话
    messages = []
    if history:
        # 将历史消息添加到消息列表
        for hist_msg in history:
            messages.append({
                "role": hist_msg.get("role"),
                "content": hist_msg.get("content")
            })

    # 添加当前用户消息
    messages.append({"role": "user", "content": message})

    tools_used = []
    total_input_tokens = 0
    total_output_tokens = 0
    iteration = 0
    max_iterations = 10  # 防止无限循环

    try:
        # 记录请求到 tracer
        if tracer:
            tracer.log("request", {
                "message": message,
                "mode": "thinking",
                "history_length": len(history) if history else 0
            })
            tracer.log("config", {
                "thinking_budget": thinking_budget,
                "enable_tools": enable_tools,
                "max_iterations": max_iterations
            })

        # 发送配置信息
        yield format_sse(SSEEventType.SESSION_CONFIG, {
            "max_turns": max_iterations,
            "permission_mode": "thinking",
            "sandbox_enabled": True,
            "sandbox_root": str(SANDBOX_ROOT),
            "thinking_budget": thinking_budget
        })

        # 使用共享的 system prompt（包含 CLAUDE.md 中的完整行为准则）
        system_prompt = generate_system_prompt()

        while iteration < max_iterations:
            iteration += 1
            safe_print(f"[THINKING] Iteration {iteration}")

            # 构建 API 调用参数
            api_params = {
                "model": config_obj.anthropic_model_thinking,  # 使用配置文件中的 Thinking 模型
                "max_tokens": 16000,
                "system": system_prompt,
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": thinking_budget
                },
                "messages": messages
            }

            # 启用工具时添加工具定义
            if enable_tools:
                api_params["tools"] = THINKING_MODE_TOOLS

            # 使用流式 API
            with client.messages.stream(**api_params) as stream:
                # 收集本轮的内容块
                current_content_blocks = []
                current_tool_use = None

                for event in stream:
                    # 处理内容块开始事件
                    if event.type == "content_block_start":
                        block = event.content_block
                        if block.type == "thinking":
                            current_content_blocks.append({
                                "type": "thinking",
                                "thinking": ""
                            })
                        elif block.type == "text":
                            current_content_blocks.append({
                                "type": "text",
                                "text": ""
                            })
                        elif block.type == "tool_use":
                            current_tool_use = {
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name,
                                "input": {}
                            }
                            current_content_blocks.append(current_tool_use)
                            # 注意：这里不立即发送 TOOL_START，因为此时 input 为空
                            # TOOL_START 将在获取完整响应后发送，以包含完整的工具输入

                    # 处理内容增量事件
                    elif event.type == "content_block_delta":
                        delta = event.delta
                        if hasattr(delta, 'thinking') and current_content_blocks:
                            # 累积 thinking 内容
                            for block in current_content_blocks:
                                if block.get("type") == "thinking":
                                    block["thinking"] += delta.thinking
                            # 流式发送给前端（不记录到 tracer）
                            yield format_sse(SSEEventType.THINKING_DELTA, {
                                "thinking": delta.thinking
                            })
                        elif hasattr(delta, 'text') and current_content_blocks:
                            # 累积 text 内容
                            for block in current_content_blocks:
                                if block.get("type") == "text":
                                    block["text"] += delta.text
                            # 流式发送给前端（不记录到 tracer）
                            yield format_sse(SSEEventType.TEXT_DELTA, {
                                "text": delta.text
                            })
                        elif hasattr(delta, 'partial_json') and current_tool_use:
                            # 工具输入的增量 JSON
                            pass  # partial_json 不需要单独处理

                    # 内容块结束
                    elif event.type == "content_block_stop":
                        pass

                # 获取完整响应
                response = stream.get_final_message()

            # 记录完整的 thinking 和 text 到 tracer（而非逐字记录）
            if tracer:
                for block in response.content:
                    if block.type == "thinking":
                        tracer.log("thinking", {
                            "thinking": block.thinking,
                            "length": len(block.thinking)
                        })
                    elif block.type == "text":
                        tracer.log("text", {
                            "text": block.text,
                            "length": len(block.text)
                        })

            # 更新 token 计数
            if response.usage:
                total_input_tokens += response.usage.input_tokens
                total_output_tokens += response.usage.output_tokens

            # 检查是否有工具调用
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            if not tool_use_blocks:
                # 没有工具调用，结束循环
                safe_print(f"[THINKING] No tool calls, ending. Stop reason: {response.stop_reason}")
                break

            # 处理工具调用
            safe_print(f"[THINKING] Processing {len(tool_use_blocks)} tool calls")

            # 构建 assistant 消息（保留 thinking blocks）
            assistant_content = []
            for block in response.content:
                if block.type == "thinking":
                    assistant_content.append({
                        "type": "thinking",
                        "thinking": block.thinking
                    })
                elif block.type == "text":
                    assistant_content.append({
                        "type": "text",
                        "text": block.text
                    })
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })

            messages.append({"role": "assistant", "content": assistant_content})

            # 执行工具并收集结果
            tool_results = []
            for tool_block in tool_use_blocks:
                tool_name = tool_block.name
                tool_input = tool_block.input
                tool_id = tool_block.id

                safe_print(f"[THINKING] Executing tool: {tool_name}")
                tools_used.append(tool_name)

                # 记录工具开始到 tracer（包含完整输入）
                if tracer:
                    tracer.log("tool_start", {
                        "tool_id": tool_id,
                        "name": tool_name,
                        "input": tool_input,
                        "iteration": iteration
                    })

                # 发送工具开始事件（使用 tool_id 字段名，与 Normal mode 一致）
                yield format_sse(SSEEventType.TOOL_START, {
                    "tool_id": tool_id,
                    "name": tool_name,
                    "input": _summarize_input(tool_name, tool_input),
                    "iteration": iteration
                })

                # 执行工具
                result = execute_thinking_tool(tool_name, tool_input)
                is_error = result.startswith("[ERROR]") or result.startswith("[SANDBOX ERROR]")

                # 记录工具结果到 tracer
                if tracer:
                    tracer.log("tool_result", {
                        "tool_id": tool_id,
                        "name": tool_name,
                        "status": "error" if is_error else "success",
                        "is_error": is_error
                    })

                # 发送工具完成事件
                yield format_sse(SSEEventType.TOOL_RESULT, {
                    "tool_id": tool_id,
                    "status": "error" if is_error else "completed",
                    "output": result[:500] + "..." if len(result) > 500 else result,
                    "error": result if is_error else None
                })

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": result
                })

            # 添加工具结果到消息
            messages.append({"role": "user", "content": tool_results})

        # 发送费用信息
        yield format_sse(SSEEventType.COST_UPDATE, {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "cost": 0,
            "total_cost": 0
        })

        yield format_sse(SSEEventType.MESSAGE_COMPLETE, {
            "tools_used": list(set(tools_used)),
            "total_tokens": total_input_tokens + total_output_tokens,
            "stop_reason": "end_turn",
            "iterations": iteration
        })

        # 记录完成到 tracer
        if tracer:
            tracer.log("usage", {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens
            })
            tracer.log("complete", {
                "tools_used": list(set(tools_used)),
                "total_tokens": total_input_tokens + total_output_tokens,
                "iterations": iteration
            })
            tracer.complete()

    except Exception as e:
        safe_print(f"[ERROR] Extended Thinking failed: {e}")
        traceback.print_exc()
        # 记录错误到 tracer
        if tracer:
            tracer.log_error(e)
        yield format_sse(SSEEventType.ERROR, {
            "error": str(e),
            "details": type(e).__name__
        })


@app.post("/api/chat/thinking")
async def chat_with_thinking(request: ChatRequest):
    """
    使用 Extended Thinking 模式对话，支持工具调用。

    与 /api/chat 不同，此端点使用 Anthropic API 直接调用，
    可以获取完整的 thinking 内容，同时支持以下工具：
    - Bash: 执行 shell 命令
    - Read: 读取文件
    - Write: 写入文件
    - Glob: 文件模式匹配

    所有文件操作都限制在沙箱目录内。

    支持对话历史：前端可传递 history 字段来维护多轮对话上下文。
    """
    # 从请求中获取 thinking_budget，默认 10000
    thinking_budget = getattr(request, 'thinking_budget', 10000) or 10000

    # 创建 tracer 用于记录请求
    trace_id = f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    tracer = TraceLogger(trace_id)

    # 将 history 转换为字典列表
    history = None
    if request.history:
        history = [{"role": msg.role, "content": msg.content} for msg in request.history]

    return StreamingResponse(
        process_thinking_stream(
            request.message,
            thinking_budget,
            tracer=tracer,
            history=history
        ),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream; charset=utf-8",
            "X-Trace-Id": trace_id
        }
    )


@app.get("/api/traces")
async def list_traces(
    status: str = None,
    has_errors: bool = None,
    has_sandbox_blocks: bool = None,
    search: str = None,
    limit: int = 100,
    offset: int = 0
):
    """列出所有 trace 日志，支持过滤和搜索

    Query Parameters:
        status: 过滤状态 (completed, error, running)
        has_errors: 是否有错误
        has_sandbox_blocks: 是否有沙箱拦截
        search: 搜索用户消息内容
        limit: 返回数量限制 (默认100)
        offset: 分页偏移
    """
    traces = []
    for f in TRACE_DIR.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as file:
                data = json.load(file)
                metadata = data.get("metadata", {})
                stats = metadata.get("stats", {})

                # 提取用户消息摘要
                summary = ""
                full_message = ""
                for event in data.get("events", []):
                    if event.get("event_type") == "request":
                        full_message = event.get("data", {}).get("message", "")
                        summary = full_message[:50] + "..." if len(full_message) > 50 else full_message
                        break

                # 应用过滤条件
                trace_status = metadata.get("status", "unknown")
                if status and trace_status != status:
                    continue

                error_count = stats.get("errors", 0)
                if has_errors is True and error_count == 0:
                    continue
                if has_errors is False and error_count > 0:
                    continue

                sandbox_blocks = stats.get("sandbox_blocks", 0)
                if has_sandbox_blocks is True and sandbox_blocks == 0:
                    continue
                if has_sandbox_blocks is False and sandbox_blocks > 0:
                    continue

                # 搜索过滤
                if search and search.lower() not in full_message.lower():
                    continue

                traces.append({
                    "trace_id": metadata["trace_id"],
                    "start_time": metadata["start_time"],
                    "status": trace_status,
                    "summary": summary,
                    "duration_ms": metadata.get("duration_ms"),
                    # 增强的统计信息
                    "stats": {
                        "tool_calls": stats.get("tool_calls", 0),
                        "iterations": stats.get("iterations", 0),
                        "sub_agents": stats.get("sub_agents", 0),
                        "errors": error_count,
                        "sandbox_blocks": sandbox_blocks,
                        "hooks_triggered": stats.get("hooks_triggered", 0),
                        "thinking_blocks": stats.get("thinking_blocks", 0)
                    }
                })
        except (json.JSONDecodeError, KeyError, IOError):
            pass  # 跳过无效的 trace 文件

    # 排序并分页
    sorted_traces = sorted(traces, key=lambda x: x["start_time"], reverse=True)
    return {
        "total": len(sorted_traces),
        "limit": limit,
        "offset": offset,
        "traces": sorted_traces[offset:offset + limit]
    }


@app.get("/api/traces/{trace_id}")
async def get_trace(trace_id: str):
    """获取指定 trace 日志"""
    trace_file = TRACE_DIR / f"{trace_id}.json"
    if not trace_file.exists():
        raise HTTPException(status_code=404, detail="Trace not found")

    with open(trace_file, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/traces/{trace_id}/timeline")
async def get_trace_timeline(trace_id: str):
    """获取 trace 的工具执行时间线视图

    返回格式化的时间线数据，用于可视化展示：
    - 工具调用的开始/结束时间
    - 并行执行的工具分组
    - 迭代轮次标记
    - 沙箱拦截事件
    """
    trace_file = TRACE_DIR / f"{trace_id}.json"
    if not trace_file.exists():
        raise HTTPException(status_code=404, detail="Trace not found")

    with open(trace_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    events = data.get("events", [])
    metadata = data.get("metadata", {})

    # 构建时间线数据
    timeline = []
    tool_starts = {}  # 记录工具开始时间 {tool_id: event}

    for event in events:
        event_type = event.get("event_type")
        elapsed_ms = event.get("elapsed_ms", 0)
        event_data = event.get("data", {})

        if event_type == "tool_start":
            tool_id = event_data.get("tool_id")
            tool_starts[tool_id] = {
                "start_ms": elapsed_ms,
                "name": event_data.get("name"),
                "iteration": event_data.get("iteration"),
                "parallel_group": event_data.get("parallel_group"),
                "input_summary": event_data.get("input", {})
            }

        elif event_type == "tool_result":
            tool_id = event_data.get("tool_id")
            start_info = tool_starts.get(tool_id)
            if start_info:
                timeline.append({
                    "type": "tool",
                    "tool_id": tool_id,
                    "name": start_info["name"],
                    "start_ms": start_info["start_ms"],
                    "end_ms": elapsed_ms,
                    "duration_ms": event_data.get("duration_ms") or (elapsed_ms - start_info["start_ms"]),
                    "status": event_data.get("status"),
                    "iteration": start_info["iteration"],
                    "parallel_group": start_info["parallel_group"],
                    "is_error": event_data.get("is_error", False)
                })

        elif event_type == "sandbox_block":
            timeline.append({
                "type": "sandbox_block",
                "tool_name": event_data.get("tool_name"),
                "time_ms": elapsed_ms,
                "reason": event_data.get("reason"),
                "blocked_path": event_data.get("blocked_path")
            })

        elif event_type == "thinking":
            timeline.append({
                "type": "thinking",
                "time_ms": elapsed_ms,
                "length": event_data.get("length", len(event_data.get("thinking", ""))),
                "estimated_tokens": event_data.get("estimated_tokens", 0)
            })

    # 计算迭代分组
    iterations = {}
    for item in timeline:
        if item["type"] == "tool" and "iteration" in item:
            iteration = item["iteration"]
            if iteration not in iterations:
                iterations[iteration] = {"start_ms": item["start_ms"], "end_ms": item["end_ms"], "tools": []}
            iterations[iteration]["tools"].append(item["tool_id"])
            iterations[iteration]["end_ms"] = max(iterations[iteration]["end_ms"], item["end_ms"])

    return {
        "trace_id": trace_id,
        "total_duration_ms": metadata.get("duration_ms"),
        "stats": metadata.get("stats", {}),
        "timeline": timeline,
        "iterations": [{"iteration": k, **v} for k, v in sorted(iterations.items())]
    }


@app.get("/api/traces/{trace_id}/download")
async def download_trace(trace_id: str):
    """下载 trace 日志文件"""
    trace_file = TRACE_DIR / f"{trace_id}.json"
    if not trace_file.exists():
        raise HTTPException(status_code=404, detail="Trace not found")

    return FileResponse(
        trace_file,
        media_type="application/json",
        filename=f"{trace_id}.json"
    )


@app.get("/api/sessions/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str):
    """获取会话信息"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    return SessionInfo(
        session_id=session_id,
        created_at=session["created_at"],
        message_count=len(session["messages"])
    )


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    del sessions[session_id]
    return {"status": "deleted"}


# === Skills API (#22) ===
SKILLS_DIR = Path(__file__).parent.parent.parent / ".claude" / "skills"


def parse_skill_metadata(content: str) -> dict:
    """解析 SKILL.md 文件的 YAML frontmatter"""
    if not content.startswith("---"):
        return {}

    try:
        # 找到 frontmatter 的结束位置
        end_idx = content.find("---", 3)
        if end_idx == -1:
            return {}

        frontmatter = content[3:end_idx].strip()
        metadata = {}
        for line in frontmatter.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                metadata[key] = value
        return metadata
    except Exception:
        return {}


@app.get("/api/skills")
async def list_skills():
    """
    列出所有可用的 Skills (#22)

    扫描 .claude/skills 目录，返回所有 Skill 的元数据。
    """
    skills = []

    if not SKILLS_DIR.exists():
        return {"skills": [], "skills_dir": str(SKILLS_DIR), "message": "Skills directory not found"}

    for skill_dir in SKILLS_DIR.iterdir():
        if not skill_dir.is_dir():
            continue

        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        try:
            with open(skill_file, "r", encoding="utf-8") as f:
                content = f.read()

            metadata = parse_skill_metadata(content)

            # 提取 Skill 内容（去掉 frontmatter）
            content_start = content.find("---", 3)
            if content_start != -1:
                skill_content = content[content_start + 3:].strip()
            else:
                skill_content = content

            skills.append({
                "id": skill_dir.name,
                "name": metadata.get("name", skill_dir.name),
                "description": metadata.get("description", ""),
                "allowed_tools": metadata.get("allowed-tools", "").split(", ") if metadata.get("allowed-tools") else [],
                "file_path": str(skill_file),
                "content_preview": skill_content[:500] + "..." if len(skill_content) > 500 else skill_content
            })
        except Exception as e:
            safe_print(f"[WARN] Failed to parse skill {skill_dir.name}: {e}")

    return {
        "skills": skills,
        "skills_dir": str(SKILLS_DIR),
        "count": len(skills)
    }


@app.get("/api/skills/{skill_id}")
async def get_skill(skill_id: str):
    """获取指定 Skill 的详细信息"""
    skill_file = SKILLS_DIR / skill_id / "SKILL.md"

    if not skill_file.exists():
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")

    with open(skill_file, "r", encoding="utf-8") as f:
        content = f.read()

    metadata = parse_skill_metadata(content)

    # 提取完整内容
    content_start = content.find("---", 3)
    if content_start != -1:
        skill_content = content[content_start + 3:].strip()
    else:
        skill_content = content

    return {
        "id": skill_id,
        "name": metadata.get("name", skill_id),
        "description": metadata.get("description", ""),
        "allowed_tools": metadata.get("allowed-tools", "").split(", ") if metadata.get("allowed-tools") else [],
        "file_path": str(skill_file),
        "content": skill_content,
        "raw": content
    }


# === WebSearch 替代方案 (#6) ===
# SDK 内置的 WebSearch 在某些环境下会失败 (exit code 1)
# 使用 SerpAPI 作为替代搜索后端

import urllib.request
import urllib.parse


def serpapi_search(query: str, max_results: int = 5) -> dict:
    """
    使用 SerpAPI 进行网络搜索

    Args:
        query: 搜索关键词
        max_results: 最大结果数

    Returns:
        搜索结果字典
    """
    try:
        # 从环境变量读取 API Key
        serpapi_key = os.environ.get("SERPAPI_API_KEY", "")
        if not serpapi_key:
            return {"error": "SERPAPI_API_KEY 未配置", "results": []}

        encoded_query = urllib.parse.quote(query)
        url = f"https://serpapi.com/search.json?q={encoded_query}&api_key={serpapi_key}&num={max_results}"

        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        results = []
        organic_results = data.get("organic_results", [])

        for i, item in enumerate(organic_results[:max_results]):
            results.append({
                "position": i + 1,
                "title": item.get("title", "无标题"),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", "")[:200],
                "displayed_link": item.get("displayed_link", "")
            })

        return {
            "success": True,
            "query": query,
            "results": results,
            "total_results": len(results)
        }

    except urllib.error.URLError as e:
        return {
            "success": False,
            "query": query,
            "error": f"网络错误: {str(e)}",
            "results": []
        }
    except Exception as e:
        return {
            "success": False,
            "query": query,
            "error": f"搜索出错: {str(e)}",
            "results": []
        }


class SearchRequest:
    """搜索请求模型"""
    pass


from pydantic import BaseModel


class SearchRequestModel(BaseModel):
    query: str
    max_results: int = 5


@app.post("/api/search")
async def web_search(request: SearchRequestModel):
    """
    网络搜索 API (#6)

    当 SDK 内置的 WebSearch 工具失败时，可以使用此端点作为替代。
    使用 SerpAPI 作为搜索后端。

    Request body:
        query: 搜索关键词
        max_results: 最大结果数 (默认 5)

    Returns:
        搜索结果列表
    """
    safe_print(f"[SEARCH] 搜索请求: {request.query}")
    result = serpapi_search(request.query, request.max_results)

    if result["success"]:
        safe_print(f"[SEARCH] 找到 {result['total_results']} 条结果")
    else:
        safe_print(f"[SEARCH] 搜索失败: {result.get('error', 'Unknown error')}")

    return result


@app.get("/api/search")
async def web_search_get(query: str, max_results: int = 5):
    """
    网络搜索 API (GET 方法)

    方便在浏览器中直接测试。
    """
    return serpapi_search(query, max_results)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
