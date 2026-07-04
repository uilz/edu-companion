"use client";

import React, { useRef, useEffect } from "react";
import { X } from "lucide-react";

/**
 * MobileBottomSheet — 移动端底部弹出导航（支持 swipe-to-close + 安全区域适配）
 *
 * 交互：
 * - 向下 swipe > 80px 关闭
 * - swipe 中背景同步淡出
 * - 顶部 safe area 适配（env(safe-area-inset-top)）
 */

interface MobileBottomSheetProps {
  children: React.ReactNode;
  onClose: () => void;
  /** 标题，默认"导航" */
  title?: string;
}

const SWIPE_CLOSE_THRESHOLD = 80; // px
const SWIPE_CLOSE_VELOCITY = 0.4; // px/ms

export default function MobileBottomSheet({
  children,
  onClose,
  title = "导航",
}: MobileBottomSheetProps) {
  const sheetRef = useRef<HTMLDivElement>(null);
  const startYRef = useRef(0);
  const currentYRef = useRef(0);
  const lastTimeRef = useRef(0);
  const lastYRef = useRef(0);
  const velocityRef = useRef(0);
  const isDraggingRef = useRef(false);

  // ── swipe 手势（仅顶部 handle 区域触发）──
  function onTouchStart(e: React.TouchEvent) {
    // 排除滚动中的 sheet 内容
    if (e.touches.length !== 1) return;
    const target = e.target as HTMLElement;
    const handle = target.closest("[data-bottom-sheet-handle]");
    if (!handle) return;

    startYRef.current = e.touches[0].clientY;
    lastYRef.current = startYRef.current;
    lastTimeRef.current = Date.now();
    velocityRef.current = 0;
    isDraggingRef.current = true;
  }

  function onTouchMove(e: React.TouchEvent) {
    if (!isDraggingRef.current) return;
    const y = e.touches[0].clientY;
    const now = Date.now();
    const dt = now - lastTimeRef.current;
    if (dt > 0) {
      velocityRef.current = (y - lastYRef.current) / dt;
    }
    lastYRef.current = y;
    currentYRef.current = Math.max(0, y - startYRef.current);
    // 应用 transform
    if (sheetRef.current) {
      sheetRef.current.style.transform = `translateY(${currentYRef.current}px)`;
    }
  }

  function onTouchEnd() {
    if (!isDraggingRef.current) return;
    isDraggingRef.current = false;
    const dy = currentYRef.current;
    const v = velocityRef.current;
    // 阈值满足：位置 > 80px 或 速度 > 0.4 px/ms 且方向向下
    if (dy > SWIPE_CLOSE_THRESHOLD || (v > SWIPE_CLOSE_VELOCITY && dy > 20)) {
      onClose();
    } else {
      // 复位
      if (sheetRef.current) {
        sheetRef.current.style.transform = "";
      }
    }
  }

  // ── Esc 关闭（桌面测试时使用）──
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  // 阻止 sheet 内 touchmove 冒泡导致页面滚动
  useEffect(() => {
    const el = sheetRef.current;
    if (!el) return;
    const preventScroll = (e: TouchEvent) => {
      // 仅当处于拖拽（swipe-to-close）时阻止
      if (isDraggingRef.current) e.preventDefault();
    };
    el.addEventListener("touchmove", preventScroll, { passive: false });
    return () => el.removeEventListener("touchmove", preventScroll);
  }, []);

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col justify-end"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div
        className="absolute inset-0 bg-black/50 animate-fadeIn"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        ref={sheetRef}
        data-testid="mobile-bottom-sheet"
        className="relative bg-[var(--color-bg)] border-t border-[var(--color-border)] max-h-[85vh] flex flex-col rounded-t-xl animate-slideIn transition-transform"
        style={{
          paddingBottom: "env(safe-area-inset-bottom, 0px)",
          willChange: "transform",
        }}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
      >
        {/* 顶部 drag handle 区 */}
        <div data-bottom-sheet-handle="" className="flex flex-col items-center pt-2 pb-1 cursor-grab active:cursor-grabbing">
          <div className="h-1 w-10 rounded-full bg-[var(--color-border)]" aria-hidden="true" />
        </div>
        <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--color-border)]">
          <span className="text-sm font-semibold text-[var(--color-text)]">{title}</span>
          <button
            onClick={onClose}
            className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            style={{ minWidth: 44, minHeight: 44 }}
            aria-label="关闭"
          >
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto overscroll-contain">{children}</div>
      </div>
    </div>
  );
}
