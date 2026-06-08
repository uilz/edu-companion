"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getCurrentUser, hasRole, type AdminUser } from "@/lib/api";

interface Health { status: string; now: string; active_users: number; pending_events: number; nodes_total: number; user_metas: number; db_size_mb: number; db_size_gb: number; pid: number; }
interface EventRow { event_id: string; event_type: string; user_id: string; node_id: string; processed: boolean; timestamp: string; payload: any; }
interface AlertCheck { alerts: any[]; alert_count: number; healthy: boolean; config: any; }

export default function MonitorPage() {
  const router = useRouter();
  const [me, setMe] = useState<AdminUser | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [events, setEvents] = useState<{ items: EventRow[]; count: number } | null>(null);
  const [trend, setTrend] = useState<{ series: any[] } | null>(null);
  const [alertCheck, setAlertCheck] = useState<AlertCheck | null>(null);
  const [logs, setLogs] = useState<{ items: string[] } | null>(null);
  const [err, setErr] = useState("");

  // Alert config modal
  const [showAlertCfg, setShowAlertCfg] = useState(false);
  const [alertCfg, setAlertCfg] = useState<Record<string, number>>({});
  const [cfgForm, setCfgForm] = useState<Record<string, number>>({});

  useEffect(() => {
    const u = getCurrentUser();
    if (!u) { router.replace("/login"); return; }
    if (!hasRole(u.role, "analyst")) { router.replace("/"); return; }
    setMe(u);
  }, [router]);

  const load = useCallback(async () => {
    if (!me) return;
    try {
      const [h, e, t, a] = await Promise.all([
        api.get<Health>("/monitor/system/health"),
        api.get<{ items: EventRow[]; count: number }>("/monitor/events/recent?limit=30"),
        api.get<{ series: any[] }>("/monitor/events/trend?days=7"),
        api.get<AlertCheck>("/monitor/alerts/check"),
      ]);
      setHealth(h); setEvents(e); setTrend(t); setAlertCheck(a);
      const cfg = await api.get<Record<string, number>>("/monitor/alerts/config");
      setAlertCfg(cfg);
      setCfgForm(cfg);
    } catch (e: any) { setErr(e.message); }
  }, [me]);

  useEffect(() => { load(); }, [load]);

  async function loadLogs() {
    try { const l = await api.get<{ items: string[] }>("/monitor/system/logs?lines=30"); setLogs(l); }
    catch (e: any) { setErr(e.message); }
  }

  async function saveAlertCfg() {
    try { await api.put("/monitor/alerts/config", cfgForm); setAlertCfg(cfgForm); setShowAlertCfg(false); }
    catch (e: any) { alert("失败: " + e.message); }
  }

  function maxCount(series: any[], key: string): number {
    return Math.max(...series.map((s: any) => Number(s[key] || 0)), 1);
  }

  const COLORS = ["#2563eb", "#059669", "#7c3aed", "#dc2626", "#ca8a04", "#0891b2"];

  return (
    <div className="page">
      <h1>系统监控</h1>
      {err && <div className="card card-error">{err}</div>}

      {/* Alerts */}
      {alertCheck && !alertCheck.healthy && (
        alertCheck.alerts.map((a: any, i: number) => (
          <div key={i} className="alert alert-warning">{a.message}</div>
        ))
      )}
      {alertCheck?.healthy && <div className="alert alert-ok">所有指标正常 ✓</div>}

      {/* Health */}
      {health && (
        <div className="kpi-grid">
          <div className="kpi"><div className="label">服务状态</div><div className="value" style={{ color: health.status === "ok" ? "#6ee7b7" : "#fca5a5" }}>{health.status}</div><div className="sub">PID {health.pid}</div></div>
          <div className="kpi"><div className="label">活跃用户</div><div className="value">{health.active_users}</div></div>
          <div className="kpi"><div className="label">待处理事件</div><div className="value" style={{ color: health.pending_events > 0 ? "#fcd34d" : "#6ee7b7" }}>{health.pending_events}</div></div>
          <div className="kpi"><div className="label">认知节点</div><div className="value">{health.nodes_total}</div></div>
          <div className="kpi"><div className="label">用户元数据</div><div className="value">{health.user_metas}</div></div>
          <div className="kpi"><div className="label">DB 大小</div><div className="value">{health.db_size_mb}<span className="unit">MB</span></div></div>
        </div>
      )}

      {/* Action buttons */}
      <div className="toolbar" style={{ marginBottom: 16 }}>
        <button className="btn-sm" onClick={() => load()}>刷新</button>
        <button className="btn-sm" onClick={loadLogs}>查看日志</button>
        <button className="btn-sm" onClick={() => { setCfgForm(alertCfg); setShowAlertCfg(true); }}>告警配置</button>
      </div>

      {/* Event trend chart */}
      {trend && trend.series.length > 0 && (
        <div className="card">
          <h2>事件趋势（7天）</h2>
          <div style={{ overflowX: "auto" }}>
            <div className="chart-bar" style={{ width: Math.max(trend.series.length * 32, 200), minHeight: 120 }}>
              {trend.series.map((s: any, i: number) => {
                const h = (Number(s.total) || 0) / maxCount(trend.series, "total") * 100;
                return (
                  <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center" }}>
                    <div style={{ flex: 1, width: "100%", display: "flex", flexDirection: "column", justifyContent: "flex-end", gap: 2 }}>
                      <div className="chart-bar-item" style={{ height: `${(Number(s.pending) || 0) / maxCount(trend.series, "total") * 100}%`, background: "#fcd34d" }} title={`待处理: ${s.pending}`} />
                      <div className="chart-bar-item" style={{ height: `${h}%`, background: "#2563eb" }} title={`总数: ${s.total}`} />
                    </div>
                    <div className="chart-bar-label">{s.day?.slice(5)}</div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Events table */}
      {events && (
        <div className="card">
          <h2>最近事件流（{events.count}）</h2>
          <div className="table-wrap" style={{ maxHeight: 360, overflowY: "auto" }}>
            <table>
              <thead><tr><th>时间</th><th>类型</th><th>用户</th><th>状态</th></tr></thead>
              <tbody>
                {events.items.length === 0 && <tr><td colSpan={4} className="empty">无事件</td></tr>}
                {events.items.slice(0, 30).map((e) => (
                  <tr key={e.event_id}>
                    <td className="code muted">{e.timestamp?.slice(0, 19)}</td>
                    <td className="code">{e.event_type}</td>
                    <td className="code">{e.user_id}</td>
                    <td>{e.processed ? <span className="badge badge-ok">ok</span> : <span className="badge badge-pending">pending</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Logs */}
      {logs && (
        <div className="card">
          <h2>后端日志（最近 {logs.items.length} 行）</h2>
          <pre>{logs.items.map((l, i) => `${l}`).join("\n")}</pre>
        </div>
      )}

      {/* Alert config modal */}
      {showAlertCfg && (
        <div className="modal-overlay" onClick={() => setShowAlertCfg(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>告警阈值配置</h2>
            {Object.entries(cfgForm).map(([k, v]) => (
              <div key={k}>
                <label>{k}</label>
                <input type="number" value={v} onChange={(e) => setCfgForm({ ...cfgForm, [k]: Number(e.target.value) })} />
              </div>
            ))}
            <div className="modal-actions">
              <button className="btn-sm" onClick={() => setShowAlertCfg(false)}>取消</button>
              <button className="btn" onClick={saveAlertCfg}>保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
