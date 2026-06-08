"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, getCurrentUser, hasRole, type AdminUser } from "@/lib/api";

interface UserRow {
  id: string;
  username: string;
  email: string;
  display_name: string;
  role: string;
  is_active: boolean;
  last_login: string | null;
  created_at: string;
}

interface ListResp { items: UserRow[]; total: number; page: number; page_size: number; }

export default function UsersPage() {
  const router = useRouter();
  const [me, setMe] = useState<AdminUser | null>(null);
  const [data, setData] = useState<ListResp | null>(null);
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  // 鉴权
  useEffect(() => {
    const u = getCurrentUser();
    if (!u) { router.replace("/login"); return; }
    if (!hasRole(u.role, "super_admin")) { router.replace("/"); return; }
    setMe(u);
  }, [router]);

  useEffect(() => {
    if (!me) return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [me, q, role]);

  async function load() {
    setLoading(true);
    setErr("");
    try {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (role) params.set("role", role);
      const d = await api.get<ListResp>(`/users?${params}`);
      setData(d);
    } catch (e: any) {
      if (e instanceof ApiError && e.status === 403) {
        setErr("需要 super_admin 权限");
      } else {
        setErr(e.message);
      }
    } finally {
      setLoading(false);
    }
  }

  async function setRoleOf(id: string, newRole: string) {
    if (!confirm(`将用户 ${id} 角色改为 ${newRole}？`)) return;
    try {
      await api.patch(`/users/${id}/role`, { role: newRole });
      await load();
    } catch (e: any) {
      alert("失败: " + e.message);
    }
  }

  async function toggleActive(u: UserRow) {
    if (!confirm(`${u.is_active ? "封禁" : "解封"} ${u.username}？`)) return;
    try {
      await api.post(`/users/${u.id}/${u.is_active ? "ban" : "unban"}`);
      await load();
    } catch (e: any) {
      alert("失败: " + e.message);
    }
  }

  return (
    <div className="page">
      <h1>用户管理 <span className="muted">({data?.total ?? "…"} 人)</span></h1>

      <div className="toolbar">
        <input
          placeholder="搜索 username / email / display_name"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ minWidth: 280 }}
        />
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="">全部角色</option>
          <option value="user">user</option>
          <option value="analyst">analyst</option>
          <option value="data_admin">data_admin</option>
          <option value="super_admin">super_admin</option>
        </select>
        <button className="btn-sm" onClick={load}>刷新</button>
      </div>

      {err && <div className="card" style={{ borderColor: "#7f1d1d", color: "#fca5a5" }}>{err}</div>}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>用户名</th>
              <th>邮箱</th>
              <th>角色</th>
              <th>状态</th>
              <th>最近登录</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={7} className="muted">加载中…</td></tr>}
            {!loading && data?.items.length === 0 && (
              <tr><td colSpan={7} className="muted">无数据</td></tr>
            )}
            {data?.items.map((u) => (
              <tr key={u.id}>
                <td className="code">{u.id.slice(0, 12)}…</td>
                <td><b>{u.username}</b>{u.display_name && <span className="muted"> ({u.display_name})</span>}</td>
                <td className="muted">{u.email || "—"}</td>
                <td>
                  <select value={u.role} onChange={(e) => setRoleOf(u.id, e.target.value)}>
                    <option value="user">user</option>
                    <option value="analyst">analyst</option>
                    <option value="data_admin">data_admin</option>
                    <option value="super_admin">super_admin</option>
                  </select>
                </td>
                <td>
                  {u.is_active
                    ? <span className="badge badge-active">active</span>
                    : <span className="badge badge-inactive">banned</span>}
                </td>
                <td className="code muted">{u.last_login || "—"}</td>
                <td>
                  <button className="btn-sm" onClick={() => toggleActive(u)}>
                    {u.is_active ? "封禁" : "解封"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
