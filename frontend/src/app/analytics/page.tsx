// 学习分析页面 — 客户端组件，展示学情数据、习惯追踪与遗忘曲线
"use client";

import { useState, useEffect, useMemo } from "react";
import { BarChart3, Loader2, BookOpen, Heart } from "lucide-react";
import Link from "next/link";
import Card from "@/components/ui/Card";
import RadarChart from "@/components/analytics/RadarChart";

// ── 共享类型 & 工具函数（来自 dashboard/analytics/utils）──
import {
  AnalyticsData, BehaviorData, Tab, Suggestion,
  generateSuggestions,
} from "@/components/dashboard/analytics/utils";

// ── 共享组件（来自 dashboard/analytics/）──
import { TrendChart } from "@/components/dashboard/analytics/TrendChart";
import { HeatmapGrid } from "@/components/dashboard/analytics/HeatmapGrid";
import { HabitTab } from "@/components/dashboard/analytics/HabitTab";
import { RetentionPanel } from "@/components/dashboard/analytics/RetentionPanel";
import { OverviewCards } from "@/components/dashboard/analytics/OverviewCards";
import { MasteryErrorsCard } from "@/components/dashboard/analytics/MasteryErrorsCard";
import { SuggestionsCard } from "@/components/dashboard/analytics/SuggestionsCard";
import { API_BASE } from "@/lib/api";

// ── 主页面 ──

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [behaviorData, setBehaviorData] = useState<BehaviorData | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("analytics");
  const [timeRange, setTimeRange] = useState<"week" | "month" | "all">("week");

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/api/practice/stats?time_range=${timeRange}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => {
        if (d && d.overview) setData(d);
        setLoading(false);
      })
      .catch(() => { setData(null); setLoading(false); });
  }, [timeRange]);

  useEffect(() => {
    if (tab === "habits") {
      fetch(`${API_BASE}/api/practice/behavior?time_range=${timeRange}`)
        .then((r) => r.json())
        .then((d) => setBehaviorData(d))
        .catch(() => {});
    }
  }, [tab, timeRange]);

  const suggestions: Suggestion[] = useMemo(() => {
    if (!data) return [];
    return generateSuggestions(data.overview, data.mastery_bars, data.error_distribution);
  }, [data]);

  // ── 加载中 ──
  if (loading) {
    return (
      <main className="min-h-screen bg-[var(--color-bg)]">
        <div className="flex items-center justify-center py-20">
          <Loader2 className="animate-spin text-[var(--color-accent)]" size={24} />
        </div>
      </main>
    );
  }

  // ── 空数据 ──
  if (!data || !data.overview || data.overview.total_questions === 0) {
    return (
      <main className="min-h-screen bg-[var(--color-bg)]">
        <div className="max-w-3xl mx-auto px-6 py-16 text-center">
          <BarChart3 size={40} className="mx-auto mb-4 text-[var(--color-text-muted)]" />
          <h1 className="text-3xl font-bold text-[var(--color-text)] mb-2">学情分析</h1>
          <p className="text-[var(--color-text-muted)] mb-6">还没有练习数据</p>
          <Link
            href="/practice"
            className="inline-block px-6 py-2.5 bg-[var(--color-accent)] text-white text-sm hover:bg-[var(--color-accent-hover)] transition-colors"
          >
            去练习
          </Link>
        </div>
      </main>
    );
  }

  const timeLabel = timeRange === "week" ? "7天" : timeRange === "month" ? "30天" : "全部";

  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-4xl mx-auto px-4 md:px-6 py-8 md:py-12">
        {/* ── Header：标题 + Tab 切换 + 时间范围 + 错题本 ── */}
        <div className="flex items-center justify-between mb-8 flex-wrap gap-3">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-[var(--color-text)]">
              <BarChart3 size={24} className="inline mr-2 text-[var(--color-accent)]" />
              学情分析
            </h1>
            <div className="flex bg-[var(--color-surface)] p-0.5" style={{ borderRadius: "2px" }}>
              {([
                { key: "analytics" as Tab, label: "数据", icon: <BarChart3 size={12} /> },
                { key: "habits" as Tab, label: "习惯", icon: <Heart size={12} /> },
              ]).map((t) => (
                <button
                  key={t.key}
                  onClick={() => setTab(t.key)}
                  className={`flex items-center gap-1 px-3 py-1 text-xs font-medium transition-colors ${
                    tab === t.key
                      ? "bg-[var(--color-accent)] text-white"
                      : "text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
                  }`}
                  style={{ borderRadius: "2px" }}
                >
                  {t.icon}{t.label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {(["week", "month", "all"] as const).map((r) => (
              <button
                key={r}
                onClick={() => setTimeRange(r)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  timeRange === r
                    ? "bg-[var(--color-accent)] text-white"
                    : "bg-[var(--color-surface)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
                }`}
              >
                {r === "week" ? "本周" : r === "month" ? "本月" : "全部"}
              </button>
            ))}
            <Link
              href="/errors"
              className="ml-2 flex items-center gap-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            >
              <BookOpen size={13} /> 错题本
            </Link>
          </div>
        </div>

        {tab === "analytics" ? (
          <>
            <OverviewCards overview={data.overview} />
            <Card title={`📈 每日练习趋势 · ${timeLabel}`} className="mb-8 !p-5">
              <TrendChart data={data.daily_trend} />
            </Card>
            <MasteryErrorsCard
              masteryBars={data.mastery_bars}
              errorDistribution={data.error_distribution}
            />
            <Card title="⏰ 学习时段" className="mb-8 !p-5">
              <HeatmapGrid data={data.hourly_heatmap} />
            </Card>
            <div className="mb-8"><RadarChart /></div>
            <RetentionPanel />
            <SuggestionsCard suggestions={suggestions} />
          </>
        ) : (
          <HabitTab data={behaviorData} />
        )}
      </div>
    </main>
  );
}
