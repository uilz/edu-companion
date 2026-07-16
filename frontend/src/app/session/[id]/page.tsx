// ============================================================
// /session/[id] 路由 — Learning Session
//
// Feature Flag 路由：
//   - exp04_enabled=true  → Exp04Session（新状态机驱动）
//   - exp04_enabled=false → SessionPage（旧实现，fallback）
//
// EPIC-01: Session Runtime Foundation
// ============================================================

import { SessionRouter } from "./SessionRouter";

export default function SessionRoute() {
  return <SessionRouter />;
}
