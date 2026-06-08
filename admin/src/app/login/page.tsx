"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { setSession, type AdminRole, type AdminUser } from "@/lib/api";

/**
 * 登录页（最简版）
 * - 通过后端 /api/auth/login 取 JWT（主后端 8000 端口）
 * - 也可以用 super_admin 种子账号快捷登录
 */
export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("default_user");
  const [password, setPassword] = useState("password");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      // 1. 调主后端 8000 拿 token
      const res = await fetch("http://127.0.0.1:8000/api/auth/login", {
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
      const role: AdminRole = data.role || "user";

      const user: AdminUser = {
        user_id: data.user_id || username,
        username,
        role,
      };
      setSession(token, user);

      // 2. 跳到默认页
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
        <h1>🛡️ Edu Admin</h1>
        <p className="muted">请用主后端账号登录。仅 super_admin / data_admin / analyst 可使用本后台。</p>
        <label>
          用户名
          <input value={username} onChange={(e) => setUsername(e.target.value)} required />
        </label>
        <label>
          密码
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {err && <div className="err">{err}</div>}
        <button className="btn" disabled={loading}>
          {loading ? "登录中…" : "登录"}
        </button>
        <p className="hint muted">
          提示：默认管理员 <code>default_user</code> 的角色可在数据库 <code>users.role</code> 字段调整。
        </p>
      </form>
    </div>
  );
}
