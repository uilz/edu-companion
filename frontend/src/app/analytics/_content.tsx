"use client";

import { useState, useEffect, useMemo } from "react";
import { BarChart3, Loader2, BookOpen, Heart } from "lucide-react";
import Link from "next/link";
import Card from "@/components/ui/Card";
import RadarChart from "@/components/analytics/RadarChart";

import {
  AnalyticsData, BehaviorData, Tab, Suggestion,
  generateSuggestions,
} from "@/components/dashboard/analytics/utils";
import { TrendChart } from "@/components/dashboard/analytics/TrendChart";
import { HeatmapGrid } from "@/components/dashboard/analytics/HeatmapGrid";
import { HabitTab } from "@/components/dashboard/analytics/HabitTab";
import { RetentionPanel } from "@/components/dashboard/analytics/RetentionPanel";
import { OverviewCards } from "@/components/dashboard/analytics/OverviewCards";
import { MasteryErrorsCard } from "@/components/dashboard/analytics/MasteryErrorsCard";
import { SuggestionsCard } from "@/components/dashboard/analytics/SuggestionsCard";
import { API_BASE } from "@/lib/api/api";

export default function AnalyticsContent() {
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

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="animate-spin text-[var(--color-accent)]" size={24} />
      </div>
    );
  }

  if (!data || !data.overview || data.overview.total_questions === 0) {
    return (
      <div className="text-center py-16">
        <BarChart3 size={40} className="mx-auto mb-4 text-[var(--color-text-muted)]" />
        <h1 className="text-3xl font-semibold text-[var(--color-text)] mb-2">学情分析</h1>
        <p className="text-[var(--color-text-muted)] mb-6">还没有练习数据</p>
        <Link
          href="/practice"
          className="inline-block px-6 py-2.5 bg-[var(--color-accent)] text-white text-sm hover:bg-[var(--color-accent-hover)] active:scale-[0.97] transition-colors"
        >
          去练习
        </Link>
      </div>
    );
  }

  const timeLabel = timeRange === "week" ? "7天" : timeRange === "month" ? "30天" : "全部";

  return (
    <div className="max-w-4xl mx-auto">
      {/* ── 时间范围 + 子 Tab ── */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div className="flex bg-[var(--color-surface)] p-0.5 rounded">
          {([
            { key: "analytics" as Tab, label: "数据", icon: <BarChart3 size={12} /> },
            { key: "habits" as Tab, label: "习惯", icon: <Heart size={12} /> },
          ]).map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex items-center gap-1 px-3 py-1 text-xs font-medium transition-colors ${
                tab === t.key
                  ? "bg-[var(--color-accent)] text-white shadow-sm"
                  : "text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
              }`}
              style={{ borderRadius: "2px" }}
            >
              {t.icon}{t.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          {(["week", "month", "all"] as const).map((r) => (
            <button
              key={r}
              onClick={() => setTimeRange(r)}
              className={`px-3 py-1.5 text-xs font-medium transition-colors rounded ${
                timeRange === r
                  ? "bg-[var(--color-accent)] text-white"
                  : "bg-[var(--color-surface)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
              }`}
            >
              {r === "week" ? "本周" : r === "month" ? "本月" : "全部"}
            </button>
          ))}
          <Link
            href="/practice/errors"
            className="ml-2 flex items-center gap-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            <BookOpen size={13} /> 错题本
          </Link>
        </div>
      </div>

      {tab === "analytics" ? (
        <>
          <OverviewCards overview={data.overview} />
          <Card title={`📈 每日练习趋势 · ${timeLabel}`} className="mb-6 !p-5">
            <TrendChart data={data.daily_trend} />
          </Card>
          <MasteryErrorsCard
            masteryBars={data.mastery_bars}
            errorDistribution={data.error_distribution}
          />
          <Card title="⏰ 学习时段" className="mb-6 !p-5">
            <HeatmapGrid data={data.hourly_heatmap} />
          </Card>
          <div className="mb-6"><RadarChart /></div>
          <RetentionPanel />
          <SuggestionsCard suggestions={suggestions} />
        </>
      ) : (
        <HabitTab data={behaviorData} />
      )}
    </div>
  );
}