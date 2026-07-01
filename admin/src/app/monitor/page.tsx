"use client";

import { useCallback, useEffect, useState } from "react";
import { api, hasRole } from "@/lib/api";
import { useAuthGuard } from "@/lib/use-auth-guard";
import type { SystemHealth, MonitorEventRow, AlertCheckResult } from "@/lib/types";

export default function MonitorPage() {
  const { ready, user } = useAuthGuard();
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [events, setEvents] = useState<{ items: MonitorEventRow[]; count: number } | null>(null);
  const [trend, setTrend] = useState<{ series: any[] } | null>(null);
  const [alertCheck, setAlertCheck] = useState<AlertCheckResult | null>(null);
  const [logs, setLogs] = useState<{ items: string[] } | null>(null);
  const [err, setErr] = useState("");

  // Alert config modal
  const [showAlertCfg, setShowAlertCfg] = useState(false);
  const [alertCfg, setAlertCfg] = useState<Record<string, number>>({});
  const [cfgForm, setCfgForm] = useState<Record<string, number>>({});

  const load = useCallback(async () => {
    if (!ready || !user || !hasRole(user.role, "analyst")) return;
    try {
      const [h, e, t, a] = await Promise.all([
        api.get<SystemHealth>("/monitor/system/health"),
        api.get<{ items: MonitorEventRow[]; count: number }>("/monitor/events/recent?limit=30"),
        api.get<{ series: any[] }>("/monitor/events/trend?days=7"),
        api.get<AlertCheckResult>("/monitor/alerts/check"),
      ]);
      setHealth(h); setEvents(e); setTrend(t); setAlertCheck(a);
      const cfg = await api.get<Record<string, number>>("/monitor/alerts/config");
      setAlertCfg(cfg);
      setCfgForm(cfg);
    } catch (e: any) { setErr(e.message); }
  }, [ready, user]);

  useEffect(() => { load(); }, [load]);

  if (!ready) return <div className="py-20 text-center text-ink-muted">加载中…</div>;
  if (!user || !hasRole(user.role, "analyst")) return null;

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

  const thClass = "px-3.5 py-2.5 text-left border-b border-divider text-fine text-ink-muted font-semibold uppercase tracking-wide bg-page sticky top-0";
  const tdClass = "px-3.5 py-2.5 border-b border-divider text-caption text-ink-secondary";

  return (
    <div>
      <h1 className="text-heading mb-5">系统监控</h1>
      {err && <div className="bg-danger/10 border border-danger/20 text-danger rounded-lg p-4 mb-4">{err}</div>}

      {/* Alerts */}
      {alertCheck && !alertCheck.healthy && (
        alertCheck.alerts.map((a, i) => (
          <div key={i} className="bg-warning/10 border border-warning/20 text-warning rounded-lg p-3 mb-3">{a.message}</div>
        ))
      )}
      {alertCheck?.healthy && <div className="bg-success/10 border border-success/20 text-success rounded-lg p-3 mb-3">所有指标正常 ✓</div>}

      {/* Health */}
      {health && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-5">
          <div className="bg-surface border border-divider rounded-lg p-4">
            <div className="text-fine text-ink-muted uppercase tracking-wide font-medium mb-2">服务状态</div>
            <div className="text-2xl font-bold" style={{ color: health.status === "ok" ? "#6ee7b7" : "#fca5a5" }}>{health.status}</div>
            <div className="text-caption text-ink-muted">PID {health.pid}</div>
          </div>
          <div className="bg-surface border border-divider rounded-lg p-4">
            <div className="text-fine text-ink-muted uppercase tracking-wide font-medium mb-2">活跃用户</div>
            <div className="text-2xl font-bold text-ink-primary">{health.active_users}</div>
          </div>
          <div className="bg-surface border border-divider rounded-lg p-4">
            <div className="text-fine text-ink-muted uppercase tracking-wide font-medium mb-2">待处理事件</div>
            <div className="text-2xl font-bold" style={{ color: health.pending_events > 0 ? "#fcd34d" : "#6ee7b7" }}>{health.pending_events}</div>
          </div>
          <div className="bg-surface border border-divider rounded-lg p-4">
            <div className="text-fine text-ink-muted uppercase tracking-wide font-medium mb-2">认知节点</div>
            <div className="text-2xl font-bold text-ink-primary">{health.nodes_total}</div>
          </div>
          <div className="bg-surface border border-divider rounded-lg p-4">
            <div className="text-fine text-ink-muted uppercase tracking-wide font-medium mb-2">用户元数据</div>
            <div className="text-2xl font-bold text-ink-primary">{health.user_metas}</div>
          </div>
          <div className="bg-surface border border-divider rounded-lg p-4">
            <div className="text-fine text-ink-muted uppercase tracking-wide font-medium mb-2">DB 大小</div>
            <div className="text-2xl font-bold text-ink-primary">{health.db_size_mb}<span className="text-caption text-ink-muted">MB</span></div>
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-2 items-center mb-4 flex-wrap">
        <button className="px-3 py-1 bg-surface border border-divider rounded-md text-fine text-ink-secondary hover:bg-surface-hover transition-colors" onClick={() => load()}>刷新</button>
        <button className="px-3 py-1 bg-surface border border-divider rounded-md text-fine text-ink-secondary hover:bg-surface-hover transition-colors" onClick={loadLogs}>查看日志</button>
        <button className="px-3 py-1 bg-surface border border-divider rounded-md text-fine text-ink-secondary hover:bg-surface-hover transition-colors" onClick={() => { setCfgForm(alertCfg); setShowAlertCfg(true); }}>告警配置</button>
      </div>

      {/* Event trend chart */}
      {trend && trend.series.length > 0 && (
        <div className="bg-surface border border-divider rounded-lg p-5 mb-4">
          <h2 className="text-heading mb-4">事件趋势（7天）</h2>
          <div style={{ overflowX: "auto" }}>
            <div className="flex items-end gap-1" style={{ width: Math.max(trend.series.length * 32, 200), minHeight: 120 }}>
              {trend.series.map((s: any, i: number) => {
                const h = (Number(s.total) || 0) / maxCount(trend.series, "total") * 100;
                return (
                  <div key={i} className="flex-1 flex flex-col items-center">
                    <div className="flex-1 w-full flex flex-col justify-end gap-0.5">
                      <div className="rounded-sm" style={{ height: `${(Number(s.pending) || 0) / maxCount(trend.series, "total") * 100}%`, background: "#fcd34d" }} title={`待处理: ${s.pending}`} />
                      <div className="rounded-sm" style={{ height: `${h}%`, background: "#2563eb" }} title={`总数: ${s.total}`} />
                    </div>
                    <div className="text-[10px] text-ink-muted mt-1">{s.day?.slice(5)}</div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Events table */}
      {events && (
        <div className="bg-surface border border-divider rounded-lg p-5 mb-4">
          <h2 className="text-heading mb-4">最近事件流（{events.count}）</h2>
          <div className="overflow-x-auto" style={{ maxHeight: 360, overflowY: "auto" }}>
            <table className="w-full border-collapse">
              <thead><tr><th className={thClass}>时间</th><th className={thClass}>类型</th><th className={thClass}>用户</th><th className={thClass}>状态</th></tr></thead>
              <tbody>
                {events.items.length === 0 && <tr><td colSpan={4} className="text-ink-muted text-center py-10 text-caption">无事件</td></tr>}
                {events.items.slice(0, 30).map((e) => (
                  <tr key={e.event_id}>
                    <td className={`${tdClass} font-mono text-fine text-ink-muted`}>{e.timestamp?.slice(0, 19)}</td>
                    <td className={`${tdClass} font-mono text-fine`}>{e.event_type}</td>
                    <td className={`${tdClass} font-mono text-fine`}>{e.user_id}</td>
                    <td className={tdClass}>{e.processed ? <span className="bg-success/15 text-success border border-success/20 rounded-full px-2 py-0.5 text-fine font-medium">ok</span> : <span className="bg-warning/15 text-warning border border-warning/20 rounded-full px-2 py-0.5 text-fine font-medium">pending</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Logs */}
      {logs && (
        <div className="bg-surface border border-divider rounded-lg p-5 mb-4">
          <h2 className="text-heading mb-4">后端日志（最近 {logs.items.length} 行）</h2>
          <pre className="font-mono text-fine text-ink-secondary bg-input rounded-md p-4 overflow-x-auto whitespace-pre-wrap">{logs.items.map((l) => `${l}`).join("\n")}</pre>
        </div>
      )}

      {/* Alert config modal */}
      {showAlertCfg && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in" onClick={() => setShowAlertCfg(false)}>
          <div className="bg-surface-elevated border border-divider rounded-xl w-[90%] max-w-[560px] max-h-[80vh] overflow-y-auto p-7 shadow-md animate-slide-up" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-5 text-heading font-semibold text-ink-primary">告警阈值配置</h2>
            {Object.entries(cfgForm).map(([k, v]) => (
              <div key={k}>
                <label className="block mt-3.5 mb-1 text-fine text-ink-secondary font-medium">{k}</label>
                <input className="w-full px-3 py-2.5 bg-input text-ink-primary border border-divider rounded-md text-body focus:outline-none focus:border-accent" type="number" value={v} onChange={(e) => setCfgForm({ ...cfgForm, [k]: Number(e.target.value) })} />
              </div>
            ))}
            <div className="flex gap-2 justify-end mt-6">
              <button className="px-3 py-1 bg-surface border border-divider rounded-md text-fine text-ink-secondary hover:bg-surface-hover transition-colors" onClick={() => setShowAlertCfg(false)}>取消</button>
              <button className="px-4 py-2 bg-accent text-white rounded-md text-caption font-medium hover:bg-accent-hover transition-colors" onClick={saveAlertCfg}>保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
