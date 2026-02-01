/**
 * TypeScript types for Agent Trace Visualization
 */

// === SSE Event Types ===

export enum SSEEventType {
  SESSION_CONFIG = 'session_config',
  TEXT_DELTA = 'text_delta',
  THINKING_DELTA = 'thinking_delta',
  TOOL_START = 'tool_start',
  TOOL_RESULT = 'tool_result',
  AGENT_SPAWN = 'agent_spawn',
  AGENT_COMPLETE = 'agent_complete',
  COST_UPDATE = 'cost_update',
  MESSAGE_COMPLETE = 'message_complete',
  ERROR = 'error',
  // Hooks 机制事件 (#23)
  HOOK_PRE_TOOL = 'hook_pre_tool',
  HOOK_POST_TOOL = 'hook_post_tool',
  // Plan Mode 事件 (#24)
  PLAN_MODE_ENTER = 'plan_mode_enter',
  PLAN_MODE_EXIT = 'plan_mode_exit',
}

export enum ToolStatus {
  RUNNING = 'running',
  COMPLETED = 'completed',
  ERROR = 'error',
}

// === SSE Event Data ===

export interface SessionConfigData {
  max_turns: number;
  permission_mode: string;
  sandbox_enabled: boolean;
  sandbox_root: string;
}

export interface TextDeltaData {
  text: string;
}

export interface ThinkingDeltaData {
  thinking: string;
}

export interface ToolStartData {
  tool_id: string;
  name: string;
  input: Record<string, unknown>;
  iteration?: number;  // 迭代轮次
  parallel_group?: string;  // 并行工具组 ID
  parallel_count?: number;  // 并行工具数量
}

export interface ToolResultData {
  tool_id: string;
  status: ToolStatus;
  output: Record<string, unknown> | null;
  error?: string;
}

export interface AgentSpawnData {
  agent_id: string;
  agent_type: string;
  description: string;
  parent_tool_id?: string;
  iteration?: number;
  depth?: number;  // 子代理深度层级
}

export interface AgentCompleteData {
  agent_id: string;
}

export interface CostUpdateData {
  input_tokens: number;
  output_tokens: number;
  cost: number;
  total_cost: number;
  // 上下文占用信息
  context_used?: number;
  context_max?: number;
  context_percent?: number;
}

export interface MessageCompleteData {
  tools_used: string[];
  total_tokens: number;
  stop_reason?: string;  // (#34)
}

export interface ErrorData {
  error: string;
  details?: string;
}

// Hooks 机制数据 (#23)
export interface HookPreToolData {
  hook_type: 'PreToolUse';
  tool_name: string;
  action: 'allow' | 'block';
  message?: string;
}

export interface HookPostToolData {
  hook_type: 'PostToolUse';
  tool_name: string;
  message?: string;
}

// Plan Mode 数据 (#24)
export interface PlanModeEnterData {
  reason: string;
  plan_prompt?: string;
}

export interface PlanModeExitData {
  approved: boolean;
  reason?: string;
}

// === UI State Types ===

export interface ToolCall {
  id: string;
  name: string;
  status: ToolStatus;
  input: Record<string, unknown>;
  output?: string | Record<string, unknown> | null;  // Can be string or object
  error?: string;
  startTime: number;
  endTime?: number;
  iteration?: number;  // 迭代轮次
  parallelGroup?: string;  // 并行工具组 ID
  isParallel?: boolean;  // 是否为并行调用
}

export interface AgentTask {
  id: string;
  type: string;
  description: string;
  parentToolId?: string;
  status: ToolStatus;
  toolCalls: ToolCall[];
  depth?: number;  // 子代理深度层级
}

// Hook 事件记录 (#23)
export interface HookEvent {
  id: string;
  type: 'pre_tool' | 'post_tool';
  toolName: string;
  action?: 'allow' | 'block';
  message: string;
  timestamp: number;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  thinking?: string;
  toolCalls: ToolCall[];
  agentTasks: AgentTask[];
  hookEvents: HookEvent[];  // (#23) Hook 事件记录
  cost?: CostUpdateData;
  isStreaming: boolean;
  stopReason?: string;  // (#34)
  planMode?: {  // (#24) Plan Mode 状态
    active: boolean;
    reason?: string;
  };
}

export interface ChatState {
  messages: Message[];
  isLoading: boolean;
  error?: string;
}

// === Component Props ===

export interface ToolCardProps {
  tool: ToolCall;
  isExpanded: boolean;
  onToggle: () => void;
}

export interface ThinkingBlockProps {
  content: string;
  isExpanded: boolean;
  onToggle: () => void;
}

export interface MessageListProps {
  messages: Message[];
}

export interface ChatWindowProps {
  onSendMessage: (message: string) => void;
  isLoading: boolean;
}
