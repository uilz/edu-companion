// 客户端组件标记，确保在浏览器端渲染
'use client';

// 引入进度页面的主组件
import ProgressPage from '@/app/progress/page';

/**
 * ProgressTab - 学习进度 Tab 组件
 * 作为仪表盘中的一个标签页，嵌套渲染进度页面内容
 */
export function ProgressTab() {
  // 直接委托给 ProgressPage 组件进行渲染
  return <ProgressPage />;
}
