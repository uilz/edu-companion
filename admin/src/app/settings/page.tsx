"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getCurrentUser, hasRole, type AdminUser } from "@/lib/api";

interface ServicesResp { services: Record<string, { port?: number; status: string; pid?: number }>; }
interface DbStatus { connected: boolean; error?: string; version_rows?: any; }
interface EnvInfo { env: Record<string, string>; }

export default function SettingsPage() {
  const router = useRouter();
  const [me, setMe] = useState<AdminUser | null>(null);
  const [services, setServices] = useState<ServicesResp | null>(null);
  const [dbStatus, setDbStatus] = useState<DbStatus | null>(null);
  const [env, setEnv] = useState<EnvInfo | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    const u = getCurrentUser();
    if (!u) { router.replace("/login"); return; }
    if (!hasRole(u.role, "super_admin")) { router.replace("/"); return; }
    setMe(u);
  }, [router]);

  useEffect(() => {
    if (!me) return;
    Promise.all([
      api.get<ServicesResp>("/settings/services"),
      api.get<DbStatus>("/settings/db-status"),
      api.get<EnvInfo>("/settings/env"),
    ]).then(([s, d, e]) => {
      setServices(s); setDbStatus(d); setEnv(e);
    }).catch((e) => setErr(e.message));
  }, [me]);

  const serviceList = services?.services
    ? Object.entries(services.services)
    : [];

  return (
    <div className="page">
      <h1>系统设置</h1>
      {err && <div className="card card-error">{err}</div>}

      <div className="grid-2">
        {/* Service Status */}
        <div className="card">
          <h2>服务状态</h2>
          {serviceList.length === 0 ? <p className="muted">加载中…</p> : (
            <table>
              <thead><tr><th>服务</th><th>端口</th><th>状态</th></tr></thead>
              <tbody>
                {serviceList.map(([name, info]) => (
                  <tr key={name}>
                    <td className="code">{name}</td>
                    <td>{info.port || "—"}</td>
                    <td>
                      {info.status === "running"
                        ? <span className="badge badge-ok">运行中</span>
                        : <span className="badge badge-inactive">离线</span>}
                      {info.pid && <span className="muted" style={{ marginLeft: 6, fontSize: 11 }}>PID {info.pid}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* DB Status */}
        <div className="card">
          <h2>数据库状态</h2>
          {!dbStatus ? <p className="muted">加载中…</p> : (
            <>
              <div className="kpi kpi-sm">
                <div className="label">连接状态</div>
                <div className="value" style={{ color: dbStatus.connected ? "#6ee7b7" : "#fca5a5", fontSize: 18 }}>
                  {dbStatus.connected ? "已连接" : "断开"}
                </div>
              </div>
              {dbStatus.error && <div className="alert alert-danger">{dbStatus.error}</div>}
            </>
          )}
        </div>
      </div>

      {/* Environment Variables */}
      <div className="card">
        <h2>环境变量</h2>
        {!env ? <p className="muted">加载中…</p> : (
          <table>
            <thead><tr><th>变量名</th><th>值</th></tr></thead>
            <tbody>
              {Object.entries(env.env).map(([k, v]) => (
                <tr key={k}>
                  <td className="code">{k}</td>
                  <td className="code">{String(v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
