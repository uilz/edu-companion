"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Calendar, Target, BarChart3, BookOpen, Network, ListChecks, Loader2, AlertCircle, type LucideIcon } from "lucide-react";
import { useDailyView, useGoals, useReviews, useViewLayouts } from "@/hooks/planning/usePlanning";
import Card from "@/components/ui/Card";

type ViewMode = "daily" | "weekly" | "knowledge" | "goals" | "reviews";

const TABS: Array<{
  key: ViewMode;
  label: string;
  icon: LucideIcon;
  desc: string;
}> = [
  { key: "daily", label: "日视图", icon: Calendar, desc: "今日时间轴 + 待安排池" },
  { key: "weekly", label: "周视图", icon: BarChart3, desc: "7 天负载分布" },
  { key: "knowledge", label: "知识视图", icon: Network, desc: "知识点 + 待办密度" },
  { key: "goals", label: "目标", icon: Target, desc: "长期目标与进度" },
  { key: "reviews", label: "周期回顾", icon: ListChecks, desc: "周/月汇总" },
];

const HABIT_LABELS: Record<string, string> = {
  beginner: "🌱 初学",
  regular: "📚 日常",
  intensive: "💪 强化",
};

const FATIGUE_LABELS: Record<string, string> = {
  low: "疲劳低",
  medium: "疲劳中等",
  high: "疲劳高",
};

export default function PlanningPage() {
  const router = useRouter();
  const [mode, setMode] = useState<ViewMode>("daily");
  const { data, loading, error } = useDailyView();
  const { goals } = useGoals();
  const { reviews } = useReviews();
  const { layouts } = useViewLayouts();

  const handleTabClick = (k: ViewMode) => {
    setMode(k);
    if (k === "daily") router.push("/planning/daily");
    else if (k === "weekly") router.push("/planning/weekly");
    else if (k === "knowledge") router.push("/planning/knowledge");
    else if (k === "goals") router.push("/planning/goals");
    else if (k === "reviews") router.push("/planning/reviews");
  };

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {/* 页面头部 */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-[var(--color-text)] tracking-tight flex items-center gap-2">
              <Calendar size={20} /> 规划工作台
            </h1>
            <p className="text-sm text-[var(--color-text-muted)] mt-1">
              后端调度引擎的前端用户工作台 — 汇聚 · 编排 · 追踪
            </p>
          </div>
          <div className="flex items-center gap-2 text-sm text-[var(--color-text-muted)]">
            <BookOpen size={14} /> 视图方案 {layouts.length} · 目标 {goals.length} · 回顾 {reviews.length}
          </div>
        </div>

        {/* Tab 切换 */}
        <div className="flex flex-wrap gap-2 mb-6">
          {TABS.map((t) => {
            const Icon = t.icon;
            const active = mode === t.key;
            return (
              <button
                key={t.key}
                onClick={() => handleTabClick(t.key)}
                className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                  active
                    ? "bg-[var(--color-accent)] text-white"
                    : "border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-card)]"
                }`}
              >
                <Icon size={15} />
                {t.label}
              </button>
            );
          })}
        </div>

        {/* 主体：默认显示概览（所有数据汇总在主页） */}
        {loading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 size={24} className="animate-spin text-[var(--color-text-muted)]" />
          </div>
        )}

        {error && (
          <div className="mb-6 px-4 py-3 border border-[var(--color-border)] text-sm text-[var(--color-text-muted)] flex items-center gap-2">
            <AlertCircle size={15} /> {error}
          </div>
        )}

        {data && (
          <div className="space-y-6">
            {/* 顶部状态条 */}
            <Card title="顶部状态条">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 border border-[var(--color-border)]">
                  <div className="text-xs text-[var(--color-text-muted)] mb-1">疲劳风险</div>
                  <div className="text-base font-semibold">
                    {FATIGUE_LABELS[data.status_bar.fatigue_risk] || data.status_bar.fatigue_risk}
                  </div>
                </div>
                <div className="p-3 border border-[var(--color-border)]">
                  <div className="text-xs text-[var(--color-text-muted)] mb-1">压力值</div>
                  <div className="text-base font-semibold">
                    {data.status_bar.pressure_score ?? "—"} / 10
                  </div>
                </div>
                <div className="p-3 border border-[var(--color-border)]">
                  <div className="text-xs text-[var(--color-text-muted)] mb-1">能量值</div>
                  <div className="text-base font-semibold">
                    {data.status_bar.energy_score ?? "—"} / 10
                  </div>
                </div>
                <div className="p-3 border border-[var(--color-border)]">
                  <div className="text-xs text-[var(--color-text-muted)] mb-1">习惯等级</div>
                  <div className="text-base font-semibold">
                    {HABIT_LABELS[data.status_bar.habit_level] || data.status_bar.habit_level}
                  </div>
                </div>
              </div>
              {data.status_bar.pomodoro_message && (
                <div className="mt-3 text-xs text-[var(--color-text-muted)]">
                  🍅 {data.status_bar.pomodoro_message}
                </div>
              )}
            </Card>

            {/* 概览提示：跳到具体视图 */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Card title="日视图">
                <p className="text-sm text-[var(--color-text-muted)] mb-3">
                  时间轴上 {data.timeline_items.length} 个已安排项，待安排池 {data.pending_pool.length} 个待办。
                </p>
                <button
                  onClick={() => handleTabClick("daily")}
                  className="text-sm text-[var(--color-accent)] hover:underline"
                >
                  打开日视图 →
                </button>
              </Card>
              <Card title="目标进度">
                <p className="text-sm text-[var(--color-text-muted)] mb-3">
                  当前 {goals.filter((g) => g.status === "active").length} 个进行中目标。
                </p>
                <button
                  onClick={() => handleTabClick("goals")}
                  className="text-sm text-[var(--color-accent)] hover:underline"
                >
                  目标管理 →
                </button>
              </Card>
              <Card title="周期回顾">
                <p className="text-sm text-[var(--color-text-muted)] mb-3">
                  已记录 {reviews.length} 份周/月回顾。
                </p>
                <button
                  onClick={() => handleTabClick("reviews")}
                  className="text-sm text-[var(--color-accent)] hover:underline"
                >
                  查看回顾 →
                </button>
              </Card>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
