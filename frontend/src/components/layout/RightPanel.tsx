// ============================================================
// RightPanel — 右栏工作面板
//
// 任务 #76 应包含：AI 助手 / 任务面板 / 快速操作
// 当前实现：最近活动 + 快速入口 + 学习状态
// 后续 Task #88+ 接入秘书引擎实时推荐
// ============================================================

"use client";

import Link from "next/link";
import {
  Brain, Sparkles, Target, Clock, TrendingUp,
  BookOpen, Dumbbell, Layers, MessageSquare, Bell,
  ChevronRight, Calendar, FileSearch,
} from "lucide-react";

const QUICK_ACTIONS = [
  { href: "/practice", icon: Dumbbell, label: "开始练习", desc: "智能推荐" },
  { href: "/conversation", icon: MessageSquare, label: "问 AI", desc: "对话助手" },
  { href: "/knowledge-tree", icon: GitGraphIcon, label: "查看知识树", desc: "图谱浏览" },
  { href: "/secretary", icon: Bell, label: "秘书通知", desc: "智能提醒" },
];

const LEARNING_STATUS = [
  { label: "今日学习", value: "—", icon: Clock },
  { label: "待复习", value: "—", icon: Target },
  { label: "掌握度", value: "—", icon: TrendingUp },
];

function GitGraphIcon(props: { size?: number; className?: string }) {
  return (
    <svg
      width={props.size || 16}
      height={props.size || 16}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className}
    >
      <circle cx="5" cy="6" r="2.5" />
      <circle cx="5" cy="18" r="2.5" />
      <circle cx="19" cy="12" r="2.5" />
      <path d="M7.5 6h3a4 4 0 0 1 4 4v0a4 4 0 0 0 4 4" />
    </svg>
  );
}

export default function RightPanel() {
  return (
    <div
      data-testid="right-panel"
      className="h-full w-full overflow-y-auto text-[var(--color-text)] text-xs p-3 space-y-4"
    >
      {/* ── 快速入口 ── */}
      <section>
        <h3 className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)] mb-2 px-1">
          快速入口
        </h3>
        <div className="space-y-1">
          {QUICK_ACTIONS.map((a) => (
            <Link
              key={a.href}
              href={a.href}
              className="flex items-center gap-2.5 px-2 py-2 rounded-lg hover:bg-[var(--color-surface-hover)] transition-colors group"
            >
              <div className="p-1.5 rounded-md bg-[var(--color-surface)] text-[var(--color-accent)] group-hover:bg-[var(--color-accent)]/10">
                <a.icon size={13} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-[12px]">{a.label}</div>
                <div className="text-[10px] text-[var(--color-text-muted)]">{a.desc}</div>
              </div>
              <ChevronRight size={12} className="text-[var(--color-text-muted)] opacity-0 group-hover:opacity-100 transition-opacity" />
            </Link>
          ))}
        </div>
      </section>

      {/* ── 学习状态 ── */}
      <section>
        <h3 className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)] mb-2 px-1">
          学习状态
        </h3>
        <div className="space-y-1.5">
          {LEARNING_STATUS.map((s) => (
            <div
              key={s.label}
              className="flex items-center gap-2 px-2 py-1.5 rounded-md bg-[var(--color-surface)]/50"
            >
              <s.icon size={12} className="text-[var(--color-text-muted)]" />
              <span className="text-[11px] text-[var(--color-text-muted)] flex-1">{s.label}</span>
              <span className="text-[11px] font-medium">{s.value}</span>
            </div>
          ))}
          <div className="text-[10px] text-[var(--color-text-muted)]/70 px-2 pt-1">
            后续 Task #88+ 接入实时数据
          </div>
        </div>
      </section>

      {/* ── AI 助手入口 ── */}
      <section>
        <Link
          href="/conversation"
          className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-gradient-to-br from-[var(--color-accent)]/10 to-[var(--color-accent)]/5 border border-[var(--color-accent)]/20 hover:from-[var(--color-accent)]/20 hover:to-[var(--color-accent)]/10 transition-colors"
        >
          <Sparkles size={14} className="text-[var(--color-accent)]" />
          <div className="flex-1 min-w-0">
            <div className="text-[12px] font-medium">唤起 AI 助手</div>
            <div className="text-[10px] text-[var(--color-text-muted)]">⌘J 快捷键</div>
          </div>
        </Link>
      </section>
    </div>
  );
}
