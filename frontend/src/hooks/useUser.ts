"use client";

import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import type { UserRole, SubscriptionTier, NavContext } from "@/lib/navConfig";
import { DEFAULT_NAV_CONTEXT } from "@/lib/navConfig";

// ── 后端角色字符串 → 抽象 UserRole 映射 ──
//
// 任务 #45：admin 已从主前端 navConfig 移除（admin 走独立 3001 项目）。
// 主前端只关心 student / guest，所有已登录用户在此都映射为 student。
// 后端 role 字段（super_admin / admin / user）保留原始字符串在 user.role
// 上，前端如需展示"超级管理员/管理员/用户"标签可读 user.role 自行判断。
function mapBackendRole(_backendRole: string | undefined | null): UserRole {
  return "student";
}

// ── localStorage 覆盖 — dev 模式角色/档位切换 ──
//
// key: edu-dev-role-override
// value: JSON.stringify({ userRole, subscriptionTier }) | null
//
// 不在生产环境编译时引入（通过 NODE_ENV 判断），但 dev 模式即可用。
const DEV_OVERRIDE_KEY = "edu-dev-role-override";

interface DevOverride {
  userRole: UserRole;
  subscriptionTier: SubscriptionTier;
}

function readDevOverride(): DevOverride | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(DEV_OVERRIDE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (
      parsed &&
      (parsed.userRole === "student" ||
        parsed.userRole === "guest") &&
      (parsed.subscriptionTier === "free" ||
        parsed.subscriptionTier === "pro" ||
        parsed.subscriptionTier === "enterprise")
    ) {
      return parsed as DevOverride;
    }
  } catch {
    // ignore
  }
  return null;
}

function writeDevOverride(value: DevOverride | null) {
  if (typeof window === "undefined") return;
  if (value === null) {
    localStorage.removeItem(DEV_OVERRIDE_KEY);
  } else {
    localStorage.setItem(DEV_OVERRIDE_KEY, JSON.stringify(value));
  }
  // 触发 useUser / DevRoleSwitcher 重渲染
  window.dispatchEvent(new Event("edu-dev-role-override-changed"));
}

// ── 公开 API ──

export interface UseUserResult {
  /** 已登录则返回后端 AuthUser；否则 null */
  user: ReturnType<typeof useAuth>["user"];
  /** 抽象 UserRole — student / guest
   *
   * 任务 #45：admin 已从主前端移除，此处只区分"已登录学生"和"未登录访客"。
   * 后端原始 role 字符串（super_admin / admin / user）保留在 user.role 上。
   */
  userRole: UserRole;
  /** 当前订阅档位 — free / pro / enterprise */
  subscriptionTier: SubscriptionTier;
  /** 给 navConfig 用的完整 NavContext */
  navContext: NavContext;
  /** 是否为已登录用户 */
  isAuthenticated: boolean;
  /** dev 模式：当前是否在使用 dev 覆盖 */
  hasDevOverride: boolean;
  /** dev 模式：设置覆盖值（写入 localStorage 并广播变更） */
  setDevOverride: (override: DevOverride | null) => void;
  /** dev 模式：清除覆盖，回到真实角色 */
  clearDevOverride: () => void;
}

/**
 * useUser — 当前用户状态聚合。
 *
 * 综合：
 *   1. AuthContext.user（来自后端 /api/auth/me）
 *   2. 后端 role 字符串 → UserRole 映射
 *   3. 订阅档位（当前后端未提供，默认 free；dev 模式可覆盖）
 *   4. dev 模式 localStorage 覆盖（用于任务 #34 验收 / 演示）
 */
export function useUser(): UseUserResult {
  const { user } = useAuth();
  const [devOverride, setDevOverrideState] = useState<DevOverride | null>(null);

  // 初始读取 dev 覆盖
  useEffect(() => {
    setDevOverrideState(readDevOverride());
  }, []);

  // 监听自定义事件，跨组件同步 dev 切换
  useEffect(() => {
    const handler = () => setDevOverrideState(readDevOverride());
    window.addEventListener("edu-dev-role-override-changed", handler);
    // 跨标签页同步
    const storageHandler = (e: StorageEvent) => {
      if (e.key === DEV_OVERRIDE_KEY) {
        setDevOverrideState(readDevOverride());
      }
    };
    window.addEventListener("storage", storageHandler);
    return () => {
      window.removeEventListener("edu-dev-role-override-changed", handler);
      window.removeEventListener("storage", storageHandler);
    };
  }, []);

  // 计算实际 userRole / subscriptionTier
  //
  // 任务 #75：realTier 硬编码 free。
  // 后端目前没有 subscriptionTier 字段；统一默认 free。dev 模式可覆盖。
  const realUserRole: UserRole = user ? mapBackendRole(user.role) : "guest";
  const realTier: SubscriptionTier = "free";

  const userRole: UserRole = devOverride?.userRole ?? realUserRole;
  const subscriptionTier: SubscriptionTier =
    devOverride?.subscriptionTier ?? realTier;

  const setDevOverride = useCallback((value: DevOverride | null) => {
    writeDevOverride(value);
    setDevOverrideState(value);
  }, []);

  const clearDevOverride = useCallback(() => {
    writeDevOverride(null);
    setDevOverrideState(null);
  }, []);

  return {
    user,
    userRole,
    subscriptionTier,
    navContext: { userRole, subscriptionTier },
    isAuthenticated: !!user,
    hasDevOverride: devOverride !== null,
    setDevOverride,
    clearDevOverride,
  };
}

// 兜底：当某些组件拿不到 useUser 上下文时使用（理论上不应该发生，
// 因为 useUser 只读取 AuthContext，不创建自己的 provider）
export function getDefaultNavContext(): NavContext {
  return DEFAULT_NAV_CONTEXT;
}
