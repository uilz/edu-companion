// ============================================================
// EXP-04 Feature Flag
//
// 简单的前端特性开关。
// - 读取 localStorage 中的 exp04_enabled
// - 支持 URL query param 覆盖（?exp04=1 / ?exp04=0）
// - 提供 React Hook
// ============================================================

"use client";

import { useSearchParams } from "next/navigation";

const STORAGE_KEY = "exp04_enabled";

/**
 * 读取 feature flag 的原始值。
 * 优先级：URL query param > localStorage > 默认 true（EXP-04 已 GA）
 */
export function isExp04Enabled(): boolean {
  if (typeof window === "undefined") return false;

  // URL query param 覆盖
  const params = new URLSearchParams(window.location.search);
  const urlFlag = params.get("exp04");
  if (urlFlag === "1") {
    localStorage.setItem(STORAGE_KEY, "1");
    return true;
  }
  if (urlFlag === "0") {
    localStorage.setItem(STORAGE_KEY, "0");
    return false;
  }

  // localStorage（如果从未设置过，返回 true）
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === null) return true;
  return stored === "1";
}

/**
 * React Hook：获取 EXP-04 开关状态。
 * 客户端渲染时读取 localStorage + URL param。
 */
export function useExp04Enabled(): boolean {
  // next/navigation 的 useSearchParams 只能在 Suspense 内使用。
  // 这里用一个 try-catch 兜底。
  try {
    useSearchParams(); // 仅用于触发重渲染，实际读取走 isExp04Enabled()
  } catch {
    // 非 Suspense 环境 → 忽略，使用 localStorage 兜底
  }
  return isExp04Enabled();
}
