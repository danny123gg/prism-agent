"""
Pydantic models for SSE events and API requests/responses.
"""

from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel


class SSEEventType(str, Enum):
    """SSE 事件类型"""
    SESSION_CONFIG = "session_config"   # 会话配置信息
    TEXT_DELTA = "text_delta"           # 流式文本块
    THINKING_DELTA = "thinking_delta"   # 思考内容
    TOOL_START = "tool_start"           # 工具开始执行
    TOOL_RESULT = "tool_result"         # 工具执行完成
    AGENT_SPAWN = "agent_spawn"         # 子代理启动
    AGENT_COMPLETE = "agent_complete"   # 子代理完成
    COST_UPDATE = "cost_update"         # 费用更新
    MESSAGE_COMPLETE = "message_complete"  # 响应完成
    ERROR = "error"                     # 错误
    # Hooks 机制事件 (#23)
    HOOK_PRE_TOOL = "hook_pre_tool"     # PreToolUse Hook 触发
    HOOK_POST_TOOL = "hook_post_tool"   # PostToolUse Hook 触发
    # Plan Mode 事件 (#24)
    PLAN_MODE_ENTER = "plan_mode_enter" # 进入计划模式
    PLAN_MODE_EXIT = "plan_mode_exit"   # 退出计划模式


class ToolStatus(str, Enum):
    """工具执行状态"""
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


# === SSE Event Data Models ===

class SessionConfigData(BaseModel):
    """会话配置数据"""
    max_turns: int = 30  # 最大迭代轮次
    permission_mode: str = "acceptEdits"
    sandbox_enabled: bool = True
    sandbox_root: str = ""


class TextDeltaData(BaseModel):
    """流式文本数据"""
    text: str


class ThinkingDeltaData(BaseModel):
    """思考内容数据"""
    thinking: str


class ToolStartData(BaseModel):
    """工具开始执行数据"""
    tool_id: str
    name: str
    input: dict[str, Any]
    iteration: Optional[int] = None  # 迭代轮次


class ToolResultData(BaseModel):
    """工具执行结果数据"""
    tool_id: str
    status: ToolStatus
    output: Any
    error: Optional[str] = None


class AgentSpawnData(BaseModel):
    """子代理启动数据"""
    agent_id: str
    agent_type: str
    description: str
    parent_tool_id: Optional[str] = None  # 关联的 Task 工具调用 ID
    depth: int = 1  # 子代理深度层级


class AgentCompleteData(BaseModel):
    """子代理完成数据"""
    agent_id: str


class CostUpdateData(BaseModel):
    """费用更新数据"""
    input_tokens: int
    output_tokens: int
    cost: float
    total_cost: float
    # 上下文占用信息
    context_used: Optional[int] = None      # 已使用的上下文 tokens
    context_max: Optional[int] = None       # 最大上下文窗口
    context_percent: Optional[float] = None # 占用百分比


class MessageCompleteData(BaseModel):
    """消息完成数据"""
    tools_used: list[str]
    total_tokens: int


class ErrorData(BaseModel):
    """错误数据"""
    error: str
    details: Optional[str] = None


# === API Models ===

class ChatMessage(BaseModel):
    """单条聊天消息"""
    role: str  # "user" 或 "assistant"
    content: str


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str
    session_id: Optional[str] = None
    history: Optional[List[ChatMessage]] = None  # 对话历史


class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str
    created_at: str
    message_count: int


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str
