/**
 * MarkdownRenderer - 简易 Markdown 渲染组件
 *
 * 支持基本的 Markdown 语法：
 * - 代码块 (```language)
 * - 行内代码 (`code`)
 * - 粗体 (**bold**)
 * - 斜体 (*italic*)
 * - 链接 ([text](url))
 * - 标题 (# ## ###)
 * - 列表 (- item)
 */

import { useMemo } from 'react';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

// 简单的语法高亮关键字
const keywords: Record<string, string[]> = {
  javascript: ['const', 'let', 'var', 'function', 'return', 'if', 'else', 'for', 'while', 'class', 'import', 'export', 'from', 'async', 'await', 'try', 'catch', 'throw', 'new', 'this', 'true', 'false', 'null', 'undefined'],
  typescript: ['const', 'let', 'var', 'function', 'return', 'if', 'else', 'for', 'while', 'class', 'import', 'export', 'from', 'async', 'await', 'try', 'catch', 'throw', 'new', 'this', 'true', 'false', 'null', 'undefined', 'interface', 'type', 'enum', 'implements', 'extends'],
  python: ['def', 'class', 'if', 'elif', 'else', 'for', 'while', 'return', 'import', 'from', 'as', 'try', 'except', 'finally', 'with', 'async', 'await', 'True', 'False', 'None', 'and', 'or', 'not', 'in', 'is', 'lambda', 'yield', 'raise', 'pass', 'break', 'continue'],
  bash: ['if', 'then', 'else', 'fi', 'for', 'do', 'done', 'while', 'case', 'esac', 'function', 'return', 'exit', 'echo', 'cd', 'ls', 'mkdir', 'rm', 'cp', 'mv', 'cat', 'grep', 'sed', 'awk', 'export', 'source'],
  json: [],
  html: [],
  css: [],
};

// 简单的语法高亮
// 使用内联样式避免 Tailwind JIT 未生成动态类名的问题
function highlightCode(code: string, language: string): string {
  const lang = language.toLowerCase();
  const langKeywords = keywords[lang] || keywords['javascript'] || [];

  let highlighted = code
    // 转义 HTML
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // 高亮字符串 - 使用占位符标记
  highlighted = highlighted.replace(
    /(["'`])(?:(?!\1)[^\\]|\\.)*\1/g,
    '{{HL_STRING}}$&{{/HL}}'
  );

  // 高亮注释 - 使用占位符标记
  highlighted = highlighted.replace(
    /(\/\/.*$|#.*$)/gm,
    '{{HL_COMMENT}}$&{{/HL}}'
  );

  // 高亮关键字 - 使用占位符标记
  if (langKeywords.length > 0) {
    const keywordRegex = new RegExp(`\\b(${langKeywords.join('|')})\\b`, 'g');
    highlighted = highlighted.replace(
      keywordRegex,
      '{{HL_KEYWORD}}$1{{/HL}}'
    );
  }

  // 高亮数字 - 使用占位符标记
  highlighted = highlighted.replace(
    /\b(\d+\.?\d*)\b/g,
    '{{HL_NUMBER}}$1{{/HL}}'
  );

  // 使用内联样式而非 Tailwind 类名 - 浅色背景方案
  highlighted = highlighted
    .replace(/\{\{HL_STRING\}\}/g, '<span style="color:#16a34a">')      // green-600 (深绿)
    .replace(/\{\{HL_COMMENT\}\}/g, '<span style="color:#78716c;font-style:italic">') // stone-500 (灰色注释)
    .replace(/\{\{HL_KEYWORD\}\}/g, '<span style="color:#9333ea;font-weight:600">')   // purple-600 (深紫)
    .replace(/\{\{HL_NUMBER\}\}/g, '<span style="color:#2563eb">')      // blue-600 (深蓝)
    .replace(/\{\{\/HL\}\}/g, '</span>');

  return highlighted;
}

// 解析 Markdown 内容
function parseMarkdown(content: string): JSX.Element[] {
  const lines = content.split('\n');
  const elements: JSX.Element[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    // 代码块
    if (line.startsWith('```')) {
      const language = line.slice(3).trim() || 'text';
      const codeLines: string[] = [];
      i++;

      while (i < lines.length && !lines[i].startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }

      const code = codeLines.join('\n');
      const highlighted = highlightCode(code, language);

      elements.push(
        <div key={key++} className="my-2 rounded-lg overflow-hidden">
          <div className="flex items-center justify-between bg-stone-800 text-stone-300 text-xs px-3 py-1.5">
            <span>{language}</span>
            <button
              className="hover:text-white transition-colors"
              onClick={() => navigator.clipboard.writeText(code)}
              title="Copy code"
            >
              Copy
            </button>
          </div>
          <pre className="bg-stone-100 p-3 overflow-x-auto text-sm font-mono border border-t-0 border-stone-200">
            <code style={{ color: '#1c1917' }} dangerouslySetInnerHTML={{ __html: highlighted }} />
          </pre>
        </div>
      );
      i++;
      continue;
    }

    // 标题
    if (line.startsWith('### ')) {
      elements.push(
        <h3 key={key++} className="text-lg font-semibold mt-3 mb-1">
          {line.slice(4)}
        </h3>
      );
      i++;
      continue;
    }
    if (line.startsWith('## ')) {
      elements.push(
        <h2 key={key++} className="text-xl font-semibold mt-4 mb-2">
          {line.slice(3)}
        </h2>
      );
      i++;
      continue;
    }
    if (line.startsWith('# ')) {
      elements.push(
        <h1 key={key++} className="text-2xl font-bold mt-4 mb-2">
          {line.slice(2)}
        </h1>
      );
      i++;
      continue;
    }

    // 列表项
    if (line.match(/^[-*]\s/)) {
      const listItems: string[] = [];
      while (i < lines.length && lines[i].match(/^[-*]\s/)) {
        listItems.push(lines[i].slice(2));
        i++;
      }
      elements.push(
        <ul key={key++} className="list-disc list-inside my-2 space-y-1">
          {listItems.map((item, idx) => (
            <li key={idx}>{formatInlineMarkdown(item)}</li>
          ))}
        </ul>
      );
      continue;
    }

    // 有序列表
    if (line.match(/^\d+\.\s/)) {
      const listItems: string[] = [];
      while (i < lines.length && lines[i].match(/^\d+\.\s/)) {
        listItems.push(lines[i].replace(/^\d+\.\s/, ''));
        i++;
      }
      elements.push(
        <ol key={key++} className="list-decimal list-inside my-2 space-y-1">
          {listItems.map((item, idx) => (
            <li key={idx}>{formatInlineMarkdown(item)}</li>
          ))}
        </ol>
      );
      continue;
    }

    // 空行
    if (line.trim() === '') {
      i++;
      continue;
    }

    // 普通段落
    elements.push(
      <p key={key++} className="my-1">
        {formatInlineMarkdown(line)}
      </p>
    );
    i++;
  }

  return elements;
}

// 格式化行内 Markdown
function formatInlineMarkdown(text: string): JSX.Element {
  // 将文本分割成片段，按顺序处理：链接 -> 代码 -> 粗体/斜体
  const elements: (string | JSX.Element)[] = [];
  let keyIndex = 0;

  // 正则匹配：链接、行内代码、粗体、斜体
  const tokenRegex = /(\[([^\]]+)\]\(([^)]+)\))|(`([^`]+)`)|(\*\*([^*]+)\*\*)|(\*([^*]+)\*)/g;
  let lastIndex = 0;
  let match;

  while ((match = tokenRegex.exec(text)) !== null) {
    // 添加匹配前的普通文本
    if (match.index > lastIndex) {
      elements.push(text.slice(lastIndex, match.index));
    }

    if (match[1]) {
      // 链接: [text](url)
      const linkText = match[2];
      const linkUrl = match[3];
      elements.push(
        <a
          key={`link-${keyIndex++}`}
          href={linkUrl}
          className="text-blue-600 hover:underline cursor-pointer"
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
        >
          {linkText}
        </a>
      );
    } else if (match[4]) {
      // 行内代码: `code`
      elements.push(
        <code
          key={`code-${keyIndex++}`}
          className="bg-stone-200 text-red-600 px-1 py-0.5 rounded text-sm font-mono"
        >
          {match[5]}
        </code>
      );
    } else if (match[6]) {
      // 粗体: **text**
      elements.push(
        <strong key={`bold-${keyIndex++}`}>{match[7]}</strong>
      );
    } else if (match[8]) {
      // 斜体: *text*
      elements.push(
        <em key={`italic-${keyIndex++}`}>{match[9]}</em>
      );
    }

    lastIndex = match.index + match[0].length;
  }

  // 添加剩余文本
  if (lastIndex < text.length) {
    elements.push(text.slice(lastIndex));
  }

  // 如果没有匹配到任何格式，返回原文本
  if (elements.length === 0) {
    return <>{text}</>;
  }

  return <>{elements}</>;
}

export function MarkdownRenderer({ content, className = '' }: MarkdownRendererProps) {
  const elements = useMemo(() => parseMarkdown(content), [content]);

  return (
    <div className={`markdown-content ${className}`}>
      {elements}
    </div>
  );
}
