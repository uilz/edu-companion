'use client';

// 从 stats 页面导入统计组件
import StatsPage from '@/app/stats/page';

/**
 * StatsTab - 学习统计 Tab 组件
 * 作为仪表盘中的一个标签页，渲染完整的统计页面内容
 */
export function StatsTab() {
  // 直接渲染统计页面组件
  return <StatsPage />;
}
