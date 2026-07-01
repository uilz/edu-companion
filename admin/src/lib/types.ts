// Admin 共享类型定义

/** 用户角色 */
export type AdminRole = "user" | "analyst" | "data_admin" | "super_admin";

/** 角色等级映射 */
export const ROLE_RANK: Record<AdminRole, number> = {
  user: 0,
  analyst: 10,
  data_admin: 20,
  super_admin: 30,
};

/** 管理员用户 */
export interface AdminUser {
  user_id: string;
  username: string;
  role: AdminRole;
}

/** 鉴权 API 返回 */
export interface AuthResult {
  access_token: string;
  refresh_token: string;
  user: AdminUser;
}

/** 分页查询参数 */
export interface PaginationParams {
  page?: number;
  page_size?: number;
}

/** 分页响应 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ═══════════════════════════════════════════════════════
// 用户管理相关类型
// ═══════════════════════════════════════════════════════

export interface UserRow {
  id: string;
  username: string;
  email: string;
  display_name: string;
  role: string;
  is_active: boolean;
  is_online?: boolean;
  last_active_at?: string | null;
  last_login: string | null;
  created_at: string;
  avatar_url: string;
}

export interface UserDetail extends UserRow {
  online?: { online: boolean };
  active_sessions?: SessionDevice[];
  recent_logins?: RecentLogin[];
  ip_analysis?: IPAnalysisItem[];
}

export interface SessionDevice {
  device_type: string;
  browser: string;
  os: string;
  ip_address: string;
  city: string | null;
  region: string | null;
  country: string | null;
  is_current: boolean;
  created_at: string;
}

export interface RecentLogin {
  created_at: string;
  device_type: string;
  browser: string;
  ip_address: string;
  city: string | null;
  region: string | null;
  country: string | null;
}

export interface IPAnalysisItem {
  ip_address: string;
  city: string | null;
  region: string | null;
  country: string | null;
  login_count: number;
  last_seen: string;
}

// ═══════════════════════════════════════════════════════
// 全局数据相关类型
// ═══════════════════════════════════════════════════════

export interface GlobalOverview {
  [key: string]: number;
}

export interface PracticeSession {
  id: string;
  user_id: string;
  username: string | null;
  status: string;
  total_count: number;
  correct_count: number;
  wrong_count: number;
  started_at: string | null;
  finished_at: string | null;
}

export interface DrillAttempt {
  stem?: string;
  question_id?: string;
  is_correct: boolean;
  time_spent: number;
  created_at: string;
}

export interface ConversationSummary {
  user_id: string;
  conv_count: number;
  updated_at: string | null;
}

// ═══════════════════════════════════════════════════════
// 系统监控相关类型
// ═══════════════════════════════════════════════════════

export interface SystemHealth {
  status: string;
  now: string;
  active_users: number;
  pending_events: number;
  nodes_total: number;
  user_metas: number;
  db_size_mb: number;
  db_size_gb: number;
  pid: number;
}

export interface MonitorEventRow {
  event_id: string;
  event_type: string;
  user_id: string;
  node_id: string;
  processed: boolean;
  timestamp: string;
  payload: unknown;
}

export interface AlertCheckResult {
  alerts: { message: string }[];
  alert_count: number;
  healthy: boolean;
  config: unknown;
}

export interface EventTrendItem {
  day: string;
  total: number;
  pending: number;
}

// ═══════════════════════════════════════════════════════
// BI 分析相关类型
// ═══════════════════════════════════════════════════════

export interface AnalyticsKpi {
  users_total: number;
  users_active: number;
  attempts_total: number;
  attempts_correct: number;
  accuracy: number;
  sessions_total: number;
  atom_nodes: number;
  questions_total: number;
  questions_active: number;
}

export interface AnalyticsActivity {
  dau: number;
  wau: number;
  mau: number;
  total: number;
}

export interface AnalyticsTrend {
  series: PracticeTrendItem[];
}

export interface PracticeTrendItem {
  day: string;
  attempts: number;
  correct: number;
  accuracy: number;
}

export interface TopWrongQuestion {
  id: string;
  stem?: string;
  difficulty: string;
  wrong_count: number;
  total_attempts: number;
}

export interface MasteryBucket {
  bucket: string;
  cnt: number;
}

export interface SubjectDistItem {
  subject: string;
  questions: number;
  nodes: number;
}

export interface DifficultyBucket {
  bucket: string;
  cnt: number;
}

export interface EngagementItem {
  username?: string;
  user_id: string;
  total_attempts: number;
  correct_attempts: number;
  active_days: number;
}

// ═══════════════════════════════════════════════════════
// 系统设置相关类型
// ═══════════════════════════════════════════════════════

export interface ServiceInfo {
  port?: number;
  status: string;
  pid?: number;
}

export interface ServicesResp {
  services: Record<string, ServiceInfo>;
}

export interface DbStatus {
  connected: boolean;
  error?: string;
  version_rows?: unknown;
}

export interface EnvInfo {
  env: Record<string, string>;
}
