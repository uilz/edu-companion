"use client";

import { useState, useEffect } from "react";
import { Loader2, AlertTriangle } from "lucide-react";
import Card from "@/components/ui/Card";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Types ──
interface ProgressSummary {
  user_id: string;
  total_questions: number;
  correct_answers: number;
  accuracy_rate: number;
  study_minutes: number;
  mastered_skills: string[];
  struggling_skills: string[];
  recent_activity: { skill_id: string; timestamp: string; is_correct: boolean }[];
  recommendations: string[];
}

interface SubjectStat {
  total: number;
  correct: number;
  total_time: number;
  mastery?: number;
}

interface DailyPoint {
  date: string;
  hours: number;
  questions: number;
}

interface ErrorStat {
  error_type: string;
  count: number;
  pct: number;
}

// ── Label helpers ──
const ERROR_LABELS: Record<string, string> = {
  conceptual: "概念错误",
  procedural: "程序错误",
  computation: "计算错误",
  reading: "审题错误",
  careless: "粗心",
  transfer: "迁移错误",
  meta: "元认知",
};

export default function ProgressPage() {
  const [summary, setSummary] = useState<ProgressSummary | null>(null);
  const [subjects, setSubjects] = useState<Record<string, SubjectStat>>({});
  const [dailyTrend, setDailyTrend] = useState<DailyPoint[]>([]);
  const [errorDist, setErrorDist] = useState<ErrorStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError("");
      try {
        const [sumRes, statsRes, trendRes, errRes] = await Promise.all([
          fetch(`${API_BASE}/api/progress/default_user`),
          fetch(`${API_BASE}/api/progress/default_user/stats`),
          fetch(`${API_BASE}/api/practice/stats?time_range=month`),
          fetch(`${API_BASE}/api/practice/errors/stats?user_id=default_user`),
        ]);

        if (sumRes.ok) {
          const s = await sumRes.json();
          setSummary(s);
        }
        if (statsRes.ok) {
          const d = await statsRes.json();
          if (d.subject_stats) setSubjects(d.subject_stats);
          if (d.daily_activity) {
            const trend: DailyPoint[] = d.daily_activity.map((a: any) => ({
              date: (a.date || "").slice(5), // MM-DD
              hours: (a.total_time || 0) / 60,
              questions: a.total || 0,
            }));
            setDailyTrend(trend);
          }
        }
        if (trendRes.ok) {
          const t = await trendRes.json();
          if (t.error_distribution) {
            const total = t.error_distribution.reduce((s: number, e: ErrorStat) => s + e.count, 0);
            setErrorDist(
              t.error_distribution.map((e: ErrorStat) => ({
                ...e,
                pct: total > 0 ? Math.round((e.count / total) * 100) : 0,
              }))
            );
          }
        }
      } catch (e) {
        setError("加载失败，请检查后端服务");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // ── Derived values ──
  const totalQuestions = summary?.total_questions || 0;
  const accuracy = summary ? Math.round(summary.accuracy_rate * 100) : 0;
  const studyHours = summary ? (summary.study_minutes / 60).toFixed(1) : "0";
  const masteredCount = summary?.mastered_skills?.length || 0;
  const maxHours = Math.max(...dailyTrend.map((d) => d.hours), 1);

  // Pie gradient for error dist
  const totalErr = errorDist.reduce((s, c) => s + c.count, 0);
  let cumPct = 0;
  const errorColors = ["#0066FF", "#737373", "#f59e0b", "#ef4444", "#a855f7", "#ec4899"];
  const gradientStops = errorDist.map((c, i) => {
    const start = cumPct;
    cumPct += totalErr > 0 ? (c.count / totalErr) * 100 : 0;
    return `${errorColors[i % errorColors.length]} ${start}% ${cumPct}%`;
  });
  const pieGradient = gradientStops.length > 0
    ? `conic-gradient(${gradientStops.join(", ")})`
    : "var(--color-surface)";

  // ── Loading ──
  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-[var(--color-accent)]" />
      </main>
    );
  }

  // ── Empty state ──
  if (!summary && !error) {
    return (
      <main className="min-h-screen bg-[var(--color-bg)] flex items-center justify-center">
        <p className="text-[var(--color-text-muted)] text-sm">暂无学习数据，开始练习吧 🚀</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-5xl mx-auto px-6 py-10 sm:py-16">
        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-[var(--color-text)] mb-10">
          学情
        </h1>

        {error && (
          <div className="mb-8 px-4 py-3 border border-[var(--color-border)] text-sm text-[var(--color-text-muted)] flex items-center gap-2">
            <AlertTriangle size={15} /> {error}
          </div>
        )}

        {/* Summary stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-12">
          {[
            { label: "总做题数", value: `${totalQuestions}` },
            { label: "正确率", value: `${accuracy}%` },
            { label: "学习时长", value: `${studyHours}h` },
            { label: "已掌握技能", value: `${masteredCount} 个` },
          ].map((s) => (
            <div key={s.label} className="border border-[var(--color-border)] bg-[var(--color-card)] p-5">
              <div className="text-2xl font-bold text-[var(--color-text)]">{s.value}</div>
              <div className="text-xs text-[var(--color-text-muted)] mt-1">{s.label}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* Knowledge mastery */}
          <Card title="知识掌握度">
            {Object.keys(subjects).length === 0 ? (
              <p className="text-sm text-[var(--color-text-muted)] py-8 text-center">
                暂无学科数据
              </p>
            ) : (
              <div className="space-y-4">
                {Object.entries(subjects).map(([name, stat]) => {
                  const mastery = stat.mastery ?? (stat.total > 0 ? Math.round((stat.correct / stat.total) * 100) : 0);
                  return (
                    <div key={name}>
                      <div className="flex items-center justify-between text-sm mb-1.5">
                        <span className="text-[var(--color-text)]">{name}</span>
                        <span className="text-[var(--color-text-muted)] text-xs">
                          {stat.correct}/{stat.total} · {mastery}%
                        </span>
                      </div>
                      <div className="w-full bg-[var(--color-surface)] h-2">
                        <div
                          className="h-full transition-all duration-700"
                          style={{
                            width: `${Math.min(mastery, 100)}%`,
                            backgroundColor:
                              mastery >= 80 ? "var(--color-success)"
                                : mastery >= 60 ? "var(--color-accent)"
                                : "var(--color-warning)",
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>

          {/* Study trend */}
          <Card title="学习趋势">
            {dailyTrend.length === 0 ? (
              <p className="text-sm text-[var(--color-text-muted)] py-8 text-center">
                暂无趋势数据
              </p>
            ) : (
              <div className="flex items-end gap-1 h-40">
                {dailyTrend.map((d, i) => (
                  <div key={`${d.date}-${i}`} className="flex-1 flex flex-col items-center gap-1">
                    <div
                      className="w-full bg-[var(--color-accent)]/80 hover:bg-[var(--color-accent)] transition-colors cursor-pointer group relative"
                      style={{ height: `${Math.max((d.hours / maxHours) * 100, 3)}%` }}
                    >
                      <div className="absolute -top-6 left-1/2 -translate-x-1/2 text-[10px] text-[var(--color-text-muted)] opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                        {d.hours.toFixed(1)}h / {d.questions}题
                      </div>
                    </div>
                    <span className="text-[9px] text-[var(--color-text-muted)]">{d.date}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Recommendations */}
          <Card title="💡 学习建议">
            {summary?.recommendations && summary.recommendations.length > 0 ? (
              <div className="space-y-2">
                {summary.recommendations.map((r, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm text-[var(--color-text-secondary)] leading-relaxed">
                    <span className="text-[var(--color-accent)] mt-0.5 flex-shrink-0">•</span>
                    <span>{r}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[var(--color-text-muted)] py-4 text-center">
                暂无建议数据，多练习几道题吧 ✨
              </p>
            )}
          </Card>

          {/* Error analysis */}
          <Card title="错题分析">
            {errorDist.length === 0 ? (
              <p className="text-sm text-[var(--color-text-muted)] py-8 text-center">
                暂无错题，继续保持 💪
              </p>
            ) : (
              <div className="flex items-center gap-8">
                <div
                  className="w-32 h-32 rounded-full flex-shrink-0"
                  style={{ background: pieGradient }}
                />
                <div className="space-y-3 flex-1">
                  {errorDist.map((cat, i) => (
                    <div key={cat.error_type} className="flex items-center gap-3">
                      <div
                        className="w-3 h-3 flex-shrink-0"
                        style={{ backgroundColor: errorColors[i % errorColors.length] }}
                      />
                      <span className="text-sm text-[var(--color-text-secondary)]">
                        {ERROR_LABELS[cat.error_type] || cat.error_type}
                      </span>
                      <span className="text-sm text-[var(--color-text)] font-medium ml-auto">
                        {cat.pct}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>
        </div>

        {/* Recent activity */}
        {summary?.recent_activity && summary.recent_activity.length > 0 && (
          <Card title="📋 最近活动" className="mt-8">
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {summary.recent_activity.slice(0, 10).map((act, i) => (
                <div key={i} className="flex items-center justify-between py-1 text-xs text-[var(--color-text-secondary)] border-b border-[var(--color-surface)] last:border-0">
                  <span>{act.skill_id}</span>
                  <span className={act.is_correct ? "text-[var(--color-success)]" : "text-[var(--color-error)]"}>
                    {act.is_correct ? "✓" : "✗"}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </main>
  );
}
