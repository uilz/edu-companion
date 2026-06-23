"use client";

import { useState, useEffect } from "react";

/** 响应式断点检测 hook */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia(query);
    setMatches(mq.matches);
    const listener = (e: MediaQueryListEvent) => setMatches(e.matches);
    mq.addEventListener("change", listener);
    return () => mq.removeEventListener("change", listener);
  }, [query]);
  return matches;
}

/**
 * useIsMobile — 快捷检测是否为移动端 (< 640px)
 */
export function useIsMobile(): boolean {
  return useMediaQuery("(max-width: 639px)");
}

/**
 * useIsTablet — 快捷检测是否为平板端 (640-1023px)
 */
export function useIsTablet(): boolean {
  return useMediaQuery("(min-width: 640px) and (max-width: 1023px)");
}

/**
 * useIsDesktop — 快捷检测是否为桌面端 (≥ 1024px)
 */
export function useIsDesktop(): boolean {
  return useMediaQuery("(min-width: 1024px)");
}
