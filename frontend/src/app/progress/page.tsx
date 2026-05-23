"use client";
// 客户端组件，启用 React 客户端交互能力

import { useState, useEffect } from "react";
// 导入 React 状态管理与副作用 hooks
import { Loader2, AlertTriangle } from "lucide-react";
// 加载动画与警告图标
import Card from "@/components/ui/Card";
// 自定义卡片 UI 组件

// API 基础地址：优先使用环境变量，否则回退到本地 8000 端口
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Types ──
// 学习进度概览数据，从后端 API /api/progress 获取
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

// 各学科统计：总题数、正确数、耗时、掌握度
interface SubjectStat {
  total: number;
  correct: number;
  total_time: number;
  mastery?: number;
}

// 每日学习趋势数据点：日期、学习时长(小时)、做题数
interface DailyPoint {
  date: string;
  hours: number;
  questions: number;
}

// 错误类型统计：类型名、出现次数、占比百分比
interface ErrorStat {
  error_type: string;
  count: number;
  pct: number;
}

// ── Label helpers ──
// 后端错误类型 key → 前端中文展示文案 的映射表
const ERROR_LABELS: Record<string, string> = {
  conceptual: "概念错误",
  procedural: "程序错误",
  computation: "计算错误",
  reading: "审题错误",
  careless: "粗心",
  transfer: "迁移错误",
  meta: "元认知",
};

// ── 主组件：学习进度页面 ──
export default function ProgressPage() {
  // 各状态定义：概览数据、学科统计、每日趋势、错误分布、加载中、错误信息
  const [summary, setSummary] = useState<ProgressSummary | null>(null);
  const [subjects, setSubjects] = useState<Record<string, SubjectStat>>({});
  const [dailyTrend, setDailyTrend] = useState<DailyPoint[]>([]);
  const [errorDist, setErrorDist] = useState<ErrorStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // ── 组件挂载时并行请求后端数据 ──
  useEffect(() => {
    async function load() {
      setLoading(true);
      setError("");
      try {
        // 并行发起四个 API 请求：概览、学科统计、趋势、错误统计
        const [sumRes, statsRes, trendRes, errRes] = await Promise.all([
          fetch(`${API_BASE}/api/progress/default_user`),
          fetch(`${API_BASE}/api/progress/default_user/stats`),
          fetch(`${API_BASE}/api/practice/stats?time_range=month`),
          fetch(`${API_BASE}/api/practice/errors/stats?user_id=default_user`),
        ]);

        // 解析概览数据
        if (sumRes.ok) {
          const s = await sumRes.json();
          setSummary(s);
        }
        // 解析学科统计与每日趋势
        if (statsRes.ok) {
          const d = await statsRes.json();
          if (d.by_subject) setSubjects(d.by_subject);
          if (d.daily) {
            // 将后端按日期分组的统计数据转换为前端折线图所需格式
            const entries = Object.entries(d.daily) as [string, { total: number; correct: number }][];
            const trend: DailyPoint[] = entries
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([date, v]) => ({
                date: date.slice(5), // 仅保留 MM-DD 部分
                hours: 0,
                questions: v.total || 0,
              }));
            setDailyTrend(trend);
          }
        }
        // 解析趋势接口中的错误分布，计算百分比
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
  // 从概览数据中推导出展示用数值
  const totalQuestions = summary?.total_questions || 0;
  const accuracy = summary ? Math.round(summary.accuracy_rate * 100) : 0;
  const studyHours = summary ? (summary.study_minutes / 60).toFixed(1) : "0";
  const masteredCount = summary?.mastered_skills?.length || 0;
  // 每日柱状图最高高度基准
  const maxHours = Math.max(...dailyTrend.map((d) => d.hours), 1);

  // 构建错误分布饼图的 conic-gradient 渐变字符串
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
  // 数据加载中：显示旋转加载图标
  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-[var(--color-accent)]" />
      </main>
    );
  }

  // ── Empty state ──
  // 后端返回空数据但无错误：展示引导文本
  if (!summary && !error) {
    return (
      <main className="min-h-screen bg-[var(--color-bg)] flex items-center justify-center">
        <p className="text-[var(--color-text-muted)] text-sm">暂无学习数据，开始练习吧 🚀</p>
      </main>
    );
  }

  // ── 主渲染：页面布局与所有数据卡片 ──
  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-5xl mx-auto px-6 py-10 sm:py-16">
        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-[var(--color-text)] mb-10">
          学情
        </h1>

        {/* 错误提示横幅 */}
        {error && (
          <div className="mb-8 px-4 py-3 border border-[var(--color-border)] text-sm text-[var(--color-text-muted)] flex items-center gap-2">
            <AlertTriangle size={15} /> {error}
          </div>
        )}

        {/* Summary stats */}
        {/* 概览统计卡片：总做题数、正确率、学习时长、已掌握技能 */}
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
          {/* 知识掌握度卡片：按学科展示进度条 */}
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
                      {/* 进度条：颜色根据掌握度等级动态变化 */}
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
          {/* 学习趋势柱状图：每日做题量分布 */}
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
          {/* 学习建议卡片：基于薄弱技能生成推荐 */}
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
          {/* 错题分析卡片：饼图 + 分类列表展示错误类型分布 */}
          <Card title="错题分析">
            {errorDist.length === 0 ? (
              <p className="text-sm text-[var(--color-text-muted)] py-8 text-center">
                暂无错题，继续保持 💪
              </p>
            ) : (
              <div className="flex items-center gap-8">
                {/* 饼图：用 conic-gradient CSS 模拟 */}
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
        {/* 最近活动列表：最近 10 条练习记录，绿色 ✔ 表示正确，红色 ✗ 表示错误 */}
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
