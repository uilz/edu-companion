'use client';

// Card 组件的属性接口
// title: 可选的卡片标题
// children: 卡片内容（React 子节点）
// className: 可选的额外 CSS 类名
// accent: 是否启用强调样式（悬停时高亮边框）
interface CardProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
  accent?: boolean;
}

// 通用卡片组件 — 用于展示内容块，支持标题、强调样式和自定义样式
export default function Card({ title, children, className = "", accent = false }: CardProps) {
  return (
    // 卡片容器：使用 CSS 变量控制背景与边框颜色，支持悬停微动效
    <div
      className={`border bg-[var(--color-card)] p-5 sm:p-6 rounded-lg transition-all duration-200
        ${accent ? 'border-[var(--color-border)] hover:border-[var(--color-accent)]' : 'border-[var(--color-border)]'}
        hover:shadow-md hover:-translate-y-0.5
        ${className}`}
    >
      {/* 如果提供了 title，则渲染卡片标题 */}
      {title && (
        <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)] mb-4 flex items-center gap-2">
          {title}
        </h3>
      )}
      {/* 渲染卡片主体内容 */}
      {children}
    </div>
  );
}
