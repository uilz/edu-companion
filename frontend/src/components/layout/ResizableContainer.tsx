// ============================================================
// ResizableContainer — 可调整容器 (stub)
//
// 任务 #76 应有正式实现（拖动分隔条 + 折叠按钮）；
// 本文件为占位，让 build 通过。
// ============================================================

"use client";

import { type ReactNode } from "react";

interface ResizableContainerProps {
  visible?: boolean;
  size?: number;
  collapsed?: boolean;
  direction?: "horizontal" | "vertical";
  minSize?: number;
  maxSize?: number;
  collapsedSize?: number;
  onResize?: (size: number) => void;
  onResizeEnd?: (size: number) => void;
  onToggleCollapse?: () => void;
  title?: string;
  hideHeader?: boolean;
  resizable?: boolean;
  className?: string;
  children?: ReactNode;
  headerRight?: ReactNode;
}

export default function ResizableContainer({
  visible = true,
  collapsed,
  title,
  hideHeader,
  className = "",
  children,
  headerRight,
  onToggleCollapse,
}: ResizableContainerProps) {
  if (!visible) return null;
  return (
    <div className={`flex flex-col h-full w-full ${className}`}>
      {!hideHeader && title && (
        <div className="flex items-center justify-between px-3 py-1.5 border-b border-[var(--color-border)]/50 text-xs">
          <span className="font-medium text-[var(--color-text)]">{title}</span>
          <div className="flex items-center gap-1">
            {headerRight}
            {onToggleCollapse && (
              <button
                onClick={onToggleCollapse}
                className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] p-0.5"
                aria-label={collapsed ? "展开" : "折叠"}
              >
                {collapsed ? "▶" : "◀"}
              </button>
            )}
          </div>
        </div>
      )}
      <div className="flex-1 min-h-0 overflow-hidden">{children}</div>
    </div>
  );
}
