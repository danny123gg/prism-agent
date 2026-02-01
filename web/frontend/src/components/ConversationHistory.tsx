/**
 * ConversationHistory - 对话历史
 *
 * 极简的历史展示
 */

import { useState, useMemo } from 'react';
import { Message } from '../types';

interface ConversationHistoryProps {
  isOpen: boolean;
  onClose: () => void;
  messages: Message[];
}

interface Turn {
  index: number;
  userMessage: string;
  assistantMessage: string;
  inputTokens: number;
  outputTokens: number;
  contextPercent: number;
  cost: number;
  toolsUsed: string[];
}

export function ConversationHistory({ isOpen, onClose, messages }: ConversationHistoryProps) {
  const [selectedTurn, setSelectedTurn] = useState<number | null>(null);

  const turns = useMemo(() => {
    const result: Turn[] = [];

    for (let i = 0; i < messages.length; i += 2) {
      const userMsg = messages[i];
      const assistantMsg = messages[i + 1];

      if (!userMsg || userMsg.role !== 'user') continue;
      if (!assistantMsg || assistantMsg.role !== 'assistant') continue;

      result.push({
        index: result.length + 1,
        userMessage: userMsg.content,
        assistantMessage: assistantMsg.content,
        inputTokens: assistantMsg.cost?.input_tokens || 0,
        outputTokens: assistantMsg.cost?.output_tokens || 0,
        contextPercent: assistantMsg.cost?.context_percent || 0,
        cost: assistantMsg.cost?.cost || 0,
        toolsUsed: assistantMsg.toolCalls.map(t => t.name),
      });
    }

    return result;
  }, [messages]);

  const stats = useMemo(() => {
    if (turns.length === 0) return null;

    const totalInput = turns.reduce((sum, t) => sum + t.inputTokens, 0);
    const totalOutput = turns.reduce((sum, t) => sum + t.outputTokens, 0);
    const totalCost = turns.reduce((sum, t) => sum + t.cost, 0);

    return { totalInput, totalOutput, totalCost, latestContext: turns[turns.length - 1]?.contextPercent || 0 };
  }, [turns]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-stone-900/30 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[80vh] overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="px-5 py-4 border-b border-stone-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-base font-medium text-stone-700">History</h2>
            <span className="text-xs text-stone-400">{turns.length} turns</span>
          </div>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-600 text-sm">Close</button>
        </div>

        <div className="p-5 overflow-y-auto max-h-[calc(80vh-60px)]">
          {turns.length === 0 ? (
            <div className="text-center py-8 text-stone-400 text-sm">No conversation history</div>
          ) : (
            <div className="space-y-6">
              {/* Stats */}
              {stats && (
                <div className="grid grid-cols-4 gap-4">
                  <div>
                    <div className="text-lg font-medium text-stone-700">{turns.length}</div>
                    <div className="text-xs text-stone-400">Turns</div>
                  </div>
                  <div>
                    <div className="text-lg font-medium text-stone-700">{(stats.totalInput + stats.totalOutput).toLocaleString()}</div>
                    <div className="text-xs text-stone-400">Tokens</div>
                  </div>
                  <div>
                    <div className="text-lg font-medium text-stone-700">${stats.totalCost.toFixed(4)}</div>
                    <div className="text-xs text-stone-400">Cost</div>
                  </div>
                  <div>
                    <div className="text-lg font-medium text-stone-700">{stats.latestContext.toFixed(0)}%</div>
                    <div className="text-xs text-stone-400">Context</div>
                  </div>
                </div>
              )}

              {/* Timeline */}
              <div className="space-y-2">
                {turns.map((turn, idx) => (
                  <div
                    key={idx}
                    className={`p-3 rounded border transition-colors ${
                      selectedTurn === idx ? 'border-stone-300 bg-stone-50' : 'border-stone-100'
                    }`}
                    onMouseEnter={() => setSelectedTurn(idx)}
                    onMouseLeave={() => setSelectedTurn(null)}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs text-stone-400">Turn {turn.index}</span>
                      <span className="text-xs text-stone-400">
                        {(turn.inputTokens + turn.outputTokens).toLocaleString()} Token · ${turn.cost.toFixed(4)}
                      </span>
                    </div>

                    <div className="text-sm text-stone-600 line-clamp-1 mb-1">
                      {turn.userMessage}
                    </div>
                    <div className="text-sm text-stone-500 line-clamp-1">
                      {turn.assistantMessage.substring(0, 100)}
                    </div>

                    {turn.toolsUsed.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {turn.toolsUsed.slice(0, 5).map((tool, i) => (
                          <span key={i} className="text-xs px-1.5 py-0.5 bg-stone-100 text-stone-500 rounded">
                            {tool}
                          </span>
                        ))}
                        {turn.toolsUsed.length > 5 && (
                          <span className="text-xs text-stone-400">+{turn.toolsUsed.length - 5}</span>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
