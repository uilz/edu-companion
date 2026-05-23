// 学习规划页面加载状态组件
// 当 /study 路由页面仍在加载异步数据（学习计划、进度和学习建议）时显示
// 这是 Next.js 自动的 Suspense 回退组件，在页面内容完全加载前展示加载提示

import { Loader2 } from "lucide-react";

/**
 * Loading 组件
 * 显示一个居中的旋转加载图标，提示用户内容正在加载中
 * 与 page.tsx 中的内联加载状态保持一致的设计风格
 */
export default function Loading() {
  return (
    // 全屏居中容器，确保加载图标位于视口中央
    <div className="min-h-screen flex items-center justify-center">
      {/* 旋转加载图标 - 使用主题色 */}
      <Loader2 size={24} className="animate-spin text-[var(--color-text-muted)]" />
    </div>
  );
}
