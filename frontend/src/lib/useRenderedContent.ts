'use client';

import { useState, useEffect, useMemo } from 'react';
import { renderMarkdown, onKatexReady } from '@/lib/math';

/**
 * Hook: renders markdown+math content.
 * Automatically re-renders when KaTeX finishes lazy-loading.
 */
export function useRenderedContent(text: string): string {
  // 记录 KaTeX 是否已完成懒加载，驱动后续重新渲染
  const [katexReady, setKatexReady] = useState(false);

  // 注册 KaTeX 加载完成回调：一旦 KaTeX 就绪，触发重渲染
  useEffect(() => {
    const unsub = onKatexReady(() => setKatexReady(true));
    return unsub;
  }, []);

  // 仅当 text 或 katexReady 变化时重新渲染内容，避免不必要的计算
  return useMemo(() => renderMarkdown(text), [text, katexReady]);
}
