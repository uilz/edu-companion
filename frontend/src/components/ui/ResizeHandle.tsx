// ============================================================
// ResizeHandle — 通用可拖动分界栏
//
// 设计目标：
//   - 轻量、可复用，不绑定任何布局容器
//   - 支持 horizontal（左右分栏竖线）和 vertical（上下分栏横线）
//   - 视觉跟随 conversation-demo-v7：hover 时 accent 色线 + 高度/长度过渡
//   - 拖拽中自动管理 body cursor 和 userSelect
//   - 双击触发折叠/展开
//   - 使用 Pointer Events + rAF 节流
//
// 用法：
//   <ResizeHandle
//     orientation="horizontal"
//     onResize={(dx) => setWidth(w + dx)}
//     onDoubleClick={() => toggleCollapse()}
//     collapsed={collapsed}
//   />
// ============================================================

"use client";

import React, { useRef, useCallback, useEffect, useState } from "react";

// ── Props ──
export interface ResizeHandleProps {
  /**
   * horizontal = 左右分栏，显示竖线（cursor: ew-resize）
   * vertical   = 上下分栏，显示横线（cursor: ns-resize）
   */
  orientation: "horizontal" | "vertical";

  /**
   * 拖拽回调。
   * delta 为相对 pointerdown 时的总位移（total delta），非增量。
   * delta > 0：向右（horizontal）或向下（vertical）拖动。
   * 父组件应配合 onResizeStart 保存初始尺寸，用 初始尺寸 ± totalDelta 计算新尺寸。
   */
  onResize: (totalDelta: number) => void;

  /** 拖拽开始回调 — 用于让父组件保存初始尺寸快照 */
  onResizeStart?: () => void;

  /** 拖拽结束回调（可用于持久化最终尺寸） */
  onResizeEnd?: () => void;

  /** 双击回调（通常用于折叠/展开） */
  onDoubleClick?: () => void;

  /** 是否已折叠（影响视觉：折叠时不显示 hover 反馈线） */
  collapsed?: boolean;

  /** 自定义 className */
  className?: string;

  /** 自定义 style */
  style?: React.CSSProperties;
}

// ── 常量 ──
const HIT_SIZE = 6;          // 点击区域宽/高
const VISUAL_SIZE = 2;        // 视觉线的宽/高
const BAR_LENGTH_DEFAULT = 32;
const BAR_LENGTH_HOVER = 48;

// ── 组件 ──
export default function ResizeHandle({
  orientation,
  onResize,
  onResizeStart,
  onResizeEnd,
  onDoubleClick,
  collapsed = false,
  className = "",
  style,
}: ResizeHandleProps) {
  // 用 ref 保存最新回调，避免 useEffect 重建
  const onResizeRef = useRef(onResize);
  const onResizeStartRef = useRef(onResizeStart);
  const onResizeEndRef = useRef(onResizeEnd);
  const onDblClickRef = useRef(onDoubleClick);
  const dragRef = useRef<{
    initialStartPos: number; // 鼠标按下时的初始位置，永不更新
    rafId: number | null;
  } | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  onResizeRef.current = onResize;
  onResizeStartRef.current = onResizeStart;
  onResizeEndRef.current = onResizeEnd;
  onDblClickRef.current = onDoubleClick;

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (e.button !== 0) return;
      e.preventDefault();
      e.stopPropagation();

      // 通知父组件快照当前尺寸
      onResizeStartRef.current?.();

      const initialStartPos = orientation === "horizontal" ? e.clientX : e.clientY;
      dragRef.current = { initialStartPos, rafId: null };
      setIsDragging(true);

      document.body.style.cursor =
        orientation === "horizontal" ? "ew-resize" : "ns-resize";
      document.body.style.userSelect = "none";
    },
    [orientation],
  );

  // 全局 pointermove / pointerup
  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const state = dragRef.current;
      if (!state) return;
      if (state.rafId !== null) return;

      state.rafId = requestAnimationFrame(() => {
        state.rafId = null;
        const currentPos =
          orientation === "horizontal" ? e.clientX : e.clientY;
        // 总位移：始终相对 pointerdown 时的初始位置
        const totalDelta = currentPos - state.initialStartPos;
        onResizeRef.current(totalDelta);
      });
    };

    const onUp = () => {
      const state = dragRef.current;
      if (!state) return;
      if (state.rafId !== null) {
        cancelAnimationFrame(state.rafId);
      }
      setIsDragging(false);
      dragRef.current = null;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      onResizeEndRef.current?.();
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      // 组件卸载时清理
      if (dragRef.current?.rafId !== null) {
        cancelAnimationFrame(dragRef.current?.rafId!);
      }
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [orientation]);

  // ── 方向相关样式 ──
  const isH = orientation === "horizontal";

  // 点击区域
  const hitStyle: React.CSSProperties = isH
    ? { width: HIT_SIZE, cursor: "ew-resize" }
    : { height: HIT_SIZE, cursor: "ns-resize" };

  // 视觉线的样式：居中绝对定位
  const barStyle: React.CSSProperties = isH
    ? {
        width: VISUAL_SIZE,
        height: BAR_LENGTH_DEFAULT,
        top: "50%",
        left: "50%",
        transform: "translate(-50%, -50%)",
        borderRadius: 2,
      }
    : {
        height: VISUAL_SIZE,
        width: BAR_LENGTH_DEFAULT,
        left: "50%",
        top: "50%",
        transform: "translate(-50%, -50%)",
        borderRadius: 2,
      };

  // hover 下视觉线变长
  const barHoverStyle: React.CSSProperties = isH
    ? { height: BAR_LENGTH_HOVER }
    : { width: BAR_LENGTH_HOVER };

  // 拖拽时的背景晕
  const draggingBg = isH
    ? "linear-gradient(90deg, transparent, var(--color-accent-glow, rgba(37,99,235,0.08)), transparent)"
    : "linear-gradient(0deg, transparent, var(--color-accent-glow, rgba(37,99,235,0.08)), transparent)";

  return (
    <div
      className={`relative flex-shrink-0 group select-none ${className}`}
      style={{ ...hitStyle, ...style }}
      onPointerDown={handlePointerDown}
      onDoubleClick={() => onDblClickRef.current?.()}
      role="separator"
      aria-orientation={orientation}
      aria-label="拖动调整尺寸；双击折叠"
      data-collapsed={collapsed || undefined}
    >
      {/* ── 默认分割线（微弱线条） ── */}
      <div
        className="absolute transition-all duration-150 ease-out"
        style={{
          ...barStyle,
          background: "var(--color-divider)",
          opacity: collapsed ? 0 : 0.35,
        }}
      />

      {/* ── Accent 线：hover 或拖拽时显示 ── */}
      <div
        className="absolute transition-all duration-150 ease-out handle-accent-line"
        style={{
          ...barStyle,
          ...barHoverStyle,
          background: "var(--color-accent)",
          opacity: collapsed ? 0 : isDragging ? 1 : 0,
        }}
      />

      {/* ── 拖拽背景晕 ── */}
      <div
        className="absolute inset-0 transition-opacity duration-150 pointer-events-none rounded-sm handle-accent-bg"
        style={{
          opacity: isDragging ? 1 : 0,
          background: draggingBg,
        }}
      />

      {/* hover 态通过全局 CSS 切换 opacity */}
      <style>{`
        .group:hover .handle-accent-line { opacity: 1 !important; }
        .group:hover .handle-accent-bg  { opacity: 1 !important; }
        .group[data-collapsed] .handle-accent-line { opacity: 0 !important; }
        .group[data-collapsed] .handle-accent-bg  { opacity: 0 !important; }
      `}</style>
    </div>
  );
}
