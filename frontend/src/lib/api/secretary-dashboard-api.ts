import { api } from "./api";

export interface DashboardFocus {
  id: string;
  type: string;
  title: string;
  description: string;
  estimated_minutes: number;
  action: {
    type: string;
    target: string;
  };
}

export interface DashboardStat {
  key: string;
  label: string;
  value: string | number;
  priority: "high" | "medium" | "low";
  icon: string;
  deep_link?: string;
}

export interface DashboardPendingItem {
  id: string;
  kind: "proposal" | "confirmation" | "notification";
  title: string;
  description: string;
  priority: number;
  action_type: string;
  source: string;
  created_at: number | string;
  tags: string[];
  emoji?: string;
  target: Record<string, unknown>;
}

export interface DashboardRecommendation {
  skill_id: string;
  label: string;
  level?: string;
  p_known?: number;
  subject?: string;
}

export interface DashboardRecommendations {
  suggestion: string;
  urgent: DashboardRecommendation[];
  building: DashboardRecommendation[];
  new_topic: DashboardRecommendation[];
}

export interface DashboardActivity {
  id: string;
  activity_type: string;
  module: string;
  title: string;
  description: string;
  timestamp: string;
  status: string;
  deep_link: string;
  meta?: Record<string, unknown>;
}

export interface DashboardTodayInfo {
  quote_enabled: boolean;
  memory_pulse: string | null;
}

export interface SecretaryDashboardData {
  greeting: string;
  date: string;
  focus: DashboardFocus | null;
  stats: DashboardStat[];
  pending: {
    items: DashboardPendingItem[];
    total: number;
  };
  recommendations: DashboardRecommendations;
  activities: {
    items: DashboardActivity[];
    total: number;
    limit: number;
    offset: number;
  };
  today: DashboardTodayInfo;
}

export const secretaryDashboardApi = {
  async getDashboard(): Promise<SecretaryDashboardData> {
    return api<SecretaryDashboardData>("/api/secretary/dashboard");
  },
};
