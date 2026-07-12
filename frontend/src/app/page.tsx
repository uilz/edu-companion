// ============================================================
// / 根路径页面 (任务 #120)
//
// 设计决策：秘书仪表盘作为统一首页
//   - 替代原 Cockpit 驾驶舱
//   - AppShell / Workbench 不再将 / 判定为 cockpit 路由
//   - 直接渲染 SecretaryDashboard
//
// 历史：
//   - 此处原为 HomePage → 占位返回 null（任务 #31/#34/#78）
//   - 由 Cockpit 接管（任务 #76/#78）
//   - 现由 SecretaryDashboard 替代（任务 #120）
// ============================================================

import SecretaryDashboard from "@/components/dashboard/SecretaryDashboard";

export default function HomePage() {
  return <SecretaryDashboard />;
}
