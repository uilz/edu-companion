// ============================================================
// RightPanel — 右栏工作面板
//
// 任务 #76 5 栏驾驶舱的右槽：
//   - 快速入口：直达 4 个核心模块
//   - 学习状态：接入 /api/practice/stats/overview + /api/progress/{user_id}/summary
//   - 唤起 AI：直接跳转 /conversation
// ============================================================

"use client";

import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import {
  Sparkles, Target, Clock, TrendingUp,
  Dumbbell, MessageSquare, Bell, ChevronRight,
  Loader2,
} from "lucide-react";
import { api } from "@/lib/api/api";
import { useCurrentUserId } from "@/hooks/useCurrentUserId";

const QUICK_ACTIONS = [
  { href: "/practice", icon: Dumbbell, label: "开始练习", desc: "智能推荐" },
  { href: "/conversation", icon: MessageSquare, label: "问 AI", desc: "对话助手" },
  { href: "/knowledge-tree", icon: "graph", label: "查看知识树", desc: "图谱浏览" },
  { href: "/secretary", icon: Bell, label: "秘书通知", desc: "智能提醒" },
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

interface LearningStats {
  todayQuestions: number | null;
  studyMinutes: number | null;
  streakDays: number | null;
  accuracy: number | null;
}

export default function RightPanel() {
  const userId = useCurrentUserId();
  const [stats, setStats] = useState<LearningStats | null>(null);
  const [loading, setLoading] = useState(false);

  const loadStats = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    try {
      const [overviewRes, progressRes] = await Promise.allSettled([
        api<{ today_questions?: number; study_minutes?: number; accuracy?: number }>(
          "/api/practice/stats/overview",
        ),
        api<{ streak?: number; yesterday?: { total: number; accuracy: number } }>(
          `/api/progress/${userId}/summary`,
        ),
      ]);
      const overview = overviewRes.status === "fulfilled" ? overviewRes.value : null;
      const progress = progressRes.status === "fulfilled" ? progressRes.value : null;
      setStats({
        todayQuestions: overview?.today_questions ?? null,
        studyMinutes: overview?.study_minutes ?? null,
        streakDays: progress?.streak ?? null,
        accuracy: overview?.accuracy ?? null,
      });
    } catch {
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

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
          {QUICK_ACTIONS.map((a) => {
            const Icon = a.icon === "graph" ? GitGraphIcon : a.icon;
            return (
              <Link
                key={a.href}
                href={a.href}
                className="flex items-center gap-2.5 px-2 py-2 rounded-lg hover:bg-[var(--color-surface-hover)] transition-colors group"
              >
                <div className="p-1.5 rounded-md bg-[var(--color-surface)] text-[var(--color-accent)] group-hover:bg-[var(--color-accent)]/10">
                  <Icon size={13} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-[12px]">{a.label}</div>
                  <div className="text-[10px] text-[var(--color-text-muted)]">{a.desc}</div>
                </div>
                <ChevronRight size={12} className="text-[var(--color-text-muted)] opacity-0 group-hover:opacity-100 transition-opacity" />
              </Link>
            );
          })}
        </div>
      </section>

      {/* ── 学习状态（实时数据） ── */}
      <section>
        <div className="flex items-center justify-between mb-2 px-1">
          <h3 className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
            学习状态
          </h3>
          {loading && <Loader2 size={9} className="animate-spin text-[var(--color-text-muted)]" />}
        </div>
        <div className="space-y-1.5">
          <StatusRow
            icon={Clock}
            label="今日学习"
            value={
              stats?.todayQuestions != null
                ? `${stats.todayQuestions} 题`
                : stats?.studyMinutes != null
                ? `${Math.round(stats.studyMinutes)}m`
                : "—"
            }
            tone="accent"
          />
          <StatusRow
            icon={TrendingUp}
            label="正确率"
            value={
              stats?.accuracy != null
                ? `${Math.round(stats.accuracy * 100)}%`
                : "—"
            }
            tone={stats?.accuracy != null && stats.accuracy >= 0.8 ? "good" : "default"}
          />
          <StatusRow
            icon={Target}
            label="连续天数"
            value={
              stats?.streakDays != null
                ? `${stats.streakDays} 天`
                : "—"
            }
            tone={stats?.streakDays && stats.streakDays >= 7 ? "good" : "default"}
          />
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

function StatusRow({
  icon: Icon,
  label,
  value,
  tone = "default",
}: {
  icon: typeof Clock;
  label: string;
  value: string;
  tone?: "default" | "accent" | "good";
}) {
  const valueColor =
    tone === "accent"
      ? "text-[var(--color-accent)]"
      : tone === "good"
      ? "text-[#10b981]"
      : "text-[var(--color-text)]";
  return (
    <div className="flex items-center gap-2 px-2 py-1.5 rounded-md bg-[var(--color-surface)]/50">
      <Icon size={12} className="text-[var(--color-text-muted)]" />
      <span className="text-[11px] text-[var(--color-text-muted)] flex-1">{label}</span>
      <span className={`text-[12px] font-semibold tabular-nums ${valueColor}`}>{value}</span>
    </div>
  );
}
