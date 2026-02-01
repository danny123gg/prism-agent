/**
 * TypeWriter - 打字效果组件
 *
 * 用于显示实时流式文本，带有打字机效果
 */

import { useEffect, useState, useRef } from 'react';

interface TypeWriterProps {
  text: string;
  speed?: number;  // 每个字符的延迟 (ms)
  isStreaming?: boolean;  // 是否正在流式输入
  children?: React.ReactNode;
}

export function TypeWriter({
  text,
  speed: _speed = 10,
  isStreaming = false,
  children,
}: TypeWriterProps) {
  const [displayedText, setDisplayedText] = useState('');
  const previousTextRef = useRef('');
  const animationRef = useRef<number | null>(null);

  useEffect(() => {
    // 如果新文本比已显示的长，逐步添加新字符
    if (text.length > displayedText.length) {
      const newChars = text.slice(displayedText.length);

      // 如果是流式输入，快速追加
      if (isStreaming) {
        // 使用 requestAnimationFrame 实现平滑动画
        let index = 0;
        const animate = () => {
          if (index < newChars.length) {
            setDisplayedText(prev => prev + newChars[index]);
            index++;
            animationRef.current = requestAnimationFrame(animate);
          }
        };
        animationRef.current = requestAnimationFrame(animate);
      } else {
        // 非流式模式，直接显示
        setDisplayedText(text);
      }
    } else if (text.length < displayedText.length) {
      // ���本变短了（可能是重置），直接更新
      setDisplayedText(text);
    }

    previousTextRef.current = text;

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [text, isStreaming]);

  // 如果不是流式输入且文本没变化，直接返回子元素
  if (!isStreaming && displayedText === text) {
    return <>{children || displayedText}</>;
  }

  return (
    <>
      {displayedText}
      {isStreaming && (
        <span className="inline-block w-2 h-4 bg-stone-400 ml-0.5 animate-pulse" />
      )}
    </>
  );
}
