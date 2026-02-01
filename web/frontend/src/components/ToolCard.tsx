/**
 * ToolCard - 工具调用卡片组件
 *
 * 简洁的工具调用展示，点击展开详情
 */

import { useState } from 'react';
import { ToolCall, ToolStatus } from '../types';

// URL 正则表达式
const URL_REGEX = /(https?:\/\/[^\s<>"{}|\\^`[\]]+)/g;

// 将文本中的 URL 转换为可点击链接
function renderTextWithLinks(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match;

  // 重置正则表达式
  URL_REGEX.lastIndex = 0;

  while ((match = URL_REGEX.exec(text)) !== null) {
    // 添加 URL 之前的文本
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    // 添加可点击的 URL
    const url = match[0];
    parts.push(
      <a
        key={`${match.index}-${url}`}
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-blue-400 hover:text-blue-300 underline break-all"
        onClick={(e) => e.stopPropagation()}
      >
        {url}
      </a>
    );

    lastIndex = match.index + url.length;
  }

  // 添加剩余文本
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : [text];
}

interface ToolCardProps {
  tool: ToolCall;
}

// Tool icons - consistent text symbols
const toolIcons: Record<string, string> = {
  Read: '◇',
  Write: '◆',
  Edit: '◈',
  Bash: '▸',
  Glob: '◎',
  Grep: '⌕',
  Task: '◇',
  WebFetch: '◉',
  WebSearch: '○',
  Skill: '★',
};

export function ToolCard({ tool }: ToolCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const icon = toolIcons[tool.name] || '•';
  const duration = tool.endTime
    ? `${((tool.endTime - tool.startTime) / 1000).toFixed(2)}s`
    : null;

  // Skill 工具的 is_error=True 是 SDK 预期行为，不是真正的错误
  const isSkillTool = tool.name === 'Skill';

  // 状态样式
  const getStatusStyle = () => {
    if (tool.status === ToolStatus.RUNNING) return 'border-l-blue-400 bg-blue-50/50';
    if (tool.status === ToolStatus.COMPLETED) return 'border-l-stone-300 bg-stone-50/50';
    if (tool.status === ToolStatus.ERROR) {
      // Skill 工具使用紫色而非红色
      if (isSkillTool) return 'border-l-purple-400 bg-purple-50/50';
      return 'border-l-red-400 bg-red-50/50';
    }
    return 'border-l-stone-300 bg-stone-50/50';
  };

  // 格式化显示输入 - 更简洁
  const formatInput = (): string => {
    const input = tool.input as Record<string, string | number | undefined>;
    if (tool.name === 'Read') return String(input.file_path || '').split('/').pop() || '';
    if (tool.name === 'Write') return String(input.file_path || '').split('/').pop() || '';
    if (tool.name === 'Edit') return String(input.file_path || '').split('/').pop() || '';
    if (tool.name === 'Bash') return String(input.command || input.description || '').slice(0, 60);
    if (tool.name === 'Glob' || tool.name === 'Grep') return String(input.pattern || '');
    if (tool.name === 'Task') return String(input.description || '');
    return '';
  };

  // 获取推理意图（仅在展开时显示）
  const getIntent = (): string | null => {
    const input = tool.input as Record<string, string | undefined>;
    if (tool.name === 'Bash' && input.description) return input.description;
    if (tool.name === 'Task' && input.description) return input.description;
    return null;
  };

  return (
    <div
      className={`border-l-2 rounded-r my-1 transition-all ${getStatusStyle()}`}
    >
      {/* 头部 - 极简 */}
      <div
        className="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-white/50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <span className="text-stone-400 text-sm w-5 text-center">{icon}</span>
        <span className="text-sm font-medium text-stone-700">{tool.name}</span>
        <span className="text-xs text-stone-400 truncate flex-1">{formatInput()}</span>

        {/* Status indicator */}
        {tool.status === ToolStatus.RUNNING && (
          <span className="flex items-center gap-1 text-xs text-blue-500">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
            <span className="animate-pulse">Running</span>
          </span>
        )}
        {tool.status === ToolStatus.ERROR && !isSkillTool && (
          <span className="text-xs text-red-500">Error</span>
        )}
        {isSkillTool && (
          <span className="text-xs text-purple-500">Loaded</span>
        )}
        {tool.status === ToolStatus.COMPLETED && duration && (
          <span className="text-xs text-stone-400">{duration}</span>
        )}

        <span className="text-stone-300 text-xs">{isExpanded ? '−' : '+'}</span>
      </div>

      {/* 展开详情 */}
      {isExpanded && (
        <div className="px-3 pb-3 pt-1 border-t border-stone-100 space-y-2">
          {/* 意图（如果有） */}
          {getIntent() && (
            <div className="text-xs text-stone-500 italic">
              → {getIntent()}
            </div>
          )}

          {/* Input */}
          <div>
            <div className="text-xs text-stone-400 mb-1">Input</div>
            <pre className="text-xs bg-stone-800 p-2 rounded overflow-x-auto max-h-32 overflow-y-auto text-stone-100 border border-stone-700">
              {JSON.stringify(tool.input, null, 2)}
            </pre>
          </div>

          {/* Output */}
          {tool.output !== undefined && (
            <div>
              <div className="text-xs text-stone-400 mb-1">Output</div>
              <pre className="text-xs bg-stone-800 p-2 rounded overflow-x-auto max-h-40 overflow-y-auto text-stone-100 border border-stone-700 whitespace-pre-wrap">
                {renderTextWithLinks(
                  typeof tool.output === 'string'
                    ? tool.output
                    : JSON.stringify(tool.output, null, 2)
                )}
              </pre>
            </div>
          )}

          {/* Error */}
          {tool.error && (
            <div>
              <div className="text-xs text-red-400 mb-1">Error</div>
              <pre className="text-xs bg-red-50 p-2 rounded text-red-600 border border-red-100">
                {tool.error}
              </pre>
            </div>
          )}

          {/* 时间 */}
          {tool.endTime && (
            <div className="text-xs text-stone-400 pt-1 border-t border-stone-100">
              {new Date(tool.startTime).toLocaleTimeString()} → {new Date(tool.endTime).toLocaleTimeString()}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
