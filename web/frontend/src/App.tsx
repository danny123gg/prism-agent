/**
 * App - 主应用组件
 *
 * Agent Trace Visualization 应用入口
 */

import { useEffect, useState, useRef } from 'react';
import { useSSE } from './hooks/useSSE';
import { MessageList } from './components/MessageList';
import { ChatWindow } from './components/ChatWindow';
import { TraceViewer } from './components/TraceViewer';
import { MetricsPanel } from './components/MetricsPanel';
import { ConversationHistory } from './components/ConversationHistory';
import { SkillPanel } from './components/SkillPanel';
import { ExampleLibrary } from './components/ExampleLibrary';
// import { PlanModeIndicator } from './components/PlanModeIndicator';  // (#24) - 暂未使用

type WarmupStatus = 'idle' | 'warming' | 'ready' | 'failed';

function App() {
  const { messages, isLoading, loadingStage, error, sessionConfig, currentIteration, sendMessage, clearMessages } = useSSE();
  const [warmupStatus, setWarmupStatus] = useState<WarmupStatus>('idle');
  const [isTraceViewerOpen, setIsTraceViewerOpen] = useState(false);
  const [isMetricsPanelOpen, setIsMetricsPanelOpen] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isSkillPanelOpen, setIsSkillPanelOpen] = useState(false);
  const [isExampleLibraryOpen, setIsExampleLibraryOpen] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // 点击外部关闭菜单
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // 页面加载时自动预热 SDK
  useEffect(() => {
    const warmup = async () => {
      setWarmupStatus('warming');
      try {
        const response = await fetch('/api/warmup', { method: 'POST' });
        const data = await response.json();
        if (data.status === 'ready' || data.status === 'already_ready') {
          setWarmupStatus('ready');
        } else if (data.status === 'warming_up') {
          // 正在预热中，轮询状态
          const checkStatus = setInterval(async () => {
            const statusRes = await fetch('/api/warmup/status');
            const statusData = await statusRes.json();
            if (statusData.ready) {
              setWarmupStatus('ready');
              clearInterval(checkStatus);
            }
          }, 1000);
        } else {
          setWarmupStatus('failed');
        }
      } catch (e) {
        console.error('Warmup failed:', e);
        setWarmupStatus('failed');
      }
    };
    warmup();
  }, []);

  // 获取状态指示器信息
  const getStatusInfo = () => {
    if (warmupStatus === 'warming') return { color: 'bg-amber-400', pulse: true, text: '预热中' };
    if (warmupStatus === 'failed') return { color: 'bg-red-400', pulse: false, text: '失败' };
    if (isLoading) return { color: 'bg-blue-400', pulse: true, text: `第 ${currentIteration} 轮` };
    if (warmupStatus === 'ready') return { color: 'bg-emerald-400', pulse: false, text: '就绪' };
    return { color: 'bg-gray-300', pulse: false, text: '空闲' };
  };
  const status = getStatusInfo();

  return (
    <div className="h-screen flex flex-col bg-stone-50">
      {/* 头部 - 极简设计 */}
      <header className="bg-white border-b border-stone-200 px-5 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-base font-medium text-stone-700">Prism</h1>

          {/* 统一状态指示器 */}
          <div className="flex items-center gap-1.5 px-2 py-1 bg-stone-100 rounded text-xs text-stone-600">
            <span className={`w-1.5 h-1.5 rounded-full ${status.color} ${status.pulse ? 'animate-pulse' : ''}`} />
            <span>{status.text}</span>
            {sessionConfig?.sandboxEnabled && <span className="text-stone-400">· 沙盒</span>}
            {sessionConfig?.permissionMode && (
              <span className="text-stone-400">· {sessionConfig.permissionMode}</span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* 下拉菜单 */}
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className="p-2 text-stone-500 hover:text-stone-700 hover:bg-stone-100 rounded transition-colors"
              title="更多选项"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>

            {isMenuOpen && (
              <div
                className="absolute right-0 mt-1 w-36 bg-white border border-stone-200 rounded-lg shadow-lg py-1 z-50"
                onMouseDown={(e) => e.stopPropagation()}
              >
                <button
                  onClick={() => { setIsExampleLibraryOpen(true); setIsMenuOpen(false); }}
                  className="w-full px-3 py-2 text-left text-sm text-stone-600 hover:bg-stone-50"
                >
                  Playground
                </button>
                <button
                  onClick={() => { setIsSkillPanelOpen(true); setIsMenuOpen(false); }}
                  className="w-full px-3 py-2 text-left text-sm text-stone-600 hover:bg-stone-50"
                >
                  Skills
                </button>
                <button
                  onClick={() => { setIsHistoryOpen(true); setIsMenuOpen(false); }}
                  className="w-full px-3 py-2 text-left text-sm text-stone-600 hover:bg-stone-50"
                >
                  History
                </button>
                <div className="my-1 border-t border-stone-100" />
                <button
                  onClick={() => { setIsMetricsPanelOpen(true); setIsMenuOpen(false); }}
                  className="w-full px-3 py-2 text-left text-sm text-stone-600 hover:bg-stone-50"
                >
                  Metrics
                </button>
                <button
                  onClick={() => { setIsTraceViewerOpen(true); setIsMenuOpen(false); }}
                  className="w-full px-3 py-2 text-left text-sm text-stone-600 hover:bg-stone-50"
                >
                  Traces
                </button>
              </div>
            )}
          </div>

          {/* 清空按钮 */}
          <button
            onClick={() => setShowClearConfirm(true)}
            className="px-3 py-1.5 text-sm text-stone-500 hover:text-stone-700 hover:bg-stone-100 rounded transition-colors"
          >
            清空
          </button>
        </div>
      </header>

      {/* 错误提示 */}
      {error && (
        <div className="bg-red-50 border-b border-red-100 px-5 py-2 text-red-600 text-sm">
          {error}
        </div>
      )}

      {/* 消息列表 */}
      <MessageList messages={messages} />

      {/* 输入区域 */}
      <ChatWindow onSendMessage={sendMessage} isLoading={isLoading} loadingStage={loadingStage} />

      {/* Trace 查看器 */}
      <TraceViewer
        isOpen={isTraceViewerOpen}
        onClose={() => setIsTraceViewerOpen(false)}
      />

      {/* 性能指标面板 */}
      <MetricsPanel
        isOpen={isMetricsPanelOpen}
        onClose={() => setIsMetricsPanelOpen(false)}
      />

      {/* 对话历史面板 */}
      <ConversationHistory
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        messages={messages}
      />

      {/* Skill 面板 (#22) */}
      <SkillPanel
        isOpen={isSkillPanelOpen}
        onClose={() => setIsSkillPanelOpen(false)}
        onUseSkill={(skillId) => {
          setIsSkillPanelOpen(false);
          sendMessage(`/${skillId}`);
        }}
      />

      {/* 示例库 (#60) */}
      <ExampleLibrary
        isOpen={isExampleLibraryOpen}
        onClose={() => setIsExampleLibraryOpen(false)}
        onSelectExample={(prompt) => {
          setIsExampleLibraryOpen(false);
          sendMessage(prompt);
        }}
      />

      {/* 清空确认对话框 */}
      {showClearConfirm && (
        <div
          className="fixed inset-0 bg-stone-900/30 flex items-center justify-center z-50"
          onClick={() => setShowClearConfirm(false)}
        >
          <div
            className="bg-white rounded-lg shadow-xl p-6 max-w-sm mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-medium text-stone-800 mb-2">清空对话？</h3>
            <p className="text-sm text-stone-600 mb-6">此操作将清除所有对话历史，无法撤销。</p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowClearConfirm(false)}
                className="px-4 py-2 text-sm text-stone-600 hover:bg-stone-100 rounded transition-colors"
              >
                取消
              </button>
              <button
                onClick={() => {
                  clearMessages();
                  setShowClearConfirm(false);
                }}
                className="px-4 py-2 text-sm text-white bg-red-500 hover:bg-red-600 rounded transition-colors"
              >
                确定清空
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
