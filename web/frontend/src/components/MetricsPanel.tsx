/**
 * MetricsPanel - 性能指标面板
 *
 * 极简的指标展示
 */

import { useState, useEffect } from 'react';

interface MetricsData {
  uptime_seconds: number;
  requests: { total: number; success: number; error: number; success_rate: number };
  latency_ms: { avg: number; p50: number; p95: number };
  ttft_ms: { avg: number };
  tokens: { total_input: number; total_output: number; throughput_per_second: number };
  tool_calls: Record<string, number>;
}

interface MetricsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export function MetricsPanel({ isOpen, onClose }: MetricsPanelProps) {
  const [metrics, setMetrics] = useState<MetricsData | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchMetrics = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/metrics');
      if (response.ok) setMetrics(await response.json());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) fetchMetrics();
  }, [isOpen]);

  if (!isOpen) return null;

  const formatMs = (ms: number) => ms < 1000 ? `${ms.toFixed(0)}ms` : `${(ms / 1000).toFixed(2)}s`;

  return (
    <div className="fixed inset-0 bg-stone-900/30 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="px-5 py-4 border-b border-stone-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-base font-medium text-stone-700">Metrics</h2>
            {metrics && (
              <span className="text-xs text-stone-400">
                Uptime: {Math.floor(metrics.uptime_seconds / 3600)}h {Math.floor((metrics.uptime_seconds % 3600) / 60)}m
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button onClick={fetchMetrics} className="text-stone-400 hover:text-stone-600 p-1.5 rounded hover:bg-stone-100 transition-colors" title="刷新">
              {loading ? (
                <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              )}
            </button>
            <button onClick={onClose} className="text-stone-400 hover:text-stone-600 text-sm">Close</button>
          </div>
        </div>

        <div className="p-5 overflow-y-auto max-h-[calc(80vh-60px)]">
          {metrics ? (
            <div className="space-y-5">
              {/* Stats Grid - 2x2 cards */}
              <div className="grid grid-cols-2 gap-4">
                {/* Requests Card */}
                <div className="bg-stone-50 rounded-lg p-4">
                  <div className="text-xs font-medium text-stone-500 mb-3">Requests</div>
                  <div className="flex items-baseline gap-2 mb-2">
                    <span className="text-2xl font-semibold text-stone-800">{metrics.requests.total}</span>
                    <span className="text-xs text-stone-400">total</span>
                  </div>
                  <div className="flex gap-4 text-xs">
                    <span className="text-emerald-600">{metrics.requests.success} ok</span>
                    <span className="text-red-500">{metrics.requests.error} error</span>
                    <span className="text-stone-500">{metrics.requests.success_rate.toFixed(0)}%</span>
                  </div>
                </div>

                {/* Latency Card */}
                <div className="bg-stone-50 rounded-lg p-4">
                  <div className="text-xs font-medium text-stone-500 mb-3">Latency</div>
                  <div className="flex items-baseline gap-2 mb-2">
                    <span className="text-2xl font-semibold text-stone-800">{formatMs(metrics.latency_ms.avg)}</span>
                    <span className="text-xs text-stone-400">avg</span>
                  </div>
                  <div className="flex gap-4 text-xs text-stone-500">
                    <span>p50: {formatMs(metrics.latency_ms.p50)}</span>
                    <span>p95: {formatMs(metrics.latency_ms.p95)}</span>
                  </div>
                </div>

                {/* Tokens Card */}
                <div className="bg-stone-50 rounded-lg p-4">
                  <div className="text-xs font-medium text-stone-500 mb-3">Tokens</div>
                  <div className="flex items-baseline gap-2 mb-2">
                    <span className="text-2xl font-semibold text-stone-800">
                      {(metrics.tokens.total_input + metrics.tokens.total_output).toLocaleString()}
                    </span>
                    <span className="text-xs text-stone-400">total</span>
                  </div>
                  <div className="flex gap-4 text-xs text-stone-500">
                    <span>{metrics.tokens.total_input.toLocaleString()} input</span>
                    <span>{metrics.tokens.total_output.toLocaleString()} output</span>
                  </div>
                </div>

                {/* Performance Card */}
                <div className="bg-stone-50 rounded-lg p-4">
                  <div className="text-xs font-medium text-stone-500 mb-3">Performance</div>
                  <div className="flex items-baseline gap-2 mb-2">
                    <span className="text-2xl font-semibold text-stone-800">{formatMs(metrics.ttft_ms.avg)}</span>
                    <span className="text-xs text-stone-400">TTFT</span>
                  </div>
                  <div className="flex gap-4 text-xs text-stone-500">
                    <span>{metrics.tokens.throughput_per_second.toFixed(1)} tok/s</span>
                  </div>
                </div>
              </div>

              {/* Tools */}
              {Object.keys(metrics.tool_calls).length > 0 && (
                <div className="pt-2">
                  <div className="text-xs font-medium text-stone-500 mb-2">Tools</div>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(metrics.tool_calls).map(([tool, count]) => (
                      <span key={tool} className="text-xs px-2 py-1 bg-stone-100 text-stone-600 rounded">
                        {tool} <span className="text-stone-400">×{count}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-8 text-stone-400 text-sm">
              {loading ? '加载中...' : '暂无数据'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
