/**
 * MessageList - 消息列表组件
 *
 * 克制优雅的消息展示
 */

import { useEffect, useRef, useState } from 'react';
import { Message, ToolCall, ToolStatus } from '../types';
import { ToolCard } from './ToolCard';
import { ThinkingBlock } from './ThinkingBlock';
import { MarkdownRenderer } from './MarkdownRenderer';
import { HooksPanel } from './HooksPanel';

interface MessageListProps {
  messages: Message[];
}

// 将工具调用按迭代轮次分组
function groupToolsByIteration(toolCalls: ToolCall[]): Map<number, ToolCall[]> {
  const groups = new Map<number, ToolCall[]>();
  toolCalls.forEach(tool => {
    const iteration = tool.iteration || 1;
    if (!groups.has(iteration)) {
      groups.set(iteration, []);
    }
    groups.get(iteration)!.push(tool);
  });
  return groups;
}

export function MessageList({ messages }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-stone-400">
        <div className="text-sm">发送消息开始对话</div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-3">
      {messages.map(msg => (
        <MessageItem key={msg.id} msg={msg} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

interface MessageItemProps {
  msg: Message;
}

function MessageItem({ msg }: MessageItemProps) {
  const iterationGroups = groupToolsByIteration(msg.toolCalls);
  const iterations = Array.from(iterationGroups.entries()).sort((a, b) => a[0] - b[0]);
  const hasMultipleIterations = iterations.length > 1;
  const [showCost, setShowCost] = useState(false);

  return (
    <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] rounded-lg ${
          msg.role === 'user'
            ? 'bg-stone-800 text-white px-4 py-2.5'
            : 'bg-white border border-stone-200 px-4 py-2.5 shadow-sm'
        }`}
      >
        {/* 用户消息 */}
        {msg.role === 'user' && (
          <div className="whitespace-pre-wrap text-sm">{msg.content}</div>
        )}

        {/* 助手消息 */}
        {msg.role === 'assistant' && (
          <div className="space-y-2">
            {/* 思考内容 */}
            {msg.thinking && <ThinkingBlock content={msg.thinking} />}

            {/* Hooks */}
            {msg.hookEvents && msg.hookEvents.length > 0 && (
              <HooksPanel events={msg.hookEvents} />
            )}

            {/* 文本内容 */}
            {(msg.content || msg.isStreaming) && (
              <div className="prose prose-stone max-w-none text-sm leading-relaxed [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
                {msg.content ? (
                  <>
                    <MarkdownRenderer content={msg.content} />
                    {msg.isStreaming && (
                      <span className="inline-block w-0.5 h-4 bg-stone-400 animate-pulse ml-0.5" />
                    )}
                  </>
                ) : (
                  <div className="flex items-center gap-2 text-stone-400">
                    <span className="w-4 h-4 border-2 border-stone-300 border-t-transparent rounded-full animate-spin" />
                    <span className="text-xs">正在思考...</span>
                  </div>
                )}
              </div>
            )}

            {/* 工具调用 - 简化的时间线 */}
            {iterations.length > 0 && (
              <div className="mt-2 pt-2 border-t border-stone-100">
                {iterations.map(([iteration, tools], iterIndex) => (
                  <div key={iteration}>
                    {/* 迭代间分隔 */}
                    {hasMultipleIterations && iterIndex > 0 && (
                      <div className="flex items-center gap-2 my-2">
                        <div className="flex-1 h-px bg-stone-200" />
                        <span className="text-xs text-stone-400">↓</span>
                        <div className="flex-1 h-px bg-stone-200" />
                      </div>
                    )}

                    {/* 迭代标记 */}
                    {hasMultipleIterations && (
                      <div className="text-xs text-stone-400 mb-1">
                        Iteration {iteration}
                      </div>
                    )}

                    {/* 工具卡片 */}
                    {tools.map(tool => (
                      <ToolCard key={tool.id} tool={tool} />
                    ))}
                  </div>
                ))}
              </div>
            )}

            {/* 子 Agent */}
            {msg.agentTasks.length > 0 && (
              <div className="mt-2 pt-2 border-t border-stone-100">
                <div className="text-xs text-stone-400 mb-2">
                  子 Agent ({msg.agentTasks.length})
                </div>
                {msg.agentTasks.map(agent => (
                  <div
                    key={agent.id}
                    className="flex items-center gap-2 text-xs py-1 text-stone-600"
                    style={{ marginLeft: agent.depth ? `${(agent.depth - 1) * 12}px` : 0 }}
                  >
                    <span className="text-stone-400">◈</span>
                    <span className="font-medium">{agent.type}</span>
                    <span className="text-stone-400 truncate flex-1">{agent.description}</span>
                    <span className={`px-1.5 py-0.5 rounded text-xs ${
                      agent.status === 'running' ? 'bg-blue-100 text-blue-600' :
                      agent.status === 'completed' ? 'bg-stone-100 text-stone-500' :
                      'bg-red-100 text-red-500'
                    }`}>
                      {agent.status === 'running' ? 'Running' : agent.status === 'completed' ? 'Completed' : 'Error'}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* 处理中指示器 - 当 isStreaming 但没有正在运行的工具时 */}
            {msg.isStreaming && (() => {
              const hasRunningTool = msg.toolCalls.some(t => t.status === ToolStatus.RUNNING);
              const hasRunningAgent = msg.agentTasks.some(a => a.status === ToolStatus.RUNNING);
              // 如果有内容且没有正在运行的工具/Agent，显示继续处理提示
              if (msg.content && !hasRunningTool && !hasRunningAgent) {
                return (
                  <div className="flex items-center gap-2 text-stone-400 mt-2 pt-2 border-t border-stone-100">
                    <span className="w-3 h-3 border-2 border-stone-300 border-t-transparent rounded-full animate-spin" />
                    <span className="text-xs">继续处理中...</span>
                  </div>
                );
              }
              return null;
            })()}

            {/* 费用信息 - 折叠 */}
            {msg.cost && !msg.isStreaming && (
              <div className="mt-2 pt-2 border-t border-stone-100">
                <button
                  onClick={() => setShowCost(!showCost)}
                  className="text-xs text-stone-400 hover:text-stone-600 transition-colors flex items-center gap-1"
                >
                  <span>{showCost ? '−' : '+'}</span>
                  <span>
                    {msg.cost.input_tokens.toLocaleString()} + {msg.cost.output_tokens.toLocaleString()} tokens
                    · ${msg.cost.cost.toFixed(4)}
                  </span>
                </button>

                {showCost && (
                  <div className="mt-2 text-xs text-stone-500 space-y-1">
                    {/* 上下文进度 */}
                    {msg.cost.context_percent !== undefined && (
                      <div className="flex items-center gap-2">
                        <span>Context</span>
                        <div className="flex-1 h-1 bg-stone-200 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              msg.cost.context_percent < 50 ? 'bg-emerald-400' :
                              msg.cost.context_percent < 80 ? 'bg-amber-400' : 'bg-red-400'
                            }`}
                            style={{ width: `${Math.min(msg.cost.context_percent, 100)}%` }}
                          />
                        </div>
                        <span>{msg.cost.context_percent}%</span>
                      </div>
                    )}

                    {/* Stop Reason */}
                    {msg.stopReason && (
                      <div className="flex items-center gap-2">
                        <span>Stop Reason:</span>
                        <span className="text-stone-600">{msg.stopReason}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
