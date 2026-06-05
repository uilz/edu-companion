"use client";

// ── 依赖导入：React 状态管理、图标库、路由、UI 组件 ──
import { useState, useEffect, useMemo } from "react";
import {
  BarChart3, Target, Clock, TrendingUp, Loader2, BookOpen,
  CalendarDays, Heart,
} from "lucide-react";
import Link from "next/link";
import Card from "@/components/ui/Card";
import RadarChart from "@/components/analytics/RadarChart";

// ── 子模块导入 ──
import {
  Overview, MasteryBar, ErrorDist, DailyPoint, HeatmapCell,
  AnalyticsData, BehaviorData, Tab, Suggestion,
  ERROR_LABELS, MASTERY_EMOJI, deltaStr, deltaColor, generateSuggestions,
} from "@/components/dashboard/analytics/utils";
import { TrendChart } from "@/components/dashboard/analytics/TrendChart";
import { HeatmapGrid } from "@/components/dashboard/analytics/HeatmapGrid";
import { HabitTab } from "@/components/dashboard/analytics/HabitTab";
import { RetentionPanel } from "@/components/dashboard/analytics/RetentionPanel";
import { DailySummaryCard } from "@/components/dashboard/analytics/DailySummaryCard";
import { API_BASE } from "@/lib/api/api";

// ═══════════════════════════════════════════════
//  主导出组件 — AnalyticsTab（学情分析页面）
// ═══════════════════════════════════════════════

export function AnalyticsTab() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [behaviorData, setBehaviorData] = useState<BehaviorData | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("analytics");          // 当前 Tab
  const [timeRange, setTimeRange] = useState<"week" | "month" | "all">("week"); // 时间范围

  // 获取分析数据（切换时间范围时重新请求）
  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/api/practice/stats?time_range=${timeRange}`)
      .then((r) => r.json())
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [timeRange]);

  // 切换到 habits Tab 时获取行为数据
  useEffect(() => {
    if (tab === "habits") {
      fetch(`${API_BASE}/api/practice/behavior?time_range=${timeRange}`)
        .then((r) => r.json())
        .then((d) => setBehaviorData(d))
        .catch(() => {});
    }
  }, [tab, timeRange]);

  // 基于数据生成建议（memo 缓存）
  const suggestions: Suggestion[] = useMemo(() => {
    if (!data) return [];
    return generateSuggestions(data.overview, data.mastery_bars, data.error_distribution);
  }, [data]);

  // ── 加载中状态 ──
  if (loading) {
    return (
      <div>
        <div className="flex items-center justify-center py-20">
          <Loader2 className="animate-spin text-[var(--color-accent)]" size={24} />
        </div>
      </div>
    );
  }

  // ── 无数据（首次使用）状态 ──
  if (!data || data.overview.total_questions === 0) {
    return (
      <div>
        <div className="max-w-3xl mx-auto px-6 py-16 text-center">
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
      </div>
    );
  }

  // ── 解构数据 ──
  const overview = data?.overview;
  const daily_trend = data?.daily_trend || [];
  const mastery_bars = data?.mastery_bars || [];
  const error_distribution = data?.error_distribution || [];
  const hourly_heatmap = data?.hourly_heatmap || [];
  const acc = overview ? (overview.accuracy * 100).toFixed(0) : "0";
  const h = overview ? Math.floor(overview.study_minutes / 60) : 0;
  const min = overview ? Math.round(overview.study_minutes % 60) : 0;

  return (
    <div>
      <div>
        {/* ── 页面头部：标题 + Tab 切换 + 时间范围 + 错题本入口 ── */}
        <div className="flex items-center justify-between mb-8 flex-wrap gap-3">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl md:text-3xl font-semibold tracking-tight text-[var(--color-text)]">
              <BarChart3 size={24} className="inline mr-2 text-[var(--color-accent)]" />
              学情分析
            </h1>
            {/* Tab 切换器：数据 / 习惯 */}
            <div className="flex bg-[var(--color-surface)] p-0.5" style={{ borderRadius: "2px" }}>
              {([
                { key: "analytics", label: "数据", icon: <BarChart3 size={12} /> },
                { key: "habits", label: "习惯", icon: <Heart size={12} /> },
              ] as { key: Tab; label: string; icon: React.ReactNode }[]).map((t) => (
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
                  {t.icon}
                  {t.label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* 时间范围切换 */}
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

        {/* ── 根据当前 Tab 显示不同内容 ── */}
        {tab === "analytics" ? (
          <>
            {/* ── ① 总览概览卡片（4 张：总题数、正确率、学习天数、时长） ── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          {[
            {
              icon: <Target size={16} />,
              label: "总题数",
              val: overview.total_questions,
              prev: overview.prev_week.total_questions,
              fmt: (n: number) => `${n}`,
            },
            {
              icon: <TrendingUp size={16} />,
              label: "正确率",
              val: overview.accuracy,
              prev: overview.prev_week.accuracy,
              fmt: (n: number) => `${(n * 100).toFixed(0)}%`,
            },
            {
              icon: <CalendarDays size={16} />,
              label: "学习天数",
              val: overview.study_days,
              prev: overview.prev_week.study_days,
              fmt: (n: number) => `${n}天`,
            },
            {
              icon: <Clock size={16} />,
              label: "学习时长",
              val: overview.study_minutes,
              prev: overview.prev_week.study_minutes,
              fmt: (n: number) => {
                const hh = Math.floor(n / 60);
                const mm = Math.round(n % 60);
                return hh > 0 ? `${hh}h${mm}m` : `${mm}m`;
              },
            },
          ].map((c, i) => (
            <Card key={i} className="!p-4">
              <div className="text-[var(--color-accent)] mb-1.5">{c.icon}</div>
              <div className="text-xl md:text-2xl font-semibold text-[var(--color-text)]">
                {c.fmt(c.val)}
              </div>
              <div className="text-[11px] text-[var(--color-text-muted)] mt-0.5">
                {c.label}
              </div>
              {/* 环比变化 */}
              <div
                className="text-[10px] mt-1"
                style={{ color: deltaColor(c.val, c.prev) }}
              >
                {deltaStr(c.val, c.prev, c.fmt)} vs 上期
              </div>
            </Card>
          ))}
        </div>

        {/* ── ② 每日练习趋势图 ── */}
        <Card title={`📈 每日练习趋势 · ${timeRange === "week" ? "7天" : timeRange === "month" ? "30天" : "全部"}`} className="mb-8 !p-5">
          <TrendChart data={daily_trend} />
        </Card>

        {/* ── ③ 知识掌握度 + ④ 错因分布（两栏并排） ── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          {/* 知识掌握度柱状图 */}
          <Card title="🔥 知识掌握度" className="!p-5">
            {mastery_bars.length === 0 ? (
              <p className="text-xs text-[var(--color-text-muted)]">暂无数据，答几道题就出来了</p>
            ) : (
              <div className="space-y-3">
                {mastery_bars.map((mb: MasteryBar) => {
                  const pct = Math.round(mb.p_known * 100);
                  const color =
                    mb.p_known >= 0.8
                      ? "var(--color-success)"
                      : mb.p_known >= 0.5
                      ? "var(--color-warning)"
                      : "var(--color-error)";
                  return (
                    <div key={mb.skill_id}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-[var(--color-text-secondary)] truncate max-w-[140px]">
                          {MASTERY_EMOJI[mb.mastery_level] || ""} {mb.skill_id}
                        </span>
                        <span className="text-xs text-[var(--color-text-muted)]">{pct}%</span>
                      </div>
                      {/* 进度条 */}
                      <div className="w-full h-1.5 bg-[var(--color-surface)]">
                        <div
                          className="h-full transition-all"
                          style={{ width: `${pct}%`, backgroundColor: color }}
                        />
                      </div>
                      <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
                        {mb.correct_count}/{mb.attempt_count}正确 · {mb.mastery_level}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>

          {/* 错因分布 */}
          <Card title="📊 错因分布" className="!p-5">
            {error_distribution.length === 0 ? (
              <p className="text-xs text-[var(--color-text-muted)]">暂无错题，继续保持！</p>
            ) : (
              <div className="space-y-3">
                {error_distribution.map((e: ErrorDist) => {
                  const label = ERROR_LABELS[e.type] || e.type;
                  return (
                    <div key={e.type}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-[var(--color-text-secondary)]">{label}</span>
                        <span className="text-xs text-[var(--color-text-muted)]">
                          {e.count}次 · {(e.pct * 100).toFixed(0)}%
                        </span>
                      </div>
                      {/* 错误占比条 */}
                      <div className="w-full h-1.5 bg-[var(--color-surface)]">
                        <div
                          className="h-full bg-[var(--color-error)] transition-all"
                          style={{ width: `${(e.pct * 100).toFixed(0)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            {error_distribution.length > 0 && (
              <Link
                href="/errors"
                className="inline-block mt-4 text-[11px] text-[var(--color-accent)] hover:underline"
              >
                查看全部错题 →
              </Link>
            )}
          </Card>
        </div>

        {/* ── ⑤ 学习时段热力图 ── */}
        <Card title="⏰ 学习时段" className="mb-8 !p-5">
          <HeatmapGrid data={hourly_heatmap} />
        </Card>

        {/* ── ⑤.5 雷达图（综合能力） ── */}
        <div className="mb-8">
          <RadarChart />
        </div>

        {/* ── ⑥ 遗忘曲线 ── */}
        <RetentionPanel />

        {/* ── ⑦ 建议行动列表 ── */}
        {suggestions.length > 0 && (
          <Card title="🎯 建议行动" className="!p-5">
            <div className="space-y-2">
              {suggestions.map((s: Suggestion, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2 text-sm text-[var(--color-text-secondary)] leading-relaxed"
                >
                  <span className="text-[var(--color-accent)] mt-0.5">•</span>
                  <span>
                    {s.text}
                    {s.link && (
                      <Link
                        href={s.link}
                        className="ml-1 text-[var(--color-accent)] hover:underline text-xs"
                      >
                        {s.action || "去看看"} →
                      </Link>
                    )}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        )}
          </>
        ) : (
          /* ── habits Tab：渲染习惯养成面板 ── */
          <HabitTab data={behaviorData} />
        )}
      </div>
    </div>
  );
}
