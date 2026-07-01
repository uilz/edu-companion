"use client";

import { useEffect, useState } from "react";
import { api, hasRole } from "@/lib/api";
import { useAuthGuard } from "@/lib/use-auth-guard";
import type { ServicesResp, DbStatus, EnvInfo } from "@/lib/types";

export default function SettingsPage() {
  const { ready, user } = useAuthGuard();
  const [services, setServices] = useState<ServicesResp | null>(null);
  const [dbStatus, setDbStatus] = useState<DbStatus | null>(null);
  const [env, setEnv] = useState<EnvInfo | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!ready || !user || !hasRole(user.role, "super_admin")) return;
    Promise.all([
      api.get<ServicesResp>("/settings/services"),
      api.get<DbStatus>("/settings/db-status"),
      api.get<EnvInfo>("/settings/env"),
    ]).then(([s, d, e]) => {
      setServices(s); setDbStatus(d); setEnv(e);
    }).catch((e) => setErr(e.message));
  }, [ready, user]);

  if (!ready) return <div className="py-20 text-center text-ink-muted">加载中…</div>;
  if (!user || !hasRole(user.role, "super_admin")) return null;

  const serviceList = services?.services
    ? Object.entries(services.services)
    : [];

  const thClass = "px-3.5 py-2.5 text-left border-b border-divider text-fine text-ink-muted font-semibold uppercase tracking-wide bg-page sticky top-0";
  const tdClass = "px-3.5 py-2.5 border-b border-divider text-caption text-ink-secondary";

  return (
    <div>
      <h1 className="text-heading mb-5">系统设置</h1>
      {err && <div className="bg-danger/10 border border-danger/20 text-danger rounded-lg p-4 mb-4">{err}</div>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Service Status */}
        <div className="bg-surface border border-divider rounded-lg p-5">
          <h2 className="text-heading mb-4">服务状态</h2>
          {serviceList.length === 0 ? <p className="text-ink-muted text-caption">加载中…</p> : (
            <table className="w-full border-collapse">
              <thead><tr><th className={thClass}>服务</th><th className={thClass}>端口</th><th className={thClass}>状态</th></tr></thead>
              <tbody>
                {serviceList.map(([name, info]) => (
                  <tr key={name}>
                    <td className={`${tdClass} font-mono text-fine`}>{name}</td>
                    <td className={tdClass}>{info.port || "—"}</td>
                    <td className={tdClass}>
                      {info.status === "running"
                        ? <span className="bg-success/15 text-success border border-success/20 rounded-full px-2 py-0.5 text-fine font-medium">运行中</span>
                        : <span className="bg-danger/15 text-danger border border-danger/20 rounded-full px-2 py-0.5 text-fine font-medium">离线</span>}
                      {info.pid && <span className="text-ink-muted ml-1.5 text-[11px]">PID {info.pid}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* DB Status */}
        <div className="bg-surface border border-divider rounded-lg p-5">
          <h2 className="text-heading mb-4">数据库状态</h2>
          {!dbStatus ? <p className="text-ink-muted text-caption">加载中…</p> : (
            <>
              <div className="bg-surface border border-divider rounded-lg p-4 mb-3">
                <div className="text-fine text-ink-muted uppercase tracking-wide font-medium mb-2">连接状态</div>
                <div className="text-lg font-bold" style={{ color: dbStatus.connected ? "#6ee7b7" : "#fca5a5" }}>
                  {dbStatus.connected ? "已连接" : "断开"}
                </div>
              </div>
              {dbStatus.error && <div className="bg-danger/10 border border-danger/20 text-danger rounded-lg p-3">{dbStatus.error}</div>}
            </>
          )}
        </div>
      </div>

      {/* Environment Variables */}
      <div className="bg-surface border border-divider rounded-lg p-5 mt-4">
        <h2 className="text-heading mb-4">环境变量</h2>
        {!env ? <p className="text-ink-muted text-caption">加载中…</p> : (
          <table className="w-full border-collapse">
            <thead><tr><th className={thClass}>变量名</th><th className={thClass}>值</th></tr></thead>
            <tbody>
              {Object.entries(env.env).map(([k, v]) => (
                <tr key={k}>
                  <td className={`${tdClass} font-mono text-fine`}>{k}</td>
                  <td className={`${tdClass} font-mono text-fine`}>{String(v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
