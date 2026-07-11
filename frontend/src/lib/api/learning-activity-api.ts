// Learning Activity API 客户端
// 依据 Phase 2 统一设计系统：跨壳学习活动流

import { authedFetchJson } from "./api";

const PREFIX = "/api/activities";

export interface LearningActivity {
  id: string;
  user_id: string;
  activity_type: string;
  module: string;
  source_event_id: string | null;
  source_event_type: string | null;
  idempotency_key: string | null;
  title: string;
  description: string;
  status: string;
  timestamp: string;
  deep_link: string;
  meta: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface LearningActivityList {
  items: LearningActivity[];
  total: number;
  limit: number;
  offset: number;
}

export interface LearningActivityStats {
  user_id: string;
  total: number;
  by_module: Record<string, number>;
  by_activity_type: Record<string, number>;
}

export interface ListActivitiesParams {
  module?: string;
  activity_type?: string;
  start_time?: string;
  end_time?: string;
  limit?: number;
  offset?: number;
}

export interface GetActivityStatsParams {
  days?: number;
  module?: string;
}

function buildQueryString(params: Record<string, any>): string {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      qs.append(key, String(value));
    }
  });
  const query = qs.toString();
  return query ? `?${query}` : "";
}

export const learningActivityService = {
  list: (params: ListActivitiesParams = {}): Promise<LearningActivityList> =>
    authedFetchJson<LearningActivityList>(`${PREFIX}/${buildQueryString(params)}`),

  stats: (params: GetActivityStatsParams = {}): Promise<LearningActivityStats> =>
    authedFetchJson<LearningActivityStats>(`${PREFIX}/stats${buildQueryString(params)}`),
};
