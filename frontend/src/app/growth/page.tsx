// ============================================================
// /growth 路由 — Growth 页面（PR-003）
//
// Growth Domain 消费端：通过 /api/growth/* 查询接口展示成长记录。
// Today 和 Profile 也可消费同一套 GrowthRecord 数据。
//
// Domain Model v1.2:
//   - GrowthRecord 由 GrowthEngine 监听 SessionCompleted 自动生成
//   - 页面只负责展示，不产生数据
// ============================================================

import GrowthPage from "@/components/growth/GrowthPage";

export default function GrowthRoute() {
  return <GrowthPage />;
}
