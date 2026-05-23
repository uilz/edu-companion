/**
 * 加载页面（骨架屏）
 * 这是根路径的加载状态组件，在页面内容完全加载之前显示。
 * 使用 PageSkeleton 组件呈现占位骨架，提升用户感知体验。
 */

import { PageSkeleton } from '@/components/ui/Skeleton';

// 根加载页面：在路由切换或数据获取期间显示骨架屏
export default function Loading() {
  return <PageSkeleton />;
}
