'use client';

interface CardProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
  accent?: boolean;
}

// 通用卡片组件 — 使用 Design Token 语义色
export default function Card({ title, children, className = "", accent = false }: CardProps) {
  return (
    <div
      className={`border bg-surface p-5 sm:p-6 rounded-md transition-all duration-200
        ${accent
          ? 'border-divider hover:border-accent'
          : 'border-divider'}
        ${className}`}
    >
      {title && (
        <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-muted mb-4 flex items-center gap-2">
          {title}
        </h3>
      )}
      {children}
    </div>
  );
}
