"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, getCurrentUser, hasRole, type AdminUser } from "@/lib/api";

interface UserRow {
  id: string; username: string; email: string; display_name: string;
  role: string; is_active: boolean; last_login: string | null; created_at: string; avatar_url: string;
}
interface ListResp { items: UserRow[]; total: number; page: number; page_size: number; }

const ROLE_COLORS: Record<string, string> = {
  super_admin: "avatar-red",
  data_admin: "avatar-purple",
  analyst: "avatar-green",
  user: "avatar-gray",
};

export default function UsersPage() {
  const router = useRouter();
  const [me, setMe] = useState<AdminUser | null>(null);
  const [data, setData] = useState<ListResp | null>(null);
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [activeFilter, setActiveFilter] = useState("");
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

  useEffect(() => {
    const u = getCurrentUser();
    if (!u) { router.replace("/login"); return; }
    if (!hasRole(u.role, "super_admin")) { router.replace("/"); return; }
    setMe(u);
  }, [router]);

  const load = useCallback(async () => {
    setLoading(true); setErr("");
    try {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (role) params.set("role", role);
      if (activeFilter) params.set("is_active", activeFilter === "active" ? "true" : "false");
      params.set("page", String(page));
      params.set("page_size", "20");
      const d = await api.get<ListResp>(`/users?${params}`);
      setData(d);
    } catch (e: any) {
      setErr(e.message);
    } finally { setLoading(false); }
  }, [q, role, activeFilter, page]);

  useEffect(() => { if (me) load(); }, [me, load]);

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

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0;

  return (
    <div className="page">
      <h1>用户管理 {data && <span className="subtitle">共 {data.total} 人</span>}</h1>

      {err && <div className="card card-error">{err}</div>}

      {/* Toolbar */}
      <div className="toolbar">
        <input placeholder="搜索 username / email / display_name" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} style={{ minWidth: 260 }} />
        <select value={role} onChange={(e) => { setRole(e.target.value); setPage(1); }}>
          <option value="">全部角色</option>
          <option value="user">user</option>
          <option value="analyst">analyst</option>
          <option value="data_admin">data_admin</option>
          <option value="super_admin">super_admin</option>
        </select>
        <select value={activeFilter} onChange={(e) => { setActiveFilter(e.target.value); setPage(1); }}>
          <option value="">全部状态</option>
          <option value="active">活跃</option>
          <option value="banned">封禁</option>
        </select>
        <button className="btn-sm" onClick={() => load()}>刷新</button>
        <span className="spacer" />
        <button className="btn-sm btn-success" onClick={() => setModal("create")}>+ 创建用户</button>
      </div>

      {/* Bulk actions */}
      {selected.size > 0 && (
        <div className="alert alert-info flex" style={{ flexWrap: "wrap" }}>
          <span>已选 {selected.size} 人</span>
          <button className="action-btn action-btn-edit" onClick={() => bulkRole("analyst")}>设为 analyst</button>
          <button className="action-btn action-btn-edit" onClick={() => bulkRole("data_admin")}>设为 data_admin</button>
          <button className="action-btn action-btn-warn" onClick={() => bulkRole("super_admin")}>设为 super_admin</button>
          <button className="action-btn action-btn-danger" onClick={() => bulkBan(true)}>批量封禁</button>
          <button className="action-btn action-btn-edit" onClick={() => bulkBan(false)}>批量解封</button>
          <button className="btn-sm" onClick={() => setSelected(new Set())}>取消</button>
        </div>
      )}

      {/* Table */}
      <div className="card" style={{ padding: 0 }}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th style={{ width: 36 }}><input type="checkbox" checked={data ? selected.size === data.items.length && data.items.length > 0 : false} onChange={selectAll} /></th>
                <th>用户</th><th>角色</th><th>状态</th><th>最近登录</th><th style={{ textAlign: "right" }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {loading && <tr><td colSpan={6} className="muted" style={{ textAlign: "center", padding: 32 }}>加载中…</td></tr>}
              {!loading && data?.items.length === 0 && <tr><td colSpan={6} className="empty">无匹配用户</td></tr>}
              {data?.items.map((u) => (
                <tr key={u.id}>
                  <td><input type="checkbox" checked={selected.has(u.id)} onChange={() => toggleSelect(u.id)} /></td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div className={`avatar ${ROLE_COLORS[u.role] || "avatar-gray"}`}>
                        {(u.display_name || u.username || "?").charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <div style={{ fontWeight: 600, color: "#f1f5f9" }}>{u.username}</div>
                        <div style={{ fontSize: 11, color: "#64748b" }}>
                          {u.display_name && <span>{u.display_name} · </span>}
                          {u.email || "—"}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <select value={u.role} onChange={(e) => setRoleOf(u.id, e.target.value)}
                      style={{ padding: "3px 6px", background: "#0f172a", color: "#e2e8f0", border: "1px solid #2d3a4d", borderRadius: 4, fontSize: 12 }}>
                      <option value="user">user</option>
                      <option value="analyst">analyst</option>
                      <option value="data_admin">data_admin</option>
                      <option value="super_admin">super_admin</option>
                    </select>
                  </td>
                  <td>{u.is_active ? <span className="badge badge-active">活跃</span> : <span className="badge badge-inactive">封禁</span>}</td>
                  <td className="code muted">{u.last_login?.slice(0, 16) || "—"}</td>
                  <td style={{ textAlign: "right" }}>
                    <div className="flex" style={{ justifyContent: "flex-end" }}>
                      <button className="action-btn action-btn-view" onClick={() => openDetail(u)}>详情</button>
                      <button className="action-btn action-btn-warn" onClick={() => { setResetTarget({ id: u.id, username: u.username }); setNewPassword(""); setModal("resetPwd"); }}>重置密码</button>
                      {u.is_active ? (
                        <button className="action-btn action-btn-danger" onClick={() => toggleActive(u)}>封禁</button>
                      ) : (
                        <button className="action-btn action-btn-edit" onClick={() => toggleActive(u)}>解封</button>
                      )}
                      <button className="action-btn action-btn-danger" onClick={() => handleDeleteUser(u)}>注销</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data && totalPages > 1 && (
          <div className="pagination" style={{ padding: "12px 16px" }}>
            <span>第 {data.page}/{totalPages} 页 (共 {data.total} 条)</span>
            <button disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</button>
            <button disabled={page >= totalPages} onClick={() => setPage(page + 1)}>下一页</button>
          </div>
        )}
      </div>

      {/* Create User Modal */}
      {modal === "create" && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>创建新用户</h2>
            <form onSubmit={handleCreate}>
              <label>用户名 *</label>
              <input required value={createForm.username} onChange={(e) => setCreateForm({ ...createForm, username: e.target.value })} />
              <label>密码 *</label>
              <input required type="password" value={createForm.password} onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })} placeholder="至少4位" />
              <label>邮箱</label>
              <input value={createForm.email} onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })} />
              <label>显示名</label>
              <input value={createForm.display_name} onChange={(e) => setCreateForm({ ...createForm, display_name: e.target.value })} />
              <label>角色</label>
              <select value={createForm.role} onChange={(e) => setCreateForm({ ...createForm, role: e.target.value })}>
                <option value="user">user</option>
                <option value="analyst">analyst</option>
                <option value="data_admin">data_admin</option>
                <option value="super_admin">super_admin</option>
              </select>
              <div className="modal-actions">
                <button type="button" className="btn-sm" onClick={() => setModal(null)}>取消</button>
                <button type="submit" className="btn">创建</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Reset Password Modal */}
      {modal === "resetPwd" && resetTarget && (
        <div className="modal-overlay" onClick={() => { setModal(null); setResetTarget(null); }}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 400 }}>
            <h2>重置密码</h2>
            <p className="muted" style={{ marginBottom: 16 }}>为用户 <strong style={{ color: "#f1f5f9" }}>{resetTarget.username}</strong> 设置新密码</p>
            <form onSubmit={handleResetPwd}>
              <label>新密码 *</label>
              <input required type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="至少4位" minLength={4} />
              <div className="modal-actions">
                <button type="button" className="btn-sm" onClick={() => { setModal(null); setResetTarget(null); }}>取消</button>
                <button type="submit" className="btn btn-warning">确认重置</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* User Detail Modal */}
      {detailUser && (
        <div className="modal-overlay" onClick={() => { setDetailUser(null); setDetailData(null); }}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 600 }}>
            {/* Header */}
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
              <div className={`avatar ${ROLE_COLORS[detailUser.role] || "avatar-gray"}`} style={{ width: 44, height: 44, fontSize: 18 }}>
                {(detailUser.display_name || detailUser.username).charAt(0).toUpperCase()}
              </div>
              <div style={{ flex: 1 }}>
                <h2 style={{ margin: 0 }}>{detailUser.username}</h2>
                <span className={`role-pill role-${detailUser.role}`}>{detailUser.role}</span>
                {detailData?.online?.online ? (
                  <span className="badge badge-active" style={{ marginLeft: 6 }}>在线</span>
                ) : (
                  <span className="badge badge-inactive" style={{ marginLeft: 6 }}>离线</span>
                )}
              </div>
              <button className="btn-sm" onClick={() => { setDetailUser(null); setDetailData(null); }}>关闭</button>
            </div>

            {/* Tabs */}
            <div style={{ display: "flex", gap: 2, marginBottom: 16, background: "#0f172a", borderRadius: 8, padding: 3 }}>
              {[
                { key: "info" as const, label: "基本信息" },
                { key: "devices" as const, label: "登录设备" },
                { key: "history" as const, label: "登录历史" },
                { key: "ip" as const, label: "IP分析" },
              ].map(t => (
                <button key={t.key} onClick={() => setDetailTab(t.key)}
                  style={{
                    flex: 1, padding: "6px 0", borderRadius: 6, fontSize: 12, fontWeight: 500,
                    background: detailTab === t.key ? "#1e293b" : "transparent",
                    color: detailTab === t.key ? "#f1f5f9" : "#64748b",
                    border: "none", cursor: "pointer", transition: "all 0.15s",
                  }}>
                  {t.label}
                </button>
              ))}
            </div>

            {detailLoading ? (
              <p className="muted" style={{ textAlign: "center", padding: 20 }}>加载中…</p>
            ) : (
              <>
                {/* 基本信息 */}
                {detailTab === "info" && (
                  <table>
                    <tbody>
                      <tr><td className="muted" style={{ width: 90 }}>ID</td><td className="code">{detailUser.id}</td></tr>
                      <tr><td className="muted">邮箱</td><td>{detailUser.email || "—"}</td></tr>
                      <tr><td className="muted">显示名</td><td>{detailUser.display_name || "—"}</td></tr>
                      <tr><td className="muted">状态</td><td>{detailUser.is_active ? <span className="badge badge-active">活跃</span> : <span className="badge badge-inactive">封禁</span>}</td></tr>
                      <tr><td className="muted">在线</td><td>{detailData?.online?.online ? <span className="badge badge-ok">在线</span> : <span className="badge badge-inactive">离线</span>}</td></tr>
                      <tr><td className="muted">最近登录</td><td className="code">{detailUser.last_login || "从未"}</td></tr>
                      <tr><td className="muted">注册时间</td><td className="code">{detailUser.created_at?.slice(0, 16)}</td></tr>
                    </tbody>
                  </table>
                )}

                {/* 登录设备（活跃会话） */}
                {detailTab === "devices" && (
                  !detailData?.active_sessions?.length ? (
                    <p className="muted" style={{ textAlign: "center", padding: 20 }}>无活跃会话</p>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {detailData.active_sessions.map((s: any, i: number) => (
                        <div key={i} style={{
                          display: "flex", alignItems: "center", gap: 12,
                          padding: "10px 14px", background: "#0f172a", borderRadius: 8,
                          border: s.is_current ? "1px solid #2563eb" : "1px solid #1e293b",
                        }}>
                          <div style={{ fontSize: 20 }}>
                            {s.device_type === "mobile" ? "📱" : s.device_type === "tablet" ? "📟" : "💻"}
                          </div>
                          <div style={{ flex: 1 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                              <span style={{ fontWeight: 600, color: "#f1f5f9", fontSize: 13 }}>
                                {s.browser} · {s.os}
                              </span>
                              {s.is_current && <span className="badge badge-ok">当前</span>}
                            </div>
                            <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>
                              IP: {s.ip_address || "—"}
                              {s.city && ` · ${s.city}`}
                              {s.region && ` · ${s.region}`}
                              {s.country && ` · ${s.country}`}
                            </div>
                          </div>
                          <div style={{ fontSize: 11, color: "#475569" }}>
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
                    <p className="muted" style={{ textAlign: "center", padding: 20 }}>无登录记录</p>
                  ) : (
                    <div className="table-wrap" style={{ maxHeight: 360, overflowY: "auto" }}>
                      <table>
                        <thead>
                          <tr><th>时间</th><th>设备</th><th>浏览器</th><th>IP</th><th>区域</th></tr>
                        </thead>
                        <tbody>
                          {detailData.recent_logins.map((log: any, i: number) => (
                            <tr key={i}>
                              <td className="code" style={{ whiteSpace: "nowrap" }}>{log.created_at?.slice(0, 16)}</td>
                              <td>{log.device_type === "mobile" ? "📱 手机" : log.device_type === "tablet" ? "📟 平板" : "💻 电脑"}</td>
                              <td>{log.browser}</td>
                              <td className="code">{log.ip_address || "—"}</td>
                              <td>{[log.city, log.region, log.country].filter(Boolean).join(" · ") || "—"}</td>
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
                    <p className="muted" style={{ textAlign: "center", padding: 20 }}>无IP记录</p>
                  ) : (
                    <div className="table-wrap" style={{ maxHeight: 360, overflowY: "auto" }}>
                      <table>
                        <thead>
                          <tr><th>IP 地址</th><th>区域</th><th>登录次数</th><th>最近登录</th></tr>
                        </thead>
                        <tbody>
                          {detailData.ip_analysis.map((ip: any, i: number) => (
                            <tr key={i}>
                              <td className="code">{ip.ip_address}</td>
                              <td>{[ip.city, ip.region, ip.country].filter(Boolean).join(" · ") || "—"}</td>
                              <td><span className="badge badge-active">{ip.login_count}</span></td>
                              <td className="code">{ip.last_seen?.slice(0, 16)}</td>
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
