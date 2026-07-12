// ============================================================
// ResizableContainer — 可调整大小 + 可折叠的容器 (任务 #76)
//
// 设计目标：
//   - 分隔栏 + 胶囊按钮始终可见
//   - 拖动分隔栏 / 胶囊按钮改尺寸
//   - 单击胶囊按钮切换 expanded ↔ collapsed
//   - 双击分隔栏切换 expanded/collapsed ↔ fullyCollapsed
//   - 拖动释放后 snap 到标准状态
//
// 方向 / 位置：
//   - panelPosition 决定分隔栏位于面板的哪一侧
//   - left/right 为水平方向；top/bottom 为垂直方向
//
// 约束：
//   - 拖动时 mousemove 节流 60fps（requestAnimationFrame）
//   - 拖动时设置 cursor + 禁止文字选择
//   - onResizeEnd 时回调父组件持久化
// ============================================================

"use client";

import {
  useRef,
  useCallback,
  useEffect,
  useMemo,
  type ReactNode,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  type MouseEvent as ReactMouseEvent,
} from "react";
import { ChevronLeft, ChevronRight, ChevronUp, ChevronDown } from "lucide-react";
import type { PanelState, PanelKey } from "@/hooks/useLayoutPrefs";
import PanelHeader from "./PanelHeader";

export type ResizeDirection = "horizontal" | "vertical";
export type PanelPosition = "left" | "right" | "top" | "bottom";

export interface ResizableContainerProps {
  /** 是否渲染该 panel */
  visible: boolean;
  /** 当前尺寸（px），由父级控制 */
  size: number;
  /** 当前状态 */
  state: PanelState;
  /** 调整方向 */
  direction: ResizeDirection;
  /** 面板位置，决定分隔栏和按钮在哪一侧 */
  panelPosition: PanelPosition;
  /** min/max 约束 */
  minSize: number;
  maxSize: number;
  /** collapsed 状态保留的最小尺寸 */
  collapsedSize: number;
  /** 对应 panel key，用于事件识别 */
  panelKey: PanelKey;
  /** 拖动时持续回调（实时更新父级 UI） */
  onResize: (newSize: number) => void;
  /** 拖动结束时回调（持久化时机） */
  onResizeEnd: (finalSize: number, finalState: PanelState) => void;
  /** 状态切换回调 */
  onStateChange: (state: PanelState) => void;
  /** 标题 */
  title: string;
  /** 标题 icon */
  icon?: ReactNode;
  /** 头部右侧操作 */
  headerRight?: ReactNode;
  /** 是否隐藏 header */
  hideHeader?: boolean;
  /** 子内容 */
  children: ReactNode;
  /** 内部内容容器类名 */
  bodyClassName?: string;
  /** 是否禁用 resize */
  resizable?: boolean;
  /** 自定义 className */
  className?: string;
  /** 自定义 style */
  style?: CSSProperties;
}

const MOVE_THRESHOLD = 2;

export default function ResizableContainer({
  visible,
  size,
  state,
  direction,
  panelPosition,
  minSize,
  maxSize,
  collapsedSize,
  panelKey,
  onResize,
  onResizeEnd,
  onStateChange,
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
  const isHorizontal = direction === "horizontal";

  // 渲染尺寸：expanded 用用户尺寸；collapsed 用窄边尺寸；
  // fullyCollapsed 保留 6px，确保分隔栏 + 胶囊按钮始终可见。
  const RESIZER_THICKNESS = 6;
  const renderSize = useMemo(() => {
    if (state === "fullyCollapsed") return RESIZER_THICKNESS;
    if (state === "collapsed") return collapsedSize;
    return Math.max(minSize, Math.min(maxSize, size));
  }, [state, collapsedSize, size, minSize, maxSize]);

  const sizeStyle: CSSProperties = isHorizontal
    ? { width: renderSize, minWidth: renderSize, maxWidth: renderSize }
    : { height: renderSize, minHeight: renderSize, maxHeight: renderSize };

  // 分隔栏位置类名
  const resizerClass = useMemo(() => {
    if (panelPosition === "left")
      return "top-0 bottom-0 -right-[3px] w-[6px] cursor-ew-resize";
    if (panelPosition === "right")
      return "top-0 bottom-0 -left-[3px] w-[6px] cursor-ew-resize";
    if (panelPosition === "top")
      return "left-0 right-0 -bottom-[3px] h-[6px] cursor-ns-resize";
    return "left-0 right-0 -top-[3px] h-[6px] cursor-ns-resize";
  }, [panelPosition]);

  // 胶囊按钮位置类名
  const btnPositionClass = useMemo(() => {
    if (panelPosition === "left") return "left-full ml-[2px]";
    if (panelPosition === "right") return "right-full mr-[2px]";
    if (panelPosition === "top") return "top-full mt-[2px]";
    return "bottom-full mb-[2px]";
  }, [panelPosition]);

  // 胶囊按钮图标：expanded 指向中心（折叠），否则指向外侧（展开）
  const btnIcon = useMemo(() => {
    const isExpanded = state === "expanded";
    const s = 14;
    if (panelPosition === "left")
      return isExpanded ? <ChevronLeft size={s} /> : <ChevronRight size={s} />;
    if (panelPosition === "right")
      return isExpanded ? <ChevronRight size={s} /> : <ChevronLeft size={s} />;
    if (panelPosition === "top")
      return isExpanded ? <ChevronUp size={s} /> : <ChevronDown size={s} />;
    return isExpanded ? <ChevronDown size={s} /> : <ChevronUp size={s} />;
  }, [state, panelPosition]);

  // 拖动状态
  const dragRef = useRef<{
    startPos: number;
    startSize: number;
    rafId: number | null;
    moved: boolean;
  } | null>(null);

  const resolveStateFromSize = useCallback(
    (value: number): PanelState => {
      if (value <= 0) return "fullyCollapsed";
      if (value <= collapsedSize + 10) return "collapsed";
      return "expanded";
    },
    [collapsedSize],
  );

  const handlePointerDown = useCallback(
    (e: ReactPointerEvent) => {
      if (!resizable) return;
      e.preventDefault();
      const startPos = isHorizontal ? e.clientX : e.clientY;
      dragRef.current = {
        startPos,
        startSize: renderSize,
        rafId: null,
        moved: false,
      };
      document.body.style.cursor = isHorizontal ? "ew-resize" : "ns-resize";
      document.body.style.userSelect = "none";
    },
    [resizable, isHorizontal, renderSize],
  );

  // 拖动方向：分隔栏始终位于面板朝向中心的一侧。
  // 无论哪个面板，鼠标远离中心方向移动（右/下）=> 面板尺寸增加。
  useEffect(() => {
    if (!resizable) return;

    const onMove = (e: PointerEvent) => {
      const ds = dragRef.current;
      if (!ds) return;
      if (ds.rafId !== null) return;
      ds.rafId = requestAnimationFrame(() => {
        ds.rafId = null;
        const pos = isHorizontal ? e.clientX : e.clientY;
        const delta = pos - ds.startPos;
        if (Math.abs(delta) > MOVE_THRESHOLD) ds.moved = true;
        const next = Math.max(0, Math.min(maxSize, ds.startSize + delta));
        onResize(next);
        // 拖动中实时切换状态，保证父级 sizeFor 使用最新 width/height
        const inferred = resolveStateFromSize(next);
        if (inferred !== state) onStateChange(inferred);
      });
    };

    const onUp = (e: PointerEvent) => {
      const ds = dragRef.current;
      if (!ds) return;
      if (ds.rafId !== null) {
        cancelAnimationFrame(ds.rafId);
        ds.rafId = null;
      }
      document.body.style.cursor = "";
      document.body.style.userSelect = "";

      const target = e.target as HTMLElement | null;
      const clickedBtn = !ds.moved && !!target?.closest('[data-resizer-btn="true"]');

      dragRef.current = null;

      // 按钮单击：expanded ↔ collapsed
      if (clickedBtn) {
        onStateChange(state === "expanded" ? "collapsed" : "expanded");
        return;
      }

      // 非按钮点击且无移动：单纯单击分隔条，留给双击处理，不切换状态
      if (!ds.moved) return;

      // 拖拽释放：snap 到标准状态
      const finalState = resolveStateFromSize(renderSize);
      onStateChange(finalState);
      onResizeEnd(renderSize, finalState);
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [resizable, isHorizontal, maxSize, onResize, onResizeEnd, onStateChange, state, renderSize, resolveStateFromSize]);

  // 双击分隔栏：expanded/collapsed → fullyCollapsed；fullyCollapsed → expanded
  const handleDoubleClick = useCallback(
    (e: ReactMouseEvent<HTMLDivElement>) => {
      if ((e.target as HTMLElement).closest('[data-resizer-btn="true"]')) return;
      onStateChange(state === "fullyCollapsed" ? "expanded" : "fullyCollapsed");
    },
    [onStateChange, state],
  );

  if (!visible) return null;

  return (
    <div
      className={`relative flex bg-page overflow-visible ${
        isHorizontal ? "flex-col h-full" : "flex-row w-full"
      } ${className}`}
      style={{ ...sizeStyle, ...style }}
      data-panel-key={panelKey}
      data-state={state}
    >
      <div
        className={`flex-1 min-h-0 min-w-0 flex flex-col overflow-hidden ${
          state === "fullyCollapsed" ? "hidden" : ""
        }`}
      >
        {!hideHeader && (
          <PanelHeader
            title={title}
            icon={icon}
            rightSlot={headerRight}
            compact
          />
        )}
        <div className={`flex-1 min-h-0 min-w-0 overflow-auto ${bodyClassName}`}>
          {children}
        </div>
      </div>

      {/* 分隔条 + 胶囊按钮 */}
      {resizable && (
        <div
          onPointerDown={handlePointerDown}
          onDoubleClick={handleDoubleClick}
          className={`
            absolute z-10 flex items-center justify-center
            ${resizerClass}
            hover:bg-accent/30 active:bg-accent/50
            transition-colors
          `}
          aria-label={`拖动调整 ${title} 尺寸；双击折叠`}
          role="separator"
          aria-orientation={isHorizontal ? "vertical" : "horizontal"}
        >
          <div
            data-resizer-btn="true"
            className={`
              absolute z-20 w-6 h-6 rounded-full
              bg-surface border border-divider shadow-sm
              flex items-center justify-center
              text-ink-muted hover:text-accent hover:border-accent
              cursor-inherit
              transition-colors
              ${btnPositionClass}
            `}
            aria-label={state === "expanded" ? `折叠 ${title}` : `展开 ${title}`}
          >
            {btnIcon}
          </div>
        </div>
      )}
    </div>
  );
}
