// ============================================================
// DevRoleSwitcher — 开发期角色切换器 (stub)
//
// 任务 #76 应有正式实现；本文件为占位，让 build 通过。
// 真实实现见后续 task。
// ============================================================

"use client";

export default function DevRoleSwitcher() {
  if (process.env.NODE_ENV !== "production") {
    return (
      <div
        data-testid="dev-role-switcher"
        className="fixed bottom-2 right-2 z-50 px-2 py-1 rounded bg-amber-500/10 border border-amber-500/30 text-amber-500 text-[10px] opacity-30 hover:opacity-100"
      >
        dev
      </div>
    );
  }
  return null;
}
