"use client";

import { type ReactNode } from "react";
import {
  BookOpen, Sparkles, AlertOctagon, Inbox, Search, History,
  GraduationCap, Wand2, RotateCcw, Brain, FileText,
  Library, ListTodo,
} from "lucide-react";

interface EmptyStateProps {
  /** 预置场景 */
  variant?: "banks" | "questions" | "history" | "errors" | "ai" | "search" | "review" | "generic";
  title: string;
  description?: string;
  /** 自定义操作 */
  action?: ReactNode;
  /** 自定义图标（覆盖预置） */
  icon?: ReactNode;
  /** 紧凑模式 — 上下 padding 缩小 */
  compact?: boolean;
}

const PRESET_ICONS: Record<string, ReactNode> = {
  banks: <Library size={28} className="text-[var(--color-text-muted)]" />,
  questions: <BookOpen size={28} className="text-[var(--color-text-muted)]" />,
  history: <History size={28} className="text-[var(--color-text-muted)]" />,
  errors: <FileText size={28} className="text-[var(--color-text-muted)]" />,
  ai: <Wand2 size={28} className="text-[var(--color-text-muted)]" />,
  search: <Search size={28} className="text-[var(--color-text-muted)]" />,
  review: <RotateCcw size={28} className="text-[var(--color-text-muted)]" />,
  generic: <Inbox size={28} className="text-[var(--color-text-muted)]" />,
};

/**
 * EmptyState — 练习模块统一空态展示
 *
 * 与 @/components/ui/EmptyState 的差异：
 *  - 内置 practice 场景变体（题库/题目/历史/错题/AI 出题/搜索/复习）
 *  - 紧凑模式（卡片内/折叠内）
 *  - 适配 practice 颜色系统（text-[var(--color-text-muted)]）
 */
export default function PracticeEmptyState({
  variant = "generic",
  title,
  description,
  action,
  icon,
  compact = false,
}: EmptyStateProps) {
  const padding = compact ? "py-8" : "py-12 sm:py-16";
  const iconBox = compact ? "mb-2" : "mb-3";
  return (
    <div className={`flex flex-col items-center justify-center ${padding} px-4 text-center`}>
      <div className={`${iconBox} opacity-60`}>{icon ?? PRESET_ICONS[variant]}</div>
      <h3 className={`text-sm font-medium text-[var(--color-text)] ${description ? "mb-1" : ""}`}>
        {title}
      </h3>
      {description && (
        <p className="text-xs text-[var(--color-text-muted)] mt-1 max-w-xs">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

// 导出常用 icons 便于复用
export {
  BookOpen, Sparkles, AlertOctagon, Inbox, Search, History,
  GraduationCap, Wand2, RotateCcw, Brain, FileText, Library, ListTodo,
};
