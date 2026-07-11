'use client';

import { type ReactNode } from 'react';

export type StatCardColorScheme = 'indigo' | 'purple' | 'green' | 'amber' | 'rose';
export type StatCardVariant = 'default' | 'minimal';

interface StatCardProps {
  /** 标签文字 */
  label: string;
  /** 数值（支持 string | number） */
  value: string | number;
  /** 图标（ReactNode） */
  icon?: ReactNode;
  /** 数值下方提示文字 */
  hint?: string;
  /** 数值右侧内联单位/后缀 */
  sub?: string;
  /** 数值文字颜色（Tailwind class，如 "text-danger"） */
  color?: string;
  /** 配色方案：左侧彩色边框 + 背景色 */
  colorScheme?: StatCardColorScheme;
  /**
   * 布局变体：
   * - default: 水平布局，标签在上、数值在下（适合网格排列）
   * - minimal: 垂直居中，图标在上、数值在中、标签在下（紧凑风格）
   */
  variant?: StatCardVariant;
  /** 外部样式类名 */
  className?: string;
}

const COLOR_SCHEME_MAP: Record<StatCardColorScheme, string> = {
  indigo: 'border-l-indigo-400 bg-accent/10',
  purple: 'border-l-purple-400 bg-accent/10',
  green:  'border-l-emerald-400 bg-success/10',
  amber:  'border-l-amber-400 bg-warning/10',
  rose:   'border-l-rose-400 bg-danger/10',
};

/**
 * StatCard — 统计数值卡片（Design System 1.0）
 *
 * 统一仪表盘、秘书、知识树等场景的数据卡样式。
 */
export function StatCard({
  label,
  value,
  icon,
  hint,
  sub,
  color,
  colorScheme,
  variant = 'default',
  className = '',
}: StatCardProps) {
  if (variant === 'minimal') {
    return (
      <div
        className={`flex flex-col items-center gap-0.5 p-3 rounded-xl bg-surface border border-divider ${className}`}
      >
        {icon && <span className={color || 'text-ink-muted'}>{icon}</span>}
        <span className="text-lg font-bold text-ink-primary">{value}</span>
        <span className="text-[9px] text-ink-muted">{label}</span>
      </div>
    );
  }

  const schemeClass = colorScheme ? COLOR_SCHEME_MAP[colorScheme] : '';

  return (
    <div
      className={`border border-divider bg-surface rounded-lg p-3 ${schemeClass} ${colorScheme ? 'border-l-2' : ''} ${className}`}
    >
      <div className="text-xs text-ink-muted flex items-center gap-1">
        {icon}
        {label}
      </div>
      <div className={`text-xl font-semibold mt-1 ${color || 'text-ink-primary'}`}>
        {value}
        {sub && (
          <span className="text-xs font-normal text-ink-muted ml-1">
            {sub}
          </span>
        )}
      </div>
      {hint && (
        <div className="text-[10px] text-ink-muted mt-1">{hint}</div>
      )}
    </div>
  );
}

export default StatCard;
