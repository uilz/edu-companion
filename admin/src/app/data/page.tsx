"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getCurrentUser, hasRole, type AdminUser } from "@/lib/api";

interface Overview {
  users_total: number; users_active: number;
  practice_sessions: number; conversations: number;
  questions: number; question_banks: number; explain_cards: number; materials: number;
  cognitive_nodes: number; cognitive_events: number;
}
interface SessionRow {
  id: string; user_id: string; username: string | null; status: string;
  total_count: number; correct_count: number; wrong_count: number;
  started_at: string | null; finished_at: string | null;
}
interface ListResp<T> { items: T[]; total: number; page: number; page_size: number; }

export default function DataPage() {
  const router = useRouter();
  const [me, setMe] = useState<AdminUser | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [sessions, setSessions] = useState<ListResp<SessionRow> | null>(null);
  const [convs, setConvs] = useState<ListResp<any> | null>(null);
  const [tab, setTab] = useState<"overview" | "sessions" | "conversations">("overview");
  const [err, setErr] = useState("");

  useEffect(() => {
    const u = getCurrentUser();
    if (!u) { router.replace("/login"); return; }
    if (!hasRole(u.role, "data_admin")) { router.replace("/"); return; }
    setMe(u);
  }, [router]);

  useEffect(() => {
    if (!me) return;
    Promise.all([
      api.get<Overview>("/data/overview"),
      api.get<ListResp<SessionRow>>(`/data/practice-sessions?page_size=20`),
      api.get<ListResp<any>>(`/data/conversations?page_size=20`),
    ]).then(([o, s, c]) => {
      setOverview(o);
      setSessions(s);
      setConvs(c);
    }).catch((e) => setErr(e.message));
  }, [me]);

  return (
    <div className="page">
      <h1>全局数据</h1>

      {err && <div className="card" style={{ borderColor: "#7f1d1d", color: "#fca5a5" }}>{err}</div>}

      <div className="toolbar">
        <button className={tab === "overview" ? "btn-sm" : "btn-sm"} onClick={() => setTab("overview")} style={tab === "overview" ? { background: "#2563eb", color: "#fff" } : {}}>概览</button>
        <button onClick={() => setTab("sessions")} className="btn-sm" style={tab === "sessions" ? { background: "#2563eb", color: "#fff" } : {}}>跨用户练习 ({sessions?.total ?? 0})</button>
        <button onClick={() => setTab("conversations")} className="btn-sm" style={tab === "conversations" ? { background: "#2563eb", color: "#fff" } : {}}>跨用户会话 ({convs?.total ?? 0})</button>
      </div>

      {tab === "overview" && overview && (
        <div className="kpi-grid">
          {Object.entries(overview).map(([k, v]) => (
            <div className="kpi" key={k}>
              <div className="label">{k}</div>
              <div className="value">{v}</div>
            </div>
          ))}
        </div>
      )}

      {tab === "sessions" && sessions && (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>用户</th>
                <th>状态</th>
                <th>题数</th>
                <th>对/错</th>
                <th>开始</th>
                <th>结束</th>
              </tr>
            </thead>
            <tbody>
              {sessions.items.length === 0 && <tr><td colSpan={7} className="muted">无数据</td></tr>}
              {sessions.items.map((s) => (
                <tr key={s.id}>
                  <td className="code">{s.id.slice(0, 14)}…</td>
                  <td>{s.username || s.user_id}</td>
                  <td><span className="code">{s.status}</span></td>
                  <td>{s.total_count}</td>
                  <td><span style={{ color: "#6ee7b7" }}>{s.correct_count}</span> / <span style={{ color: "#fca5a5" }}>{s.wrong_count}</span></td>
                  <td className="code muted">{s.started_at?.slice(0, 19) || "—"}</td>
                  <td className="code muted">{s.finished_at?.slice(0, 19) || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "conversations" && convs && (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>用户</th>
                <th>会话数</th>
                <th>更新时间</th>
              </tr>
            </thead>
            <tbody>
              {convs.items.length === 0 && <tr><td colSpan={3} className="muted">无数据</td></tr>}
              {convs.items.map((c: any, i: number) => (
                <tr key={i}>
                  <td className="code">{c.user_id}</td>
                  <td>{c.conv_count}</td>
                  <td className="code muted">{c.updated_at || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
