"use client";

import { useQuery, type UseQueryOptions } from "@tanstack/react-query";

/**
 * 通用 API 查询 hook，封装 TanStack Query 的 useQuery，
 * 返回与项目现有模式兼容的 { data, loading, error, refetch } 接口。
 *
 * 使用示例：
 *   const { data, loading, error, refetch } = useApiQuery(
 *     ["flashcard-stats"],
 *     () => flashcardService.getStats(),
 *   );
 *
 * @param queryKey  - TanStack Query 的 queryKey，用于缓存和去重
 * @param fetcher   - 异步数据获取函数，返回 Promise<T>
 * @param options   - 额外的 useQuery 配置（enabled, onSuccess 等）
 */
export function useApiQuery<T>(
  queryKey: unknown[],
  fetcher: () => Promise<T>,
  options?: Omit<UseQueryOptions<T, Error>, "queryKey" | "queryFn">,
) {
  const { data, isLoading, isError, error, refetch } = useQuery<T, Error>({
    queryKey,
    queryFn: fetcher,
    ...options,
  });

  return {
    data: data ?? null,
    loading: isLoading,
    error: isError ? error : null,
    refetch,
  };
}