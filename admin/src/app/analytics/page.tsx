"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getCurrentUser, hasRole, type AdminUser } from "@/lib/api";

interface Kpi { users_total: number; users_active: number; attempts_total: number; attempts_correct: number; accuracy: number; sessions_total: number; atom_nodes: number; questions_total: number; questions_active: number; }
interface ActivityResp { dau: number; wau: number; mau: number; total: number; }
interface TrendResp { series: { day: string; attempts: number; correct: number; accuracy: number }[]; }

const COLORS = ["#2563eb", "#059669", "#7c3aed", "#dc2626", "#ca8a04", "#0891b2"];

export default function AnalyticsPage() {
  const router = useRouter();
  const [me, setMe] = useState<AdminUser | null>(null);
  const [kpi, setKpi] = useState<Kpi | null>(null);
  const [trend, setTrend] = useState<TrendResp | null>(null);
  const [wrong, setWrong] = useState<{ items: any[] } | null>(null);
  const [mastery, setMastery] = useState<{ buckets: any[] } | null>(null);
  const [activity, setActivity] = useState<ActivityResp | null>(null);
  const [subjectDist, setSubjectDist] = useState<{ items: any[] } | null>(null);
  const [difficulty, setDifficulty] = useState<{ buckets: any[] } | null>(null);
  const [engagement, setEngagement] = useState<{ items: any[] } | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    const u = getCurrentUser();
    if (!u) { router.replace("/login"); return; }
    if (!hasRole(u.role, "analyst")) { router.replace("/"); return; }
    setMe(u);
  }, [router]);

  useEffect(() => {
    if (!me) return;
    Promise.all([
      api.get<Kpi>("/analytics/kpi"),
      api.get<TrendResp>("/analytics/practice-trend?days=14"),
      api.get<{ items: any[] }>("/analytics/top-wrong-questions?limit=10"),
      api.get<{ buckets: any[] }>("/analytics/mastery-distribution"),
      api.get<ActivityResp>("/analytics/user-activity"),
      api.get<{ items: any[] }>("/analytics/subject-distribution"),
      api.get<{ buckets: any[] }>("/analytics/difficulty-distribution"),
      api.get<{ items: any[] }>("/analytics/user-engagement?limit=10"),
    ]).then(([k, t, w, m, a, sd, d, e]) => {
      setKpi(k); setTrend(t); setWrong(w); setMastery(m);
      setActivity(a); setSubjectDist(sd); setDifficulty(d); setEngagement(e);
    }).catch((e) => setErr(e.message));
  }, [me]);

  function maxCount(series: any[], key: string): number {
    return Math.max(...series.map((s: any) => Number(s[key] || 0)), 1);
  }

  return (
    <div className="page">
      <h1>BI 分析</h1>
      {err && <div className="card card-error">{err}</div>}

      {/* KPI */}
      {kpi && (
        <div className="kpi-grid">
          <div className="kpi"><div className="label">用户总数 / 活跃</div><div className="value">{kpi.users_total} / {kpi.users_active}</div></div>
          <div className="kpi"><div className="label">练习正确率</div><div className="value">{(kpi.accuracy * 100).toFixed(1)}<span className="unit">%</span></div></div>
          <div className="kpi"><div className="label">练习总量</div><div className="value">{kpi.attempts_total}<span className="unit">次</span></div></div>
          <div className="kpi"><div className="label">练习会话</div><div className="value">{kpi.sessions_total}</div></div>
          <div className="kpi"><div className="label">认知节点</div><div className="value">{kpi.atom_nodes}</div></div>
          <div className="kpi"><div className="label">有效题目</div><div className="value">{kpi.questions_active}<span className="unit">/{kpi.questions_total}</span></div></div>
        </div>
      )}

      {/* Activity + Mastery side by side */}
      {activity && (
        <div className="grid-2">
          <div className="card">
            <h2>用户活跃度</h2>
            <div className="kpi-grid">
              <div className="kpi kpi-sm"><div className="label">DAU (1d)</div><div className="value">{activity.dau}</div></div>
              <div className="kpi kpi-sm"><div className="label">WAU (7d)</div><div className="value">{activity.wau}</div></div>
              <div className="kpi kpi-sm"><div className="label">MAU (30d)</div><div className="value">{activity.mau}</div></div>
              <div className="kpi kpi-sm"><div className="label">总用户</div><div className="value">{activity.total}</div></div>
            </div>
          </div>

          {mastery && (
            <div className="card">
              <h2>掌握度分布</h2>
              {mastery.buckets.length === 0 ? <p className="empty">无数据</p> : (
                <div>
                  {mastery.buckets.map((b: any, i: number) => {
                    const total = mastery.buckets.reduce((s: number, x: any) => s + (x.cnt || 0), 0);
                    const pct = total > 0 ? Math.round((b.cnt || 0) / total * 100) : 0;
                    return (
                      <div className="chart-row" key={i}>
                        <div className="chart-label">{b.bucket}</div>
                        <div className="chart-fill">
                          <div className="chart-fill-inner" style={{ width: `${pct}%`, background: COLORS[i % COLORS.length] }} />
                        </div>
                        <div className="chart-value">{b.cnt}</div>
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
        <div className="grid-2">
          {trend.series.length > 0 && (
            <div className="card">
              <h2>练习趋势（14天）</h2>
              <div style={{ overflowX: "auto" }}>
                <div className="chart-bar" style={{ width: Math.max(trend.series.length * 28, 200) }}>
                  {trend.series.map((s: any, i: number) => {
                    const h = (s.attempts || 0) / maxCount(trend.series, "attempts") * 100;
                    return (
                      <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center" }}>
                        <div style={{ flex: 1, width: "100%", display: "flex", flexDirection: "column", justifyContent: "flex-end" }}>
                          <div className="chart-bar-item" style={{ height: `${h}%`, background: s.accuracy > 0.7 ? "#059669" : s.accuracy > 0.4 ? "#ca8a04" : "#dc2626" }} title={`正确率: ${(s.accuracy * 100).toFixed(0)}%`} />
                        </div>
                        <div className="chart-bar-label">{s.day?.slice(5)}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {difficulty && (
            <div className="card">
              <h2>难度分布</h2>
              {difficulty.buckets.length === 0 ? <p className="empty">无数据</p> : (
                <div>
                  {difficulty.buckets.map((b: any, i: number) => {
                    const total = difficulty.buckets.reduce((s: number, x: any) => s + (x.cnt || 0), 0);
                    const pct = total > 0 ? Math.round((b.cnt || 0) / total * 100) : 0;
                    return (
                      <div className="chart-row" key={i}>
                        <div className="chart-label">{b.bucket}</div>
                        <div className="chart-fill">
                          <div className="chart-fill-inner" style={{ width: `${pct}%`, background: ["#059669", "#ca8a04", "#dc2626"][i] || "#2563eb" }} />
                        </div>
                        <div className="chart-value">{b.cnt} ({pct}%)</div>
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
      <div className="grid-2">
        {subjectDist && (
          <div className="card">
            <h2>学科分布</h2>
            {subjectDist.items.length === 0 ? <p className="empty">无数据</p> : (
              <table>
                <thead><tr><th>学科</th><th>题目数</th><th>知识节点</th></tr></thead>
                <tbody>
                  {subjectDist.items.map((s: any, i: number) => (
                    <tr key={i}><td className="code">{s.subject}</td><td>{s.questions}</td><td>{s.nodes || 0}</td></tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {wrong && (
          <div className="card">
            <h2>错题 TOP {wrong.items.length}</h2>
            {wrong.items.length === 0 ? <p className="empty">无数据</p> : (
              <table>
                <thead><tr><th>题干</th><th>难度</th><th>错率</th></tr></thead>
                <tbody>
                  {wrong.items.map((w) => {
                    const rate = w.total_attempts > 0 ? (w.wrong_count / w.total_attempts * 100).toFixed(0) : "0";
                    return (
                      <tr key={w.id}>
                        <td style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{w.stem?.slice(0, 40) || "—"}</td>
                        <td>{w.difficulty}</td>
                        <td style={{ color: Number(rate) > 50 ? "#fca5a5" : "#cbd5e1" }}>{rate}% ({w.wrong_count}/{w.total_attempts})</td>
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
        <div className="card">
          <h2>用户参与度排名（TOP {engagement.items.length}）</h2>
          {engagement.items.length === 0 ? <p className="empty">无数据</p> : (
            <table>
              <thead><tr><th>排名</th><th>用户</th><th>总练习</th><th>正确</th><th>活跃天数</th></tr></thead>
              <tbody>
                {engagement.items.map((u: any, i: number) => (
                  <tr key={i}>
                    <td>{i + 1}</td>
                    <td>{u.username || u.user_id}</td>
                    <td>{u.total_attempts}</td>
                    <td><span style={{ color: "#6ee7b7" }}>{u.correct_attempts}</span></td>
                    <td>{u.active_days}<span className="muted">天</span></td>
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
