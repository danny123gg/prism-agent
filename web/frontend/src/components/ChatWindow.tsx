/**
 * ChatWindow - 聊天输入组件
 *
 * 极简输入区域
 */

import { useState, FormEvent, KeyboardEvent, useRef, useEffect } from 'react';

type LoadingStage = 'idle' | 'connecting' | 'waiting' | 'thinking' | 'processing' | 'tool_calling';

interface ChatWindowProps {
  onSendMessage: (message: string, useThinking?: boolean) => void;
  isLoading: boolean;
  loadingStage: LoadingStage;
}

/* 加载状态标签 - 预留给后续使用
const loadingLabels: Record<LoadingStage, string> = {
  idle: '',
  connecting: 'Connecting',
  waiting: 'Waiting',
  thinking: 'Thinking',
  processing: 'Processing',
  tool_calling: 'Running',
};
*/

export function ChatWindow({ onSendMessage, isLoading, loadingStage: _loadingStage }: ChatWindowProps) {
  const [input, setInput] = useState('');
  const [useThinking, setUseThinking] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 自动调整 textarea 高度
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }
  }, [input]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input.trim(), useThinking);
      setInput('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="border-t border-stone-200 bg-white px-4 pt-3 pb-4">
      {/* 模式选择 - 输入框上方 */}
      <div className="flex items-center gap-3 mb-2 px-1">
        <button
          type="button"
          onClick={() => setUseThinking(false)}
          disabled={isLoading}
          className={`text-xs px-2 py-1 rounded transition-colors ${
            !useThinking
              ? 'bg-stone-800 text-white'
              : 'text-stone-400 hover:text-stone-600'
          }`}
        >
          Normal
        </button>
        <button
          type="button"
          onClick={() => setUseThinking(true)}
          disabled={isLoading}
          className={`text-xs px-2 py-1 rounded transition-colors ${
            useThinking
              ? 'bg-amber-500 text-white'
              : 'text-stone-400 hover:text-stone-600'
          }`}
        >
          Thinking
        </button>
        {useThinking && (
          <span className="text-xs text-amber-600">Extended thinking enabled</span>
        )}
      </div>

      {/* 输入框 + 发送按钮 */}
      <div className="flex gap-2 items-end">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入消息..."
          className={`flex-1 resize-none border rounded-lg px-4 py-2 text-sm focus:outline-none transition-colors ${
            useThinking
              ? 'border-amber-300 focus:border-amber-400'
              : 'border-stone-200 focus:border-stone-400'
          }`}
          rows={1}
          disabled={isLoading}
          style={{ minHeight: '38px', maxHeight: '120px' }}
        />
        <button
          type="submit"
          disabled={!input.trim() || isLoading}
          className={`flex-shrink-0 w-[38px] h-[38px] flex items-center justify-center rounded-lg transition-colors ${
            !input.trim() || isLoading
              ? 'bg-stone-100 text-stone-400'
              : 'bg-stone-800 text-white hover:bg-stone-700'
          }`}
        >
          {isLoading ? (
            <span className="w-4 h-4 border-2 border-stone-400 border-t-transparent rounded-full animate-spin block" />
          ) : (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          )}
        </button>
      </div>
    </form>
  );
}
