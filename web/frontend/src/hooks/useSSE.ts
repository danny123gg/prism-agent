/**
 * SSE Hook for Agent Trace Streaming
 *
 * 处理 Server-Sent Events 流，解析事件并更新状态
 */

import { useState, useCallback, useRef } from 'react';
import {
  SSEEventType,
  ToolStatus,
  Message,
  ToolCall,
  AgentTask,
  HookEvent,
  CostUpdateData,
  TextDeltaData,
  ThinkingDeltaData,
  ToolStartData,
  ToolResultData,
  AgentSpawnData,
  AgentCompleteData,
  MessageCompleteData,
  ErrorData,
  SessionConfigData,
  HookPreToolData,
  HookPostToolData,
} from '../types';

// 加载阶段枚举
export type LoadingStage = 'idle' | 'connecting' | 'waiting' | 'thinking' | 'processing' | 'tool_calling';

// 会话配置接口
export interface SessionConfig {
  maxTurns: number;
  permissionMode: string;
  sandboxEnabled: boolean;
  sandboxRoot: string;
}

/**
 * 生成历史对话摘要
 *
 * 简单策略：提取每轮对话的关键信息（用户问题 + 简短回复）
 *
 * 未来可以改进为：
 * 1. 使用模型 API 生成更智能的摘要
 * 2. 识别重要实体和关键信息
 * 3. 保留重要的上下文（如用户偏好、设定等）
 */
function generateHistorySummary(messages: Array<{ role: string; content: string }>): string {
  const summaryParts: string[] = [];

  for (let i = 0; i < messages.length; i += 2) {
    const userMsg = messages[i];
    const assistantMsg = messages[i + 1];

    if (userMsg && assistantMsg) {
      // 截取用户问题（最多100字符）
      const userPreview = userMsg.content.length > 100
        ? userMsg.content.substring(0, 100) + '...'
        : userMsg.content;

      // 截取助手回复（最多150字符）
      const assistantPreview = assistantMsg.content.length > 150
        ? assistantMsg.content.substring(0, 150) + '...'
        : assistantMsg.content;

      summaryParts.push(`Q${Math.floor(i / 2) + 1}: ${userPreview}\nA: ${assistantPreview}`);
    }
  }

  return summaryParts.join('\n\n');
}

interface UseSSEReturn {
  messages: Message[];
  isLoading: boolean;
  loadingStage: LoadingStage;
  error: string | null;
  sessionConfig: SessionConfig | null;
  currentIteration: number;
  sendMessage: (message: string, useThinking?: boolean) => Promise<void>;
  clearMessages: () => void;
}

export function useSSE(): UseSSEReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState<LoadingStage>('idle');
  const [error, setError] = useState<string | null>(null);
  const [sessionConfig, setSessionConfig] = useState<SessionConfig | null>(null);
  const [currentIteration, setCurrentIteration] = useState(0);
  const abortControllerRef = useRef<AbortController | null>(null);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  const sendMessage = useCallback(async (userMessage: string, useThinking: boolean = false) => {
    // 取消之前的请求
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    setIsLoading(true);
    setLoadingStage('connecting');
    setError(null);

    // 添加用户消息
    const userMsgId = `user-${Date.now()}`;
    const assistantMsgId = `assistant-${Date.now()}`;

    setMessages(prev => [
      ...prev,
      {
        id: userMsgId,
        role: 'user',
        content: userMessage,
        toolCalls: [],
        agentTasks: [],
        hookEvents: [],  // (#23) Hook 事件记录
        isStreaming: false,
      },
      {
        id: assistantMsgId,
        role: 'assistant',
        content: '',
        toolCalls: [],
        agentTasks: [],
        hookEvents: [],  // (#23) Hook 事件记录
        isStreaming: true,
      },
    ]);

    // 根据 useThinking 选择 API 端点
    const apiEndpoint = useThinking ? '/api/chat/thinking' : '/api/chat';

    // 滑动窗口 + 摘要策略
    // 保留最近 5 轮完整对话，之前的对话生成摘要
    const RECENT_TURNS = 5;  // 保留最近 5 轮对话
    const fullHistory = messages
      .filter(msg => msg.role === 'user' || msg.role === 'assistant')
      .map(msg => ({
        role: msg.role,
        content: msg.content
      }));

    let historyToSend: Array<{ role: string; content: string }> = [];

    if (fullHistory.length > RECENT_TURNS * 2) {
      // 如果历史超过 5 轮，进行压缩
      const oldMessages = fullHistory.slice(0, -(RECENT_TURNS * 2));
      const recentMessages = fullHistory.slice(-(RECENT_TURNS * 2));

      // 生成摘要（简单方式：提取关键信息）
      const summary = generateHistorySummary(oldMessages);

      // 构建历史：[摘要] + [最近5轮]
      historyToSend = [
        { role: 'user', content: `[历史对话摘要]\n${summary}\n\n[以下是最近的对话]` },
        ...recentMessages
      ];
    } else {
      // 历史较短，直接使用全量历史
      historyToSend = fullHistory;
    }

    try {
      const response = await fetch(apiEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage,
          history: historyToSend.length > 0 ? historyToSend : undefined
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body');
      }

      // 连接成功，等待响应
      setLoadingStage('waiting');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            // Event type is extracted in the data processing below
            continue;
          }
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6);
            try {
              const data = JSON.parse(dataStr);
              // 从上一行获取事件类型
              const eventLine = lines[lines.indexOf(line) - 1];
              const eventType = eventLine?.startsWith('event: ')
                ? eventLine.slice(7).trim() as SSEEventType
                : null;

              if (eventType) {
                processEvent(assistantMsgId, eventType, data);
              }
            } catch (e) {
              console.error('Failed to parse SSE data:', e);
            }
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMsg);
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMsgId
            ? { ...msg, content: `Error: ${errorMsg}`, isStreaming: false }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
      setLoadingStage('idle');
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMsgId ? { ...msg, isStreaming: false } : msg
        )
      );
    }
  }, [messages]);

  const processEvent = useCallback(
    (msgId: string, eventType: SSEEventType, data: unknown) => {
      // 处理会话配置事件
      if (eventType === SSEEventType.SESSION_CONFIG) {
        const config = data as SessionConfigData;
        setSessionConfig({
          maxTurns: config.max_turns,
          permissionMode: config.permission_mode,
          sandboxEnabled: config.sandbox_enabled,
          sandboxRoot: config.sandbox_root,
        });
        return;
      }

      // 根据事件类型更新加载阶段
      switch (eventType) {
        case SSEEventType.THINKING_DELTA:
          setLoadingStage('thinking');
          break;
        case SSEEventType.TEXT_DELTA:
          setLoadingStage('processing');
          break;
        case SSEEventType.TOOL_START:
          setLoadingStage('tool_calling');
          // 更新当前迭代轮次
          const toolData = data as ToolStartData;
          if (toolData.iteration !== undefined) {
            setCurrentIteration(toolData.iteration);
          }
          break;
        case SSEEventType.MESSAGE_COMPLETE:
          setLoadingStage('idle');
          break;
      }

      setMessages(prev =>
        prev.map(msg => {
          if (msg.id !== msgId) return msg;

          switch (eventType) {
            case SSEEventType.TEXT_DELTA: {
              const { text } = data as TextDeltaData;
              return { ...msg, content: msg.content + text };
            }

            case SSEEventType.THINKING_DELTA: {
              const { thinking } = data as ThinkingDeltaData;
              return { ...msg, thinking: (msg.thinking || '') + thinking };
            }

            case SSEEventType.TOOL_START: {
              const { tool_id, name, input, iteration, parallel_group, parallel_count } = data as ToolStartData;
              const newTool: ToolCall = {
                id: tool_id,
                name,
                status: ToolStatus.RUNNING,
                input,
                startTime: Date.now(),
                iteration,
                parallelGroup: parallel_group,
                isParallel: parallel_count !== undefined && parallel_count > 1,
              };
              return { ...msg, toolCalls: [...msg.toolCalls, newTool] };
            }

            case SSEEventType.TOOL_RESULT: {
              const { tool_id, status, output, error } = data as ToolResultData;
              return {
                ...msg,
                toolCalls: msg.toolCalls.map(tool =>
                  tool.id === tool_id
                    ? {
                        ...tool,
                        status: status as ToolStatus,
                        output,
                        error,
                        endTime: Date.now(),
                      }
                    : tool
                ),
              };
            }

            case SSEEventType.AGENT_SPAWN: {
              const { agent_id, agent_type, description, parent_tool_id, depth } =
                data as AgentSpawnData;
              const newAgent: AgentTask = {
                id: agent_id,
                type: agent_type,
                description,
                parentToolId: parent_tool_id,
                status: ToolStatus.RUNNING,
                toolCalls: [],
                depth,
              };
              return { ...msg, agentTasks: [...msg.agentTasks, newAgent] };
            }

            case SSEEventType.AGENT_COMPLETE: {
              const { agent_id } = data as AgentCompleteData;
              return {
                ...msg,
                agentTasks: msg.agentTasks.map(agent =>
                  agent.id === agent_id
                    ? { ...agent, status: ToolStatus.COMPLETED }
                    : agent
                ),
              };
            }

            case SSEEventType.COST_UPDATE: {
              const costData = data as CostUpdateData;
              return { ...msg, cost: costData };
            }

            case SSEEventType.MESSAGE_COMPLETE: {
              const { stop_reason } = data as MessageCompleteData;
              return { ...msg, isStreaming: false, stopReason: stop_reason };
            }

            case SSEEventType.ERROR: {
              const { error: errorMsg } = data as ErrorData;
              return {
                ...msg,
                content: msg.content + `\n\nError: ${errorMsg}`,
                isStreaming: false,
              };
            }

            // Hook 事件处理 (#23)
            case SSEEventType.HOOK_PRE_TOOL: {
              const hookData = data as HookPreToolData;
              const newHookEvent: HookEvent = {
                id: `hook-pre-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
                type: 'pre_tool',
                toolName: hookData.tool_name,
                action: hookData.action,
                message: hookData.message || `PreToolUse: ${hookData.tool_name}`,
                timestamp: Date.now(),
              };
              return { ...msg, hookEvents: [...(msg.hookEvents || []), newHookEvent] };
            }

            case SSEEventType.HOOK_POST_TOOL: {
              const hookData = data as HookPostToolData;
              const newHookEvent: HookEvent = {
                id: `hook-post-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
                type: 'post_tool',
                toolName: hookData.tool_name,
                message: hookData.message || `PostToolUse: ${hookData.tool_name}`,
                timestamp: Date.now(),
              };
              return { ...msg, hookEvents: [...(msg.hookEvents || []), newHookEvent] };
            }

            default:
              return msg;
          }
        })
      );
    },
    []
  );

  return {
    messages,
    isLoading,
    loadingStage,
    error,
    sessionConfig,
    currentIteration,
    sendMessage,
    clearMessages,
  };
}
