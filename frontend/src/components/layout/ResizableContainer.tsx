// ============================================================
// ResizableContainer — 可调整大小 + 可折叠的容器 (任务 #76)
//
// 设计目标：
//   - 拖动分隔条（resizer）改尺寸，限制 min/max
//   - 双击分隔条 = 折叠/展开
//   - 折叠状态由父组件控制（lifted state），保证 Workbench 可同步多个 panel
//   - 内部使用 CSS 变量传递实际尺寸，父级 grid 即可对齐
//
// 方向：
//   - horizontal：左右拖动 (leftPanel / rightPanel 用)
//   - vertical：上下拖动 (topBar / bottomBar 用)
//
// 约束：
//   - 拖动时 mousemove 节流 60fps（requestAnimationFrame）
//   - 拖动时设置 cursor: ew-resize / ns-resize + 禁止文字选择
//   - onResizeEnd 时回调父组件持久化
// ============================================================

"use client";

import {
  useRef,
  useCallback,
  useEffect,
  type ReactNode,
  type CSSProperties,
} from "react";
import type { PanelPref } from "@/hooks/useLayoutPrefs";
import PanelHeader, {
  type CollapseDirection,
} from "./PanelHeader";

export type ResizeDirection = "horizontal" | "vertical";

export interface ResizableContainerProps {
  /** 是否渲染该 panel（visible=false 不渲染） */
  visible: boolean;
  /** 当前尺寸（px），由父级控制 */
  size: number;
  /** 折叠状态 */
  collapsed: boolean;
  /** 调整方向 */
  direction: ResizeDirection;
  /** min/max 约束 */
  minSize: number;
  maxSize: number;
  /** 折叠时保留的最小尺寸（留一条窄边便于点击展开） */
  collapsedSize: number;
  /** 拖动时持续回调（实时更新父级 UI） */
  onResize: (newSize: number) => void;
  /** 拖动结束时回调（持久化时机） */
  onResizeEnd: (finalSize: number) => void;
  /** 折叠/展开回调（按钮 / 双击触发） */
  onToggleCollapse: () => void;
  /** 标题 */
  title: string;
  /** 标题 icon */
  icon?: ReactNode;
  /** 头部右侧操作 */
  headerRight?: ReactNode;
  /** 是否隐藏 header（驾驶舱主区一般不需要） */
  hideHeader?: boolean;
  /** 子内容 */
  children: ReactNode;
  /** 内部内容容器类名 */
  bodyClassName?: string;
  /** 是否禁用 resize（驾驶舱主区禁用） */
  resizable?: boolean;
  /** 自定义 className */
  className?: string;
  /** 自定义 style（用于外层 grid 定位等） */
  style?: CSSProperties;
}

export default function ResizableContainer({
  visible,
  size,
  collapsed,
  direction,
  minSize,
  maxSize,
  collapsedSize,
  onResize,
  onResizeEnd,
  onToggleCollapse,
  title,
  icon,
  headerRight,
  hideHeader = false,
  children,
  bodyClassName = "",
  resizable = true,
  className = "",
  style,
}: ResizableContainerProps) {
  const dragStateRef = useRef<{
    startPos: number;
    startSize: number;
    rafId: number | null;
  } | null>(null);

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (!resizable || collapsed) return;
      e.preventDefault();
      e.stopPropagation();
      const startPos = direction === "horizontal" ? e.clientX : e.clientY;
      dragStateRef.current = {
        startPos,
        startSize: size,
        rafId: null,
      };
      document.body.style.cursor =
        direction === "horizontal" ? "ew-resize" : "ns-resize";
      document.body.style.userSelect = "none";
    },
    [resizable, collapsed, direction, size],
  );

  // 拖动过程中：节流到 rAF
  useEffect(() => {
    if (!resizable) return;
    const onMove = (e: PointerEvent) => {
      const state = dragStateRef.current;
      if (!state) return;
      if (state.rafId !== null) return;
      state.rafId = requestAnimationFrame(() => {
        state.rafId = null;
        const currentPos = direction === "horizontal" ? e.clientX : e.clientY;
        const delta = currentPos - state.startPos;
        const next = Math.max(minSize, Math.min(maxSize, state.startSize + delta));
        onResize(next);
      });
    };
    const onUp = () => {
      const state = dragStateRef.current;
      if (!state) return;
      if (state.rafId !== null) {
        cancelAnimationFrame(state.rafId);
        state.rafId = null;
      }
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      // 从 CSS 变量读取最终值（onResize 同步写入）
      const root = document.documentElement;
      const cssVar =
        direction === "horizontal"
          ? "--resizable-current-w"
          : "--resizable-current-h";
      const fromCss = parseFloat(root.style.getPropertyValue(cssVar) || "");
      const final =
        Number.isFinite(fromCss) && fromCss > 0 ? fromCss : state.startSize;
      onResizeEnd(final);
      dragStateRef.current = null;
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [direction, maxSize, minSize, onResize, onResizeEnd, resizable]);

  // 每次 onResize 同步当前值到 CSS 变量，便于 pointerup 读取
  useEffect(() => {
    if (typeof document === "undefined") return;
    const cssVar =
      direction === "horizontal" ? "--resizable-current-w" : "--resizable-current-h";
    document.documentElement.style.setProperty(cssVar, `${size}px`);
  }, [size, direction]);

  if (!visible) return null;

  // 折叠后的渲染尺寸
  const renderSize = collapsed ? collapsedSize : size;

  // header 中折叠按钮的朝向：水平方向 panel 一般折叠为窄边
  const collapseDir: CollapseDirection =
    direction === "horizontal" ? "left" : "up";

  const isHorizontal = direction === "horizontal";
  const sizeStyle: CSSProperties = isHorizontal
    ? { width: renderSize, minWidth: renderSize, maxWidth: renderSize }
    : { height: renderSize, minHeight: renderSize, maxHeight: renderSize };

  return (
    <div
      className={`relative flex bg-page ${isHorizontal ? "flex-col" : "flex-row"} ${className}`}
      style={{ ...sizeStyle, ...style }}
    >
      <div className="flex-1 min-h-0 min-w-0 flex flex-col overflow-hidden">
        {!hideHeader && (
          <PanelHeader
            title={title}
            icon={icon}
            collapsed={collapsed}
            direction={collapseDir}
            onToggleCollapse={onToggleCollapse}
            rightSlot={headerRight}
            compact
          />
        )}
        <div className={`flex-1 min-h-0 min-w-0 overflow-auto ${bodyClassName}`}>
          {children}
        </div>
      </div>

      {/* 分隔条 / 折叠触发条 */}
      {resizable && (
        <div
          onPointerDown={handlePointerDown}
          onDoubleClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onToggleCollapse();
          }}
          className={`
            absolute z-10
            ${
              isHorizontal
                ? "top-0 bottom-0 -right-[3px] w-[6px] cursor-ew-resize"
                : "-bottom-[3px] left-0 right-0 h-[6px] cursor-ns-resize"
            }
            hover:bg-accent/30 active:bg-accent/50
            transition-colors
          `}
          aria-label={`拖动调整 ${title} 尺寸；双击折叠`}
          role="separator"
          aria-orientation={isHorizontal ? "vertical" : "horizontal"}
        />
      )}
    </div>
  );
}
