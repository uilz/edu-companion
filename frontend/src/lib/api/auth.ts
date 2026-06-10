/**
 * 认证模块 — 登录/注册/令牌管理/请求拦截
 *
 * 职责：
 * - JWT 令牌存储（localStorage）
 * - 登录/注册/刷新 API 调用
 * - 自动为所有 API 请求附加 Authorization header
 * - 令牌过期自动刷新
 * - 认证状态 React Context
 */

// ── 令牌存储 ──

const TOKEN_KEY = "access_token";
const REFRESH_KEY = "refresh_token";
const USER_KEY = "current_user";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function getCurrentUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function setTokens(access: string, refresh: string, user: AuthUser) {
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
}

// ── 类型 ──

export interface AuthUser {
  id: string;
  username: string;
  display_name: string;
  email: string;
  role: string;
  avatar_url?: string;
}

export interface AuthResult {
  user: AuthUser;
  access_token: string;
  refresh_token: string;
}

// ── API 调用 — 使用相对路径，走 Next.js 代理 ──

async function authFetch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`/api/auth${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    // FastAPI 验证错误返回 {detail: [...]} 或 {detail: "string"}
    const detail = data.detail;
    let msg = `认证失败 (${res.status})`;
    if (typeof detail === "string") {
      msg = detail;
    } else if (Array.isArray(detail)) {
      msg = detail.map((d: any) => d.msg || JSON.stringify(d)).join("; ");
    } else if (detail && typeof detail === "object") {
      msg = JSON.stringify(detail).slice(0, 200);
    }
    throw new Error(msg);
  }
  return data as T;
}

export async function login(username: string, password: string): Promise<AuthResult> {
  const result = await authFetch<AuthResult>("/login", { username, password });
  setTokens(result.access_token, result.refresh_token, result.user);
  return result;
}

export async function loginByEmail(email: string, password: string): Promise<AuthResult> {
  const result = await authFetch<AuthResult>("/login/email", { email, password });
  setTokens(result.access_token, result.refresh_token, result.user);
  return result;
}

export async function register(
  username: string,
  password: string,
  display_name?: string,
  email?: string,
): Promise<AuthResult> {
  const result = await authFetch<AuthResult>("/register", {
    username,
    password,
    display_name: display_name || "",
    email: email || "",
  });
  setTokens(result.access_token, result.refresh_token, result.user);
  return result;
}

export async function refreshToken(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;

  try {
    const res = await fetch("/api/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) {
      clearAuth();
      return null;
    }
    const data = await res.json();
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(REFRESH_KEY, data.refresh_token);
    return data.access_token;
  } catch {
    clearAuth();
    return null;
  }
}

export async function fetchCurrentUser(): Promise<AuthUser | null> {
  const token = getAccessToken();
  if (!token) return null;

  try {
    const res = await fetch("/api/auth/me", {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return null;
    const user = await res.json();
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    return user;
  } catch {
    return null;
  }
}

// ── 认证请求封装（自动附加 token + 自动刷新） ──

let isRefreshing = false;
let refreshPromise: Promise<string | null> | null = null;

export async function authedFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getAccessToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let res = await fetch(path, {
    ...options,
    headers,
  });

  // 401 → 尝试刷新令牌
  if (res.status === 401 && token) {
    if (!isRefreshing) {
      isRefreshing = true;
      refreshPromise = refreshToken().finally(() => {
        isRefreshing = false;
      });
    }

    const newToken = await refreshPromise;
    if (newToken) {
      headers["Authorization"] = `Bearer ${newToken}`;
      res = await fetch(path, {
        ...options,
        headers,
      });
    } else {
      clearAuth();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      // 不 throw — redirect 已触发，ErrorBoundary 不应收到错误
      // 返回一个永远 pending 的 Promise，await 自动挂起（页面即将跳转）
      return new Promise<T>(() => {});
    }
  }

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text.slice(0, 100)}`);
  }

  return res.json();
}

export async function uploadAvatar(file: File): Promise<string> {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");

  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch("/api/auth/avatar", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "头像上传失败");
  }
  return data.avatar_url;
}

// 注：历史上 "ensureDefaultUser" / "/api/auth/ensure-default" 端点已删除。
// 任何"匿名访问自动建账号"的行为都被移除。详见 CHANGELOG。
