"use client";

import { useAuth } from "@/contexts/AuthContext";

/**
 * 当前登录用户 ID。
 * - 未登录 / AuthProvider 还在加载 → 返回 null
 * - 已登录 → 返回后端 AuthUser.id（UUID 字符串）
 *
 * 用法:
 *   const userId = useCurrentUserId();
 *   useEffect(() => {
 *     if (!userId) return; // 未登录时直接跳过请求
 *     fetch(`/api/xxx?user_id=${userId}`).then(...)
 *   }, [userId]);
 */
export function useCurrentUserId(): string | null {
  return useAuth().user?.id ?? null;
}
