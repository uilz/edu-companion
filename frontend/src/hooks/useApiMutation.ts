"use client";

import { useMutation, useQueryClient, type UseMutationOptions } from "@tanstack/react-query";

/**
 * 通用 API 变更 hook，封装 TanStack Query 的 useMutation，
 * 支持成功后自动失效相关查询缓存。
 *
 * 使用示例：
 *   const deleteCard = useApiMutation(
 *     (cardId: string) => flashcardService.delete(cardId),
 *     { invalidateQueries: ["flashcard-list"] },
 *   );
 *   await deleteCard.mutate(cardId);
 *
 * @param mutationFn         - 异步变更函数
 * @param invalidateQueries  - 成功后需要失效的 queryKey 前缀列表
 * @param options            - 额外的 useMutation 配置
 */
export function useApiMutation<TVars, TData = unknown>(
  mutationFn: (vars: TVars) => Promise<TData>,
  {
    invalidateQueries,
    onSuccess: userOnSuccess,
    ...options
  }: {
    invalidateQueries?: unknown[][];
    onSuccess?: (data: TData, vars: TVars) => void;
  } & Omit<UseMutationOptions<TData, Error, TVars>, "mutationFn" | "onSuccess"> = {},
) {
  const queryClient = useQueryClient();

  return useMutation<TData, Error, TVars>({
    mutationFn,
    ...options,
    onSuccess: (data, vars) => {
      if (invalidateQueries) {
        for (const key of invalidateQueries) {
          queryClient.invalidateQueries({ queryKey: key });
        }
      }
      userOnSuccess?.(data, vars);
    },
  });
}