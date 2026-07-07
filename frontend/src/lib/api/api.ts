// ── Shared API base URL ──
// Import this from other modules instead of re-declaring API_BASE in each file.
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
import { navigateToLogin } from "./navigation";

// ══════════════════════════════════════════════════════════════
//  Unified request helpers — 自动附加认证令牌
// ══════════════════════════════════════════════════════════════

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("access_token");
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

async function apiFetch<T>(base: string, path: string, options?: RequestInit): Promise<T> {
  const authHeaders = getAuthHeaders();
  const res = await fetch(`${base}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...options?.headers,
    },
    ...options,
  });

  // 401 → 尝试刷新令牌
  if (res.status === 401) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      const retryHeaders = getAuthHeaders();
      const retryRes = await fetch(`${base}${path}`, {
        headers: {
          "Content-Type": "application/json",
          ...retryHeaders,
          ...options?.headers,
        },
        ...options,
      });
      if (!retryRes.ok) {
        const text = await retryRes.text().catch(() => "");
        throw new Error(`API ${retryRes.status}: ${text.slice(0, 100)}`);
      }
      return retryRes.json();
    }
    // 刷新失败 → 清除认证并跳转登录
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("current_user");
    navigateToLogin();
    throw new Error("登录已过期");
  }

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text.slice(0, 100)}`);
  }
  return res.json();
}

let _refreshing = false;
let _refreshPromise: Promise<boolean> | null = null;

async function tryRefreshToken(): Promise<boolean> {
  if (_refreshing) return _refreshPromise!;
  _refreshing = true;
  _refreshPromise = (async () => {
    const refresh = localStorage.getItem("refresh_token");
    if (!refresh) return false;
    try {
      const res = await fetch("/api/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (!res.ok) return false;
      const data = await res.json();
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      return true;
    } catch {
      return false;
    } finally {
      _refreshing = false;
    }
  })();
  return _refreshPromise;
}

/** 认知/图谱 API helper — uses /api prefix */
export const cognitiveApi = <T,>(p: string, o?: RequestInit) => apiFetch<T>("/api", p, o);

/** tree/conversations API helper — uses /api/conversations prefix */
export const tree = <T,>(p: string, o?: RequestInit) => apiFetch<T>("/api/conversations", p, o);

/** 练习 API helper — uses /api/practice prefix */
export const practiceApi = <T,>(p: string, o?: RequestInit) => apiFetch<T>("/api/practice", p, o);

/** 通用 API 请求（带认证） */
export const api = <T,>(path: string, o?: RequestInit) => apiFetch<T>(API_BASE, path, o);

/**
 * 带认证的 fetch 请求，返回原始 Response。
 * 适用于需要处理非 JSON 响应（下载 blob/stream）或需要自定义状态处理的场景。
 * 自动附加 Authorization header 并处理 401 刷新。
 */
export async function authedFetch(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  const authHeaders = getAuthHeaders();
  const isFormData = options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...authHeaders,
    ...options?.headers as Record<string, string>,
  };
  if (!isFormData && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  // 401 → 尝试刷新令牌
  if (res.status === 401) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      const retryHeaders: Record<string, string> = {
        ...getAuthHeaders(),
        ...options?.headers as Record<string, string>,
      };
      if (!isFormData && !retryHeaders["Content-Type"]) {
        retryHeaders["Content-Type"] = "application/json";
      }
      return fetch(`${API_BASE}${path}`, {
        ...options,
        headers: retryHeaders,
      });
    }
    // 刷新失败 → 清除认证并跳转登录
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("current_user");
    navigateToLogin();
    throw new Error("登录已过期");
  }

  return res;
}

/**
 * 带认证的 fetch 请求，自动解析 JSON 响应。
 * 适用于大多数 JSON API 调用，是 auth.ts 中 authedFetch 的替代。
 */
export async function authedFetchJson<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await authedFetch(path, options);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text.slice(0, 100)}`);
  }
  return res.json() as Promise<T>;
}
