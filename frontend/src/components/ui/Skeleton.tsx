// 导入 cn 工具函数，用于合并 Tailwind CSS 类名
import { cn } from '@/lib/utils/utils';

// Skeleton 组件的属性接口定义
interface SkeletonProps {
  className?: string;          // 自定义类名
  variant?: 'text' | 'card' | 'circle' | 'rect';  // 骨架屏变体类型
}

/**
 * Skeleton 骨架屏组件
 * 在内容加载完成前显示占位效果，提升用户体验
 *
 * @param className - 自定义类名
 * @param variant  - 变体类型：text（文本行）、card（卡片）、circle（圆形）、rect（矩形）
 */
export function Skeleton({ className, variant = 'text' }: SkeletonProps) {
  // 基础样式：脉冲动画 + 灰色背景 + 圆角
  const base = 'animate-pulse bg-[var(--color-border)] dark:bg-[var(--color-surface-hover)] rounded';

  // 各变体对应的尺寸样式
  const variants = {
    text: 'h-4 w-full',          // 文本行：高度 4，宽度 100%
    card: 'h-32 w-full rounded-lg', // 卡片：高度 32，宽度 100%，大圆角
    circle: 'h-12 w-12 rounded-full', // 圆形：12x12，完全圆角
    rect: 'h-24 w-full',         // 矩形：高度 24，宽度 100%
  };

  // 渲染骨架占位元素
  return <div className={cn(base, variants[variant], className)} />;
}

/**
 * PageSkeleton 页面级骨架屏
 * 模拟典型页面布局，包含标题、卡片网格、长矩形和文本行
 */
export function PageSkeleton() {
  return (
    <div className="space-y-6 p-6">
      {/* 页面标题占位 */}
      <Skeleton variant="text" className="h-8 w-1/3" />
      {/* 三列卡片网格占位 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} variant="card" />
        ))}
      </div>
      {/* 大矩形区域占位 */}
      <Skeleton variant="rect" className="h-48" />
      {/* 多行文本占位 */}
      <div className="space-y-3">
        <Skeleton variant="text" className="h-4 w-5/6" />
        <Skeleton variant="text" className="h-4 w-4/6" />
        <Skeleton variant="text" className="h-4 w-3/6" />
      </div>
    </div>
  );
}

/**
 * ChatSkeleton 聊天界面骨架屏
 * 模拟聊天消息列表，左右交替显示气泡占位
 */
export function ChatSkeleton() {
  return (
    <div className="flex flex-col gap-4 p-4">
      {[1, 2, 3].map((i) => (
        // 根据索引奇偶性决定消息对齐方向：偶数靠右（自己），奇数靠左（对方）
        <div key={i} className={`flex ${i % 2 === 0 ? 'justify-end' : 'justify-start'}`}>
          <Skeleton
            variant="card"
            className={i % 2 === 0 ? 'h-16 w-2/3' : 'h-20 w-3/4'}
          />
        </div>
      ))}
    </div>
  );
}
