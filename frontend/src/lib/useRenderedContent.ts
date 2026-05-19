'use client';

import { useState, useEffect, useMemo } from 'react';
import { renderContent, onKatexReady } from '@/lib/math';

/**
 * Hook: renders markdown+math content.
 * Automatically re-renders when KaTeX finishes lazy-loading.
 */
export function useRenderedContent(text: string): string {
  const [katexReady, setKatexReady] = useState(false);

  useEffect(() => {
    const unsub = onKatexReady(() => setKatexReady(true));
    return unsub;
  }, []);

  return useMemo(() => renderContent(text), [text, katexReady]);
}
