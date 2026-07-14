// ============================================================
// / 根路径页面 — Today（PR-001）
//
// Today 是苹果果 V1 的首页，回答三个问题：
//   1. 今天最值得学习什么？
//   2. 为什么？
//   3. 完成以后我成长了什么？
//
// 设计原则（Product Bible §007）：
//   - 首页展示用户的状态，不展示功能模块
//   - AI 主动推荐，用户确认后进入 Learning Session
//   - 唯一 CTA：「开始今天」
//
// 历史：
//   - 原为 Cockpit 驾驶舱（任务 #76/#78）
//   - 后为 SecretaryDashboard（任务 #120）
//   - PR-001 重构为 Today 页面
// ============================================================

import TodayPage from "@/components/today/TodayPage";

export default function RootPage() {
  return <TodayPage />;
}
