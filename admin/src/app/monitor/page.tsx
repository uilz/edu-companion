"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getCurrentUser, hasRole, type AdminUser } from "@/lib/api";

interface Health { status: string; now: string; active_users: number; pending_events: number; nodes_total: number; user_metas: number; db_size_mb: number; }
interface EventRow { event_id: string; event_type: string; user_id: string; node_id: string; processed: boolean; timestamp: string; payload: any; }
interface EventsResp { items: EventRow[]; count: number; }
interface StatsResp { window_hours: number; by_type: { event_type: string; cnt: number; pending: number }[]; }

export default function MonitorPage() {
  const router = useRouter();
  const [me, setMe] = useState<AdminUser | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [events, setEvents] = useState<EventsResp | null>(null);
  const [stats, setStats] = useState<StatsResp | null>(null);
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
      fetch("/api/admin/monitor/system/health", { headers: { Authorization: `Bearer ${localStorage.getItem("admin_token") || ""}` } }).then((r) => r.json()),
      api.get<EventsResp>("/monitor/events/recent?limit=50"),
      api.get<StatsResp>("/monitor/events/stats?hours=24"),
    ]).then(([h, e, s]) => {
      setHealth(h);
      setEvents(e);
      setStats(s);
    }).catch((e) => setErr(e.message));
  }, [me]);

  return (
    <div className="page">
      <h1>系统监控</h1>
      {err && <div className="card" style={{ borderColor: "#7f1d1d", color: "#fca5a5" }}>{err}</div>}

      {health && (
        <div className="kpi-grid">
          <div className="kpi"><div className="label">服务状态</div><div className="value" style={{ color: health.status === "ok" ? "#6ee7b7" : "#fca5a5" }}>{health.status}</div></div>
          <div className="kpi"><div className="label">活跃用户</div><div className="value">{health.active_users}</div></div>
          <div className="kpi"><div className="label">待处理事件</div><div className="value" style={{ color: health.pending_events > 0 ? "#fcd34d" : "#6ee7b7" }}>{health.pending_events}</div></div>
          <div className="kpi"><div className="label">认知节点</div><div className="value">{health.nodes_total}</div></div>
          <div className="kpi"><div className="label">用户元数据</div><div className="value">{health.user_metas}</div></div>
          <div className="kpi"><div className="label">DB 大小</div><div className="value">{health.db_size_mb}<span className="unit">MB</span></div></div>
          <div className="kpi"><div className="label">当前时间</div><div className="value" style={{ fontSize: 14 }}>{health.now?.slice(0, 19)}</div></div>
        </div>
      )}

      {stats && (
        <div className="card">
          <h2>最近 {stats.window_hours}h 事件分布</h2>
          {stats.by_type.length === 0 ? <p className="muted">无事件</p> : (
            <table>
              <thead><tr><th>类型</th><th>总数</th><th>待处理</th><th>分布</th></tr></thead>
              <tbody>
                {stats.by_type.map((b) => {
                  const total = stats.by_type.reduce((s, x) => s + x.cnt, 0) || 1;
                  const pct = Math.round((b.cnt / total) * 100);
                  return (
                    <tr key={b.event_type}>
                      <td className="code">{b.event_type}</td>
                      <td>{b.cnt}</td>
                      <td>{b.pending > 0 ? <span className="badge badge-pending">{b.pending}</span> : "—"}</td>
                      <td style={{ width: 240 }}>
                        <div style={{ background: "#334155", height: 8, borderRadius: 4, overflow: "hidden" }}>
                          <div style={{ width: `${pct}%`, background: "#2563eb", height: "100%" }} />
                        </div>
                        <span className="code muted" style={{ fontSize: 11 }}>{pct}%</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {events && (
        <div className="card">
          <h2>最近事件流（{events.count}）</h2>
          <div style={{ maxHeight: 480, overflow: "auto" }}>
            <table>
              <thead><tr><th>时间</th><th>类型</th><th>用户</th><th>节点</th><th>状态</th><th>Payload</th></tr></thead>
              <tbody>
                {events.items.length === 0 && <tr><td colSpan={6} className="muted">无事件</td></tr>}
                {events.items.map((e) => (
                  <tr key={e.event_id}>
                    <td className="code muted">{e.timestamp?.slice(0, 19)}</td>
                    <td className="code">{e.event_type}</td>
                    <td className="code">{e.user_id}</td>
                    <td className="code">{e.node_id}</td>
                    <td>
                      {e.processed
                        ? <span className="badge badge-ok">processed</span>
                        : <span className="badge badge-pending">pending</span>}
                    </td>
                    <td><pre style={{ margin: 0, maxWidth: 360, maxHeight: 80, overflow: "auto" }}>{JSON.stringify(e.payload, null, 2)}</pre></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
