/**
 * HooksPanel - Hooks 可视化组件
 *
 * 极简的 Hook 事件展示
 */

import { useState } from 'react';
import { HookEvent } from '../types';

interface HooksPanelProps {
  events: HookEvent[];
}

export function HooksPanel({ events }: HooksPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (events.length === 0) return null;

  const blockedCount = events.filter(e => e.action === 'block').length;

  return (
    <div className="border-l-2 border-stone-200 pl-3 my-2">
      <button
        className="text-xs text-stone-400 hover:text-stone-600 transition-colors flex items-center gap-2 w-full text-left"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <span>{isExpanded ? '−' : '+'}</span>
        <span>Hooks</span>
        <span className="text-stone-300">{events.length}</span>
        {blockedCount > 0 && (
          <span className="text-red-400">{blockedCount} 已拦截</span>
        )}
      </button>

      {isExpanded && (
        <div className="mt-2 space-y-1">
          {events.map((event) => (
            <div
              key={event.id}
              className={`flex items-center gap-2 text-xs py-1 ${
                event.action === 'block' ? 'text-red-500' : 'text-stone-500'
              }`}
            >
              <span className="text-stone-300">
                {event.type === 'pre_tool' ? '→' : '←'}
              </span>
              <span className="font-medium">{event.toolName}</span>
              {event.action && (
                <span className={event.action === 'block' ? 'text-red-400' : 'text-stone-400'}>
                  {event.action === 'block' ? '拦截' : event.action}
                </span>
              )}
              {event.message && (
                <span className="text-stone-400 truncate flex-1">{event.message}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
