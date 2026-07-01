"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, hasRole } from "@/lib/api";
import { useAuthGuard } from "@/lib/use-auth-guard";
import type { UserRow, PaginatedResponse } from "@/lib/types";

const ROLE_COLORS: Record<string, string> = {
  super_admin: "bg-[#dc2626]",
  data_admin: "bg-[#7c3aed]",
  analyst: "bg-[#059669]",
  user: "bg-[#475569]",
};

/** 把 ISO 时间格式化为"X 分钟前"的相对时间（基于浏览器本地时间） */
function formatLastActive(iso: string | null | undefined): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (isNaN(t)) return "—";
  const diffSec = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (diffSec < 60) return "刚刚";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} 分钟前`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} 小时前`;
  // 超过 1 天直接显示日期
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function UsersPage() {
  const { ready, user } = useAuthGuard();
  const [data, setData] = useState<PaginatedResponse<UserRow> | null>(null);
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [activeFilter, setActiveFilter] = useState("");
  const [onlineFilter, setOnlineFilter] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  // Modal state
  const [modal, setModal] = useState<"create" | "resetPwd" | null>(null);
  const [createForm, setCreateForm] = useState({ username: "", password: "", email: "", display_name: "", role: "user" });
  const [resetTarget, setResetTarget] = useState<{ id: string; username: string } | null>(null);
  const [newPassword, setNewPassword] = useState("");

  // Detail modal
  const [detailUser, setDetailUser] = useState<UserRow | null>(null);
  const [detailData, setDetailData] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailTab, setDetailTab] = useState<"info" | "devices" | "history" | "ip">("info");

  // 30 秒轮询：拉取最新在线状态
  const POLL_INTERVAL_MS = 30_000;

  const load = useCallback(async () => {
    setLoading(true); setErr("");
    try {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (role) params.set("role", role);
      if (activeFilter) params.set("is_active", activeFilter === "active" ? "true" : "false");
      if (onlineFilter) params.set("is_online", onlineFilter === "online" ? "true" : "false");
      params.set("page", String(page));
      params.set("page_size", "20");
      const d = await api.get<PaginatedResponse<UserRow>>(`/users?${params}`);
      setData(d);
    } catch (e: any) {
      setErr(e.message);
    } finally { setLoading(false); }
  }, [q, role, activeFilter, onlineFilter, page]);

  useEffect(() => {
    if (!ready || !user || !hasRole(user.role, "super_admin")) return;
    load();
    const t = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(t);
  }, [ready, user, load]);

  if (!ready) return <div className="py-20 text-center text-ink-muted">加载中…</div>;
  if (!user || !hasRole(user.role, "super_admin")) return null;

  async function setRoleOf(id: string, newRole: string) {
    if (!confirm(`将用户 ${id.slice(0, 12)} 角色改为 ${newRole}？`)) return;
    try { await api.patch(`/users/${id}`, { role: newRole }); load(); }
    catch (e: any) { alert("失败: " + e.message); }
  }

  async function toggleActive(u: UserRow) {
    if (!confirm(`${u.is_active ? "封禁" : "解封"} ${u.username}？`)) return;
    try { await api.post(`/users/${u.id}/${u.is_active ? "ban" : "unban"}`); load(); }
    catch (e: any) { alert("失败: " + e.message); }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.post("/users/create", createForm);
      setModal(null);
      setCreateForm({ username: "", password: "", email: "", display_name: "", role: "user" });
      load();
    } catch (e: any) { alert("创建失败: " + e.message); }
  }

  async function handleResetPwd(e: React.FormEvent) {
    e.preventDefault();
    if (!resetTarget) return;
    try {
      await api.post(`/users/${resetTarget.id}/reset-pwd`, { new_password: newPassword });
      setModal(null);
      setResetTarget(null);
      setNewPassword("");
      alert(`已重置 ${resetTarget.username} 的密码`);
    } catch (e: any) { alert("重置失败: " + e.message); }
  }

  async function handleDeleteUser(u: UserRow) {
    if (!confirm(`确认注销用户 ${u.username}？此操作不可恢复。`)) return;
    try {
      await api.delete(`/users/${u.id}`);
      load();
    } catch (e: any) { alert("注销失败: " + e.message); }
  }

  async function openDetail(u: UserRow) {
    setDetailUser(u);
    setDetailLoading(true);
    setDetailData(null);
    setDetailTab("info");
    try {
      const r = await api.get<any>(`/users/${u.id}/login-log?limit=50`);
      setDetailData(r);
    } catch { setDetailData(null); }
    setDetailLoading(false);
  }

  function selectAll() {
    if (!data) return;
    if (selected.size === data.items.length) setSelected(new Set());
    else setSelected(new Set(data.items.map((i) => i.id)));
  }

  function toggleSelect(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelected(next);
  }

  async function bulkRole(newRole: string) {
    if (!selected.size || !confirm(`批量修改 ${selected.size} 个用户角色为 ${newRole}？`)) return;
    try { await api.post("/users/bulk/role", { user_ids: Array.from(selected), role: newRole }); setSelected(new Set()); load(); }
    catch (e: any) { alert("失败: " + e.message); }
  }

  async function bulkBan(ban: boolean) {
    if (!selected.size || !confirm(`${ban ? "封禁" : "解封"} ${selected.size} 个用户？`)) return;
    try { await api.post(`/users/bulk/${ban ? "ban" : "unban"}`, { user_ids: Array.from(selected) }); setSelected(new Set()); load(); }
    catch (e: any) { alert("失败: " + e.message); }
  }

  async function bulkDelete() {
    if (!selected.size || !confirm(`确认删除 ${selected.size} 个用户？此操作不可恢复！`)) return;
    try { await api.post("/users/bulk/delete", { user_ids: Array.from(selected) }); setSelected(new Set()); load(); }
    catch (e: any) { alert("删除失败: " + e.message); }
  }

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0;

  // ── reusable class snippets ──
  const thClass = "px-3.5 py-2.5 text-left border-b border-divider text-fine text-ink-muted font-semibold uppercase tracking-wide bg-page sticky top-0";
  const tdClass = "px-3.5 py-2.5 border-b border-divider text-caption text-ink-secondary";
  const inputClass = "px-3 py-1.5 bg-input text-ink-primary border border-divider rounded-md text-caption focus:outline-none focus:border-accent";

  return (
    <div>
      <h1 className="text-heading mb-5">用户管理 {data && <span className="text-caption text-ink-muted ml-2">共 {data.total} 人</span>}</h1>

      {err && <div className="bg-danger/10 border border-danger/20 text-danger rounded-lg p-4 mb-4">{err}</div>}

      {/* Toolbar */}
      <div className="flex gap-2 items-center mb-3.5 flex-wrap">
        <input className={inputClass} placeholder="搜索 username / email / display_name" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} style={{ minWidth: 260 }} />
        <select className={inputClass} value={role} onChange={(e) => { setRole(e.target.value); setPage(1); }}>
          <option value="">全部角色</option>
          <option value="user">user</option>
          <option value="analyst">analyst</option>
          <option value="data_admin">data_admin</option>
          <option value="super_admin">super_admin</option>
        </select>
        <select className={inputClass} value={activeFilter} onChange={(e) => { setActiveFilter(e.target.value); setPage(1); }}>
          <option value="">全部状态</option>
          <option value="active">活跃</option>
          <option value="banned">封禁</option>
        </select>
        <select className={inputClass} value={onlineFilter} onChange={(e) => { setOnlineFilter(e.target.value); setPage(1); }}>
          <option value="">全部在线</option>
          <option value="online">在线</option>
          <option value="offline">离线</option>
        </select>
        <button className="px-3 py-1 bg-surface border border-divider rounded-md text-fine text-ink-secondary hover:bg-surface-hover transition-colors" onClick={() => load()}>刷新</button>
        <span className="flex-1" />
        <button className="px-3 py-1 bg-success text-black rounded-md text-fine font-medium hover:brightness-90 transition-colors" onClick={() => setModal("create")}>+ 创建用户</button>
      </div>

      {/* Bulk actions */}
      {selected.size > 0 && (
        <div className="flex flex-wrap items-center gap-2.5 bg-accent/10 border border-accent/20 text-accent rounded-lg p-3 mb-4">
          <span>已选 {selected.size} 人</span>
          <button className="px-2.5 py-1 rounded-md text-fine font-medium bg-success/15 text-success border border-success/20 hover:brightness-90 transition-colors" onClick={() => bulkRole("analyst")}>设为 analyst</button>
          <button className="px-2.5 py-1 rounded-md text-fine font-medium bg-success/15 text-success border border-success/20 hover:brightness-90 transition-colors" onClick={() => bulkRole("data_admin")}>设为 data_admin</button>
          <button className="px-2.5 py-1 rounded-md text-fine font-medium bg-warning/15 text-warning border border-warning/20 hover:brightness-90 transition-colors" onClick={() => bulkRole("super_admin")}>设为 super_admin</button>
          <button className="px-2.5 py-1 rounded-md text-fine font-medium bg-danger/15 text-danger border border-danger/20 hover:brightness-90 transition-colors" onClick={() => bulkBan(true)}>批量封禁</button>
          <button className="px-2.5 py-1 rounded-md text-fine font-medium bg-success/15 text-success border border-success/20 hover:brightness-90 transition-colors" onClick={() => bulkBan(false)}>批量解封</button>
          <button className="px-2.5 py-1 rounded-md text-fine font-medium bg-danger/15 text-danger border border-danger/20 hover:brightness-90 transition-colors" onClick={bulkDelete}>批量注销</button>
          <button className="px-3 py-1 bg-surface border border-divider rounded-md text-fine text-ink-secondary hover:bg-surface-hover transition-colors" onClick={() => setSelected(new Set())}>取消</button>
        </div>
      )}

      {/* Table */}
      <div className="bg-surface border border-divider rounded-lg mb-4 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                <th className={thClass} style={{ width: 36 }}><input type="checkbox" checked={data ? selected.size === data.items.length && data.items.length > 0 : false} onChange={selectAll} /></th>
                <th className={thClass}>用户</th><th className={thClass}>角色</th><th className={thClass}>状态</th><th className={thClass}>在线</th><th className={thClass}>上次活跃</th><th className={thClass}>最近登录</th><th className={`${thClass} text-right`}>操作</th>
              </tr>
            </thead>
            <tbody>
              {loading && <tr><td colSpan={8} className="text-ink-muted text-center py-8 text-caption">加载中…</td></tr>}
              {!loading && data?.items.length === 0 && <tr><td colSpan={8} className="text-ink-muted text-center py-10 text-caption">无匹配用户</td></tr>}
              {data?.items.map((u) => (
                <tr key={u.id} className="group">
                  <td className={tdClass}><input type="checkbox" checked={selected.has(u.id)} onChange={() => toggleSelect(u.id)} /></td>
                  <td className={tdClass}>
                    <div className="flex items-center gap-2.5">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-bold shrink-0 ${ROLE_COLORS[u.role] || "bg-[#475569]"}`}>
                        {(u.display_name || u.username || "?").charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <div className="font-semibold text-ink-primary">{u.username}</div>
                        <div className="text-[11px] text-ink-muted">
                          {u.display_name && <span>{u.display_name} · </span>}
                          {u.email || "—"}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className={tdClass}>
                    <select value={u.role} onChange={(e) => setRoleOf(u.id, e.target.value)}
                      className="px-1.5 py-0.5 bg-input text-ink-primary border border-divider rounded text-fine focus:outline-none focus:border-accent">
                      <option value="user">user</option>
                      <option value="analyst">analyst</option>
                      <option value="data_admin">data_admin</option>
                      <option value="super_admin">super_admin</option>
                    </select>
                  </td>
                  <td className={tdClass}>{u.is_active ? <span className="bg-success/15 text-success border border-success/20 rounded-full px-2 py-0.5 text-fine font-medium">活跃</span> : <span className="bg-danger/15 text-danger border border-danger/20 rounded-full px-2 py-0.5 text-fine font-medium">封禁</span>}</td>
                  <td className={tdClass}>
                    {u.is_online ? (
                      <span className="inline-flex items-center gap-1.5 bg-success/15 text-success border border-success/20 rounded-full px-2 py-0.5 text-fine font-medium whitespace-nowrap">
                        <span className="w-1.5 h-1.5 rounded-full bg-success" />
                        在线
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 bg-ink-muted/15 text-ink-muted border border-divider rounded-full px-2 py-0.5 text-fine font-medium whitespace-nowrap">
                        <span className="w-1.5 h-1.5 rounded-full bg-ink-muted" />
                        离线
                      </span>
                    )}
                  </td>
                  <td className={`${tdClass} font-mono text-fine text-ink-muted whitespace-nowrap`} title={u.last_active_at || ""}>
                    {formatLastActive(u.last_active_at)}
                  </td>
                  <td className={`${tdClass} font-mono text-fine text-ink-muted whitespace-nowrap`}>{u.last_login?.slice(0, 16) || "—"}</td>
                  <td className={`${tdClass} text-right`}>
                    <div className="flex items-center gap-1.5 justify-end">
                      <button className="px-2.5 py-1 rounded-md text-fine font-medium bg-accent/15 text-accent border border-accent/20 hover:brightness-90 transition-colors" onClick={() => openDetail(u)}>详情</button>
                      <button className="px-2.5 py-1 rounded-md text-fine font-medium bg-warning/15 text-warning border border-warning/20 hover:brightness-90 transition-colors" onClick={() => { setResetTarget({ id: u.id, username: u.username }); setNewPassword(""); setModal("resetPwd"); }}>重置密码</button>
                      {u.is_active ? (
                        <button className="px-2.5 py-1 rounded-md text-fine font-medium bg-danger/15 text-danger border border-danger/20 hover:brightness-90 transition-colors" onClick={() => toggleActive(u)}>封禁</button>
                      ) : (
                        <button className="px-2.5 py-1 rounded-md text-fine font-medium bg-success/15 text-success border border-success/20 hover:brightness-90 transition-colors" onClick={() => toggleActive(u)}>解封</button>
                      )}
                      <button className="px-2.5 py-1 rounded-md text-fine font-medium bg-danger/15 text-danger border border-danger/20 hover:brightness-90 transition-colors" onClick={() => handleDeleteUser(u)}>注销</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data && totalPages > 1 && (
          <div className="flex justify-end items-center gap-2 py-3 px-4 text-caption text-ink-muted border-t border-divider">
            <span>第 {data.page}/{totalPages} 页 (共 {data.total} 条)</span>
            <button className={`px-2.5 py-1 rounded-md text-fine border border-divider ${page <= 1 ? "text-ink-muted opacity-50 cursor-not-allowed" : "text-ink-secondary hover:bg-surface-hover transition-colors"}`} disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</button>
            <button className={`px-2.5 py-1 rounded-md text-fine border border-divider ${page >= totalPages ? "text-ink-muted opacity-50 cursor-not-allowed" : "text-ink-secondary hover:bg-surface-hover transition-colors"}`} disabled={page >= totalPages} onClick={() => setPage(page + 1)}>下一页</button>
          </div>
        )}
      </div>

      {/* Create User Modal */}
      {modal === "create" && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in" onClick={() => setModal(null)}>
          <div className="bg-surface-elevated border border-divider rounded-xl w-[90%] max-w-[560px] max-h-[80vh] overflow-y-auto p-7 shadow-md animate-slide-up" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-5 text-heading font-semibold text-ink-primary">创建新用户</h2>
            <form onSubmit={handleCreate}>
              <label className="block mt-3.5 mb-1 text-fine text-ink-secondary font-medium">用户名 *</label>
              <input className="w-full px-3 py-2.5 bg-input text-ink-primary border border-divider rounded-md text-body focus:outline-none focus:border-accent" required value={createForm.username} onChange={(e) => setCreateForm({ ...createForm, username: e.target.value })} />
              <label className="block mt-3.5 mb-1 text-fine text-ink-secondary font-medium">密码 *</label>
              <input className="w-full px-3 py-2.5 bg-input text-ink-primary border border-divider rounded-md text-body focus:outline-none focus:border-accent" required type="password" value={createForm.password} onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })} placeholder="至少4位" />
              <label className="block mt-3.5 mb-1 text-fine text-ink-secondary font-medium">邮箱</label>
              <input className="w-full px-3 py-2.5 bg-input text-ink-primary border border-divider rounded-md text-body focus:outline-none focus:border-accent" value={createForm.email} onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })} />
              <label className="block mt-3.5 mb-1 text-fine text-ink-secondary font-medium">显示名</label>
              <input className="w-full px-3 py-2.5 bg-input text-ink-primary border border-divider rounded-md text-body focus:outline-none focus:border-accent" value={createForm.display_name} onChange={(e) => setCreateForm({ ...createForm, display_name: e.target.value })} />
              <label className="block mt-3.5 mb-1 text-fine text-ink-secondary font-medium">角色</label>
              <select className="w-full px-3 py-2.5 bg-input text-ink-primary border border-divider rounded-md text-body focus:outline-none focus:border-accent" value={createForm.role} onChange={(e) => setCreateForm({ ...createForm, role: e.target.value })}>
                <option value="user">user</option>
                <option value="analyst">analyst</option>
                <option value="data_admin">data_admin</option>
                <option value="super_admin">super_admin</option>
              </select>
              <div className="flex gap-2 justify-end mt-6">
                <button type="button" className="px-3 py-1 bg-surface border border-divider rounded-md text-fine text-ink-secondary hover:bg-surface-hover transition-colors" onClick={() => setModal(null)}>取消</button>
                <button type="submit" className="px-4 py-2 bg-accent text-white rounded-md text-caption font-medium hover:bg-accent-hover transition-colors">创建</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Reset Password Modal */}
      {modal === "resetPwd" && resetTarget && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in" onClick={() => { setModal(null); setResetTarget(null); }}>
          <div className="bg-surface-elevated border border-divider rounded-xl w-[90%] max-w-[400px] max-h-[80vh] overflow-y-auto p-7 shadow-md animate-slide-up" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-5 text-heading font-semibold text-ink-primary">重置密码</h2>
            <p className="text-ink-muted text-caption mb-4">为用户 <strong className="text-ink-primary">{resetTarget.username}</strong> 设置新密码</p>
            <form onSubmit={handleResetPwd}>
              <label className="block mt-3.5 mb-1 text-fine text-ink-secondary font-medium">新密码 *</label>
              <input className="w-full px-3 py-2.5 bg-input text-ink-primary border border-divider rounded-md text-body focus:outline-none focus:border-accent" required type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="至少4位" minLength={4} />
              <div className="flex gap-2 justify-end mt-6">
                <button type="button" className="px-3 py-1 bg-surface border border-divider rounded-md text-fine text-ink-secondary hover:bg-surface-hover transition-colors" onClick={() => { setModal(null); setResetTarget(null); }}>取消</button>
                <button type="submit" className="px-4 py-2 bg-warning text-black rounded-md text-caption font-medium hover:brightness-90 transition-colors">确认重置</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* User Detail Modal */}
      {detailUser && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in" onClick={() => { setDetailUser(null); setDetailData(null); }}>
          <div className="bg-surface-elevated border border-divider rounded-xl w-[90%] max-w-[600px] max-h-[80vh] overflow-y-auto p-7 shadow-md animate-slide-up" onClick={(e) => e.stopPropagation()}>
            {/* Header */}
            <div className="flex items-center gap-3 mb-4">
              <div className={`w-11 h-11 rounded-full flex items-center justify-center text-white text-lg font-bold shrink-0 ${ROLE_COLORS[detailUser.role] || "bg-[#475569]"}`}>
                {(detailUser.display_name || detailUser.username).charAt(0).toUpperCase()}
              </div>
              <div className="flex-1">
                <h2 className="m-0 text-heading">{detailUser.username}</h2>
                <span className={`inline-block mt-0.5 px-2 py-0.5 rounded-full text-fine font-semibold ${
                  detailUser.role === "super_admin" ? "bg-[#dc2626]/20 text-[#fca5a5]" :
                  detailUser.role === "data_admin" ? "bg-[#7c3aed]/20 text-[#c4b5fd]" :
                  detailUser.role === "analyst" ? "bg-[#059669]/20 text-[#6ee7b7]" :
                  "bg-[#475569]/20 text-[#94a3b8]"
                }`}>{detailUser.role}</span>
                {detailData?.online?.online ? (
                  <span className="ml-1.5 bg-success/15 text-success border border-success/20 rounded-full px-2 py-0.5 text-fine font-medium">在线</span>
                ) : (
                  <span className="ml-1.5 bg-danger/15 text-danger border border-danger/20 rounded-full px-2 py-0.5 text-fine font-medium">离线</span>
                )}
              </div>
              <button className="px-3 py-1 bg-surface border border-divider rounded-md text-fine text-ink-secondary hover:bg-surface-hover transition-colors" onClick={() => { setDetailUser(null); setDetailData(null); }}>关闭</button>
            </div>

            {/* Tabs */}
            <div className="flex gap-0.5 mb-4 bg-input rounded-lg p-0.5">
              {[
                { key: "info" as const, label: "基本信息" },
                { key: "devices" as const, label: "登录设备" },
                { key: "history" as const, label: "登录历史" },
                { key: "ip" as const, label: "IP分析" },
              ].map(t => (
                <button key={t.key} onClick={() => setDetailTab(t.key)}
                  className={`flex-1 py-1.5 rounded-md text-fine font-medium border-none cursor-pointer transition-colors ${
                    detailTab === t.key ? "bg-surface-elevated text-ink-primary" : "bg-transparent text-ink-muted hover:text-ink-secondary"
                  }`}>
                  {t.label}
                </button>
              ))}
            </div>

            {detailLoading ? (
              <p className="text-ink-muted text-center py-5 text-caption">加载中…</p>
            ) : (
              <>
                {/* 基本信息 */}
                {detailTab === "info" && (
                  <table className="w-full border-collapse">
                    <tbody>
                      <tr><td className="px-3.5 py-2.5 border-b border-divider text-caption text-ink-muted" style={{ width: 90 }}>ID</td><td className="px-3.5 py-2.5 border-b border-divider text-caption text-ink-secondary font-mono text-fine">{detailUser.id}</td></tr>
                      <tr><td className="px-3.5 py-2.5 border-b border-divider text-caption text-ink-muted">邮箱</td><td className="px-3.5 py-2.5 border-b border-divider text-caption text-ink-secondary">{detailUser.email || "—"}</td></tr>
                      <tr><td className="px-3.5 py-2.5 border-b border-divider text-caption text-ink-muted">显示名</td><td className="px-3.5 py-2.5 border-b border-divider text-caption text-ink-secondary">{detailUser.display_name || "—"}</td></tr>
                      <tr><td className="px-3.5 py-2.5 border-b border-divider text-caption text-ink-muted">状态</td><td className="px-3.5 py-2.5 border-b border-divider text-caption text-ink-secondary">{detailUser.is_active ? <span className="bg-success/15 text-success border border-success/20 rounded-full px-2 py-0.5 text-fine font-medium">活跃</span> : <span className="bg-danger/15 text-danger border border-danger/20 rounded-full px-2 py-0.5 text-fine font-medium">封禁</span>}</td></tr>
                      <tr><td className="px-3.5 py-2.5 border-b border-divider text-caption text-ink-muted">在线</td><td className="px-3.5 py-2.5 border-b border-divider text-caption text-ink-secondary">{detailData?.online?.online ? <span className="bg-success/15 text-success border border-success/20 rounded-full px-2 py-0.5 text-fine font-medium">在线</span> : <span className="bg-danger/15 text-danger border border-danger/20 rounded-full px-2 py-0.5 text-fine font-medium">离线</span>}</td></tr>
                      <tr><td className="px-3.5 py-2.5 border-b border-divider text-caption text-ink-muted">最近登录</td><td className="px-3.5 py-2.5 border-b border-divider text-caption text-ink-secondary font-mono text-fine">{detailUser.last_login || "从未"}</td></tr>
                      <tr><td className="px-3.5 py-2.5 border-b border-divider text-caption text-ink-muted">注册时间</td><td className="px-3.5 py-2.5 border-b border-divider text-caption text-ink-secondary font-mono text-fine">{detailUser.created_at?.slice(0, 16)}</td></tr>
                    </tbody>
                  </table>
                )}

                {/* 登录设备（活跃会话） */}
                {detailTab === "devices" && (
                  !detailData?.active_sessions?.length ? (
                    <p className="text-ink-muted text-center py-10 text-caption">无活跃会话</p>
                  ) : (
                    <div className="flex flex-col gap-2">
                      {detailData.active_sessions.map((s: any, i: number) => (
                        <div key={i} className={`flex items-center gap-3 px-3.5 py-2.5 bg-input rounded-lg border ${s.is_current ? "border-accent" : "border-divider"}`}>
                          <div className="text-xl">
                            {s.device_type === "mobile" ? "📱" : s.device_type === "tablet" ? "📟" : "💻"}
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center gap-1.5">
                              <span className="font-semibold text-ink-primary text-[13px]">
                                {s.browser} · {s.os}
                              </span>
                              {s.is_current && <span className="bg-success/15 text-success border border-success/20 rounded-full px-2 py-0.5 text-fine font-medium">当前</span>}
                            </div>
                            <div className="text-[11px] text-ink-muted mt-0.5">
                              IP: {s.ip_address || "—"}
                              {s.city && ` · ${s.city}`}
                              {s.region && ` · ${s.region}`}
                              {s.country && ` · ${s.country}`}
                            </div>
                          </div>
                          <div className="text-[11px] text-ink-muted">
                            {s.created_at?.slice(0, 16)}
                          </div>
                        </div>
                      ))}
                    </div>
                  )
                )}

                {/* 登录历史 */}
                {detailTab === "history" && (
                  !detailData?.recent_logins?.length ? (
                    <p className="text-ink-muted text-center py-10 text-caption">无登录记录</p>
                  ) : (
                    <div className="overflow-x-auto" style={{ maxHeight: 360, overflowY: "auto" }}>
                      <table className="w-full border-collapse">
                        <thead>
                          <tr><th className={thClass}>时间</th><th className={thClass}>设备</th><th className={thClass}>浏览器</th><th className={thClass}>IP</th><th className={thClass}>区域</th></tr>
                        </thead>
                        <tbody>
                          {detailData.recent_logins.map((log: any, i: number) => (
                            <tr key={i}>
                              <td className={`${tdClass} font-mono text-fine whitespace-nowrap`}>{log.created_at?.slice(0, 16)}</td>
                              <td className={tdClass}>{log.device_type === "mobile" ? "📱 手机" : log.device_type === "tablet" ? "📟 平板" : "💻 电脑"}</td>
                              <td className={tdClass}>{log.browser}</td>
                              <td className={`${tdClass} font-mono text-fine`}>{log.ip_address || "—"}</td>
                              <td className={tdClass}>{[log.city, log.region, log.country].filter(Boolean).join(" · ") || "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )
                )}

                {/* IP 分析 */}
                {detailTab === "ip" && (
                  !detailData?.ip_analysis?.length ? (
                    <p className="text-ink-muted text-center py-10 text-caption">无IP记录</p>
                  ) : (
                    <div className="overflow-x-auto" style={{ maxHeight: 360, overflowY: "auto" }}>
                      <table className="w-full border-collapse">
                        <thead>
                          <tr><th className={thClass}>IP 地址</th><th className={thClass}>区域</th><th className={thClass}>登录次数</th><th className={thClass}>最近登录</th></tr>
                        </thead>
                        <tbody>
                          {detailData.ip_analysis.map((ip: any, i: number) => (
                            <tr key={i}>
                              <td className={`${tdClass} font-mono text-fine`}>{ip.ip_address}</td>
                              <td className={tdClass}>{[ip.city, ip.region, ip.country].filter(Boolean).join(" · ") || "—"}</td>
                              <td className={tdClass}><span className="bg-success/15 text-success border border-success/20 rounded-full px-2 py-0.5 text-fine font-medium">{ip.login_count}</span></td>
                              <td className={`${tdClass} font-mono text-fine`}>{ip.last_seen?.slice(0, 16)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
