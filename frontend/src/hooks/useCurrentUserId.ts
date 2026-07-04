"use client";

/**
 * useCurrentUserId — 当前用户 ID 快捷 hook
 *
 * Task #87 重建（原源文件丢失）
 *
 * 设计：
 *   - 薄包装：在 useAuth 之上提供 userId 字符串
 *   - 已弃用 useUserData 的 fetcher 模式请用 useUserData；
 *     本 hook 只用于"已登录"场景的快速读取
 *   - 未登录返回 null（不抛错）
 */

import { useAuth } from "@/contexts/AuthContext";

export function useCurrentUserId(): string | null {
  const { user } = useAuth();
  return user?.id ?? null;
}

export default useCurrentUserId;
