"use client";

import { useEffect, useState } from "react";
import { api, hasRole } from "@/lib/api";
import { useAuthGuard } from "@/lib/use-auth-guard";
import type { AnalyticsKpi, AnalyticsActivity, AnalyticsTrend, TopWrongQuestion, MasteryBucket, SubjectDistItem, DifficultyBucket, EngagementItem } from "@/lib/types";

const COLORS = ["#2563eb", "#059669", "#7c3aed", "#dc2626", "#ca8a04", "#0891b2"];

export default function AnalyticsPage() {
  const { ready, user } = useAuthGuard();
  const [kpi, setKpi] = useState<AnalyticsKpi | null>(null);
  const [trend, setTrend] = useState<AnalyticsTrend | null>(null);
  const [wrong, setWrong] = useState<{ items: TopWrongQuestion[] } | null>(null);
  const [mastery, setMastery] = useState<{ buckets: MasteryBucket[] } | null>(null);
  const [activity, setActivity] = useState<AnalyticsActivity | null>(null);
  const [subjectDist, setSubjectDist] = useState<{ items: SubjectDistItem[] } | null>(null);
  const [difficulty, setDifficulty] = useState<{ buckets: DifficultyBucket[] } | null>(null);
  const [engagement, setEngagement] = useState<{ items: EngagementItem[] } | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!ready || !user || !hasRole(user.role, "analyst")) return;
    // Promise.allSettled：任一查询失败不影响其他区段渲染，并把错误显式标到该区段
    const settled = Promise.allSettled([
      api.get<AnalyticsKpi>("/analytics/kpi"),
      api.get<AnalyticsTrend>("/analytics/practice-trend?days=14"),
      api.get<{ items: TopWrongQuestion[] }>("/analytics/top-wrong-questions?limit=10"),
      api.get<{ buckets: MasteryBucket[] }>("/analytics/mastery-distribution"),
      api.get<AnalyticsActivity>("/analytics/user-activity"),
      api.get<{ items: SubjectDistItem[] }>("/analytics/subject-distribution"),
      api.get<{ buckets: DifficultyBucket[] }>("/analytics/difficulty-distribution"),
      api.get<{ items: EngagementItem[] }>("/analytics/user-engagement?limit=10"),
    ]);
    settled.then(([k, t, w, m, a, sd, d, e]) => {
      const failed: string[] = [];
      if (k.status === "fulfilled") setKpi(k.value); else failed.push(`KPI: ${k.reason?.message}`);
      if (t.status === "fulfilled") setTrend(t.value); else failed.push(`趋势: ${t.reason?.message}`);
      if (w.status === "fulfilled") setWrong(w.value); else failed.push(`错题: ${w.reason?.message}`);
      if (m.status === "fulfilled") setMastery(m.value); else failed.push(`掌握度: ${m.reason?.message}`);
      if (a.status === "fulfilled") setActivity(a.value); else failed.push(`活跃度: ${a.reason?.message}`);
      if (sd.status === "fulfilled") setSubjectDist(sd.value); else failed.push(`学科: ${sd.reason?.message}`);
      if (d.status === "fulfilled") setDifficulty(d.value); else failed.push(`难度: ${d.reason?.message}`);
      if (e.status === "fulfilled") setEngagement(e.value); else failed.push(`参与度: ${e.reason?.message}`);
      if (failed.length > 0) setErr(failed.join(" | "));
    });
  }, [ready, user]);

  if (!ready) return <div className="py-20 text-center text-ink-muted">加载中…</div>;
  if (!user || !hasRole(user.role, "analyst")) return null;

  function maxCount(series: any[], key: string): number {
    return Math.max(...series.map((s: any) => Number(s[key] || 0)), 1);
  }

  const kpiLabelCls = "text-fine text-ink-muted uppercase tracking-wide font-medium mb-2";
  const kpiValueCls = "text-2xl font-bold text-ink-primary";
  const kpiSubCls = "text-caption text-ink-muted";
  const kpiCardCls = "bg-surface border border-divider rounded-lg p-4";
  const cardCls = "bg-surface border border-divider rounded-lg p-5";
  const thClass = "px-3.5 py-2.5 text-left border-b border-divider text-fine text-ink-muted font-semibold uppercase tracking-wide bg-page sticky top-0";
  const tdClass = "px-3.5 py-2.5 border-b border-divider text-caption text-ink-secondary";
  const headingCls = "text-heading mb-4";

  return (
    <div>
      <h1 className="text-heading mb-5">BI 分析</h1>
      {err && <div className="bg-danger/10 border border-danger/20 text-danger rounded-lg p-4 mb-4">{err}</div>}

      {/* KPI */}
      {kpi && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-5">
          <div className={kpiCardCls}><div className={kpiLabelCls}>用户总数 / 活跃</div><div className={kpiValueCls}>{kpi.users_total} / {kpi.users_active}</div></div>
          <div className={kpiCardCls}><div className={kpiLabelCls}>练习正确率</div><div className={kpiValueCls}>{(kpi.accuracy * 100).toFixed(1)}<span className={kpiSubCls}>%</span></div></div>
          <div className={kpiCardCls}><div className={kpiLabelCls}>练习总量</div><div className={kpiValueCls}>{kpi.attempts_total}<span className={kpiSubCls}>次</span></div></div>
          <div className={kpiCardCls}><div className={kpiLabelCls}>练习会话</div><div className={kpiValueCls}>{kpi.sessions_total}</div></div>
          <div className={kpiCardCls}><div className={kpiLabelCls}>认知节点</div><div className={kpiValueCls}>{kpi.atom_nodes}</div></div>
          <div className={kpiCardCls}><div className={kpiLabelCls}>有效题目</div><div className={kpiValueCls}>{kpi.questions_active}<span className={kpiSubCls}>/{kpi.questions_total}</span></div></div>
        </div>
      )}

      {/* Activity + Mastery side by side */}
      {activity && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div className={cardCls}>
            <h2 className={headingCls}>用户活跃度</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className={kpiCardCls}><div className={kpiLabelCls}>DAU (1d)</div><div className={kpiValueCls}>{activity.dau}</div></div>
              <div className={kpiCardCls}><div className={kpiLabelCls}>WAU (7d)</div><div className={kpiValueCls}>{activity.wau}</div></div>
              <div className={kpiCardCls}><div className={kpiLabelCls}>MAU (30d)</div><div className={kpiValueCls}>{activity.mau}</div></div>
              <div className={kpiCardCls}><div className={kpiLabelCls}>总用户</div><div className={kpiValueCls}>{activity.total}</div></div>
            </div>
          </div>

          {mastery && (
            <div className={cardCls}>
              <h2 className={headingCls}>掌握度分布</h2>
              {mastery.buckets.length === 0 ? <p className="text-ink-muted text-center py-10 text-caption">无数据</p> : (
                <div>
                  {mastery.buckets.map((b, i) => {
                    const total = mastery.buckets.reduce((s: number, x) => s + (x.cnt || 0), 0);
                    const pct = total > 0 ? Math.round((b.cnt || 0) / total * 100) : 0;
                    return (
                      <div key={i} className="flex items-center gap-3 mb-2">
                        <div className="w-20 text-fine text-ink-muted shrink-0">{b.bucket}</div>
                        <div className="flex-1 bg-input rounded-full h-5 overflow-hidden">
                          <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: COLORS[i % COLORS.length] }} />
                        </div>
                        <div className="w-10 text-right text-fine text-ink-secondary">{b.cnt}</div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Practice Trend + Difficulty */}
      {trend && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          {trend.series.length > 0 && (
            <div className={cardCls}>
              <h2 className={headingCls}>练习趋势（14天）</h2>
              <div style={{ overflowX: "auto" }}>
                <div className="flex items-end gap-0.5" style={{ width: Math.max(trend.series.length * 28, 200) }}>
                  {trend.series.map((s, i) => {
                    const h = (s.attempts || 0) / maxCount(trend.series, "attempts") * 100;
                    return (
                      <div key={i} className="flex-1 flex flex-col items-center">
                        <div className="flex-1 w-full flex flex-col justify-end">
                          <div className="rounded-sm" style={{ height: `${h}%`, background: s.accuracy > 0.7 ? "#059669" : s.accuracy > 0.4 ? "#ca8a04" : "#dc2626" }} title={`正确率: ${(s.accuracy * 100).toFixed(0)}%`} />
                        </div>
                        <div className="text-[10px] text-ink-muted mt-1">{s.day?.slice(5)}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {difficulty && (
            <div className={cardCls}>
              <h2 className={headingCls}>难度分布</h2>
              {difficulty.buckets.length === 0 ? <p className="text-ink-muted text-center py-10 text-caption">无数据</p> : (
                <div>
                  {difficulty.buckets.map((b, i) => {
                    const total = difficulty.buckets.reduce((s: number, x) => s + (x.cnt || 0), 0);
                    const pct = total > 0 ? Math.round((b.cnt || 0) / total * 100) : 0;
                    return (
                      <div key={i} className="flex items-center gap-3 mb-2">
                        <div className="w-20 text-fine text-ink-muted shrink-0">{b.bucket}</div>
                        <div className="flex-1 bg-input rounded-full h-5 overflow-hidden">
                          <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: ["#059669", "#ca8a04", "#dc2626"][i] || "#2563eb" }} />
                        </div>
                        <div className="w-20 text-right text-fine text-ink-secondary">{b.cnt} ({pct}%)</div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Subject Distribution + Wrong Questions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        {subjectDist && (
          <div className={cardCls}>
            <h2 className={headingCls}>学科分布</h2>
            {subjectDist.items.length === 0 ? <p className="text-ink-muted text-center py-10 text-caption">无数据</p> : (
              <table className="w-full border-collapse">
                <thead><tr><th className={thClass}>学科</th><th className={thClass}>题目数</th><th className={thClass}>知识节点</th></tr></thead>
                <tbody>
                  {subjectDist.items.map((s, i) => (
                    <tr key={i}><td className={`${tdClass} font-mono text-fine`}>{s.subject}</td><td className={tdClass}>{s.questions}</td><td className={tdClass}>{s.nodes || 0}</td></tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {wrong && (
          <div className={cardCls}>
            <h2 className={headingCls}>错题 TOP {wrong.items.length}</h2>
            {wrong.items.length === 0 ? <p className="text-ink-muted text-center py-10 text-caption">无数据</p> : (
              <table className="w-full border-collapse">
                <thead><tr><th className={thClass}>题干</th><th className={thClass}>难度</th><th className={thClass}>错率</th></tr></thead>
                <tbody>
                  {wrong.items.map((w) => {
                    const rate = w.total_attempts > 0 ? (w.wrong_count / w.total_attempts * 100).toFixed(0) : "0";
                    return (
                      <tr key={w.id}>
                        <td className={tdClass} style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{w.stem?.slice(0, 40) || "—"}</td>
                        <td className={tdClass}>{w.difficulty}</td>
                        <td className={tdClass} style={{ color: Number(rate) > 50 ? "#fca5a5" : "#cbd5e1" }}>{rate}% ({w.wrong_count}/{w.total_attempts})</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {/* Engagement */}
      {engagement && (
        <div className={cardCls}>
          <h2 className={headingCls}>用户参与度排名（TOP {engagement.items.length}）</h2>
          {engagement.items.length === 0 ? <p className="text-ink-muted text-center py-10 text-caption">无数据</p> : (
            <table className="w-full border-collapse">
              <thead><tr><th className={thClass}>排名</th><th className={thClass}>用户</th><th className={thClass}>总练习</th><th className={thClass}>正确</th><th className={thClass}>活跃天数</th></tr></thead>
              <tbody>
                {engagement.items.map((u, i) => (
                  <tr key={i}>
                    <td className={tdClass}>{i + 1}</td>
                    <td className={tdClass}>{u.username || u.user_id}</td>
                    <td className={tdClass}>{u.total_attempts}</td>
                    <td className={tdClass}><span style={{ color: "#6ee7b7" }}>{u.correct_attempts}</span></td>
                    <td className={tdClass}>{u.active_days}<span className="text-ink-muted">天</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
