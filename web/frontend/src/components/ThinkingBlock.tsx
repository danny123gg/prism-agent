/**
 * ThinkingBlock - 思考内容折叠面板
 *
 * 极简设计，默认折叠
 */

import { useState } from 'react';

interface ThinkingBlockProps {
  content: string;
  defaultExpanded?: boolean;
}

export function ThinkingBlock({ content, defaultExpanded = false }: ThinkingBlockProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  if (!content) return null;

  const lines = content.split('\n').filter(line => line.trim());
  const preview = lines[0]?.slice(0, 50) || '';

  return (
    <div className="border-l-2 border-stone-200 pl-3 my-2">
      <button
        className="text-xs text-stone-400 hover:text-stone-600 transition-colors flex items-center gap-2 w-full text-left"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <span>{isExpanded ? '−' : '+'}</span>
        <span>Thinking</span>
        {!isExpanded && preview && (
          <span className="text-stone-300 truncate">{preview}...</span>
        )}
      </button>

      {isExpanded && (
        <pre className="mt-2 text-xs text-stone-500 whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto">
          {content}
        </pre>
      )}
    </div>
  );
}
