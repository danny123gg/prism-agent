/**
 * SkillPanel - Skill 面板
 *
 * 极简的 Skill 展示
 */

import { useState, useEffect } from 'react';

interface Skill {
  id: string;
  name: string;
  description: string;
  allowed_tools: string[];
  file_path: string;
  content_preview: string;
}

interface SkillDetail extends Skill {
  content: string;
  raw: string;
}

interface SkillPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onUseSkill?: (skillId: string) => void;
}

export function SkillPanel({ isOpen, onClose, onUseSkill }: SkillPanelProps) {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [selectedSkill, setSelectedSkill] = useState<SkillDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSkills = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/skills');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setSkills(data.skills || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch');
    } finally {
      setLoading(false);
    }
  };

  const fetchSkillDetail = async (skillId: string) => {
    setLoading(true);
    try {
      const response = await fetch(`/api/skills/${skillId}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setSelectedSkill(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) fetchSkills();
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-stone-900/30 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[80vh] overflow-hidden" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="px-5 py-4 border-b border-stone-100 flex items-center justify-between">
          <h2 className="text-base font-medium text-stone-700">Skills</h2>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-600 text-sm">
            Close
          </button>
        </div>

        {/* Content */}
        <div className="flex h-[calc(80vh-60px)]">
          {/* List */}
          <div className="w-1/3 border-r border-stone-100 overflow-y-auto p-4">
            {error && (
              <div className="text-xs text-red-500 mb-3">{error}</div>
            )}

            {loading && skills.length === 0 ? (
              <div className="text-xs text-stone-400">加载中...</div>
            ) : skills.length === 0 ? (
              <div className="text-center py-8 text-stone-400 text-sm">
                暂无配置的 Skill
              </div>
            ) : (
              <div className="space-y-1">
                {skills.map((skill) => (
                  <button
                    key={skill.id}
                    onClick={() => fetchSkillDetail(skill.id)}
                    className={`w-full text-left p-2 rounded text-sm transition-colors ${
                      selectedSkill?.id === skill.id
                        ? 'bg-stone-100 text-stone-800'
                        : 'text-stone-600 hover:bg-stone-50'
                    }`}
                  >
                    <div className="font-medium">{skill.name}</div>
                    <div className="text-xs text-stone-400 mt-0.5 line-clamp-1">
                      {skill.description}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Detail */}
          <div className="flex-1 overflow-y-auto p-5">
            {selectedSkill ? (
              <div className="space-y-4">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-medium text-stone-800">{selectedSkill.name}</h3>
                    <p className="text-sm text-stone-500 mt-1">{selectedSkill.description}</p>
                  </div>
                  {onUseSkill && (
                    <button
                      onClick={() => onUseSkill(selectedSkill.id)}
                      className="px-3 py-1.5 bg-stone-800 text-white rounded text-sm hover:bg-stone-700"
                    >
                      Use
                    </button>
                  )}
                </div>

                {selectedSkill.allowed_tools.length > 0 && (
                  <div>
                    <div className="text-xs text-stone-400 mb-1">工具权限</div>
                    <div className="flex flex-wrap gap-1">
                      {selectedSkill.allowed_tools.map((tool) => (
                        <span key={tool} className="text-xs px-1.5 py-0.5 bg-stone-100 text-stone-600 rounded">
                          {tool}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div>
                  <div className="text-xs text-stone-400 mb-1">内容</div>
                  <pre className="text-xs text-stone-600 bg-stone-50 p-3 rounded overflow-auto max-h-72 border border-stone-100">
                    {selectedSkill.content}
                  </pre>
                </div>

                <div className="text-xs text-stone-400 pt-2 border-t border-stone-100">
                  输入 <code className="bg-stone-100 px-1 rounded">/{selectedSkill.id}</code> 触发
                </div>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-stone-400 text-sm">
                选择一个 Skill
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
