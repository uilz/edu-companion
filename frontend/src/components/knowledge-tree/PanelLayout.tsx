"use client";

import React, { useCallback, useEffect, useRef } from "react";
import { useIsMobile } from "@/hooks/useMediaQuery";

const AUTO_COLLAPSE_THRESHOLD = 120; // 宽度小于此值自动收起
const COLLAPSE_DELAY = 300; // 拖拽停止后多久触发收起检查

export function AutoCollapsePanel({ side, width, onCollapse, children }: {
  side: "left" | "right";
  width: number;
  onCollapse: () => void;
  children: React.ReactNode;
}) {
  const isMobile = useIsMobile();
  const triggerZone = Math.max(width * 0.05, 10);

  // 移动端自动收起面板
  useEffect(() => {
    if (isMobile) {
      onCollapse();
    }
  }, [isMobile, onCollapse]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const inTriggerZone = side === "left"
      ? e.clientX - rect.left < triggerZone
      : rect.right - e.clientX < triggerZone;

    if (inTriggerZone) {
      onCollapse();
    }
  }, [side, triggerZone, onCollapse]);

  return (
    <div
      className="flex-shrink-0 relative max-sm:!w-screen"
      style={{ width: `${width}px` }}
      onMouseMove={handleMouseMove}
    >
      {children}
    </div>
  );
}

export function ResizeHandle({ side, onResize, onAutoCollapse }: {
  side: "left" | "right";
  onResize: (dx: number) => void;
  onAutoCollapse?: () => void;
}) {
  const dragging = useRef(false);
  const lastX = useRef(0);
  const onResizeRef = useRef(onResize);
  const onAutoCollapseRef = useRef(onAutoCollapse);
  const collapseTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 始终保持最新的回调引用
  onResizeRef.current = onResize;
  onAutoCollapseRef.current = onAutoCollapse;

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return;
    e.preventDefault();
    dragging.current = true;
    lastX.current = e.clientX;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    // 清除之前的收起定时器
    if (collapseTimer.current) {
      clearTimeout(collapseTimer.current);
      collapseTimer.current = null;
    }
  }, []);

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!dragging.current) return;
      const dx = e.clientX - lastX.current;
      lastX.current = e.clientX;
      onResizeRef.current(dx);
    };

    const onMouseUp = (e: MouseEvent) => {
      if (!dragging.current) return;
      dragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";

      // 拖拽到边缘 ~5% 时自动收起对应边栏
      const threshold = Math.max(window.innerWidth * 0.05, 40);
      if (side === "left" && e.clientX <= threshold) {
        onAutoCollapseRef.current?.();
      } else if (side === "right" && e.clientX >= window.innerWidth - threshold) {
        onAutoCollapseRef.current?.();
      }
    };

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
    return () => {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };
  }, [side]); // side 不变，仅此依赖

  return (
    <div
      className="flex-shrink-0 relative cursor-col-resize group"
      style={{ width: 6 }}
      onMouseDown={handleMouseDown}
    >
      <div className={`absolute inset-y-0 ${side === "left" ? "right-0.5" : "left-0.5"} w-[2px] bg-[var(--color-border)] group-hover:bg-[var(--color-accent)] transition-colors rounded-full`} />
    </div>
  );
}