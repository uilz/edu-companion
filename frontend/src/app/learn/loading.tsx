// 学习页加载状态组件 - 在页面内容加载完成前显示骨架屏占位
import { ChatSkeleton } from '@/components/ui/Skeleton';

// 默认导出的 Loading 组件，用于 Next.js 的流式加载和 Suspense 回退
// 当 /learn 路由页面仍在加载异步数据时，渲染聊天风格的骨架屏动画
export default function Loading() {
  return <ChatSkeleton />;
}
