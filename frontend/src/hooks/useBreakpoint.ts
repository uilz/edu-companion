"use client";

import { useState, useEffect, useCallback } from "react";

type Breakpoint = "mobile" | "tablet" | "desktop";

/**
 * useBreakpoint — 返回当前屏幕断点和常用尺寸信息
 *
 * mobile:  < 640px  (sm)
 * tablet:  640-1023px (md)
 * desktop: ≥ 1024px (lg)
 */
export function useBreakpoint(): {
  breakpoint: Breakpoint;
  isMobile: boolean;
  isTablet: boolean;
  isDesktop: boolean;
  width: number;
  height: number;
  /** 首次挂载（同步过 window.innerWidth） */
  isMounted: boolean;
} {
  const [info, setInfo] = useState({
    width: 0,
    height: 0,
    breakpoint: "desktop" as Breakpoint,
    isMounted: false,
  });

  useEffect(() => {
    if (typeof window === "undefined") return;

    const update = () => {
      const w = window.innerWidth;
      let bp: Breakpoint = "desktop";
      if (w < 640) bp = "mobile";
      else if (w < 1024) bp = "tablet";

      setInfo({
        width: w,
        height: window.innerHeight,
        breakpoint: bp,
        isMounted: true,
      });
    };

    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  return {
    breakpoint: info.breakpoint,
    isMobile: info.breakpoint === "mobile",
    isTablet: info.breakpoint === "tablet",
    isDesktop: info.breakpoint === "desktop",
    width: info.width,
    height: info.height,
    isMounted: info.isMounted,
  };
}

export { useMediaQuery } from "./useMediaQuery";