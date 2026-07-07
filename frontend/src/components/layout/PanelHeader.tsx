// ============================================================
// PanelHeader — Panel 顶部标题栏 (任务 #76)
//
// 用途：5 栏驾驶舱中每个 panel 的头部，提供
//   - 标题
//   - 折叠按钮 (◀/▶ / ▲/▼)
//   - 可选右侧操作槽
//
// 风格遵循 design-language.md professional 风格：
//   圆角 6px / 字号 13-14px / 间距 8-12 / 颜色 slate
// ============================================================

"use client";

import { type ReactNode } from "react";
import {
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  X,
} from "lucide-react";

export type CollapseDirection = "left" | "right" | "up" | "down";

export interface PanelHeaderProps {
  title: string;
  icon?: ReactNode;
  /** 是否已折叠（决定按钮朝向） */
  collapsed?: boolean;
  /** 双击分隔条时折叠的方向（与按钮图标保持一致） */
  direction?: CollapseDirection;
  /** 折叠 / 展开回调 */
  onToggleCollapse?: () => void;
  /** 关闭整个 panel 回调（可选） */
  onClose?: () => void;
  /** 右侧附加操作 */
  rightSlot?: ReactNode;
  /** 紧凑模式：去掉 padding，让 panel 自身更紧凑 */
  compact?: boolean;
}

export default function PanelHeader({
  title,
  icon,
  collapsed = false,
  direction = "right",
  onToggleCollapse,
  onClose,
  rightSlot,
  compact = false,
}: PanelHeaderProps) {
  const py = compact ? "py-1.5" : "py-2";
  const px = compact ? "px-2.5" : "px-3";
  const textSize = compact ? "text-[12px]" : "text-[13px]";

  const collapseIcon = (() => {
    if (collapsed) {
      // 展开方向 = 反方向
      if (direction === "left") return <ChevronRight size={14} />;
      if (direction === "right") return <ChevronLeft size={14} />;
      if (direction === "up") return <ChevronDown size={14} />;
      return <ChevronUp size={14} />;
    }
    if (direction === "left") return <ChevronLeft size={14} />;
    if (direction === "right") return <ChevronRight size={14} />;
    if (direction === "up") return <ChevronUp size={14} />;
    return <ChevronDown size={14} />;
  })();

  return (
    <div
      className={`flex items-center gap-2 ${px} ${py} border-b border-divider bg-page-secondary/50 select-none`}
    >
      {icon && <span className="text-ink-secondary shrink-0">{icon}</span>}
      <span
        className={`flex-1 truncate font-medium text-ink-primary ${textSize} tracking-tight`}
        title={title}
      >
        {title}
      </span>
      {rightSlot}
      {onToggleCollapse && (
        <button
          onClick={onToggleCollapse}
          aria-label={collapsed ? `展开 ${title}` : `折叠 ${title}`}
          className="shrink-0 p-1 rounded text-ink-muted hover:text-ink-primary hover:bg-surface-hover transition-colors"
        >
          {collapseIcon}
        </button>
      )}
      {onClose && (
        <button
          onClick={onClose}
          aria-label={`关闭 ${title}`}
          className="shrink-0 p-1 rounded text-ink-muted hover:text-danger hover:bg-danger/10 transition-colors"
        >
          <X size={14} />
        </button>
      )}
    </div>
  );
}
