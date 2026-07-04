// ============================================================
// /dashboard 路径页面 (任务 #78)
//
// 设计决策：单驾驶舱架构
//   - Cockpit 接管所有设备的 / 和 /dashboard 路由
//   - AppShell 根据 pathname 判断是否为 cockpit 路由
//   - 路由若是 cockpit，直接渲染 <Cockpit />，不渲染 children
//   - 因此本组件仅作为占位：返回 null 让 AppShell 接管
//
// 历史：
//   - 此处原为 DashboardPage (OverviewTab 容器，任务 #12/#50/#67 时期)
//   - OverviewTab 提供 8+ 卡片平铺（移动端/平板端）
//   - 已被 Cockpit 替代（任务 #76 引入，#78 全设备通用）
//   - OverviewTab.tsx 已删除（任务 #78）
// ============================================================

export default function DashboardPage() {
  return null;
}
