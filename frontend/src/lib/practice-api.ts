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
