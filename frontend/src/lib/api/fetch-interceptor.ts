/**
 * 全局 fetch 拦截器 — 自动为所有 API 请求附加认证令牌
 *
 * 在应用启动时调用 initFetchInterceptor() 即可。
 * 后续所有 fetch 调用会自动附带 Authorization header。
 */

let _origFetch: typeof fetch | null = null;

function interceptedFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  // 未初始化时直接放行
  if (!_origFetch) {
    return window.fetch(input, init);
  }

  // 只拦截同源 API 请求
  const url = typeof input === "string" ? input : input instanceof URL ? input.href : (input as Request).url;
  const isApiRequest = url.startsWith("/") || url.startsWith(window.location.origin);

  if (!isApiRequest) {
    return _origFetch(input, init);
  }

  // 获取 token
  const token = localStorage.getItem("access_token");
  if (!token) {
    return _origFetch(input, init);
  }

  // 合并 Authorization header
  const headers = new Headers(init?.headers || (input as Request).headers);
  if (!headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return _origFetch(input, { ...init, headers });
}

let _initialized = false;

export function initFetchInterceptor() {
  if (_initialized || typeof window === "undefined") return;
  _origFetch = window.fetch;
  window.fetch = interceptedFetch as typeof fetch;
  _initialized = true;
}
