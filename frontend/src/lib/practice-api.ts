// ══════════════════════════════════════════════════════════════
//  v7 练习系统 API 客户端
// ══════════════════════════════════════════════════════════════

import { apiFetch } from "@/store/tree-helpers";

// ── 类型 ──

export interface V7Question {
  id: string;
  bank_id: string;
  question_type: "single" | "multiple" | "fill" | "free_form";
  stem: string;
  options: V7Option[];
  difficulty: number;
  cognitive_node_ids: string[];
  metadata: Record<string, any>;
  // 已回答的题会带这些
  answered?: boolean;
  is_correct?: boolean | null;
  time_spent?: number;
  _attempts?: number;
  _wrongs?: number;
}

export interface V7Option {
  letter: string;
  text: string;
  is_correct: boolean;
  distractor_type?: string;
}

export interface V7Session {
  session_id: string;
  bank_id: string;
  mode: string;
  session_type: string;
  status: "created" | "active" | "completed";
  total_count: number;
  correct_count: number;
  wrong_count: number;
  score: number | null;
  duration_seconds?: number | null;
  config: Record<string, any>;
  cognitive_node_ids: string[];
  questions: V7Question[];
  created_at: string;
  started_at: string;
  finished_at: string | null;
}

export interface V7SubmitResult {
  is_correct: boolean;
  correct_answer: string[];
  analysis: string;
  consecutive_correct: number;
  mastered: boolean;
  wrong_count_increased: boolean;
}

export interface V7Bank {
  id: string;
  name: string;
  description: string;
  question_count: number;
  auto_created: boolean;
}

export interface V7SessionListItem {
  session_id: string;
  bank_id: string;
  mode: string;
  status: string;
  total_count: number;
  correct_count: number;
  wrong_count: number;
  score: number | null;
  duration_seconds: number | null;
  created_at: string;
}

// ── API 调用 ──

const V7_BASE = "/api/v7/practice";

async function v7fetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${V7_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    cache: "no-store",
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`v7 API error ${res.status}: ${text}`);
  }
  return res.json();
}

/** 根据知识点 ID 解析（或创建）题库 */
export async function resolveBankForNode(nodeId: string): Promise<{ bank_id: string; bank: V7Bank }> {
  return v7fetch("/resolve/node", {
    method: "POST",
    body: JSON.stringify({ node_id: nodeId }),
  });
}

/** 创建练习会话（含自适应选题） */
export async function createPracticeSession(
  bankId: string,
  options?: {
    mode?: string;
    count?: number;
    cognitive_node_ids?: string[];
    config?: Record<string, any>;
  }
): Promise<V7Session> {
  return v7fetch("/sessions", {
    method: "POST",
    body: JSON.stringify({
      bank_id: bankId,
      mode: options?.mode ?? "adaptive",
      count: options?.count ?? 5,
      cognitive_node_ids: options?.cognitive_node_ids,
      config: options?.config,
    }),
  });
}

/** 提交答题 */
export async function submitAnswer(
  sessionId: string,
  questionId: string,
  answer: string[],
  timeSpent?: number,
  hintsUsed?: number
): Promise<V7SubmitResult> {
  return v7fetch(`/sessions/${sessionId}/submit`, {
    method: "POST",
    body: JSON.stringify({
      question_id: questionId,
      answer,
      time_spent: timeSpent ?? 0,
      hints_used: hintsUsed ?? 0,
    }),
  });
}

/** 完成会话 */
export async function completeSession(sessionId: string): Promise<V7Session> {
  return v7fetch(`/sessions/${sessionId}/complete`, { method: "POST" });
}

/** 获取会话详情 */
export async function getSession(sessionId: string): Promise<V7Session> {
  return v7fetch(`/sessions/${sessionId}`);
}

/** 获取会话列表 */
export async function listSessions(options?: {
  bank_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<{ items: V7SessionListItem[]; total: number }> {
  const params = new URLSearchParams();
  if (options?.bank_id) params.set("bank_id", options.bank_id);
  if (options?.status) params.set("status", options.status);
  if (options?.limit) params.set("limit", String(options.limit));
  if (options?.offset) params.set("offset", String(options.offset));
  const qs = params.toString();
  return v7fetch(`/sessions${qs ? `?${qs}` : ""}`);
}

/** AI 出题 */
export async function generateQuestions(
  message: string,
  options?: {
    bank_id?: string;
    conversation_id?: string;
    node_id?: string;
  }
): Promise<{ bank_id: string; bank_name: string; generated: number; questions: V7Question[]; params: any }> {
  return v7fetch("/generate", {
    method: "POST",
    body: JSON.stringify({
      message,
      ...options,
    }),
  });
}

/** 获取题库列表 */
export async function listBanks(): Promise<V7Bank[]> {
  return v7fetch("/banks");
}

// ── 统计 ──

export interface V7Overview {
  total_questions: number;
  total_correct: number;
  total_wrong: number;
  accuracy: number;
  total_sessions: number;
  study_minutes: number;
  mastered_count: number;
  weak_count: number;
  due_review_count: number;
  today_questions: number;
}

export interface V7DailyPoint {
  date: string;
  count: number;
  correct: number;
  wrong: number;
  minutes: number;
}

/** 获取概览统计 */
export async function getOverview(): Promise<V7Overview> {
  return v7fetch("/stats/overview");
}

/** 获取每日趋势 */
export async function getDailyTrend(days: number = 30): Promise<V7DailyPoint[]> {
  return v7fetch(`/stats/daily?days=${days}`);
}

/** 获取会话历史 */
export async function getSessionHistory(limit: number = 10): Promise<V7SessionListItem[]> {
  return v7fetch(`/stats/sessions?limit=${limit}`);
}

/** 获取薄弱知识点 */
export async function getWeakSkills(): Promise<{ skill_id: string; label: string; mastery: number; attempts: number; trend: string; load: number }[]> {
  return v7fetch("/stats/weak-skills");
}

// ── 错题本 ──

export interface ErrorBookItem {
  question_id: string;
  bank_id: string;
  stem: string;
  options: V7Option[];
  question_type: string;
  difficulty: number;
  cognitive_node_ids: string[];
  analysis: string;
  total_attempts: number;
  wrong_count: number;
  wrong_rate: number;
  mastered: boolean;
  last_wrong: string | null;
  last_done: string | null;
}

export interface ErrorBookResult {
  items: ErrorBookItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ErrorBookStats {
  unique_wrong_questions: number;
  total_wrong_attempts: number;
  mastered_from_errors: number;
  still_weak: number;
  related_nodes: number;
}

/** 获取错题本 */
export async function getErrorBook(options?: {
  bank_id?: string;
  cognitive_node_id?: string;
  min_wrongs?: number;
  sort_by?: string;
  page?: number;
  page_size?: number;
}): Promise<ErrorBookResult> {
  const params = new URLSearchParams();
  if (options?.bank_id) params.set("bank_id", options.bank_id);
  if (options?.cognitive_node_id) params.set("cognitive_node_id", options.cognitive_node_id);
  if (options?.min_wrongs) params.set("min_wrongs", String(options.min_wrongs));
  if (options?.sort_by) params.set("sort_by", options.sort_by);
  if (options?.page) params.set("page", String(options.page));
  if (options?.page_size) params.set("page_size", String(options.page_size));
  const qs = params.toString();
  return v7fetch(`/error-book${qs ? `?${qs}` : ""}`);
}

/** 获取错题本概览 */
export async function getErrorBookStats(): Promise<ErrorBookStats> {
  return v7fetch("/error-book/stats");
}

/** 清除已掌握错题 */
export async function clearMasteredErrors(): Promise<{ cleared: number; message: string }> {
  return v7fetch("/error-book/clear-mastered", { method: "POST" });
}

// ── 复习调度 ──

export interface DueQuestion {
  question: V7Question;
  due: boolean;
  days_overdue: number;
  days_until_next_review: number;
  priority_score: number;
  consecutive_correct: number;
  wrong_count: number;
  mastered: boolean;
  ef: number;
  interval_days: number;
}

export interface ReviewStats {
  total_questions_reviewed: number;
  due_now: number;
  mastered: number;
  not_mastered: number;
  due_in_1d: number;
  due_in_7d: number;
  average_ef: number;
}

/** 获取到期望习题 */
export async function getDueQuestions(options?: {
  bank_id?: string;
  cognitive_node_id?: string;
  limit?: number;
}): Promise<DueQuestion[]> {
  const params = new URLSearchParams();
  if (options?.bank_id) params.set("bank_id", options.bank_id);
  if (options?.cognitive_node_id) params.set("cognitive_node_id", options.cognitive_node_id);
  if (options?.limit) params.set("limit", String(options.limit));
  const qs = params.toString();
  return v7fetch(`/review/due${qs ? `?${qs}` : ""}`);
}

/** 获取复习统计 */
export async function getReviewStats(options?: { bank_id?: string }): Promise<ReviewStats> {
  const qs = options?.bank_id ? `?bank_id=${options.bank_id}` : "";
  return v7fetch(`/review/stats${qs}`);
}
