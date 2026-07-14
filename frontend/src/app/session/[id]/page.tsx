// ============================================================
// /session/[id] 路由 — Learning Session（PR-002b）
//
// Session 是苹果果 V1 核心聚合根。
// Today 通过 POST /api/session 创建 Session → redirect 到此页面。
//
// Domain Model v1.2:
//   - Session 有自己的生命周期（intro → learn → practice → reflect）
//   - Conversation 是 Session 的内部交互组件
//   - Stage 来自 Session 状态机，不靠关键词猜测
//   - 结束后 Growth Engine 监听 SessionCompleted 生成 GrowthSummary
// ============================================================

import SessionPage from "@/components/session/SessionPage";

export default function SessionRoute() {
  return <SessionPage />;
}
