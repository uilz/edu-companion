// ============================================================
// BottomBar — 底栏 (stub)
//
// 任务 #76 应有正式实现（快捷操作 / 状态栏）；
// 本文件为占位，让 build 通过。
// ============================================================

"use client";

export default function BottomBar() {
  return (
    <div
      data-testid="bottom-bar"
      className="h-full w-full flex items-center justify-between px-3 text-xs text-[var(--color-text-muted)] border-t border-[var(--color-border)]/50"
    >
      <span>edu-companion</span>
      <span className="text-[10px] opacity-60">v1.0</span>
    </div>
  );
}
