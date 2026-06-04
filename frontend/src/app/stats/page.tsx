"use client";

import { useState, useEffect } from "react";
import {
  BarChart3, Target, Clock, TrendingUp, Loader2,
  Brain, ChevronRight, RotateCcw, Zap, Calendar,
} from "lucide-react";
import Card from "@/components/ui/Card";
import {
  getOverview, getDailyTrend, getSessionHistory,
  getWeakSkills,
  type V7Overview, type V7DailyPoint, type V7SessionListItem,
} from "@/lib/practice-api";

export default function StatsPage() {
  const [overview, setOverview] = useState<V7Overview | null>(null);
  const [trend, setTrend] = useState<V7DailyPoint[]>([]);
  const [sessions, setSessions] = useState<V7SessionListItem[]>([]);
  const [weakSkills, setWeakSkills] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getOverview(),
      getDailyTrend(30),
      getSessionHistory(10),
      getWeakSkills(),
    ])
      .then(([ov, tr, ses, wk]) => {
        setOverview(ov);
        setTrend(tr);
        setSessions(ses);
        setWeakSkills(wk);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <main className="min-h-screen bg-[var(--color-bg)]">
        <div className="flex items-center justify-center py-20">
          <Loader2 className="animate-spin text-[var(--color-accent)]" size={24} />
        </div>
      </main>
    );
  }

  const hours = overview?.study_minutes ? Math.floor(overview.study_minutes / 60) : 0;
  const minutes = overview?.study_minutes ? Math.round(overview.study_minutes % 60) : 0;
  const maxCount = Math.max(...trend.map((d) => d.count), 1);

  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        <h1 className="text-2xl font-semibold text-[var(--color-text)] mb-6 tracking-tight">
          学习统计
        </h1>

        {/* 概览卡片 */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
          {[
            {
              icon: <BarChart3 size={20} />, label: "总答题",
              value: `${overview?.total_questions ?? 0}`,
              sub: `正确 ${overview?.total_correct ?? 0} · 错误 ${overview?.total_wrong ?? 0}`,
            },
            {
              icon: <TrendingUp size={20} />, label: "正确率",
              value: `${overview?.accuracy ?? "?"}%`,
              sub: (overview?.accuracy ?? 0) >= 80 ? "优秀 🎉"
                : (overview?.accuracy ?? 0) >= 60 ? "良好 👍" : "需努力 💪",
            },
            {
              icon: <Clock size={20} />, label: "学习时长",
              value: hours > 0 ? `${hours}h${minutes}m` : `${minutes}m`,
              sub: `${overview?.total_sessions ?? 0} 次练习`,
            },
            {
              icon: <Brain size={20} />, label: "知识掌握",
              value: `${overview?.mastered_count ?? 0}`,
              sub: `已掌握 · ${overview?.weak_count ?? 0} 薄弱`,
            },
          ].map((card, i) => (
            <Card key={i}>
              <div className="text-[var(--color-accent)] mb-2">{card.icon}</div>
              <div className="text-2xl font-semibold text-[var(--color-text)]">{card.value}</div>
              <div className="text-xs text-[var(--color-text-muted)]">{card.label} · {card.sub}</div>
            </Card>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          {/* 每日趋势图 */}
          <div>
            <h2 className="text-base font-semibold text-[var(--color-text)] mb-3 flex items-center gap-2">
              <Calendar size={14} className="text-[var(--color-accent)]" />
              近 30 天练习趋势
            </h2>
            <div className="bg-[var(--color-surface)] rounded-xl p-4 border border-[var(--color-border)]/60">
              {/* 柱状图 */}
              <div className="flex items-end gap-[3px] h-24 mb-2">
                {trend.map((d) => {
                  const height = maxCount > 0 ? (d.count / maxCount) * 100 : 0;
                  return (
                    <div key={d.date} className="flex-1 flex flex-col items-center justify-end h-full group relative">
                      <div
                        className="w-full rounded-t-sm transition-all hover:opacity-80 cursor-pointer"
                        style={{
                          height: `${Math.max(height, d.count > 0 ? 4 : 0)}%`,
                          backgroundColor: d.correct > d.wrong
                            ? "var(--color-success)"
                            : d.wrong > 0
                              ? "var(--color-error)"
                              : "var(--color-border)",
                          opacity: d.count > 0 ? 0.8 : 0.2,
                        }}
                        title={`${d.date}: ${d.count}题 (正确${d.correct}/错误${d.wrong})`}
                      />
                      {/* Tooltip on hover */}
                      {d.count > 0 && (
                        <div className="absolute bottom-full mb-1 hidden group-hover:block z-10">
                          <div className="bg-[var(--color-text)] text-[var(--color-bg)] text-[9px] px-1.5 py-0.5 rounded whitespace-nowrap">
                            {d.date.slice(5)}: {d.count}题
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              <div className="flex items-center justify-between text-[9px] text-[var(--color-text-muted)]">
                <span>{trend[0]?.date?.slice(5) ?? ""}</span>
                <span>{trend[Math.floor(trend.length / 2)]?.date?.slice(5) ?? ""}</span>
                <span>{trend[trend.length - 1]?.date?.slice(5) ?? ""}</span>
              </div>
              <div className="flex items-center gap-3 mt-2 text-[9px] text-[var(--color-text-muted)]">
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-[var(--color-success)]" />正确</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-[var(--color-error)]" />错误</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-[var(--color-border)]" />无练习</span>
              </div>
            </div>
          </div>

          {/* 待复习 & 薄弱 */}
          <div>
            <h2 className="text-base font-semibold text-[var(--color-text)] mb-3 flex items-center gap-2">
              <RotateCcw size={14} className="text-amber-500" />
              待复习
            </h2>
            {overview && overview.due_review_count > 0 ? (
              <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 mb-4">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-2xl font-bold text-amber-500">{overview.due_review_count}</span>
                    <span className="text-sm text-amber-500/80 ml-1">题到期</span>
                  </div>
                  <Zap size={20} className="text-amber-500" />
                </div>
                <p className="text-[11px] text-[var(--color-text-muted)] mt-1">
                  今日已完成 {overview.today_questions} 题
                </p>
              </div>
            ) : (
              <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4 mb-4">
                <div className="flex items-center gap-2">
                  <Target size={16} className="text-green-500" />
                  <span className="text-sm text-green-600">所有题目已复习！</span>
                </div>
                <p className="text-[11px] text-[var(--color-text-muted)] mt-1">
                  今日已完成 {overview?.today_questions ?? 0} 题
                </p>
              </div>
            )}

            {/* 薄弱知识点 */}
            <h2 className="text-base font-semibold text-[var(--color-text)] mt-4 mb-3 flex items-center gap-2">
              <Brain size={14} className="text-red-500" />
              薄弱知识点
            </h2>
            {weakSkills.length > 0 ? (
              <div className="space-y-2">
                {weakSkills.slice(0, 5).map((sk) => (
                  <div key={sk.skill_id} className="flex items-center justify-between p-2.5 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]/60">
                    <div className="flex-1 min-w-0 mr-3">
                      <p className="text-sm text-[var(--color-text)] truncate">{sk.label}</p>
                      <p className="text-[10px] text-[var(--color-text-muted)]">
                        {sk.attempts}次练习 · {sk.trend === "ascending" ? "📈" : sk.trend === "descending" ? "📉" : "➡️"}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-[var(--color-border)] rounded-full overflow-hidden">
                        <div className="h-full bg-red-500 rounded-full transition-all"
                          style={{ width: `${sk.mastery * 100}%` }} />
                      </div>
                      <span className="text-[11px] text-[var(--color-text-muted)] w-8 text-right">
                        {Math.round(sk.mastery * 100)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-4 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]/60 text-center">
                <p className="text-xs text-[var(--color-text-muted)]">暂无薄弱点数据 · 多练习就会看到进步！</p>
              </div>
            )}
          </div>
        </div>

        {/* 最近练习 */}
        <div className="mb-8">
          <h2 className="text-base font-semibold text-[var(--color-text)] mb-3 flex items-center gap-2">
            <BarChart3 size={14} className="text-[var(--color-accent)]" />
            最近练习
          </h2>
          {sessions.length > 0 ? (
            <div className="space-y-2">
              {sessions.map((s) => {
                const scoreColor = s.score != null
                  ? s.score >= 80 ? "text-green-500"
                    : s.score >= 60 ? "text-yellow-500"
                    : "text-red-500"
                  : "text-[var(--color-text-muted)]";
                const modeLabel = s.mode === "adaptive" ? "自适应"
                  : s.mode === "review" ? "复习" : s.mode === "challenge" ? "挑战" : s.mode;
                return (
                  <div key={s.session_id}
                    className="flex items-center justify-between p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]/60">
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold ${
                        s.score != null && s.score >= 80 ? "bg-green-500/10 text-green-500"
                          : s.score != null && s.score >= 60 ? "bg-yellow-500/10 text-yellow-500"
                          : "bg-[var(--color-border)]/50 text-[var(--color-text-muted)]"
                      }`}>
                        {s.score != null ? Math.round(s.score) : "?"}
                      </div>
                      <div>
                        <p className="text-sm text-[var(--color-text)] font-medium">{modeLabel}</p>
                        <p className="text-[10px] text-[var(--color-text-muted)]">
                          {s.correct_count}/{s.total_count} 正确
                          {s.duration_seconds != null && ` · ${Math.floor(s.duration_seconds / 60)}:${String(s.duration_seconds % 60).padStart(2, "0")}`}
                        </p>
                      </div>
                    </div>
                    <span className="text-[10px] text-[var(--color-text-muted)]">
                      {s.created_at ? s.created_at.slice(0, 10) : ""}
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-6 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]/60 text-center">
              <Brain size={24} className="text-[var(--color-text-muted)] mx-auto mb-2" />
              <p className="text-sm text-[var(--color-text-muted)]">还没有练习记录</p>
              <p className="text-xs text-[var(--color-text-muted)] mt-1">进入知识点图谱开始首次练习</p>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
