// ============================================================
// SessionRouter — Feature Flag 客户端路由
//
// 根据 localStorage + URL param 决定渲染哪个 Session 实现。
// 必须为客户端组件（useExp04Enabled 需要 window）。
// ============================================================

"use client";

import { useExp04Enabled } from "@/lib/exp04/feature-flag";
import SessionPage from "@/components/session/SessionPage";
import Exp04Session from "@/components/session/Exp04Session";

export function SessionRouter() {
  const exp04Enabled = useExp04Enabled();

  if (exp04Enabled) {
    return <Exp04Session />;
  }

  return <SessionPage />;
}
