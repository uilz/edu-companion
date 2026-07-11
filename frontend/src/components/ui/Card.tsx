'use client';

import { type ReactNode, type HTMLAttributes } from 'react';

/* ── 简单默认导出（向后兼容） ── */
interface CardProps {
  title?: string;
  children: ReactNode;
  className?: string;
  accent?: boolean;
}

/**
 * Card — 通用卡片组件（Design System 1.0）
 *
 * 提供两种 API：
 * 1. 简单默认：<Card title="标题">内容</Card>（向后兼容旧页面）
 * 2. 复合组件：<Card><CardHeader><CardTitle>...</CardTitle><CardDescription>...</CardDescription></CardHeader><CardContent>...</CardContent></Card>
 *
 * 默认圆角 12px（rounded-lg），背景 surface，边框 divider。
 */
export default function Card({ title, children, className = '', accent = false }: CardProps) {
  return (
    <div
      className={`border bg-surface p-5 sm:p-6 rounded-lg transition-all duration-normal
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

/* ── 复合组件 API（shadcn 风格） ── */

interface DivProps extends HTMLAttributes<HTMLDivElement> {
  children?: ReactNode;
}

export function CardHeader({ className = '', children, ...rest }: DivProps) {
  return (
    <div className={`flex flex-col gap-1.5 p-6 pb-3 ${className}`} {...rest}>
      {children}
    </div>
  );
}

export function CardTitle({ className = '', children, ...rest }: DivProps) {
  return (
    <h3
      className={`text-base font-semibold leading-none tracking-tight text-ink-primary flex items-center gap-2 ${className}`}
      {...rest}
    >
      {children}
    </h3>
  );
}

export function CardDescription({ className = '', children, ...rest }: DivProps) {
  return (
    <p className={`text-sm text-ink-secondary ${className}`} {...rest}>
      {children}
    </p>
  );
}

export function CardContent({ className = '', children, ...rest }: DivProps) {
  return (
    <div className={`p-6 pt-0 ${className}`} {...rest}>
      {children}
    </div>
  );
}

export function CardFooter({ className = '', children, ...rest }: DivProps) {
  return (
    <div className={`flex items-center p-6 pt-0 ${className}`} {...rest}>
      {children}
    </div>
  );
}
