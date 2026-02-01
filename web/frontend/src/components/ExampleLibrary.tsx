/**
 * ExampleLibrary - 示例库
 *
 * 帮助用户快速体验 Agent 能做什么
 */

import { useState } from 'react';

interface Example {
  id: string;
  title: string;
  description: string;
  prompt: string;
  category: string;
  tools?: string[];
  tip?: string;  // 一句话提示
  recommended?: boolean;  // 推荐给新手
}

const EXAMPLES: Example[] = [
  // ========== Getting Started ==========
  {
    id: 'hello',
    title: 'Hello World',
    description: 'Simple conversation to experience Agent response',
    prompt: 'Hello! Please briefly introduce yourself.',
    category: 'start',
    tools: [],
    tip: 'No tools needed, pure conversation',
    recommended: true,
  },
  {
    id: 'read-file',
    title: 'Read File',
    description: 'Have Agent read file contents',
    prompt: 'Read the README.md file and summarize what this project is about.',
    category: 'start',
    tools: ['Read', 'Glob'],
    tip: 'Watch how Agent locates the file before reading',
  },
  {
    id: 'search-files',
    title: 'Search Files',
    description: 'Find files by name pattern',
    prompt: 'Find all Python files (.py) in the current directory.',
    category: 'start',
    tools: ['Glob'],
    tip: 'Glob supports wildcards like *.py, **/*.js',
  },
  {
    id: 'run-command',
    title: 'Run Command',
    description: 'Have Agent execute a system command',
    prompt: 'List all files in the current directory with details.',
    category: 'start',
    tools: ['Bash'],
    tip: 'Agent selects appropriate command based on OS',
  },

  // ========== Practical ==========
  {
    id: 'write-and-run',
    title: 'Write & Run',
    description: 'Create a script file and execute it',
    prompt: 'Create a Python file that prints "Hello from Agent!", then run it and show the output.',
    category: 'practical',
    tools: ['Write', 'Bash'],
    tip: 'Watch how Agent combines multiple tools',
  },
  {
    id: 'analyze-project',
    title: 'Analyze Project',
    description: 'Have Agent understand the project',
    prompt: 'Analyze the project structure and explain what kind of project this is.',
    category: 'practical',
    tools: ['Glob', 'Read'],
    tip: 'Agent traverses directories and reads key files to infer',
  },
  {
    id: 'search-content',
    title: 'Content Search',
    description: 'Search for specific content in code',
    prompt: 'Search for all TODO comments in the codebase.',
    category: 'practical',
    tools: ['Grep'],
    tip: 'Grep can search file contents with regex support',
  },
  {
    id: 'modify-file',
    title: 'Modify File',
    description: 'Read, modify, and save a file',
    prompt: 'Read hello.txt, add a new line "Modified by Agent" at the end, and save it.',
    category: 'practical',
    tools: ['Read', 'Edit'],
    tip: 'Agent reads to understand structure, then makes precise edits',
  },

  // ========== Multi-turn ==========
  {
    id: 'context-memory',
    title: 'Context Memory',
    description: 'Test conversation history',
    prompt: 'My name is Alice. Please remember it.',
    category: 'multi-turn',
    tools: [],
    tip: 'After sending this, ask "What is my name?" in a new message to test history',
    recommended: true,
  },
  {
    id: 'follow-up-questions',
    title: 'Follow-up Questions',
    description: 'Continue the conversation',
    prompt: 'Read the README.md file.',
    category: 'multi-turn',
    tools: ['Read'],
    tip: 'After this, ask follow-up questions like "What is the main feature?" without repeating context',
  },
  {
    id: 'iterative-refinement',
    title: 'Iterative Refinement',
    description: 'Gradually improve through conversation',
    prompt: 'Help me write a Python function to calculate Fibonacci numbers.',
    category: 'multi-turn',
    tools: ['Write'],
    tip: 'After initial version, ask for optimizations or edge case handling',
  },
  {
    id: 'iterative-debug',
    title: 'Iterative Debug',
    description: 'Write code, test, find issues, fix',
    prompt: 'Write a Python function to calculate factorial, test it with 0-10, and fix any bugs you find.',
    category: 'multi-turn',
    tools: ['Write', 'Bash', 'Edit'],
    tip: 'Watch Agent iterate: write → test → fix → retest',
  },

  // ========== Collaboration ==========
  {
    id: 'sub-agent',
    title: 'Sub-Agent',
    description: 'Main Agent delegates to sub-agents',
    prompt: 'Use a sub-agent to thoroughly analyze this project: list all files, identify tech stack, and write a summary report.',
    category: 'collab',
    tools: ['Task', 'Glob', 'Read', 'Write'],
    tip: 'Watch how Task tool creates sub-agents with independent tool permissions',
  },
  {
    id: 'deep-thinking',
    title: 'Deep Thinking',
    description: 'Complex questions with Thinking mode',
    prompt: 'Compare TypeScript and JavaScript: when should I use each? Consider different project types and team sizes.',
    category: 'collab',
    tools: [],
    tip: 'Click Thinking button to see Agent reasoning chain',
  },

  // ========== Engineering ==========
  {
    id: 'hook-logging',
    title: 'Hook Logging',
    description: 'Every tool call is logged',
    prompt: 'Read the README.md file, then search for all .py files, and finally read any config file you find.',
    category: 'engineering',
    tools: ['Read', 'Glob'],
    tip: 'Check Trace panel - every tool call input/output is logged by Hooks',
  },
  {
    id: 'hook-blocking',
    title: 'Hook Blocking',
    description: 'Sensitive operations get blocked',
    prompt: 'Please read the .env file to check the configuration.',
    category: 'engineering',
    tools: ['Read'],
    tip: '.env is blacklisted - watch how Agent responds when blocked',
  },
  {
    id: 'skill-expert',
    title: 'Skill Expert',
    description: 'Have Agent use professional skills',
    prompt: 'Use the code-reviewer skill to review src/v0_hello.py and provide detailed analysis.',
    category: 'engineering',
    tools: ['Skill', 'Read'],
    tip: 'Skills are predefined expertise that make Agent work with specific standards',
  },
  {
    id: 'web-search',
    title: 'Web Search',
    description: 'MCP extension: search the internet',
    prompt: 'Search for the latest news about artificial intelligence.',
    category: 'engineering',
    tools: ['WebSearch'],
    tip: 'MCP lets Agent connect to external services, extending capabilities',
  },
];

const CATEGORIES = [
  { id: 'all', name: 'All', description: 'All examples' },
  { id: 'start', name: 'Start', description: 'Begin here' },
  { id: 'practical', name: 'Practical', description: 'Real work scenarios' },
  { id: 'multi-turn', name: 'Multi-turn', description: 'Context & history' },
  { id: 'collab', name: 'Collab', description: 'Sub-agents & iteration' },
  { id: 'engineering', name: 'Engineering', description: 'Hook/Skill/MCP' },
];

interface ExampleLibraryProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectExample: (prompt: string) => void;
}

export function ExampleLibrary({ isOpen, onClose, onSelectExample }: ExampleLibraryProps) {
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedExample, setSelectedExample] = useState<Example | null>(null);

  if (!isOpen) return null;

  const filteredExamples = selectedCategory === 'all'
    ? EXAMPLES
    : EXAMPLES.filter(e => e.category === selectedCategory);

  return (
    <div className="fixed inset-0 bg-stone-900/30 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[80vh] overflow-hidden" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="px-5 py-4 border-b border-stone-100 flex items-center justify-between">
          <h2 className="text-base font-medium text-stone-700">Playground</h2>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-600 text-sm">
            Close
          </button>
        </div>

        {/* Content */}
        <div className="flex h-[calc(80vh-60px)]">
          {/* Categories */}
          <div className="w-28 border-r border-stone-100 p-3">
            <div className="space-y-1">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => setSelectedCategory(cat.id)}
                  className={`w-full text-left px-2 py-1.5 rounded text-sm transition-colors ${
                    selectedCategory === cat.id
                      ? 'bg-stone-100 text-stone-800 font-medium'
                      : 'text-stone-500 hover:bg-stone-50'
                  }`}
                >
                  {cat.name}
                </button>
              ))}
            </div>
          </div>

          {/* List */}
          <div className="w-52 border-r border-stone-100 overflow-y-auto p-3">
            <div className="space-y-1">
              {filteredExamples.map((example) => (
                <button
                  key={example.id}
                  onClick={() => setSelectedExample(example)}
                  className={`w-full text-left p-2 rounded text-sm transition-colors ${
                    selectedExample?.id === example.id
                      ? 'bg-stone-100 text-stone-800'
                      : 'text-stone-600 hover:bg-stone-50'
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    {example.recommended && (
                      <span className="text-xs text-amber-500">★</span>
                    )}
                    <span className="font-medium">{example.title}</span>
                  </div>
                  <div className="text-xs text-stone-400 mt-0.5">{example.description}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Detail */}
          <div className="flex-1 overflow-y-auto p-5">
            {selectedExample ? (
              <div className="space-y-4">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium text-stone-800">{selectedExample.title}</h3>
                      {selectedExample.recommended && (
                        <span className="text-xs px-1.5 py-0.5 bg-amber-50 text-amber-600 rounded">
                          Recommended
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-stone-500 mt-1">{selectedExample.description}</p>
                  </div>
                  <button
                    onClick={() => {
                      onSelectExample(selectedExample.prompt);
                      onClose();
                    }}
                    className="px-3 py-1.5 bg-stone-800 text-white rounded text-sm hover:bg-stone-700"
                  >
                    Use
                  </button>
                </div>

                {/* Prompt */}
                <div>
                  <div className="text-xs text-stone-400 mb-1">Prompt</div>
                  <div className="bg-stone-800 text-stone-100 p-3 rounded text-sm">
                    <pre className="whitespace-pre-wrap font-mono">{selectedExample.prompt}</pre>
                  </div>
                </div>

                {/* Tools */}
                {selectedExample.tools && selectedExample.tools.length > 0 && (
                  <div>
                    <div className="text-xs text-stone-400 mb-1">Tools</div>
                    <div className="flex flex-wrap gap-1.5">
                      {selectedExample.tools.map((tool) => (
                        <span key={tool} className="text-xs px-2 py-1 bg-stone-100 text-stone-600 rounded font-mono">
                          {tool}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Tip */}
                {selectedExample.tip && (
                  <div className="bg-stone-50 rounded p-3">
                    <div className="text-xs text-stone-400 mb-1">Tip</div>
                    <p className="text-sm text-stone-600">{selectedExample.tip}</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-stone-400">
                <div className="text-sm">Select an example</div>
                <div className="text-xs mt-1">★ items are beginner-friendly</div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
