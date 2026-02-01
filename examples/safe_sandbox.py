#!/usr/bin/env python3
"""
Safe Sandbox - Hook 实战示例 (安全控制)

本示例展示 Hook 机制在**安全沙箱**场景中的应用：
- 文件路径白名单/黑名单
- 危险命令拦截
- 敏感信息检测
- 操作频率限制

这是企业级 Agent 部署的核心安全机制。

核心概念:
- PreToolUse Hook: 在操作执行前进行安全检查
- 返回 continue_: False 拦截危险操作
- 多层防护: 路径检查 + 命令检查 + 内容检查

Run: python examples/safe_sandbox.py
"""

import asyncio
import sys
import io
import re
import os
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Set, Dict, Any, Callable
from enum import Enum
from dotenv import load_dotenv
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, HookMatcher

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

load_dotenv()


# ============================================================
# Security Policy
# ============================================================

class BlockReason(Enum):
    """拦截原因"""
    PATH_BLACKLIST = "path_in_blacklist"
    PATH_NOT_IN_WHITELIST = "path_not_in_whitelist"
    DANGEROUS_COMMAND = "dangerous_command"
    SENSITIVE_CONTENT = "sensitive_content"
    RATE_LIMIT = "rate_limit_exceeded"
    EXTENSION_BLOCKED = "file_extension_blocked"


@dataclass
class SecurityPolicy:
    """
    安全策略配置

    可以根据不同场景配置不同的策略。
    """

    # 文件路径白名单 (相对于工作目录)
    # 设为 None 表示不启用白名单
    allowed_paths: Optional[List[str]] = None

    # 文件路径黑名单 (支持通配符模式)
    blocked_paths: List[str] = field(default_factory=lambda: [
        ".env",
        ".env.*",
        "**/credentials*",
        "**/secrets*",
        "**/*.pem",
        "**/*.key",
        "**/password*",
        "**/token*",
        "**/.git/**",
        "**/node_modules/**",
    ])

    # 允许的文件扩展名 (设为 None 表示不限制)
    allowed_extensions: Optional[List[str]] = None

    # 禁止的文件扩展名
    blocked_extensions: List[str] = field(default_factory=lambda: [
        ".exe", ".dll", ".so", ".dylib",
        ".sh", ".bat", ".cmd", ".ps1",
    ])

    # 危险命令模式
    dangerous_commands: List[str] = field(default_factory=lambda: [
        r"rm\s+-rf",
        r"rm\s+-r\s+/",
        r"rmdir\s+/s",
        r"del\s+/[fqs]",
        r"format\s+",
        r"mkfs\.",
        r"dd\s+if=",
        r">\s*/dev/",
        r"shutdown",
        r"reboot",
        r"halt",
        r"init\s+0",
        r"curl.*\|\s*(bash|sh)",
        r"wget.*\|\s*(bash|sh)",
        r"eval\s*\(",
        r"exec\s*\(",
    ])

    # 敏感内容模式 (检测写入内容)
    sensitive_patterns: List[str] = field(default_factory=lambda: [
        r"(?i)password\s*[=:]\s*['\"]?\w+",
        r"(?i)api[_-]?key\s*[=:]\s*['\"]?\w+",
        r"(?i)secret\s*[=:]\s*['\"]?\w+",
        r"(?i)token\s*[=:]\s*['\"]?\w+",
        r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",
        r"(?i)aws[_-]?access[_-]?key",
        r"(?i)aws[_-]?secret",
    ])

    # 操作频率限制
    max_operations_per_minute: int = 60
    max_writes_per_minute: int = 20
    max_bash_per_minute: int = 10


# ============================================================
# Security Guard
# ============================================================

class SecurityGuard:
    """
    安全守卫

    基于策略检查每个操作，决定是否允许执行。
    """

    def __init__(self, policy: SecurityPolicy, work_dir: Optional[str] = None):
        self.policy = policy
        self.work_dir = Path(work_dir).resolve() if work_dir else Path.cwd().resolve()

        # 操作计数 (用于频率限制)
        self._operation_times: List[float] = []
        self._write_times: List[float] = []
        self._bash_times: List[float] = []

        # 拦截记录
        self.blocked_operations: List[Dict[str, Any]] = []

    def check_operation(
        self,
        tool_name: str,
        tool_input: Dict[str, Any]
    ) -> tuple[bool, Optional[BlockReason], str]:
        """
        检查操作是否安全

        Returns:
            (allowed, reason, message)
        """
        import time
        import fnmatch

        current_time = time.time()

        # 1. 频率限制检查
        self._cleanup_old_times(current_time)

        if len(self._operation_times) >= self.policy.max_operations_per_minute:
            return False, BlockReason.RATE_LIMIT, "Too many operations per minute"

        if tool_name == "Write" and len(self._write_times) >= self.policy.max_writes_per_minute:
            return False, BlockReason.RATE_LIMIT, "Too many write operations per minute"

        if tool_name == "Bash" and len(self._bash_times) >= self.policy.max_bash_per_minute:
            return False, BlockReason.RATE_LIMIT, "Too many bash operations per minute"

        # 2. 路径检查 (Read, Write, Edit, Glob)
        path_fields = ["file_path", "path"]
        for field in path_fields:
            if field in tool_input:
                path = tool_input[field]
                allowed, reason, msg = self._check_path(path)
                if not allowed:
                    return False, reason, msg

        # 3. 命令检查 (Bash)
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            allowed, reason, msg = self._check_command(command)
            if not allowed:
                return False, reason, msg

        # 4. 内容检查 (Write)
        if tool_name == "Write":
            content = tool_input.get("content", "")
            allowed, reason, msg = self._check_content(content)
            if not allowed:
                return False, reason, msg

        # 记录操作时间
        self._operation_times.append(current_time)
        if tool_name == "Write":
            self._write_times.append(current_time)
        if tool_name == "Bash":
            self._bash_times.append(current_time)

        return True, None, ""

    def _check_path(self, path: str) -> tuple[bool, Optional[BlockReason], str]:
        """检查文件路径"""
        import fnmatch

        try:
            # 解析路径
            target_path = Path(path)
            if not target_path.is_absolute():
                target_path = self.work_dir / target_path
            target_path = target_path.resolve()

            # 检查扩展名
            ext = target_path.suffix.lower()
            if ext in self.policy.blocked_extensions:
                return False, BlockReason.EXTENSION_BLOCKED, f"Extension blocked: {ext}"

            if self.policy.allowed_extensions:
                if ext not in self.policy.allowed_extensions:
                    return False, BlockReason.EXTENSION_BLOCKED, f"Extension not allowed: {ext}"

            # 获取相对路径用于模式匹配
            try:
                rel_path = target_path.relative_to(self.work_dir)
                rel_str = str(rel_path).replace("\\", "/")
            except ValueError:
                rel_str = str(target_path).replace("\\", "/")

            # 检查黑名单
            for pattern in self.policy.blocked_paths:
                if fnmatch.fnmatch(rel_str, pattern):
                    return False, BlockReason.PATH_BLACKLIST, f"Path blocked by pattern: {pattern}"
                # 也检查文件名
                if fnmatch.fnmatch(target_path.name, pattern):
                    return False, BlockReason.PATH_BLACKLIST, f"Filename blocked by pattern: {pattern}"

            # 检查白名单 (如果启用)
            if self.policy.allowed_paths is not None:
                in_whitelist = False
                for allowed in self.policy.allowed_paths:
                    allowed_path = (self.work_dir / allowed).resolve()
                    try:
                        target_path.relative_to(allowed_path)
                        in_whitelist = True
                        break
                    except ValueError:
                        continue

                if not in_whitelist:
                    return False, BlockReason.PATH_NOT_IN_WHITELIST, f"Path not in whitelist: {path}"

        except Exception as e:
            return False, BlockReason.PATH_BLACKLIST, f"Path check error: {e}"

        return True, None, ""

    def _check_command(self, command: str) -> tuple[bool, Optional[BlockReason], str]:
        """检查 Bash 命令"""
        for pattern in self.policy.dangerous_commands:
            if re.search(pattern, command, re.IGNORECASE):
                return False, BlockReason.DANGEROUS_COMMAND, f"Dangerous command pattern: {pattern}"

        return True, None, ""

    def _check_content(self, content: str) -> tuple[bool, Optional[BlockReason], str]:
        """检查写入内容"""
        for pattern in self.policy.sensitive_patterns:
            if re.search(pattern, content):
                return False, BlockReason.SENSITIVE_CONTENT, f"Sensitive content detected"

        return True, None, ""

    def _cleanup_old_times(self, current_time: float):
        """清理超过 1 分钟的记录"""
        cutoff = current_time - 60

        self._operation_times = [t for t in self._operation_times if t > cutoff]
        self._write_times = [t for t in self._write_times if t > cutoff]
        self._bash_times = [t for t in self._bash_times if t > cutoff]

    def record_blocked(self, tool_name: str, tool_input: Dict, reason: BlockReason, message: str):
        """记录被拦截的操作"""
        self.blocked_operations.append({
            "timestamp": datetime.now().isoformat(),
            "tool_name": tool_name,
            "tool_input_preview": str(tool_input)[:100],
            "reason": reason.value,
            "message": message,
        })


# ============================================================
# Sandbox Agent
# ============================================================

class SandboxAgent:
    """
    安全沙箱 Agent

    所有操作都经过安全检查，危险操作会被拦截。
    """

    def __init__(
        self,
        policy: Optional[SecurityPolicy] = None,
        work_dir: Optional[str] = None
    ):
        self.policy = policy or SecurityPolicy()
        self.guard = SecurityGuard(self.policy, work_dir)

    def _build_options(self) -> ClaudeAgentOptions:
        """构建带安全检查的选项"""

        async def security_hook(hook_input, tool_use_id, context):
            tool_name = hook_input["tool_name"]
            tool_input = hook_input["tool_input"]

            # 执行安全检查
            allowed, reason, message = self.guard.check_operation(tool_name, tool_input)

            if not allowed:
                # 记录拦截
                self.guard.record_blocked(tool_name, tool_input, reason, message)

                # 打印拦截信息
                print(f"\n  [BLOCKED] {tool_name}")
                print(f"            Reason: {reason.value}")
                print(f"            Detail: {message}")

                return {"continue_": False}

            # 允许执行
            print(f"  [OK] {tool_name}", end="")
            return {"continue_": True}

        async def post_hook(hook_input, tool_use_id, context):
            print(" -> done")
            return {"continue_": True}

        hooks = {
            "PreToolUse": [HookMatcher(matcher=None, hooks=[security_hook])],
            "PostToolUse": [HookMatcher(matcher=None, hooks=[post_hook])],
        }

        return ClaudeAgentOptions(
            model="sonnet",
            permission_mode="bypassPermissions",
            allowed_tools=["Read", "Glob", "Grep", "Write", "Bash"],
            hooks=hooks,
            max_turns=15,
        )

    async def run(self, prompt: str) -> str:
        """在沙箱中执行任务"""

        print("\n[Sandbox] Security Policy Active")
        print(f"  - Blocked paths: {len(self.policy.blocked_paths)} patterns")
        print(f"  - Dangerous commands: {len(self.policy.dangerous_commands)} patterns")
        print(f"  - Rate limit: {self.policy.max_operations_per_minute} ops/min")
        print("-" * 60)

        options = self._build_options()
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

        # 打印拦截统计
        if self.guard.blocked_operations:
            print("\n" + "=" * 60)
            print(f"SECURITY REPORT: {len(self.guard.blocked_operations)} operations blocked")
            print("=" * 60)
            for op in self.guard.blocked_operations:
                print(f"  - {op['tool_name']}: {op['reason']}")
                print(f"    {op['message']}")

        return result_text


# ============================================================
# Demo Functions
# ============================================================

async def demo_path_protection():
    """演示路径保护"""
    print("\n" + "=" * 60)
    print("Demo 1: Path Protection")
    print("=" * 60)
    print()
    print("测试路径黑名单保护，尝试读取敏感文件...")
    print()

    agent = SandboxAgent()

    # 尝试读取敏感文件
    prompt = """请尝试完成以下任务:
1. 读取 .env 文件的内容
2. 读取 src/v0_hello.py 文件的内容

报告哪些操作成功，哪些被拦截。"""

    result = await agent.run(prompt)
    print("\n--- Result ---")
    print(result[:300] if result else "(No output)")


async def demo_command_protection():
    """演示危险命令拦截"""
    print("\n" + "=" * 60)
    print("Demo 2: Dangerous Command Protection")
    print("=" * 60)
    print()
    print("测试危险命令拦截...")
    print()

    agent = SandboxAgent()

    # 尝试执行危险命令
    prompt = """请尝试执行以下命令:
1. 运行 echo "Hello World" 命令
2. 运行 rm -rf /tmp/test 命令

报告哪些命令成功执行，哪些被拦截。"""

    result = await agent.run(prompt)
    print("\n--- Result ---")
    print(result[:300] if result else "(No output)")


async def demo_whitelist_mode():
    """演示白名单模式"""
    print("\n" + "=" * 60)
    print("Demo 3: Whitelist Mode")
    print("=" * 60)
    print()
    print("启用路径白名单，只允许访问特定目录...")
    print()

    # 创建严格的白名单策略
    strict_policy = SecurityPolicy(
        allowed_paths=["src/", "examples/"],  # 只允许这两个目录
        blocked_paths=[],  # 清空黑名单，完全依赖白名单
    )

    agent = SandboxAgent(policy=strict_policy)

    prompt = """请尝试完成以下任务:
1. 列出 src/ 目录的文件
2. 列出 tests/ 目录的文件
3. 读取 README.md 文件

报告哪些操作成功，哪些被拦截。"""

    result = await agent.run(prompt)
    print("\n--- Result ---")
    print(result[:300] if result else "(No output)")


async def demo_content_protection():
    """演示敏感内容检测"""
    print("\n" + "=" * 60)
    print("Demo 4: Sensitive Content Detection")
    print("=" * 60)
    print()
    print("测试写入敏感内容的拦截...")
    print()

    agent = SandboxAgent()

    # 尝试写入敏感内容
    prompt = """请创建两个文件:
1. 创建 sandbox_test/normal.txt，内容为 "Hello World"
2. 创建 sandbox_test/config.txt，内容为 "password=secret123"

报告哪些操作成功，哪些被拦截。"""

    result = await agent.run(prompt)
    print("\n--- Result ---")
    print(result[:300] if result else "(No output)")

    # 清理测试文件
    import shutil
    try:
        shutil.rmtree("sandbox_test")
    except:
        pass


# ============================================================
# Main
# ============================================================

async def main():
    print("=" * 60)
    print("Safe Sandbox - Hook 实战示例 (安全控制)")
    print("=" * 60)
    print()
    print("本示例展示如何使用 Hook 实现安全沙箱:")
    print("- 文件路径白名单/黑名单")
    print("- 危险命令拦截")
    print("- 敏感内容检测")
    print("- 操作频率限制")
    print()

    # Demo 1: 路径保护
    await demo_path_protection()

    # Demo 2: 命令保护
    await demo_command_protection()

    # Demo 3: 白名单模式
    await demo_whitelist_mode()

    # Demo 4: 内容保护
    await demo_content_protection()

    print("\n" + "=" * 60)
    print("All Demos Complete!")
    print("=" * 60)
    print()
    print("Key Takeaways:")
    print("1. PreToolUse Hook 可以在操作执行前进行安全检查")
    print("2. 返回 continue_: False 可以拦截危险操作")
    print("3. 多层防护 (路径 + 命令 + 内容) 提供全面保护")
    print("4. 白名单模式适合严格受控环境")


if __name__ == "__main__":
    asyncio.run(main())
