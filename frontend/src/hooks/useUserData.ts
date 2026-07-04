"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useAuth } from "@/contexts/AuthContext";

interface UseUserDataResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

/**
 * 统一用户数据加载 hook
 *
 * 设计目标：
 * 1. 自动等待 AuthContext 完成 authLoading，避免「未登录态」与「加载中态」混淆导致的死锁
 * 2. 原子管理 loading / error / refetch，消除每个页面手写 useEffect + useState + useCallback 的样板
 * 3. fetcher 收到稳定的 userId（来自 AuthContext.user.id），调用方无需自己处理
 *
 * 替代旧的 useCurrentUserId 模式：
 *   const userId = useCurrentUserId();
 *   useEffect(() => { if (!userId) return; ... }, [userId]);
 *
 * 新模式：
 *   const { data, loading, error, refetch } = useUserData(async (userId) => {
 *     return await api(`/api/xxx?user_id=${userId}`);
 *   });
 */
export function useUserData<T>(
  fetcher: (userId: string) => Promise<T>,
  deps: unknown[] = [],
): UseUserDataResult<T> {
  const { user, loading: authLoading } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const doFetch = useCallback(async () => {
    if (authLoading || !user) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetcherRef.current(user.id);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, [authLoading, user]);

  useEffect(() => {
    doFetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, user, ...deps]);

  return { data, loading, error, refetch: doFetch };
}
