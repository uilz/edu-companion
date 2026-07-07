/**
 * 共享导航回调 — 供非 React 模块在 SPA 内跳转
 *
 * 问题：api.ts / proposal-navigator.ts 等非 React 模块无法直接使用 useRouter。
 * 方案：导出可注入的回调，由 ClientProviders 在挂载时用 useRouter 设置。
 */

type NavigateFn = (url: string) => void;

let _navigate: NavigateFn | null = null;

/** 应用初始化时调用，注入 useRouter 驱动的导航函数 */
export function setNavigate(fn: NavigateFn) {
  _navigate = fn;
}

/** 通用 SPA 导航 — 如果回调未注入，降级到 window.location */
export function navigate(url: string) {
  if (_navigate) {
    _navigate(url);
  } else if (typeof window !== "undefined") {
    window.location.href = url;
  }
}

/** 跳转到登录页 — 便捷封装 */
export function navigateToLogin() {
  navigate("/login");
}