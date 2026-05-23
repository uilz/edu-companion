// 导入页面骨架屏组件，用于异步加载时的占位展示
import { PageSkeleton } from '@/components/ui/Skeleton';

/**
 * 练习页面加载状态组件
 * 当练习页面因路由懒加载或异步数据请求而处于 loading 状态时，
 * 展示此骨架屏作为过渡，提升用户体验。
 */
export default function Loading() {
  // 渲染骨架屏占位内容
  return <PageSkeleton />;
}
