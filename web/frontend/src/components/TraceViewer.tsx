/**
 * TraceViewer - Trace 日志查看器
 *
 * 完整的 Trace 展示，包含：
 * - 用户请求
 * - 费用和 Token 使用
 * - 模型信息
 * - 输出预览
 * - MCP 服务器状态
 * - 事件时间线
 */

import { useState, useEffect, useMemo } from 'react';

interface TraceStats {
  tool_calls: number;
  iterations: number;
  sub_agents: number;
  errors: number;
  sandbox_blocks: number;
  hooks_triggered: number;
  thinking_blocks: number;
}

interface Trace {
  trace_id: string;
  start_time: string;
  status: string;
  summary?: string;
  duration_ms?: number;
  tool_count?: number;
  stats?: TraceStats;
}

interface TracesResponse {
  total: number;
  limit: number;
  offset: number;
  traces: Trace[];
}

interface TraceEvent {
  timestamp: string;
  elapsed_ms: number;
  event_type: string;
  summary?: string;
  data: Record<string, unknown>;
  raw?: string;
}

interface TraceDetail {
  metadata: {
    trace_id: string;
    start_time: string;
    status: string;
    duration_ms?: number;
    stats?: TraceStats;
  };
  events: TraceEvent[];
}

interface TraceViewerProps {
  isOpen: boolean;
  onClose: () => void;
}

// 从事件中提取的摘要信息
interface TraceSummary {
  userRequest?: string;
  model?: string;
  cost?: number;
  inputTokens?: number;
  outputTokens?: number;
  cacheCreationTokens?: number;
  cacheReadTokens?: number;
  outputPreview?: string;
  mcpToolsCalled?: Array<{ name: string; count: number }>;  // 改为实际调用的 MCP 工具
}

// 从事件列表中提取摘要信息
function extractSummary(events: TraceEvent[]): TraceSummary {
  const summary: TraceSummary = {};
  const mcpToolCounts: Record<string, number> = {};  // 统计 MCP 工具调用次数

  for (const event of events) {
    // 用户请求
    if (event.event_type === 'request' && event.data.message) {
      summary.userRequest = event.data.message as string;
    }

    // Token 使用和费用
    if (event.event_type === 'usage') {
      summary.cost = event.data.cost as number;
      summary.inputTokens = event.data.input_tokens as number;
      summary.outputTokens = event.data.output_tokens as number;
    }

    // 统计 MCP 工具调用（从 tool_start 事件中提取）
    if (event.event_type === 'tool_start' && event.data.name) {
      const toolName = event.data.name as string;
      if (toolName.startsWith('mcp__')) {
        // 提取 MCP 服务名（如 mcp__tavily__search -> tavily）
        const parts = toolName.split('__');
        const serverName = parts[1] || toolName;
        mcpToolCounts[serverName] = (mcpToolCounts[serverName] || 0) + 1;
      }
    }

    // 输出文本 - 支持两种格式：
    // 1. Normal 模式: text_delta 事件，使用 delta 字段
    // 2. Thinking 模式: text 事件，使用 text 字段
    if (event.event_type === 'text_delta') {
      const textContent = (event.data.delta || event.data.text) as string;
      if (textContent) {
        summary.outputPreview = (summary.outputPreview || '') + textContent;
      }
    } else if (event.event_type === 'text' && event.data.text) {
      // Thinking 模式的完整文本块
      summary.outputPreview = (summary.outputPreview || '') + (event.data.text as string);
    }

    // 从 raw_message 中提取模型和缓存信息
    if (event.event_type === 'raw_message' && event.raw) {
      try {
        // 尝试解析 raw 字符串中的信息
        const rawStr = event.raw;

        // 提取模型名称
        const modelMatch = rawStr.match(/'model':\s*'([^']+)'/);
        if (modelMatch && !summary.model) {
          summary.model = modelMatch[1];
        }

        // 提取缓存 token
        const cacheCreationMatch = rawStr.match(/'cache_creation_input_tokens':\s*(\d+)/);
        if (cacheCreationMatch) {
          summary.cacheCreationTokens = parseInt(cacheCreationMatch[1]);
        }
        const cacheReadMatch = rawStr.match(/'cache_read_input_tokens':\s*(\d+)/);
        if (cacheReadMatch) {
          summary.cacheReadTokens = parseInt(cacheReadMatch[1]);
        }
      } catch {
        // 忽略解析错误
      }
    }
  }

  // 转换 MCP 工具统计为数组
  const mcpTools = Object.entries(mcpToolCounts).map(([name, count]) => ({ name, count }));
  if (mcpTools.length > 0) {
    summary.mcpToolsCalled = mcpTools.sort((a, b) => b.count - a.count);
  }

  return summary;
}

// 事件优先级定义（组件外部定义，避免 Hooks 顺序问题）
function getEventPriority(eventType: string): 'high' | 'medium' | 'low' {
  switch (eventType) {
    // 高优先级：用户最关心的核心事件
    case 'tool_start':
    case 'tool_result':
    case 'sandbox_block':
    case 'thinking':
    case 'request':
    case 'complete':
      return 'high';
    // 中优先级：有价值但非核心
    case 'text_delta':
    case 'usage':
    case 'config':
    case 'hook_pre_tool':
    case 'hook_post_tool':
    case 'retry':
    case 'agent_complete':
      return 'medium';
    // 低优先级：底层/噪音事件
    case 'raw_message':
    case 'hook_keep_stream':
    default:
      return 'low';
  }
}

export function TraceViewer({ isOpen, onClose }: TraceViewerProps) {
  const [traces, setTraces] = useState<Trace[]>([]);
  const [totalTraces, setTotalTraces] = useState(0);
  const [selectedTrace, setSelectedTrace] = useState<TraceDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [showOutput, setShowOutput] = useState(true);
  // 搜索和过滤状态
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [showErrorsOnly, setShowErrorsOnly] = useState(false);
  const [showSandboxBlocksOnly, setShowSandboxBlocksOnly] = useState(false);
  // 低优先级事件默认收起状态
  const [showLowPriority, setShowLowPriority] = useState(false);

  // 提取当前选中 trace 的摘要
  const traceSummary = useMemo(() => {
    if (!selectedTrace) return null;
    return extractSummary(selectedTrace.events);
  }, [selectedTrace]);

  useEffect(() => {
    if (isOpen) fetchTraces();
  }, [isOpen, searchQuery, statusFilter, showErrorsOnly, showSandboxBlocksOnly]);

  const fetchTraces = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (searchQuery) params.set('search', searchQuery);
      if (statusFilter) params.set('status', statusFilter);
      if (showErrorsOnly) params.set('has_errors', 'true');
      if (showSandboxBlocksOnly) params.set('has_sandbox_blocks', 'true');
      params.set('limit', '50');

      const response = await fetch(`/api/traces?${params.toString()}`);
      if (response.ok) {
        const data: TracesResponse = await response.json();
        setTraces(data.traces);
        setTotalTraces(data.total);
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchTraceDetail = async (traceId: string) => {
    try {
      setLoading(true);
      setShowOutput(true);
      const response = await fetch(`/api/traces/${traceId}`);
      if (response.ok) setSelectedTrace(await response.json());
    } finally {
      setLoading(false);
    }
  };

  // 按工具调用周期分组事件 (必须在 early return 之前)
  const groupedEvents = useMemo(() => {
    if (!selectedTrace) return [];

    const groups: Array<{
      type: 'tool_cycle' | 'standalone';
      toolName?: string;
      toolId?: string;
      iteration?: number;
      events: TraceEvent[];
      status?: string;
      hasSandboxBlock?: boolean;
    }> = [];

    let currentToolGroup: typeof groups[0] | null = null;

    for (const event of selectedTrace.events) {
      if (event.event_type === 'tool_start') {
        // 开始新的工具调用周期
        if (currentToolGroup) {
          groups.push(currentToolGroup);
        }
        currentToolGroup = {
          type: 'tool_cycle',
          toolName: event.data.name as string,
          toolId: event.data.tool_id as string,
          iteration: event.data.iteration as number,
          events: [event],
          hasSandboxBlock: false,
        };
      } else if (currentToolGroup && event.event_type === 'tool_result') {
        // 结束当前工具调用周期
        currentToolGroup.events.push(event);
        currentToolGroup.status = event.data.status as string;
        groups.push(currentToolGroup);
        currentToolGroup = null;
      } else if (currentToolGroup && ['hook_keep_stream', 'hook_pre_tool', 'hook_post_tool', 'sandbox_block', 'raw_message'].includes(event.event_type)) {
        // 属于当前工具周期的中间事件
        currentToolGroup.events.push(event);
        if (event.event_type === 'sandbox_block') {
          currentToolGroup.hasSandboxBlock = true;
        }
      } else {
        // 独立事件
        if (currentToolGroup) {
          groups.push(currentToolGroup);
          currentToolGroup = null;
        }
        groups.push({
          type: 'standalone',
          events: [event],
        });
      }
    }

    // 处理最后一个未关闭的组
    if (currentToolGroup) {
      groups.push(currentToolGroup);
    }

    return groups;
  }, [selectedTrace]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-stone-900/50 z-50" onClick={onClose}>
      <div className="absolute inset-4 bg-white rounded-xl shadow-2xl flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="px-5 py-4 border-b border-stone-100 flex items-center justify-between">
          <h2 className="text-base font-medium text-stone-700">Traces</h2>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-600 text-sm">
            Close
          </button>
        </div>

        <div className="flex-1 flex overflow-hidden">
          {/* List */}
          <div className="w-96 border-r border-stone-100 flex flex-col overflow-hidden">
            {/* 搜索和过滤区域 */}
            <div className="p-3 bg-stone-50 border-b border-stone-100 space-y-2">
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="搜索..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="flex-1 text-xs px-2 py-1.5 border border-stone-200 rounded focus:outline-none focus:ring-1 focus:ring-blue-400"
                />
                <button onClick={() => fetchTraces()} className="text-stone-400 hover:text-stone-600 p-1.5 rounded hover:bg-stone-100" title="刷新">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                </button>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-stone-500">{totalTraces} 条</span>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="text-xs px-1.5 py-1 border border-stone-200 rounded bg-white"
                >
                  <option value="">全部状态</option>
                  <option value="completed">已完成</option>
                  <option value="error">错误</option>
                  <option value="running">运行中</option>
                </select>
                <label className="flex items-center gap-1 text-xs text-stone-600">
                  <input type="checkbox" checked={showErrorsOnly} onChange={(e) => setShowErrorsOnly(e.target.checked)} className="w-3 h-3" />
                  有错误
                </label>
                <label className="flex items-center gap-1 text-xs text-orange-600">
                  <input
                    type="checkbox"
                    checked={showSandboxBlocksOnly}
                    onChange={(e) => setShowSandboxBlocksOnly(e.target.checked)}
                    onMouseDown={(e) => e.stopPropagation()}
                    className="w-3 h-3"
                  />
                  沙箱拦截
                </label>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-2">
              {loading && !selectedTrace && <div className="text-xs text-stone-400 p-2">加载中...</div>}

              <div className="space-y-1">
                {traces.map(trace => (
                  <button
                    key={trace.trace_id}
                    onClick={() => fetchTraceDetail(trace.trace_id)}
                    className={`w-full text-left px-2.5 py-2 rounded text-sm transition-colors ${
                      selectedTrace?.metadata.trace_id === trace.trace_id
                        ? 'bg-stone-100 text-stone-800'
                        : trace.status === 'error'
                          ? 'text-stone-600 hover:bg-red-50 border-l-2 border-red-300'
                          : trace.stats?.sandbox_blocks
                            ? 'text-stone-600 hover:bg-orange-50 border-l-2 border-orange-300'
                            : 'text-stone-600 hover:bg-stone-50'
                    }`}
                  >
                    <div className="flex items-center gap-1.5">
                      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                        trace.status === 'completed' ? 'bg-emerald-400' :
                        trace.status === 'error' ? 'bg-red-400' : 'bg-amber-400'
                      }`} />
                      <span className="text-xs text-stone-400">{new Date(trace.start_time).toLocaleTimeString()}</span>
                      {trace.duration_ms && (
                        <span className="text-xs text-stone-300">{(trace.duration_ms / 1000).toFixed(1)}s</span>
                      )}
                      {trace.stats && trace.stats.tool_calls > 0 && (
                        <span className="text-xs text-stone-400">{trace.stats.tool_calls} tools</span>
                      )}
                    </div>
                    {trace.summary ? (
                      <div className="text-xs text-stone-600 pl-3 mt-1 line-clamp-2">
                        {trace.summary}
                      </div>
                    ) : (
                      <div className="text-xs text-stone-300 pl-3 mt-1 italic">
                        无消息
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Detail */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {selectedTrace ? (
              <>
                {/* 用户请求区域 */}
                {traceSummary?.userRequest && (
                  <div className="px-4 py-3 bg-slate-50 border-b border-slate-200">
                    <div className="text-xs text-slate-500 mb-1">User Request</div>
                    <div className="text-sm text-slate-800 font-medium line-clamp-3">
                      {traceSummary.userRequest}
                    </div>
                  </div>
                )}

                {/* 核心指标栏 */}
                <div className={`px-4 py-3 border-b flex flex-wrap items-center gap-x-4 gap-y-2 ${
                  selectedTrace.metadata.status === 'error'
                    ? 'bg-red-50 border-red-200'
                    : selectedTrace.metadata.status === 'completed'
                      ? 'bg-emerald-50 border-emerald-200'
                      : 'bg-amber-50 border-amber-200'
                }`}>
                  {/* 状态徽章 */}
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                    selectedTrace.metadata.status === 'error'
                      ? 'bg-red-100 text-red-700'
                      : selectedTrace.metadata.status === 'completed'
                        ? 'bg-emerald-100 text-emerald-700'
                        : 'bg-amber-100 text-amber-700'
                  }`}>
                    {selectedTrace.metadata.status === 'completed' ? '✓ Completed' :
                     selectedTrace.metadata.status === 'error' ? '✗ Error' : '⋯ Running'}
                  </span>

                  {/* 模型 */}
                  {traceSummary?.model && (
                    <span className="text-xs text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">
                      {traceSummary.model.replace('claude-', '').replace('-20251101', '')}
                    </span>
                  )}

                  {/* Duration */}
                  {selectedTrace.metadata.duration_ms && (
                    <span className="text-xs text-stone-600">
                      <span className="text-stone-400">Duration</span> {(selectedTrace.metadata.duration_ms / 1000).toFixed(2)}s
                    </span>
                  )}

                  {/* Cost */}
                  {traceSummary?.cost !== undefined && (
                    <span className="text-xs text-amber-600">
                      <span className="text-stone-400">Cost</span> ${traceSummary.cost.toFixed(4)}
                    </span>
                  )}

                  {/* Tools and Iterations */}
                  {selectedTrace.metadata.stats && (
                    <>
                      <span className="text-xs text-blue-600">
                        <span className="text-stone-400">Tools</span> {selectedTrace.metadata.stats.tool_calls}
                      </span>
                      <span className="text-xs text-violet-600">
                        <span className="text-stone-400">Iterations</span> {selectedTrace.metadata.stats.iterations}
                      </span>
                    </>
                  )}
                </div>

                {/* Token 使用详情 */}
                {(traceSummary?.inputTokens || traceSummary?.outputTokens) && (
                  <div className="px-4 py-2 bg-stone-50 border-b border-stone-200 flex flex-wrap gap-3 text-xs">
                    <span className="text-stone-500 font-medium">Token:</span>
                    {traceSummary.inputTokens && (
                      <span className="text-stone-600">
                        <span className="text-stone-400">Input</span> {traceSummary.inputTokens.toLocaleString()}
                      </span>
                    )}
                    {traceSummary.outputTokens && (
                      <span className="text-stone-600">
                        <span className="text-stone-400">Output</span> {traceSummary.outputTokens.toLocaleString()}
                      </span>
                    )}
                    {traceSummary.cacheCreationTokens !== undefined && traceSummary.cacheCreationTokens > 0 && (
                      <span className="text-cyan-600">
                        <span className="text-stone-400">Cache Write</span> {traceSummary.cacheCreationTokens.toLocaleString()}
                      </span>
                    )}
                    {traceSummary.cacheReadTokens !== undefined && traceSummary.cacheReadTokens > 0 && (
                      <span className="text-green-600">
                        <span className="text-stone-400">Cache Read</span> {traceSummary.cacheReadTokens.toLocaleString()}
                      </span>
                    )}
                  </div>
                )}

                {/* MCP 工具调用统计 */}
                {traceSummary?.mcpToolsCalled && traceSummary.mcpToolsCalled.length > 0 && (
                  <div className="px-4 py-2 bg-violet-50 border-b border-violet-200 flex flex-wrap gap-2 text-xs">
                    <span className="text-violet-500 font-medium">MCP 调用:</span>
                    {traceSummary.mcpToolsCalled.map(tool => (
                      <span
                        key={tool.name}
                        className="px-1.5 py-0.5 rounded bg-violet-100 text-violet-700"
                      >
                        {tool.name} ×{tool.count}
                      </span>
                    ))}
                  </div>
                )}

                {/* Output Preview (collapsible) */}
                {traceSummary?.outputPreview && (
                  <div className="border-b border-stone-200">
                    <button
                      onClick={() => setShowOutput(!showOutput)}
                      className="w-full px-4 py-2 flex items-center justify-between text-xs text-stone-600 hover:bg-stone-50 transition-colors"
                    >
                      <span className="font-medium">Output Preview</span>
                      <span className="text-stone-400">{showOutput ? '▲' : '▼'}</span>
                    </button>
                    {showOutput && (
                      <div className="px-4 py-3 bg-white border-t border-stone-100 max-h-48 overflow-y-auto">
                        <pre className="text-xs text-stone-700 whitespace-pre-wrap font-mono leading-relaxed">
                          {traceSummary.outputPreview.slice(0, 2000)}
                          {traceSummary.outputPreview.length > 2000 && '...'}
                        </pre>
                      </div>
                    )}
                  </div>
                )}

                {/* Events 标题和控制 */}
                <div className="flex items-center justify-between border-b border-stone-200 px-4 py-2">
                  <span className="text-xs font-medium text-stone-600">
                    Events ({selectedTrace.events.length})
                    {groupedEvents.filter(g => g.type === 'tool_cycle').length > 0 && (
                      <span className="text-stone-400 ml-2">
                        · {groupedEvents.filter(g => g.type === 'tool_cycle').length} 工具调用
                      </span>
                    )}
                  </span>
                  <label className="flex items-center gap-1.5 text-xs text-stone-500 cursor-pointer hover:text-stone-700">
                    <input
                      type="checkbox"
                      checked={showLowPriority}
                      onChange={(e) => setShowLowPriority(e.target.checked)}
                      className="w-3 h-3"
                    />
                    显示 SDK 底层消息
                  </label>
                </div>

                {/* 分组事件列表 */}
                <div className="flex-1 overflow-y-auto">
                  <div className="p-4 space-y-3">
                    {groupedEvents.map((group, groupIdx) => {
                      if (group.type === 'tool_cycle') {
                        // 工具调用周期组
                        const highPriorityEvents = group.events.filter(e => getEventPriority(e.event_type) !== 'low');
                        const lowPriorityEvents = group.events.filter(e => getEventPriority(e.event_type) === 'low');

                        return (
                          <div
                            key={groupIdx}
                            className={`rounded-lg border ${
                              group.hasSandboxBlock
                                ? 'border-red-300 bg-red-50/50'
                                : group.status === 'error'
                                  ? 'border-red-200 bg-red-50/30'
                                  : 'border-blue-200 bg-blue-50/30'
                            }`}
                          >
                            {/* 工具调用组头部 */}
                            <div className={`px-3 py-2 border-b ${
                              group.hasSandboxBlock
                                ? 'border-red-200 bg-red-100/50'
                                : group.status === 'error'
                                  ? 'border-red-100 bg-red-50'
                                  : 'border-blue-100 bg-blue-50'
                            } rounded-t-lg`}>
                              <div className="flex items-center gap-2">
                                <span className={`text-xs font-medium ${
                                  group.hasSandboxBlock ? 'text-red-700' : group.status === 'error' ? 'text-red-600' : 'text-blue-700'
                                }`}>
                                  🔧 {group.toolName}
                                </span>
                                {group.iteration && (
                                  <span className="text-xs text-stone-400">迭代 #{group.iteration}</span>
                                )}
                                {group.hasSandboxBlock && (
                                  <span className="text-xs px-1.5 py-0.5 rounded bg-red-200 text-red-700">🚫 沙箱拦截</span>
                                )}
                                {group.status && !group.hasSandboxBlock && (
                                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                                    group.status === 'error' ? 'bg-red-100 text-red-600' : 'bg-emerald-100 text-emerald-600'
                                  }`}>
                                    {group.status === 'error' ? '失败' : '成功'}
                                  </span>
                                )}
                              </div>
                            </div>
                            {/* 组内事件 */}
                            <div className="p-2 space-y-1">
                              {highPriorityEvents.map((event, idx) => (
                                <EventCard key={idx} event={event} />
                              ))}
                              {showLowPriority && lowPriorityEvents.length > 0 && (
                                <div className="mt-2 pt-2 border-t border-stone-200/50 space-y-1">
                                  <div className="text-xs text-stone-400 px-2">SDK 底层 ({lowPriorityEvents.length})</div>
                                  {lowPriorityEvents.map((event, idx) => (
                                    <EventCard key={`low-${idx}`} event={event} />
                                  ))}
                                </div>
                              )}
                              {!showLowPriority && lowPriorityEvents.length > 0 && (
                                <div className="text-xs text-stone-400 px-3 py-1">
                                  + {lowPriorityEvents.length} 个底层消息
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      } else {
                        // 独立事件
                        const event = group.events[0];
                        const priority = getEventPriority(event.event_type);

                        // 低优先级独立事件的显示控制
                        if (priority === 'low' && !showLowPriority) {
                          return null;
                        }

                        return (
                          <div key={groupIdx} className={priority === 'low' ? 'opacity-60' : ''}>
                            <EventCard event={event} />
                          </div>
                        );
                      }
                    })}
                  </div>
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-stone-400 text-sm">
                Select a trace to view details
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// 格式化时间显示
const formatElapsed = (ms: number): string => {
  if (ms < 1000) return `+${ms}ms`;
  if (ms < 60000) return `+${(ms / 1000).toFixed(1)}s`;
  return `+${(ms / 60000).toFixed(1)}min`;
};

function EventCard({ event }: { event: TraceEvent }) {
  const [isExpanded, setIsExpanded] = useState(false);

  // 根据事件类型和状态确定颜色
  const getEventStyle = () => {
    const isError = event.summary?.toLowerCase().includes('error') ||
                    (event.data as { status?: string; is_error?: boolean })?.status === 'error' ||
                    (event.data as { is_error?: boolean })?.is_error === true;

    if (isError) {
      return {
        border: 'border-red-400',
        bg: 'bg-red-50',
        badge: 'bg-red-100 text-red-700',
        text: 'text-red-600'
      };
    }

    switch (event.event_type) {
      case 'thinking':
        return {
          border: 'border-pink-400',
          bg: 'hover:bg-pink-50',
          badge: 'bg-pink-100 text-pink-700',
          text: 'text-pink-600'
        };
      case 'tool_start':
        return {
          border: 'border-blue-300',
          bg: 'hover:bg-blue-50',
          badge: 'bg-blue-100 text-blue-700',
          text: 'text-blue-600'
        };
      case 'tool_result':
        return {
          border: 'border-emerald-300',
          bg: 'hover:bg-emerald-50',
          badge: 'bg-emerald-100 text-emerald-700',
          text: 'text-emerald-600'
        };
      case 'complete':
        return {
          border: 'border-green-400',
          bg: 'hover:bg-green-50',
          badge: 'bg-green-100 text-green-700',
          text: 'text-green-600'
        };
      case 'request':
        return {
          border: 'border-slate-300',
          bg: 'hover:bg-slate-50',
          badge: 'bg-slate-100 text-slate-700',
          text: 'text-slate-600'
        };
      case 'config':
        return {
          border: 'border-violet-300',
          bg: 'hover:bg-violet-50',
          badge: 'bg-violet-100 text-violet-700',
          text: 'text-violet-600'
        };
      case 'usage':
        return {
          border: 'border-amber-300',
          bg: 'hover:bg-amber-50',
          badge: 'bg-amber-100 text-amber-700',
          text: 'text-amber-600'
        };
      case 'text_delta':
        return {
          border: 'border-cyan-300',
          bg: 'hover:bg-cyan-50',
          badge: 'bg-cyan-100 text-cyan-700',
          text: 'text-cyan-600'
        };
      case 'raw_message':
        return {
          border: 'border-stone-200',
          bg: 'hover:bg-stone-50',
          badge: 'bg-stone-100 text-stone-600',
          text: 'text-stone-500'
        };
      case 'sandbox_block':
        return {
          border: 'border-red-500',
          bg: 'bg-red-50 hover:bg-red-100',
          badge: 'bg-red-200 text-red-800',
          text: 'text-red-700'
        };
      case 'retry':
        return {
          border: 'border-orange-400',
          bg: 'hover:bg-orange-50',
          badge: 'bg-orange-100 text-orange-700',
          text: 'text-orange-600'
        };
      case 'hook_pre_tool':
        return {
          border: 'border-indigo-300',
          bg: 'hover:bg-indigo-50',
          badge: 'bg-indigo-100 text-indigo-700',
          text: 'text-indigo-600'
        };
      case 'hook_post_tool':
        return {
          border: 'border-purple-300',
          bg: 'hover:bg-purple-50',
          badge: 'bg-purple-100 text-purple-700',
          text: 'text-purple-600'
        };
      case 'agent_complete':
        return {
          border: 'border-teal-400',
          bg: 'hover:bg-teal-50',
          badge: 'bg-teal-100 text-teal-700',
          text: 'text-teal-600'
        };
      default:
        return {
          border: 'border-stone-200',
          bg: 'hover:bg-stone-50',
          badge: 'bg-stone-100 text-stone-600',
          text: 'text-stone-500'
        };
    }
  };

  const style = getEventStyle();

  // 获取事件的简短描述
  const getEventLabel = () => {
    switch (event.event_type) {
      case 'request': return 'Request';
      case 'config': return 'Config';
      case 'tool_start': return 'Tool Start';
      case 'tool_result': return 'Tool Result';
      case 'text_delta': return 'Text';
      case 'thinking': return 'Thinking';
      case 'usage': return 'Token';
      case 'complete': return 'Complete';
      case 'raw_message': return 'SDK';
      case 'sandbox_block': return 'Blocked';
      case 'retry': return 'Retry';
      case 'hook_pre_tool': return 'Hook Pre';
      case 'hook_post_tool': return 'Hook Post';
      case 'agent_complete': return 'Agent Done';
      default: return event.event_type;
    }
  };

  // 渲染结构化的详情内容
  const renderExpandedContent = () => {
    const data = event.data as Record<string, unknown>;

    // 辅助函数：截断长文本
    const truncate = (text: string, maxLen = 500) => {
      if (text.length <= maxLen) return text;
      return text.slice(0, maxLen) + '... (' + (text.length - maxLen) + ' more chars)';
    };

    // 辅助函数：格式化对象为可读字符串
    const formatValue = (val: unknown, maxLen = 500): string => {
      if (val === null || val === undefined) return '';
      if (typeof val === 'string') return truncate(val, maxLen);
      if (typeof val === 'object') {
        const str = JSON.stringify(val, null, 2);
        return truncate(str, maxLen);
      }
      return String(val);
    };

    switch (event.event_type) {
      case 'tool_start':
        // 支持两种数据格式：新格式 (full_input) 和旧格式 (input)
        const toolInput = data.full_input || data.input;
        return (
          <div className="space-y-2">
            <div className="flex gap-4 text-xs flex-wrap">
              <span><span className="text-stone-400">Tool:</span> <span className="font-medium text-blue-600">{String(data.name)}</span></span>
              {data.tool_id ? <span><span className="text-stone-400">ID:</span> <span className="font-mono text-stone-500">{String(data.tool_id).slice(0, 12)}...</span></span> : null}
              {data.iteration ? <span><span className="text-stone-400">Iteration:</span> <span className="font-medium">#{String(data.iteration)}</span></span> : null}
              {data.is_mcp ? <span className="text-xs px-1.5 py-0.5 rounded bg-violet-100 text-violet-600">MCP</span> : null}
            </div>
            {toolInput ? (
              <div>
                <div className="text-xs text-stone-400 mb-1">Input:{data.input_truncated ? <span className="text-amber-500 ml-1">(truncated, {String(data.input_length)} chars total)</span> : null}</div>
                <pre className="text-xs bg-blue-50 p-2 rounded overflow-auto max-h-48 text-stone-700 border border-blue-100 whitespace-pre-wrap">
                  {formatValue(toolInput, 2000)}
                </pre>
              </div>
            ) : null}
          </div>
        );

      case 'tool_result':
        // 支持两种数据格式：新格式 (full_output) 和旧格式 (output_summary)
        const toolOutput = data.full_output ||
          (data.output_summary as Record<string, unknown>)?.result ||
          data.output_summary;
        return (
          <div className="space-y-2">
            <div className="flex gap-4 text-xs flex-wrap">
              {data.tool_name ? <span><span className="text-stone-400">Tool:</span> <span className="font-medium">{String(data.tool_name)}</span></span> : null}
              {data.tool_id ? <span><span className="text-stone-400">ID:</span> <span className="font-mono text-stone-500">{String(data.tool_id).slice(0, 12)}...</span></span> : null}
              <span><span className="text-stone-400">Status:</span> <span className={data.is_error ? 'text-red-600 font-medium' : 'text-emerald-600 font-medium'}>{data.status ? String(data.status) : (data.is_error ? 'error' : 'success')}</span></span>
              {data.duration_ms !== undefined ? <span><span className="text-stone-400">Duration:</span> <span className="font-medium">{String(data.duration_ms)}ms</span></span> : null}
            </div>
            {toolOutput ? (
              <div>
                <div className="text-xs text-stone-400 mb-1">Output:{data.output_truncated ? <span className="text-amber-500 ml-1">(truncated, {String(data.output_length)} chars total)</span> : null}</div>
                <pre className={`text-xs p-2 rounded overflow-auto max-h-48 border whitespace-pre-wrap ${data.is_error ? 'bg-red-50 text-red-700 border-red-100' : 'bg-emerald-50 text-stone-700 border-emerald-100'}`}>
                  {formatValue(toolOutput, 2000)}
                </pre>
              </div>
            ) : null}
          </div>
        );

      case 'usage':
        return (
          <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs">
            {data.input_tokens !== undefined && (
              <div><span className="text-stone-400">Input Tokens:</span> <span className="font-medium">{(data.input_tokens as number).toLocaleString()}</span></div>
            )}
            {data.output_tokens !== undefined && (
              <div><span className="text-stone-400">Output Tokens:</span> <span className="font-medium">{(data.output_tokens as number).toLocaleString()}</span></div>
            )}
            {data.cost !== undefined && (
              <div><span className="text-stone-400">Cost:</span> <span className="font-medium text-amber-600">${(data.cost as number).toFixed(4)}</span></div>
            )}
            {data.total_cost !== undefined && (
              <div><span className="text-stone-400">Total Cost:</span> <span className="font-medium text-amber-600">${(data.total_cost as number).toFixed(4)}</span></div>
            )}
          </div>
        );

      case 'complete':
        const toolUsage = data.tool_usage as Record<string, number> | undefined;
        return (
          <div className="space-y-2">
            <div className="flex gap-4 text-xs flex-wrap">
              {data.total_cost !== undefined && <span><span className="text-stone-400">Total Cost:</span> <span className="font-medium text-amber-600">${(data.total_cost as number).toFixed(4)}</span></span>}
              {data.total_input_tokens !== undefined && <span><span className="text-stone-400">Input:</span> <span className="font-medium">{(data.total_input_tokens as number).toLocaleString()}</span></span>}
              {data.total_output_tokens !== undefined && <span><span className="text-stone-400">Output:</span> <span className="font-medium">{(data.total_output_tokens as number).toLocaleString()}</span></span>}
            </div>
            {toolUsage && Object.keys(toolUsage).length > 0 && (
              <div>
                <div className="text-xs text-stone-400 mb-1">Tool Usage:</div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(toolUsage).map(([tool, count]) => (
                    <span key={tool} className="text-xs px-2 py-0.5 rounded bg-stone-100 text-stone-600">
                      {tool}: {count}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        );

      case 'sandbox_block':
        return (
          <div className="space-y-1 text-xs">
            <div><span className="text-stone-400">Tool:</span> <span className="font-medium text-red-600">{String(data.tool_name)}</span></div>
            <div><span className="text-stone-400">Reason:</span> <span className="text-red-700">{String(data.reason)}</span></div>
            {data.blocked_path ? <div><span className="text-stone-400">Path:</span> <span className="font-mono text-stone-500">{String(data.blocked_path)}</span></div> : null}
          </div>
        );

      case 'thinking':
        return (
          <div>
            <div className="text-xs text-stone-400 mb-1">Thinking Content:</div>
            <pre className="text-xs bg-pink-50 p-2 rounded overflow-auto max-h-48 text-stone-700 border border-pink-100 whitespace-pre-wrap">
              {formatValue(data.content || data.thinking, 2000)}
            </pre>
          </div>
        );

      case 'request':
        return (
          <div className="text-xs">
            <div className="text-stone-400 mb-1">User Message:</div>
            <div className="bg-slate-50 p-2 rounded border border-slate-100 whitespace-pre-wrap text-stone-700">
              {formatValue(data.message, 1000)}
            </div>
          </div>
        );

      case 'config':
        return (
          <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs">
            {data.model ? <div><span className="text-stone-400">Model:</span> <span className="font-medium">{String(data.model)}</span></div> : null}
            {data.permission_mode ? <div><span className="text-stone-400">Permission:</span> <span className="font-medium">{String(data.permission_mode)}</span></div> : null}
            {data.allowed_tools ? (
              <div className="col-span-2">
                <span className="text-stone-400">Tools:</span>{' '}
                <span className="text-violet-600">{(data.allowed_tools as string[]).join(', ')}</span>
              </div>
            ) : null}
          </div>
        );

      default:
        // 默认显示原始 JSON
        return (
          <pre className="text-xs bg-stone-50 p-2 rounded overflow-auto max-h-48 text-stone-600 border border-stone-200">
            {JSON.stringify(data, null, 2)}
          </pre>
        );
    }
  };

  return (
    <div className={`border-l-2 ${style.border} pl-3 py-0.5`}>
      <button
        className={`w-full text-left flex items-center gap-2 text-sm py-1.5 px-1 rounded transition-colors ${style.bg}`}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <span className="text-xs text-stone-400 w-16 font-mono">{formatElapsed(event.elapsed_ms)}</span>
        <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${style.badge}`}>
          {getEventLabel()}
        </span>
        {event.summary && (
          <span className={`text-xs truncate flex-1 ${style.text}`}>{event.summary}</span>
        )}
        <span className="text-stone-400 text-xs">{isExpanded ? '−' : '+'}</span>
      </button>

      {isExpanded && (
        <div className="mt-1">
          {renderExpandedContent()}
        </div>
      )}
    </div>
  );
}
