"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { setSession, type AdminRole, type AdminUser } from "@/lib/api";

/**
 * 登录页
 * - 通过认证网关 18001 取 JWT
 * - 仅 super_admin / data_admin / analyst 可使用管理后台
 */
export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      const res = await fetch("http://127.0.0.1:18001/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(`登录失败: ${res.status} ${t.slice(0, 100)}`);
      }
      const data = await res.json();
      const token: string = data.access_token;
      const u = data.user || {};
      const role: AdminRole = (u.role || "user") as AdminRole;

      if (!["super_admin", "data_admin", "analyst"].includes(role)) {
        throw new Error(`角色 ${role} 无管理后台权限`);
      }

      const user: AdminUser = {
        user_id: u.id || u.username || username,
        username: u.username || username,
        role,
      };
      setSession(token, user);

      router.push(role === "super_admin" ? "/users" : "/analytics");
    } catch (e: any) {
      setErr(e.message || "登录失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <div style={{ fontSize: 36, marginBottom: 8 }}>&#x1F6E1;&#xFE0F;</div>
          <h1 style={{ margin: 0, fontSize: 22 }}>Edu Admin</h1>
          <p className="muted" style={{ marginTop: 6, fontSize: 13 }}>管理后台登录</p>
        </div>
        <label>
          用户名
          <input value={username} onChange={(e) => setUsername(e.target.value)} required placeholder="请输入用户名" />
        </label>
        <label>
          密码
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            placeholder="请输入密码"
          />
        </label>
        {err && <div className="err">{err}</div>}
        <button className="btn" disabled={loading}>
          {loading ? "登录中…" : "登录"}
        </button>
        <p className="hint muted" style={{ textAlign: "center", marginTop: 16 }}>
          仅 super_admin / data_admin / analyst 可登录
        </p>
      </form>
    </div>
  );
}
