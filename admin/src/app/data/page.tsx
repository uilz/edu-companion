"use client";

import { useCallback, useEffect, useState } from "react";
import { api, hasRole } from "@/lib/api";
import { useAuthGuard } from "@/lib/use-auth-guard";
import type { GlobalOverview, PracticeSession, ConversationSummary, DrillAttempt, PaginatedResponse } from "@/lib/types";

export default function DataPage() {
  const { ready, user } = useAuthGuard();
  const [overview, setOverview] = useState<GlobalOverview | null>(null);
  const [tab, setTab] = useState<"overview" | "sessions" | "conversations" | "drill">("overview");
  const [err, setErr] = useState("");
  const [sessions, setSessions] = useState<PaginatedResponse<PracticeSession> | null>(null);
  const [convs, setConvs] = useState<PaginatedResponse<ConversationSummary> | null>(null);
  const [sessionPage, setSessionPage] = useState(1);
  const [convPage, setConvPage] = useState(1);

  // Per-user drill
  const [drillUserId, setDrillUserId] = useState("");
  const [drillSessions, setDrillSessions] = useState<PaginatedResponse<any> | null>(null);
  const [drillAttempts, setDrillAttempts] = useState<any[] | null>(null);
  const [drillLoading, setDrillLoading] = useState(false);

  const load = useCallback(async () => {
    if (!ready || !user || !hasRole(user.role, "data_admin")) return;
    try {
      const [o, s, c] = await Promise.all([
        api.get<GlobalOverview>("/data/overview"),
        api.get<PaginatedResponse<PracticeSession>>(`/data/practice-sessions?page=${sessionPage}&page_size=20`),
        api.get<PaginatedResponse<ConversationSummary>>(`/data/conversations?page=${convPage}&page_size=20`),
      ]);
      setOverview(o); setSessions(s); setConvs(c);
    } catch (e: any) { setErr(e.message); }
  }, [ready, user, sessionPage, convPage]);

  useEffect(() => { load(); }, [load]);

  if (!ready) return <div className="py-20 text-center text-ink-muted">加载中…</div>;
  if (!user || !hasRole(user.role, "data_admin")) return null;

  async function drill() {
    if (!drillUserId.trim()) return;
    setDrillLoading(true);
    try {
      const [s, a] = await Promise.all([
        api.get<PaginatedResponse<any>>(`/data/users/${drillUserId.trim()}/sessions?page_size=10`),
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

  const thClass = "px-3.5 py-2.5 text-left border-b border-divider text-fine text-ink-muted font-semibold uppercase tracking-wide bg-page sticky top-0";
  const tdClass = "px-3.5 py-2.5 border-b border-divider text-caption text-ink-secondary";
  const inputClass = "px-3 py-1.5 bg-input text-ink-primary border border-divider rounded-md text-caption focus:outline-none focus:border-accent";
  const tabBtnClass = (active: boolean) =>
    `px-3 py-1 rounded-md text-fine font-medium transition-colors ${
      active ? "bg-accent text-white" : "bg-surface border border-divider text-ink-secondary hover:bg-surface-hover"
    }`;

  return (
    <div>
      <h1 className="text-heading mb-5">全局数据</h1>
      {err && <div className="bg-danger/10 border border-danger/20 text-danger rounded-lg p-4 mb-4">{err}</div>}

      <div className="flex gap-2 items-center mb-3.5 flex-wrap">
        <button className={tabBtnClass(tab === "overview")} onClick={() => setTab("overview")}>概览</button>
        <button className={tabBtnClass(tab === "sessions")} onClick={() => setTab("sessions")}>练习会话 ({sessions?.total ?? 0})</button>
        <button className={tabBtnClass(tab === "conversations")} onClick={() => setTab("conversations")}>会话 ({convs?.total ?? 0})</button>
        <button className={tabBtnClass(tab === "drill")} onClick={() => setTab("drill")}>按用户钻取</button>
        <span className="flex-1" />
        <button className="px-3 py-1 bg-surface border border-divider rounded-md text-fine text-ink-secondary hover:bg-surface-hover transition-colors" onClick={() => exportCsv("sessions")}>导出会话 CSV</button>
        <button className="px-3 py-1 bg-surface border border-divider rounded-md text-fine text-ink-secondary hover:bg-surface-hover transition-colors" onClick={() => exportCsv("users")}>导出用户 CSV</button>
      </div>

      {/* Overview */}
      {tab === "overview" && overview && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mb-5">
          {Object.entries(overview).map(([k, v]) => (
            <div className="bg-surface border border-divider rounded-lg p-4" key={k}>
              <div className="text-fine text-ink-muted uppercase tracking-wide font-medium mb-2">{k}</div>
              <div className="text-2xl font-bold text-ink-primary">{v}</div>
              <div className="text-caption text-ink-muted">
                <div className="bg-[#334155] h-1 rounded-sm mt-1">
                  <div style={{ width: `${Math.min(100, (v as number) / 10)}%`, background: OV_COLORS[k]?.bg || "#2563eb", height: "100%", borderRadius: 2 }} />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Sessions */}
      {tab === "sessions" && sessions && (
        <div className="bg-surface border border-divider rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead><tr><th className={thClass}>ID</th><th className={thClass}>用户</th><th className={thClass}>状态</th><th className={thClass}>题数</th><th className={thClass}>对/错</th><th className={thClass}>正确率</th><th className={thClass}>开始</th></tr></thead>
              <tbody>
                {sessions.items.length === 0 && <tr><td colSpan={7} className="text-ink-muted text-center py-10 text-caption">无数据</td></tr>}
                {sessions.items.map((s) => (
                  <tr key={s.id}>
                    <td className={`${tdClass} font-mono text-fine`}>{s.id.slice(0, 10)}…</td>
                    <td className={tdClass}>{s.username || s.user_id?.slice(0, 12)}</td>
                    <td className={`${tdClass} font-mono text-fine`}>{s.status}</td>
                    <td className={tdClass}>{s.total_count}</td>
                    <td className={tdClass}><span style={{ color: "#6ee7b7" }}>{s.correct_count}</span> / <span style={{ color: "#fca5a5" }}>{s.wrong_count}</span></td>
                    <td className={tdClass}>{s.total_count > 0 ? `${(s.correct_count / s.total_count * 100).toFixed(1)}%` : "—"}</td>
                    <td className={`${tdClass} font-mono text-fine text-ink-muted`}>{s.started_at?.slice(0, 16) || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {sessions.total > 20 && (
            <div className="flex justify-end items-center gap-2 py-3 px-4 text-caption text-ink-muted border-t border-divider">
              <button className={`px-2.5 py-1 rounded-md text-fine border border-divider ${sessionPage <= 1 ? "text-ink-muted opacity-50" : "text-ink-secondary hover:bg-surface-hover transition-colors"}`} disabled={sessionPage <= 1} onClick={() => setSessionPage(sessionPage - 1)}>上一页</button>
              <span>第 {sessionPage}/{(Math.ceil(sessions.total / 20))} 页</span>
              <button className={`px-2.5 py-1 rounded-md text-fine border border-divider ${sessionPage >= Math.ceil(sessions.total / 20) ? "text-ink-muted opacity-50" : "text-ink-secondary hover:bg-surface-hover transition-colors"}`} disabled={sessionPage >= Math.ceil(sessions.total / 20)} onClick={() => setSessionPage(sessionPage + 1)}>下一页</button>
            </div>
          )}
        </div>
      )}

      {/* Conversations */}
      {tab === "conversations" && convs && (
        <div className="bg-surface border border-divider rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead><tr><th className={thClass}>用户</th><th className={thClass}>会话数</th><th className={thClass}>更新时间</th></tr></thead>
              <tbody>
                {convs.items.length === 0 && <tr><td colSpan={3} className="text-ink-muted text-center py-10 text-caption">无数据</td></tr>}
                {convs.items.map((c, i) => (
                  <tr key={i}><td className={`${tdClass} font-mono text-fine`}>{c.user_id}</td><td className={tdClass}>{c.conv_count}</td><td className={`${tdClass} font-mono text-fine text-ink-muted`}>{c.updated_at?.slice(0, 16) || "—"}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          {convs.total > 20 && (
            <div className="flex justify-end items-center gap-2 py-3 px-4 text-caption text-ink-muted border-t border-divider">
              <button className={`px-2.5 py-1 rounded-md text-fine border border-divider ${convPage <= 1 ? "text-ink-muted opacity-50" : "text-ink-secondary hover:bg-surface-hover transition-colors"}`} disabled={convPage <= 1} onClick={() => setConvPage(convPage - 1)}>上一页</button>
              <span>第 {convPage}/{(Math.ceil(convs.total / 20))} 页</span>
              <button className={`px-2.5 py-1 rounded-md text-fine border border-divider ${convPage >= Math.ceil(convs.total / 20) ? "text-ink-muted opacity-50" : "text-ink-secondary hover:bg-surface-hover transition-colors"}`} disabled={convPage >= Math.ceil(convs.total / 20)} onClick={() => setConvPage(convPage + 1)}>下一页</button>
            </div>
          )}
        </div>
      )}

      {/* Per-user Drill */}
      {tab === "drill" && (
        <div className="bg-surface border border-divider rounded-lg p-5">
          <div className="flex gap-2 items-center mb-4 p-3 bg-page rounded-md">
            <label className="text-fine text-ink-secondary font-medium">输入用户 ID：</label>
            <input className={inputClass} value={drillUserId} onChange={(e) => setDrillUserId(e.target.value)} placeholder="例如 u_apple_admin" style={{ width: 280 }} />
            <button className="px-3 py-1 bg-surface border border-divider rounded-md text-fine text-ink-secondary hover:bg-surface-hover transition-colors disabled:opacity-50" onClick={drill} disabled={drillLoading}>查询</button>
          </div>

          {drillLoading && <p className="text-ink-muted text-caption">加载中…</p>}

          {drillSessions && (
            <>
              <h3 className="text-caption font-semibold text-ink-muted uppercase tracking-wide mt-6 mb-3 pb-2 border-b border-divider">练习会话</h3>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead><tr><th className={thClass}>ID</th><th className={thClass}>状态</th><th className={thClass}>题数</th><th className={thClass}>对/错</th><th className={thClass}>开始</th></tr></thead>
                  <tbody>
                    {drillSessions.items.length === 0 && <tr><td colSpan={5} className="text-ink-muted text-center py-10 text-caption">无会话</td></tr>}
                    {drillSessions.items.map((s: any) => (
                      <tr key={s.id}>
                        <td className={`${tdClass} font-mono text-fine`}>{s.id.slice(0, 10)}…</td>
                        <td className={tdClass}>{s.status}</td>
                        <td className={tdClass}>{s.total_count}</td>
                        <td className={tdClass}><span style={{ color: "#6ee7b7" }}>{s.correct_count}</span> / <span style={{ color: "#fca5a5" }}>{s.wrong_count}</span></td>
                        <td className={`${tdClass} font-mono text-fine text-ink-muted`}>{s.started_at?.slice(0, 16) || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {drillAttempts && (
            <>
              <h3 className="text-caption font-semibold text-ink-muted uppercase tracking-wide mt-6 mb-3 pb-2 border-b border-divider">最近练习明细</h3>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead><tr><th className={thClass}>题目标题</th><th className={thClass}>结果</th><th className={thClass}>耗时(s)</th><th className={thClass}>时间</th></tr></thead>
                  <tbody>
                    {drillAttempts.length === 0 && <tr><td colSpan={3} className="text-ink-muted text-center py-10 text-caption">无记录</td></tr>}
                    {drillAttempts.map((a: any, i: number) => (
                      <tr key={i}>
                        <td className={tdClass} style={{ maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.stem?.slice(0, 40) || a.question_id?.slice(0, 16)}</td>
                        <td className={tdClass}>{a.is_correct ? <span className="bg-success/15 text-success border border-success/20 rounded-full px-2 py-0.5 text-fine font-medium">正确</span> : <span className="bg-danger/15 text-danger border border-danger/20 rounded-full px-2 py-0.5 text-fine font-medium">错误</span>}</td>
                        <td className={tdClass}>{a.time_spent?.toFixed(1)}</td>
                        <td className={`${tdClass} font-mono text-fine text-ink-muted`}>{a.created_at?.slice(0, 16)}</td>
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
