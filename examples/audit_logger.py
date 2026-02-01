#!/usr/bin/env python3
"""
Audit Logger - Hook 实战示例 (观测性)

本示例展示 Hook 机制在**审计合规**场景中的应用：
- 记录所有 Agent 操作到结构化日志
- 生成审计报告（统计、时间线、风险评估）
- 支持多种输出格式（控制台、JSON 文件）

这是企业级 Agent 部署的关键能力：可追溯、可审计、可复现。

核心概念:
- PreToolUse Hook: 记录操作意图
- PostToolUse Hook: 记录操作结果
- 结构化日志: 便于分析和查询

Run: python examples/audit_logger.py
"""

import asyncio
import sys
import io
import json
import os
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from enum import Enum
from dotenv import load_dotenv
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, HookMatcher

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

load_dotenv()


# ============================================================
# Audit Data Structures
# ============================================================

class RiskLevel(Enum):
    """操作风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditRecord:
    """单条审计记录"""
    timestamp: str
    event_type: str  # "pre_tool_use" | "post_tool_use" | "blocked"
    tool_name: str
    tool_use_id: str
    risk_level: str
    details: Dict[str, Any]
    duration_ms: Optional[float] = None
    success: Optional[bool] = None
    error: Optional[str] = None


@dataclass
class AuditSession:
    """审计会话 - 包含一次 Agent 交互的所有记录"""
    session_id: str
    start_time: str
    end_time: Optional[str] = None
    prompt: str = ""
    records: List[AuditRecord] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# Audit Logger Class
# ============================================================

class AuditLogger:
    """
    审计日志记录器

    功能:
    - 记录所有工具调用的详细信息
    - 评估操作风险等级
    - 生成审计报告
    - 支持导出为 JSON
    """

    # 风险评估规则
    RISK_RULES = {
        # 高风险操作
        "Write": RiskLevel.HIGH,
        "Edit": RiskLevel.HIGH,
        "Bash": RiskLevel.CRITICAL,
        "NotebookEdit": RiskLevel.MEDIUM,
        # 低风险操作
        "Read": RiskLevel.LOW,
        "Glob": RiskLevel.LOW,
        "Grep": RiskLevel.LOW,
        # 默认
        "default": RiskLevel.MEDIUM,
    }

    # 敏感路径模式
    SENSITIVE_PATTERNS = [
        ".env", "credentials", "secret", "password", "token",
        "private", "key", ".pem", ".key", "config"
    ]

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir) if output_dir else Path("audit_logs")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.current_session: Optional[AuditSession] = None
        self._tool_start_times: Dict[str, float] = {}

    def start_session(self, prompt: str) -> str:
        """开始新的审计会话"""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_session = AuditSession(
            session_id=session_id,
            start_time=datetime.now().isoformat(),
            prompt=prompt,
        )
        return session_id

    def end_session(self) -> AuditSession:
        """结束当前会话并生成摘要"""
        if not self.current_session:
            raise ValueError("No active session")

        self.current_session.end_time = datetime.now().isoformat()
        self.current_session.summary = self._generate_summary()

        # 保存到文件
        self._save_session()

        session = self.current_session
        self.current_session = None
        return session

    def assess_risk(self, tool_name: str, tool_input: Dict[str, Any]) -> RiskLevel:
        """评估操作风险等级"""
        # 基础风险
        base_risk = self.RISK_RULES.get(tool_name, self.RISK_RULES["default"])

        # 检查敏感路径
        path_fields = ["file_path", "path", "pattern", "command"]
        for field in path_fields:
            if field in tool_input:
                value = str(tool_input[field]).lower()
                for pattern in self.SENSITIVE_PATTERNS:
                    if pattern in value:
                        # 涉及敏感路径，提升风险等级
                        if base_risk == RiskLevel.LOW:
                            return RiskLevel.MEDIUM
                        elif base_risk == RiskLevel.MEDIUM:
                            return RiskLevel.HIGH
                        else:
                            return RiskLevel.CRITICAL

        return base_risk

    def record_pre_tool_use(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_use_id: str
    ) -> AuditRecord:
        """记录工具调用前事件"""
        import time
        self._tool_start_times[tool_use_id] = time.time()

        risk = self.assess_risk(tool_name, tool_input)

        # 提取关键信息用于日志
        details = self._extract_details(tool_name, tool_input)

        record = AuditRecord(
            timestamp=datetime.now().isoformat(),
            event_type="pre_tool_use",
            tool_name=tool_name,
            tool_use_id=tool_use_id[:16],
            risk_level=risk.value,
            details=details,
        )

        if self.current_session:
            self.current_session.records.append(record)

        return record

    def record_post_tool_use(
        self,
        tool_name: str,
        tool_use_id: str,
        tool_response: Any,
    ) -> AuditRecord:
        """记录工具调用后事件"""
        import time

        # 计算耗时
        start_time = self._tool_start_times.pop(tool_use_id, None)
        duration_ms = None
        if start_time:
            duration_ms = (time.time() - start_time) * 1000

        # 检查是否有错误
        success = True
        error = None
        if isinstance(tool_response, dict):
            if "error" in tool_response:
                success = False
                error = str(tool_response.get("error", ""))[:200]

        record = AuditRecord(
            timestamp=datetime.now().isoformat(),
            event_type="post_tool_use",
            tool_name=tool_name,
            tool_use_id=tool_use_id[:16],
            risk_level="",  # 已在 pre 中记录
            details={},
            duration_ms=round(duration_ms, 2) if duration_ms else None,
            success=success,
            error=error,
        )

        if self.current_session:
            self.current_session.records.append(record)

        return record

    def _extract_details(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """提取工具调用的关键信息"""
        details = {}

        if tool_name == "Read":
            details["file"] = tool_input.get("file_path", "N/A")
        elif tool_name == "Write":
            details["file"] = tool_input.get("file_path", "N/A")
            details["content_length"] = len(tool_input.get("content", ""))
        elif tool_name == "Edit":
            details["file"] = tool_input.get("file_path", "N/A")
            details["old_string_preview"] = tool_input.get("old_string", "")[:50]
        elif tool_name == "Bash":
            details["command"] = tool_input.get("command", "N/A")[:100]
        elif tool_name == "Glob":
            details["pattern"] = tool_input.get("pattern", "N/A")
            details["path"] = tool_input.get("path", ".")
        elif tool_name == "Grep":
            details["pattern"] = tool_input.get("pattern", "N/A")
            details["path"] = tool_input.get("path", ".")
        else:
            # 通用处理
            for key, value in list(tool_input.items())[:3]:
                details[key] = str(value)[:100]

        return details

    def _generate_summary(self) -> Dict[str, Any]:
        """生成会话摘要"""
        if not self.current_session:
            return {}

        records = self.current_session.records
        pre_records = [r for r in records if r.event_type == "pre_tool_use"]
        post_records = [r for r in records if r.event_type == "post_tool_use"]

        # 统计工具使用
        tool_counts = {}
        for r in pre_records:
            tool_counts[r.tool_name] = tool_counts.get(r.tool_name, 0) + 1

        # 统计风险等级
        risk_counts = {}
        for r in pre_records:
            risk_counts[r.risk_level] = risk_counts.get(r.risk_level, 0) + 1

        # 统计成功/失败
        success_count = sum(1 for r in post_records if r.success)
        failure_count = sum(1 for r in post_records if not r.success)

        # 计算平均耗时
        durations = [r.duration_ms for r in post_records if r.duration_ms]
        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            "total_operations": len(pre_records),
            "tool_usage": tool_counts,
            "risk_distribution": risk_counts,
            "success_count": success_count,
            "failure_count": failure_count,
            "avg_duration_ms": round(avg_duration, 2),
            "high_risk_operations": sum(
                1 for r in pre_records
                if r.risk_level in ["high", "critical"]
            ),
        }

    def _save_session(self):
        """保存会话到 JSON 文件"""
        if not self.current_session:
            return

        filename = f"audit_{self.current_session.session_id}.json"
        filepath = self.output_dir / filename

        # 转换为可序列化的格式
        data = {
            "session_id": self.current_session.session_id,
            "start_time": self.current_session.start_time,
            "end_time": self.current_session.end_time,
            "prompt": self.current_session.prompt,
            "records": [asdict(r) for r in self.current_session.records],
            "summary": self.current_session.summary,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\n[Audit] Session saved to: {filepath}")

    def print_report(self):
        """打印审计报告到控制台"""
        if not self.current_session:
            print("No active session")
            return

        session = self.current_session
        summary = self._generate_summary()

        print("\n" + "=" * 60)
        print("AUDIT REPORT")
        print("=" * 60)

        print(f"\nSession ID: {session.session_id}")
        print(f"Start Time: {session.start_time}")
        print(f"Prompt: {session.prompt[:80]}...")

        print("\n--- Statistics ---")
        print(f"Total Operations: {summary['total_operations']}")
        print(f"Success: {summary['success_count']} | Failure: {summary['failure_count']}")
        print(f"Avg Duration: {summary['avg_duration_ms']}ms")

        print("\n--- Tool Usage ---")
        for tool, count in summary['tool_usage'].items():
            print(f"  {tool}: {count}")

        print("\n--- Risk Distribution ---")
        for risk, count in summary['risk_distribution'].items():
            indicator = "!" if risk in ["high", "critical"] else " "
            print(f"  {indicator} {risk}: {count}")

        if summary['high_risk_operations'] > 0:
            print(f"\n[!] WARNING: {summary['high_risk_operations']} high-risk operations detected")

        print("\n--- Timeline (Last 10) ---")
        for record in session.records[-10:]:
            ts = record.timestamp.split("T")[1][:8]
            if record.event_type == "pre_tool_use":
                risk_mark = "*" if record.risk_level in ["high", "critical"] else " "
                print(f"  {ts} [{risk_mark}] {record.tool_name}")
                if record.details:
                    detail_str = str(record.details)[:60]
                    print(f"           {detail_str}")
            elif record.event_type == "post_tool_use":
                status = "OK" if record.success else "FAIL"
                duration = f"{record.duration_ms}ms" if record.duration_ms else "N/A"
                print(f"           -> {status} ({duration})")

        print("\n" + "=" * 60)


# ============================================================
# Audited Agent
# ============================================================

class AuditedAgent:
    """
    带审计功能的 Agent

    将审计日志记录器集成到 Agent 中，
    自动记录所有操作。
    """

    def __init__(self, audit_dir: Optional[str] = None):
        self.logger = AuditLogger(audit_dir)
        self.client = ClaudeSDKClient()

    def _build_options(self) -> ClaudeAgentOptions:
        """构建带审计 Hook 的选项"""

        # 用于跟踪工具调用的字典
        tool_info = {}

        # Pre-tool-use hook: 记录操作意图
        async def audit_pre_hook(hook_input, tool_use_id, context):
            tool_name = hook_input["tool_name"]
            tool_input = hook_input["tool_input"]

            record = self.logger.record_pre_tool_use(
                tool_name, tool_input, tool_use_id
            )

            # 保存工具信息用于 post_hook
            tool_info[tool_use_id] = {
                "name": tool_name,
                "risk": record.risk_level,
            }

            # 控制台输出 - 每个操作独立一行
            risk_mark = ""
            if record.risk_level == "critical":
                risk_mark = "[!] "
            elif record.risk_level == "high":
                risk_mark = "[*] "

            # 提取关键信息显示
            detail = ""
            if tool_name == "Read":
                path = tool_input.get("file_path", "")
                detail = f" <- {Path(path).name}" if path else ""
            elif tool_name == "Write":
                path = tool_input.get("file_path", "")
                detail = f" -> {Path(path).name}" if path else ""
            elif tool_name == "Glob":
                detail = f" ({tool_input.get('pattern', '')})"
            elif tool_name == "Bash":
                cmd = tool_input.get("command", "")[:30]
                detail = f" $ {cmd}..."

            print(f"  {risk_mark}{tool_name}{detail}", flush=True)

            return {"continue_": True}

        # Post-tool-use hook: 记录操作结果
        async def audit_post_hook(hook_input, tool_use_id, context):
            tool_name = hook_input.get("tool_name", "unknown")
            tool_response = hook_input.get("tool_response", {})

            record = self.logger.record_post_tool_use(
                tool_name, tool_use_id, tool_response
            )

            # 获取工具信息
            info = tool_info.pop(tool_use_id, {})
            name = info.get("name", tool_name)

            # 控制台输出 - 结果独立一行
            status = "OK" if record.success else "FAIL"
            duration = f"{record.duration_ms:.0f}ms" if record.duration_ms else "N/A"
            print(f"    └─ {name}: {status} ({duration})", flush=True)

            return {"continue_": True}

        hooks = {
            "PreToolUse": [HookMatcher(matcher=None, hooks=[audit_pre_hook])],
            "PostToolUse": [HookMatcher(matcher=None, hooks=[audit_post_hook])],
        }

        return ClaudeAgentOptions(
            model="sonnet",
            permission_mode="bypassPermissions",
            allowed_tools=["Read", "Glob", "Grep", "Write", "Bash"],
            hooks=hooks,
            max_turns=15,
        )

    async def run(self, prompt: str) -> str:
        """执行任务并记录审计日志"""

        # 开始审计会话
        session_id = self.logger.start_session(prompt)
        print(f"\n[Audit] Session started: {session_id}")
        print(f"[Audit] Prompt: {prompt[:60]}...")
        print("-" * 60)

        options = self._build_options()
        result_text = ""

        try:
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

        finally:
            # 结束审计会话
            self.logger.print_report()
            self.logger.end_session()

        return result_text


# ============================================================
# Demo
# ============================================================

async def main():
    print("=" * 60)
    print("Audit Logger - Hook 实战示例")
    print("=" * 60)
    print()
    print("本示例展示如何使用 Hook 实现企业级审计日志:")
    print("- 记录所有操作到结构化日志")
    print("- 评估操作风险等级")
    print("- 生成审计报告")
    print()

    # 创建带审计的 Agent
    agent = AuditedAgent(audit_dir="audit_logs")

    # 执行任务
    prompt = """请完成以下任务:
1. 列出 src/ 目录下的所有 Python 文件
2. 读取 src/v0_hello.py 的前 20 行
3. 在 audit_logs/ 目录创建一个 test_output.txt 文件，内容为 "Audit test completed"
"""

    result = await agent.run(prompt)

    print("\n--- Agent Output ---")
    print(result[:500] if result else "(No text output)")

    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)
    print("\nCheck audit_logs/ directory for detailed JSON logs.")


if __name__ == "__main__":
    asyncio.run(main())
