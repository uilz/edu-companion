'use client';

import { type ReactNode } from 'react';
import { ArrowRight } from 'lucide-react';

export type EntryCardVariant = 'card' | 'button';

interface EntryCardProps {
  icon: ReactNode;
  title: string;
  description: string;
  onClick: () => void;
  cta: string;
  variant?: EntryCardVariant;
}

/**
 * EntryCard — 入口卡片组件
 *
 * 两种变体：
 * - card:   卡片布局，底部有独立的 CTA 按钮（reading 页面风格）
 * - button: 整张卡片可点击，hover 有背景色变化（liveroom 页面风格）
 */
export function EntryCard({
  icon,
  title,
  description,
  onClick,
  cta,
  variant = 'card',
}: EntryCardProps) {
  if (variant === 'button') {
    return (
      <button
        onClick={onClick}
        className="border border bg-surface rounded-lg p-5 text-left hover:bg-surface-hover transition-colors"
      >
        <div className="flex items-center gap-2 text font-medium">
          {icon}
          {title}
        </div>
        <div className="text-xs text-muted mt-1.5 leading-relaxed">
          {description}
        </div>
        <div className="text-xs text-success mt-3 inline-flex items-center gap-1">
          {cta} →
        </div>
      </button>
    );
  }

  return (
    <div className="border border bg-surface rounded-lg p-4">
      <div className="flex items-center gap-2 mb-2 text">
        {icon}
        <h3 className="text-sm font-semibold">{title}</h3>
      </div>
      <p className="text-xs text-muted mb-3">{description}</p>
      <button
        onClick={onClick}
        className="text-xs text-accent hover:underline inline-flex items-center gap-1"
      >
        {cta} <ArrowRight size={12} />
      </button>
    </div>
  );
}

export default EntryCard;