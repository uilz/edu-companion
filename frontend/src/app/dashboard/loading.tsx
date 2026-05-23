// 导入页面骨架屏组件，用于加载态占位显示
import { PageSkeleton } from '@/components/ui/Skeleton';

// 仪表盘加载状态页面 —— 当仪表盘页面数据正在获取时，显示骨架屏占位
export default function Loading() {
  // 渲染骨架屏组件作为加载占位内容
  return <PageSkeleton />;
}
