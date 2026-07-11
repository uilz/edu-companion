"use client";

import { useMemo } from "react";
import {
  learningActivityService,
  type LearningActivity,
  type LearningActivityStats,
  type ListActivitiesParams,
  type GetActivityStatsParams,
} from "@/lib/api/learning-activity-api";
import { useApiQuery } from "./useApiQuery";

export type { LearningActivity, LearningActivityStats, ListActivitiesParams };

const QUERY_KEY = "learning-activities";

function buildQueryKey(prefix: string, params: Record<string, any>): unknown[] {
  return [prefix, ...Object.entries(params).flat()];
}

/**
 * 查询用户学习活动流
 *
 * 用法：
 *   const { data, loading, error, refetch } = useLearningActivities({ limit: 20 });
 */
export function useLearningActivities(params: ListActivitiesParams = {}) {
  const memoizedParams = useMemo(
    () => ({
      limit: params.limit ?? 50,
      offset: params.offset ?? 0,
      ...(params.module ? { module: params.module } : {}),
      ...(params.activity_type ? { activity_type: params.activity_type } : {}),
      ...(params.start_time ? { start_time: params.start_time } : {}),
      ...(params.end_time ? { end_time: params.end_time } : {}),
    }),
    [
      params.limit,
      params.offset,
      params.module,
      params.activity_type,
      params.start_time,
      params.end_time,
    ],
  );

  return useApiQuery(
    buildQueryKey(QUERY_KEY, memoizedParams),
    () => learningActivityService.list(memoizedParams),
  );
}

/**
 * 查询学习活动统计
 *
 * 用法：
 *   const { data, loading, error, refetch } = useLearningActivityStats({ days: 7 });
 */
export function useLearningActivityStats(params: GetActivityStatsParams = {}) {
  const memoizedParams = useMemo(
    () => ({
      days: params.days ?? 30,
      ...(params.module ? { module: params.module } : {}),
    }),
    [params.days, params.module],
  );

  return useApiQuery(
    buildQueryKey(`${QUERY_KEY}-stats`, memoizedParams),
    () => learningActivityService.stats(memoizedParams),
  );
}
