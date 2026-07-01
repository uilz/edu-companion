"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login, setSession } from "@/lib/api";
import type { AdminRole, AdminUser } from "@/lib/types";

const ALLOWED_ROLES: AdminRole[] = ["super_admin", "data_admin", "analyst"];

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
      const data = await login(username, password);
      const role: AdminRole = (data.user.role || "user") as AdminRole;

      if (!ALLOWED_ROLES.includes(role)) {
        throw new Error(`角色 ${role} 无管理后台权限`);
      }

      const user: AdminUser = {
        user_id: data.user.user_id || data.user.username || username,
        username: data.user.username || username,
        role,
      };
      setSession(data.access_token, data.refresh_token, user);

      router.push(role === "super_admin" ? "/users" : "/analytics");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-page">
      <form
        onSubmit={submit}
        className="w-[380px] bg-surface-elevated p-10 rounded-xl border border-divider shadow-md animate-slide-up"
      >
        <div className="text-center mb-6">
          <div className="text-4xl mb-2">&#x1F6E1;&#xFE0F;</div>
          <h1 className="text-heading text-ink-primary">Edu Admin</h1>
          <p className="text-caption text-ink-muted mt-1">管理后台登录</p>
        </div>

        <label className="block text-caption text-ink-secondary font-medium mt-4 mb-1">
          用户名
        </label>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          placeholder="请输入用户名"
          className="w-full px-3 py-2.5 bg-input text-ink-primary border border-divider rounded-md text-body
                     focus:outline-none focus:border-accent transition-colors duration-fast"
        />

        <label className="block text-caption text-ink-secondary font-medium mt-4 mb-1">
          密码
        </label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          placeholder="请输入密码"
          className="w-full px-3 py-2.5 bg-input text-ink-primary border border-divider rounded-md text-body
                     focus:outline-none focus:border-accent transition-colors duration-fast"
        />

        {err && (
          <div className="mt-3 p-2.5 bg-danger/10 border border-danger/20 rounded-md text-caption text-danger">
            {err}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full mt-5 py-2.5 rounded-md font-medium text-body bg-accent text-white
                     hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed
                     transition-colors duration-fast"
        >
          {loading ? "登录中…" : "登录"}
        </button>

        <p className="text-center mt-4 text-fine text-ink-muted">
          仅 super_admin / data_admin / analyst 可登录
        </p>
      </form>
    </div>
  );
}
