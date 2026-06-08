"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getCurrentUser, hasRole, type AdminUser } from "@/lib/api";

interface Overview { [k: string]: number; }
interface SessionRow { id: string; user_id: string; username: string | null; status: string; total_count: number; correct_count: number; wrong_count: number; started_at: string | null; finished_at: string | null; }
interface ListResp<T> { items: T[]; total: number; page: number; page_size: number; }

export default function DataPage() {
  const router = useRouter();
  const [me, setMe] = useState<AdminUser | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [tab, setTab] = useState<"overview" | "sessions" | "conversations" | "drill">("overview");
  const [err, setErr] = useState("");
  const [sessions, setSessions] = useState<ListResp<SessionRow> | null>(null);
  const [convs, setConvs] = useState<ListResp<any> | null>(null);
  const [sessionPage, setSessionPage] = useState(1);
  const [convPage, setConvPage] = useState(1);

  // Per-user drill
  const [drillUserId, setDrillUserId] = useState("");
  const [drillSessions, setDrillSessions] = useState<ListResp<any> | null>(null);
  const [drillAttempts, setDrillAttempts] = useState<any[] | null>(null);
  const [drillLoading, setDrillLoading] = useState(false);

  useEffect(() => {
    const u = getCurrentUser();
    if (!u) { router.replace("/login"); return; }
    if (!hasRole(u.role, "data_admin")) { router.replace("/"); return; }
    setMe(u);
  }, [router]);

  const load = useCallback(async () => {
    if (!me) return;
    try {
      const [o, s, c] = await Promise.all([
        api.get<Overview>("/data/overview"),
        api.get<ListResp<SessionRow>>(`/data/practice-sessions?page=${sessionPage}&page_size=20`),
        api.get<ListResp<any>>(`/data/conversations?page=${convPage}&page_size=20`),
      ]);
      setOverview(o); setSessions(s); setConvs(c);
    } catch (e: any) { setErr(e.message); }
  }, [me, sessionPage, convPage]);

  useEffect(() => { load(); }, [load]);

  async function drill() {
    if (!drillUserId.trim()) return;
    setDrillLoading(true);
    try {
      const [s, a] = await Promise.all([
        api.get<ListResp<any>>(`/data/users/${drillUserId.trim()}/sessions?page_size=10`),
        api.get<{ items: any[] }>(`/data/users/${drillUserId.trim()}/attempts?limit=20`),
      ]);
      setDrillSessions(s); setDrillAttempts(a.items);
    } catch (e: any) { setErr(e.message); }
    setDrillLoading(false);
  }

  async function exportCsv(type: string) {
    window.open(`/api/admin/data/export/${type}`, "_blank");
  }

  const OV_COLORS: Record<string, { bg: string }> = {
    users_total: { bg: "#2563eb" }, users_active: { bg: "#059669" },
    practice_sessions: { bg: "#7c3aed" }, practice_attempts: { bg: "#dc2626" },
    conversations: { bg: "#0891b2" }, questions: { bg: "#ca8a04" },
    cognitive_nodes: { bg: "#2563eb" }, cognitive_events: { bg: "#9333ea" },
  };

  return (
    <div className="page">
      <h1>全局数据</h1>
      {err && <div className="card card-error">{err}</div>}

      <div className="toolbar">
        <button className="btn-sm" onClick={() => setTab("overview")} style={tab === "overview" ? { background: "#2563eb", color: "#fff" } : {}}>概览</button>
        <button className="btn-sm" onClick={() => setTab("sessions")} style={tab === "sessions" ? { background: "#2563eb", color: "#fff" } : {}}>练习会话 ({sessions?.total ?? 0})</button>
        <button className="btn-sm" onClick={() => setTab("conversations")} style={tab === "conversations" ? { background: "#2563eb", color: "#fff" } : {}}>会话 ({convs?.total ?? 0})</button>
        <button className="btn-sm" onClick={() => setTab("drill")} style={tab === "drill" ? { background: "#2563eb", color: "#fff" } : {}}>按用户钻取</button>
        <span className="spacer" />
        <button className="btn-sm" onClick={() => exportCsv("sessions")}>导出会话 CSV</button>
        <button className="btn-sm" onClick={() => exportCsv("users")}>导出用户 CSV</button>
      </div>

      {/* Overview */}
      {tab === "overview" && overview && (
        <div className="kpi-grid">
          {Object.entries(overview).map(([k, v]) => (
            <div className="kpi" key={k}>
              <div className="label">{k}</div>
              <div className="value">{v}</div>
              <div className="sub">
                <div style={{ background: "#334155", height: 4, borderRadius: 2, marginTop: 4 }}>
                  <div style={{ width: `${Math.min(100, (v as number) / 10)}%`, background: OV_COLORS[k]?.bg || "#2563eb", height: "100%", borderRadius: 2 }} />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Sessions */}
      {tab === "sessions" && sessions && (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead><tr><th>ID</th><th>用户</th><th>状态</th><th>题数</th><th>对/错</th><th>正确率</th><th>开始</th></tr></thead>
              <tbody>
                {sessions.items.length === 0 && <tr><td colSpan={7} className="empty">无数据</td></tr>}
                {sessions.items.map((s) => (
                  <tr key={s.id}>
                    <td className="code">{s.id.slice(0, 10)}…</td>
                    <td>{s.username || s.user_id?.slice(0, 12)}</td>
                    <td><span className="code">{s.status}</span></td>
                    <td>{s.total_count}</td>
                    <td><span style={{ color: "#6ee7b7" }}>{s.correct_count}</span> / <span style={{ color: "#fca5a5" }}>{s.wrong_count}</span></td>
                    <td>{s.total_count > 0 ? `${(s.correct_count / s.total_count * 100).toFixed(1)}%` : "—"}</td>
                    <td className="code muted">{s.started_at?.slice(0, 16) || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {sessions.total > 20 && (
            <div className="pagination">
              <button disabled={sessionPage <= 1} onClick={() => setSessionPage(sessionPage - 1)}>上一页</button>
              <span>第 {sessionPage}/{(Math.ceil(sessions.total / 20))} 页</span>
              <button disabled={sessionPage >= Math.ceil(sessions.total / 20)} onClick={() => setSessionPage(sessionPage + 1)}>下一页</button>
            </div>
          )}
        </div>
      )}

      {/* Conversations */}
      {tab === "conversations" && convs && (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead><tr><th>用户</th><th>会话数</th><th>更新时间</th></tr></thead>
              <tbody>
                {convs.items.length === 0 && <tr><td colSpan={3} className="empty">无数据</td></tr>}
                {convs.items.map((c: any, i: number) => (
                  <tr key={i}><td className="code">{c.user_id}</td><td>{c.conv_count}</td><td className="code muted">{c.updated_at?.slice(0, 16) || "—"}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          {convs.total > 20 && (
            <div className="pagination">
              <button disabled={convPage <= 1} onClick={() => setConvPage(convPage - 1)}>上一页</button>
              <span>第 {convPage}/{(Math.ceil(convs.total / 20))} 页</span>
              <button disabled={convPage >= Math.ceil(convs.total / 20)} onClick={() => setConvPage(convPage + 1)}>下一页</button>
            </div>
          )}
        </div>
      )}

      {/* Per-user Drill */}
      {tab === "drill" && (
        <div className="card">
          <div className="card-toolbar">
            <label>输入用户 ID：</label>
            <input value={drillUserId} onChange={(e) => setDrillUserId(e.target.value)} placeholder="例如 u_apple_admin" style={{ width: 280 }} />
            <button className="btn-sm" onClick={drill} disabled={drillLoading}>查询</button>
          </div>

          {drillLoading && <p className="muted">加载中…</p>}

          {drillSessions && (
            <>
              <h3>练习会话</h3>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>ID</th><th>状态</th><th>题数</th><th>对/错</th><th>开始</th></tr></thead>
                  <tbody>
                    {drillSessions.items.length === 0 && <tr><td colSpan={5} className="empty">无会话</td></tr>}
                    {drillSessions.items.map((s: any) => (
                      <tr key={s.id}>
                        <td className="code">{s.id.slice(0, 10)}…</td>
                        <td>{s.status}</td>
                        <td>{s.total_count}</td>
                        <td><span style={{ color: "#6ee7b7" }}>{s.correct_count}</span> / <span style={{ color: "#fca5a5" }}>{s.wrong_count}</span></td>
                        <td className="code muted">{s.started_at?.slice(0, 16) || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {drillAttempts && (
            <>
              <h3 style={{ marginTop: 12 }}>最近练习明细</h3>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>题目标题</th><th>结果</th><th>耗时(s)</th><th>时间</th></tr></thead>
                  <tbody>
                    {drillAttempts.length === 0 && <tr><td colSpan={3} className="empty">无记录</td></tr>}
                    {drillAttempts.map((a: any, i: number) => (
                      <tr key={i}>
                        <td style={{ maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.stem?.slice(0, 40) || a.question_id?.slice(0, 16)}</td>
                        <td>{a.is_correct ? <span className="badge badge-ok">正确</span> : <span className="badge badge-inactive">错误</span>}</td>
                        <td>{a.time_spent?.toFixed(1)}</td>
                        <td className="code muted">{a.created_at?.slice(0, 16)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
