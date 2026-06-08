"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getCurrentUser, hasRole, type AdminUser } from "@/lib/api";

interface Kpi {
  users_total: number; users_active: number;
  attempts_total: number; attempts_correct: number; accuracy: number;
  sessions_total: number; atom_nodes: number;
  questions_total: number; questions_active: number;
}
interface TrendResp { days: number; series: any[] }
interface WrongItem { id: string; stem: string; difficulty: number; bank_id: string; wrong_count: number; total_attempts: number }
interface MasteryResp { buckets: any[] }
interface ActivityResp { dau: number; wau: number; mau: number; total: number }

export default function AnalyticsPage() {
  const router = useRouter();
  const [me, setMe] = useState<AdminUser | null>(null);
  const [kpi, setKpi] = useState<Kpi | null>(null);
  const [trend, setTrend] = useState<TrendResp | null>(null);
  const [wrong, setWrong] = useState<{ items: WrongItem[] } | null>(null);
  const [mastery, setMastery] = useState<MasteryResp | null>(null);
  const [activity, setActivity] = useState<ActivityResp | null>(null);
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
      api.get<{ items: WrongItem[] }>("/analytics/top-wrong-questions?limit=10"),
      api.get<MasteryResp>("/analytics/mastery-distribution"),
      api.get<ActivityResp>("/analytics/user-activity"),
    ]).then(([k, t, w, m, a]) => {
      setKpi(k);
      setTrend(t);
      setWrong(w);
      setMastery(m);
      setActivity(a);
    }).catch((e) => setErr(e.message));
  }, [me]);

  return (
    <div className="page">
      <h1>BI 分析</h1>
      {err && <div className="card" style={{ borderColor: "#7f1d1d", color: "#fca5a5" }}>{err}</div>}

      {kpi && (
        <div className="kpi-grid">
          <div className="kpi"><div className="label">用户总数 / 活跃</div><div className="value">{kpi.users_total} / {kpi.users_active}</div></div>
          <div className="kpi"><div className="label">练习正确率</div><div className="value">{(kpi.accuracy * 100).toFixed(1)}<span className="unit">%</span></div></div>
          <div className="kpi"><div className="label">练习尝试</div><div className="value">{kpi.attempts_total}<span className="unit"> ({kpi.attempts_correct} 对)</span></div></div>
          <div className="kpi"><div className="label">练习会话</div><div className="value">{kpi.sessions_total}</div></div>
          <div className="kpi"><div className="label">认知节点 (atom)</div><div className="value">{kpi.atom_nodes}</div></div>
          <div className="kpi"><div className="label">题目 (已删/总数)</div><div className="value">{kpi.questions_active} / {kpi.questions_total}</div></div>
        </div>
      )}

      {activity && (
        <div className="card">
          <h2>用户活跃度（基于 last_login）</h2>
          <div className="kpi-grid" style={{ marginBottom: 0 }}>
            <div className="kpi"><div className="label">DAU (1d)</div><div className="value">{activity.dau}</div></div>
            <div className="kpi"><div className="label">WAU (7d)</div><div className="value">{activity.wau}</div></div>
            <div className="kpi"><div className="label">MAU (30d)</div><div className="value">{activity.mau}</div></div>
            <div className="kpi"><div className="label">总用户</div><div className="value">{activity.total}</div></div>
          </div>
        </div>
      )}

      {trend && (
        <div className="card">
          <h2>最近 {trend.days} 天练习趋势</h2>
          {trend.series.length === 0
            ? <p className="muted">无练习数据</p>
            : (
              <table>
                <thead><tr><th>日期</th><th>次数</th><th>正确率</th></tr></thead>
                <tbody>
                  {trend.series.map((r: any, i: number) => (
                    <tr key={i}>
                      <td className="code">{r.day || r.date || "—"}</td>
                      <td>{r.cnt ?? r.count ?? 0}</td>
                      <td>{r.accuracy != null ? `${(Number(r.accuracy) * 100).toFixed(1)}%` : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
        </div>
      )}

      {wrong && (
        <div className="card">
          <h2>错题 TOP {wrong.items.length}</h2>
          {wrong.items.length === 0
            ? <p className="muted">无错题数据</p>
            : (
              <table>
                <thead><tr><th>ID</th><th>题干（前 60）</th><th>难度</th><th>错/总</th><th>错率</th></tr></thead>
                <tbody>
                  {wrong.items.map((w) => {
                    const rate = w.total_attempts > 0 ? (w.wrong_count / w.total_attempts * 100).toFixed(0) : "0";
                    return (
                      <tr key={w.id}>
                        <td className="code">{w.id.slice(0, 18)}…</td>
                        <td>{w.stem?.slice(0, 60) || "—"}</td>
                        <td>{w.difficulty}</td>
                        <td>{w.wrong_count} / {w.total_attempts}</td>
                        <td style={{ color: Number(rate) > 50 ? "#fca5a5" : "#cbd5e1" }}>{rate}%</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
        </div>
      )}

      {mastery && (
        <div className="card">
          <h2>知识点掌握度分布</h2>
          {mastery.buckets.length === 0
            ? <p className="muted">无数据</p>
            : (
              <table>
                <thead><tr><th>掌握度区间</th><th>节点数</th></tr></thead>
                <tbody>
                  {mastery.buckets.map((b: any, i: number) => (
                    <tr key={i}>
                      <td className="code">{b.bucket || b.range || "—"}</td>
                      <td>{b.cnt ?? b.count ?? 0}</td>
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
