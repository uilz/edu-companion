/**
 * Admin API 客户端 — JWT 认证 + 自动刷新
 *
 * 认证链路: admin(3001) → Nginx(8080) → auth-gateway(18001)
 * 数据链路: admin(3001) → next rewrites → app_admin(8001)
 */
import type { AdminRole, AdminUser, AuthResult } from "./types";
export type { AdminRole, AdminUser, AuthResult };

// ── API 路径 ──
const API_BASE = "/api/admin";

// ── Token 本地存储 ──
const TOKEN_KEY = "admin_token";
const REFRESH_KEY = "admin_refresh_token";
const ROLE_KEY = "admin_role";
const USER_KEY = "admin_user";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function getCurrentUser(): AdminUser | null {
  if (typeof window === "undefined") return null;
  const u = localStorage.getItem(USER_KEY);
  if (!u) return null;
  try { return JSON.parse(u); } catch { return null; }
}

export function setSession(token: string, refreshToken: string, user: AdminUser) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(REFRESH_KEY, refreshToken);
  localStorage.setItem(ROLE_KEY, user.role);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(ROLE_KEY);
  localStorage.removeItem(USER_KEY);
}

// ── RBAC 辅助 ──
import { ROLE_RANK } from "./types";

export function hasRole(role: AdminRole | undefined | null, min: AdminRole): boolean {
  if (!role) return false;
  return (ROLE_RANK[role] ?? 0) >= ROLE_RANK[min];
}

// ── 登录 ──
export async function login(username: string, password: string): Promise<AuthResult> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const data = await res.json();
  if (!res.ok) {
    const detail = data.detail;
    let msg = `登录失败 (${res.status})`;
    if (typeof detail === "string") msg = detail;
    else if (Array.isArray(detail)) msg = detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join("; ");
    throw new Error(msg);
  }
  return data as AuthResult;
}

// ── Token 刷新 ──
let _refreshing = false;
let _refreshPromise: Promise<boolean> | null = null;

async function tryRefreshToken(): Promise<boolean> {
  if (_refreshing) return _refreshPromise!;
  const refresh = getRefreshToken();
  if (!refresh) return false;

  _refreshing = true;
  _refreshPromise = (async () => {
    try {
      const res = await fetch("/api/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (!res.ok) return false;
      const data = await res.json();
      localStorage.setItem(TOKEN_KEY, data.access_token);
      localStorage.setItem(REFRESH_KEY, data.refresh_token);
      return true;
    } catch {
      return false;
    } finally {
      _refreshing = false;
    }
  })();
  return _refreshPromise;
}

// ── API 错误 ──
export class ApiError extends Error {
  constructor(public status: number, public body: string) {
    super(`HTTP ${status}: ${body.slice(0, 200)}`);
  }
}

// ── 核心请求函数（带 401 自动刷新） ──
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res = await fetch(`${API_BASE}${path}`, { ...init, headers });

  // 401 → 尝试刷新
  if (res.status === 401 && token) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      const newToken = getToken();
      if (newToken) headers["Authorization"] = `Bearer ${newToken}`;
      res = await fetch(`${API_BASE}${path}`, { ...init, headers });
    } else {
      clearSession();
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
      return new Promise<T>(() => {});
    }
  }

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ── 便捷方法 ──
export const api = {
  get: <T>(p: string) => request<T>(p),
  post: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(p: string) => request<T>(p, { method: "DELETE" }),
};
