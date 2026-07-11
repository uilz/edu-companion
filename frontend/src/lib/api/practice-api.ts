// ══════════════════════════════════════════════════════════════
//  练习系统 API 客户端
// ══════════════════════════════════════════════════════════════

// ── 类型 ──

export interface V7Question {
  id: string;
  bank_id: string;
  question_type: "single" | "multiple" | "judge" | "choice" | "fill" | "free_form";
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
  status: "created" | "active" | "paused" | "completed" | "timeout" | "cancelled";
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
  metacognition_feedback?: string;
  attempt_id?: string;
  submitted_event_id?: string;
}

export interface AttemptFeedbackNode {
  node_id: string | null;
  label: string;
  information_gain: number;
  proficiency_before: number;
  proficiency_after: number;
}

export interface AttemptFeedback {
  attempt_id: string;
  session_id: string;
  question_id: string;
  is_correct: boolean;
  submitted_at: string | null;
  is_final: boolean;
  feedback: {
    information_gain: number;
    uncertainty_reduction_percent: number;
    proficiency_before: number;
    proficiency_after: number;
    uncertainty_before: number;
    uncertainty_after: number;
    nodes: AttemptFeedbackNode[];
  };
  metacognition: {
    advice: string;
    confidence_before: number | null;
    bias: string;
  };
  suggestions: Array<{
    type: string;
    title: string;
    node_id?: string | null;
    reason: string;
  }>;
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
  bank_name?: string;
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

import { practiceApi, authedFetch } from "@/lib/api/api";
import type { SelfExplainRequest, SelfExplainResult } from "@/types";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  return practiceApi<T>(path, options);
}

/** 根据知识点 ID 解析（或创建）题库 */
export async function resolveBankForNode(nodeId: string): Promise<{ bank_id: string; bank: V7Bank }> {
  return apiFetch("/resolve/node", {
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
    question_ids?: string[];
  }
): Promise<V7Session> {
  const body: Record<string, any> = {
    bank_id: bankId,
    mode: options?.mode ?? "adaptive",
    count: options?.count ?? 5,
  };
  if (options?.cognitive_node_ids) body.cognitive_node_ids = options.cognitive_node_ids;
  if (options?.config) body.config = options.config;
  if (options?.question_ids) body.question_ids = options.question_ids;
  return apiFetch("/sessions", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** 提交答题 */
export async function submitAnswer(
  sessionId: string,
  questionId: string,
  answer: string[],
  timeSpent?: number,
  hintsUsed?: number,
  confidenceBefore?: number
): Promise<V7SubmitResult> {
  return apiFetch(`/sessions/${sessionId}/submit`, {
    method: "POST",
    body: JSON.stringify({
      question_id: questionId,
      answer,
      time_spent: timeSpent ?? 0,
      hints_used: hintsUsed ?? 0,
      confidence_before: confidenceBefore,
    }),
  });
}

/** 按 attempt_id 查询答题后的信息增益与掌握度变化 */
export async function getAttemptFeedback(attemptId: string): Promise<AttemptFeedback> {
  return apiFetch(`/feedback/${attemptId}`);
}

/** 完成会话 */
export async function completeSession(sessionId: string): Promise<V7Session> {
  return apiFetch(`/sessions/${sessionId}/complete`, { method: "POST" });
}

/** 获取会话详情 */
export async function getSession(sessionId: string): Promise<V7Session> {
  return apiFetch(`/sessions/${sessionId}`);
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
  return apiFetch(`/sessions${qs ? `?${qs}` : ""}`);
}

/** AI 出题（支持指定参考资料） */
export async function generateQuestions(
  message: string,
  options?: {
    bank_id?: string;
    conv_id?: string;
    node_id?: string;
    material_ids?: string[];
  }
): Promise<{
  bank_id: string;
  bank_name: string;
  generated: number;
  questions: V7Question[];
  has_material_context?: boolean;
  params: any;
}> {
  return apiFetch("/generate", {
    method: "POST",
    body: JSON.stringify({
      message,
      ...options,
    }),
  });
}

/** 基于指定资料出题（显式参数） */
export async function generateFromMaterials(
  materialIds: string[],
  options?: {
    subject?: string;
    skill_id?: string;
    bloom_level?: string;
    difficulty?: number;
    count?: number;
    content_type?: string;
    bank_id?: string;
  }
): Promise<{
  bank_id: string;
  bank_name: string;
  generated: number;
  questions: V7Question[];
  has_material_context: boolean;
  material_count: number;
  params: any;
}> {
  return apiFetch("/generate-from-materials", {
    method: "POST",
    body: JSON.stringify({
      material_ids: materialIds,
      ...options,
    }),
  });
}

// ── 资料 ──

export interface MaterialItem {
  material_id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  purpose: string;
  status: string;
  chunk_count: number;
  skills: string[];
  created_at: string;
  indexed_at: string | null;
}

export interface MaterialListResult {
  total: number;
  page: number;
  page_size: number;
  items: MaterialItem[];
}

/** 获取已上传资料列表 */
export async function listMaterials(
  options?: {
    purpose?: string;
    status?: string;
    search?: string;
    page?: number;
    page_size?: number;
  }
): Promise<MaterialListResult> {
  const params = new URLSearchParams();
  if (options?.purpose) params.set("purpose", options.purpose);
  if (options?.status) params.set("status", options.status);
  if (options?.search) params.set("search", options.search);
  if (options?.page) params.set("page", String(options.page));
  if (options?.page_size) params.set("page_size", String(options.page_size));
  const qs = params.toString();
  const res = await fetch(`/api/files${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

/** 获取题库列表 */
export async function listBanks(): Promise<V7Bank[]> {
  return apiFetch("/banks");
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
  return apiFetch("/stats/overview");
}

/** 获取每日趋势 */
export async function getDailyTrend(days: number = 30): Promise<V7DailyPoint[]> {
  return apiFetch(`/stats/daily?days=${days}`);
}

/** 获取会话历史 */
export async function getSessionHistory(limit: number = 10): Promise<V7SessionListItem[]> {
  return apiFetch(`/stats/sessions?limit=${limit}`);
}

/** 获取薄弱知识点 */
export async function getWeakSkills(): Promise<{ skill_id: string; label: string; mastery: number; attempts: number; trend: string; load: number }[]> {
  return apiFetch("/stats/weak-skills");
}

/** 综合推荐：薄弱知识点 + 待复习题目 + 推荐题库 + 学习建议 */
export interface PracticeRecommendation {
  weak_skills: { skill_id: string; label: string; mastery: number; attempts: number; trend: string }[];
  due_questions: DueQuestion[];
  due_review_count: number;
  suggested_banks: { id: string; name: string; matching_questions: number }[];
  study_suggestions: string[];
  total_weak: number;
}
export async function getRecommendations(limit: number = 5): Promise<PracticeRecommendation> {
  return apiFetch(`/recommendations?limit=${limit}`);
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
  cold_start?: boolean;
  cold_start_hint?: string;
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
  return apiFetch(`/error-book${qs ? `?${qs}` : ""}`);
}

/** 获取错题本概览 */
export async function getErrorBookStats(): Promise<ErrorBookStats> {
  return apiFetch("/error-book/stats");
}

/** 清除已掌握错题 */
export async function clearMasteredErrors(): Promise<{ cleared: number; message: string }> {
  return apiFetch("/error-book/clear-mastered", { method: "POST" });
}

// ── 参考资料 ──

export interface ReferenceResult {
  bvid: string;
  title: string;
  author: string;
  cover: string;
  link: string;
  duration: string;
  played: string;
  danmaku: number;
  description: string;
}

export interface ReferenceResponse {
  results: ReferenceResult[];
  total: number;
  error?: string;
  node_label?: string;
  search_query?: string;
}

/** 搜索参考资料（B站视频） */
export async function searchReferences(
  query: string,
  options?: { source?: string; page?: number; page_size?: number }
): Promise<ReferenceResponse> {
  const params = new URLSearchParams({ q: query });
  if (options?.source) params.set("source", options.source);
  if (options?.page) params.set("page", String(options.page));
  if (options?.page_size) params.set("page_size", String(options.page_size));
  return apiFetch(`/references/search?${params.toString()}`);
}

/** 根据知识点搜索参考资料 */
export async function searchReferencesForNode(
  nodeId: string,
  source?: string
): Promise<ReferenceResponse & { node_label?: string }> {
  const params = new URLSearchParams({ node_id: nodeId });
  if (source) params.set("source", source);
  return apiFetch(`/references/for-node?${params.toString()}`);
}

/** 根据题目搜索参考资料 */
export async function searchReferencesForQuestion(
  questionId: string,
  source?: string
): Promise<ReferenceResponse & { search_query?: string }> {
  const params = new URLSearchParams({ question_id: questionId });
  if (source) params.set("source", source);
  return apiFetch(`/references/for-question?${params.toString()}`);
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
  is_cold_start?: boolean;
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
  return apiFetch(`/review/due${qs ? `?${qs}` : ""}`);
}

/** 获取复习统计 */
export async function getReviewStats(options?: { bank_id?: string }): Promise<ReviewStats> {
  const qs = options?.bank_id ? `?bank_id=${options.bank_id}` : "";
  return apiFetch(`/review/stats${qs}`);
}

// ── 考试模式 ──

export interface ExamConfig {
  mode: string;
  duration_minutes: number;
  deadline: string;
  question_count: number;
}

export interface ExamQuestion {
  id: string;
  sort_order: number;
  stem: string;
  options: V7Option[];
  question_type: string;
  difficulty: number;
  cognitive_node_ids: string[];
  answered: boolean;
  is_correct: boolean | null;
}

export interface ExamResult {
  session_id: string;
  status: string;
  user_id: string;
  score: number;
  grade: string;
  grade_color: string;
  stats: {
    total: number;
    answered: number;
    correct: number;
    wrong: number;
    unanswered: number;
    score: number;
    duration: number;
    finished_at: string;
  };
  type_stats: Record<string, { total: number; correct: number; wrong: number }>;
  question_results: ExamQuestionResult[];
}

export interface ExamQuestionResult {
  sort_order: number;
  question_id: string;
  stem: string;
  question_type: string;
  user_answer: string[];
  correct_answer: string[];
  is_correct: boolean;
  analysis: string;
  time_spent: number;
}

export interface ExamTimeInfo {
  valid: boolean;
  status: string;
  remaining_seconds: number;
  elapsed_seconds?: number;
  deadline?: string;
  auto_submitted?: boolean;
  message?: string;
  error?: string;
}

export interface AnswerSheetItem {
  index: number;
  question_id: string;
  answered: boolean;
  is_correct: boolean | null;
}

export interface AnswerSheetResult {
  session_id: string;
  total: number;
  answered: number;
  unanswered: number;
  items: AnswerSheetItem[];
}

/** 创建考试 */
export async function createExam(
  bankId: string,
  options?: {
    count?: number;
    duration_minutes?: number;
    cognitive_node_ids?: string[];
    config?: Record<string, any>;
  }
): Promise<{
  session_id: string;
  bank_id: string;
  mode: string;
  session_type: string;
  status: string;
  total_count: number;
  questions: ExamQuestion[];
  config: ExamConfig;
  deadline: string;
  duration_minutes: number;
  created_at: string;
}> {
  return apiFetch("/exam", {
    method: "POST",
    body: JSON.stringify({
      bank_id: bankId,
      ...options,
    }),
  });
}

/** 获取考试剩余时间 */
export async function getExamTime(sessionId: string): Promise<ExamTimeInfo> {
  return apiFetch(`/exam/${sessionId}/time`);
}

/** 提交考试单题答案 */
export async function submitExamAnswer(
  sessionId: string,
  questionId: string,
  answer: string[],
  timeSpent?: number,
  isFinal?: boolean,
): Promise<{ is_correct: boolean; correct_answer: string[]; explanation: string }> {
  return apiFetch(`/exam/${sessionId}/submit`, {
    method: "POST",
    body: JSON.stringify({
      question_id: questionId,
      answer,
      time_spent: timeSpent ?? 0,
      is_final: isFinal ?? false,
    }),
  });
}

/** 提交考试所有答案 */
export async function submitAllExam(sessionId: string): Promise<ExamResult> {
  return apiFetch(`/exam/${sessionId}/submit-all`, { method: "POST" });
}

/** 获取考试成绩报告 */
export async function getExamResult(sessionId: string): Promise<ExamResult> {
  return apiFetch(`/exam/${sessionId}/result`);
}

/** 获取答题卡状态 */
export async function getExamAnswerSheet(sessionId: string): Promise<AnswerSheetResult> {
  return apiFetch(`/exam/${sessionId}/answer-sheet`);
}

// ── 题目辅助 ──

/** 获取题目提示（渐进式） */
export async function getQuestionHint(
  questionId: string,
  currentLevel: number = 0
): Promise<{
  hint: { level: number; text: string; type: string };
  next_level_available: boolean;
}> {
  const res = await authedFetch("/api/practice/hint", {
    method: "POST",
    body: JSON.stringify({ question_id: questionId, current_level: currentLevel }),
  });
  return res.json();
}

/** AI 深入讲解某道题 */
export async function getQuestionExplanation(
  questionId: string,
  style: "detailed" | "concise" | "step_by_step" = "detailed"
): Promise<{ explanation: string; question_id: string; style: string }> {
  return apiFetch(`/questions/${questionId}/explain?style=${style}`);
}

/** 生成同类变体题目 */
export async function generateSimilarQuestions(
  questionId: string,
  count: number = 3
): Promise<{ generated: number; questions: V7Question[] }> {
  return apiFetch(`/questions/${questionId}/similar`, {
    method: "POST",
    body: JSON.stringify({ count }),
  });
}

/** 收藏/取消收藏 */
export async function toggleFavorite(questionId: string): Promise<{ is_favorite: boolean }> {
  return apiFetch(`/questions/${questionId}/favorite`, { method: "POST" });
}

/** 斩题/恢复 */
export async function toggleSlash(questionId: string): Promise<{ is_slashed: boolean }> {
  return apiFetch(`/questions/${questionId}/slash`, { method: "POST" });
}

// ── 批量和对话出题 ──

/** 批量出题：一次对多个知识点生成不同 Bloom 层次的题目 */
export async function bulkGenerateQuestions(
  bankId: string,
  plans: { skill_id: string; subject: string; bloom_level: string; count: number }[],
  materialIds?: string[]
): Promise<{ generated: number; questions: V7Question[] }> {
  return apiFetch("/generate-bulk", {
    method: "POST",
    body: JSON.stringify({ bank_id: bankId, plans, material_ids: materialIds }),
  });
}

/** 对话场景出题 */
export async function generateFromConversation(
  conversationId: string,
  message: string,
  context?: any[],
  materialIds?: string[]
): Promise<{ bank_id: string; generated: number; questions: V7Question[] }> {
  return apiFetch("/generate-from-conversation", {
    method: "POST",
    body: JSON.stringify({
      conv_id: conversationId,
      message,
      context,
      material_ids: materialIds,
    }),
  });
}

// ── 会话结果 ──

/** 获取会话结果报告 */
export async function getSessionResult(sessionId: string): Promise<{
  session_id: string;
  score: number;
  total: number;
  correct: number;
  wrong: number;
  accuracy: number;
  duration_seconds: number;
  question_results: any[];
  cognitive_summary: any;
}> {
  return apiFetch(`/sessions/${sessionId}/result`);
}

// ── 未完成会话 ──

export interface UnfinishedSession {
  session_id: string;
  bank_id: string;
  session_type: string;
  mode: string;
  status: string;
  total_count: number;
  answered_count: number;
  created_at: string;
}

/** 获取未完成的会话列表 */
export async function getUnfinishedSessions(): Promise<{ items: UnfinishedSession[]; total: number }> {
  return apiFetch("/sessions/unfinished");
}

// ── 错题本扩展 ──

/** 错题复习提交 */
export async function reviewErrorQuestion(
  questionId: string,
  isCorrect: boolean,
  timeSpent: number = 0
): Promise<{ reviewed: string; is_correct: boolean }> {
  return apiFetch(`/error-book/${questionId}/review`, {
    method: "POST",
    body: JSON.stringify({ is_correct: isCorrect, time_spent: timeSpent }),
  });
}

/** 错题关联资料推荐 */
export async function getErrorMaterials(
  questionId: string,
  limit: number = 3
): Promise<{ question_id: string; materials: any[] }> {
  return apiFetch(`/error-book/${questionId}/materials?limit=${limit}`);
}

// ── 答题历史 ──

export interface AnswerHistoryItem {
  attempt_id: string;
  session_id: string;
  question_id: string;
  user_answer: string[];
  is_correct: boolean;
  time_spent_seconds: number;
  is_wrong: boolean;
  wrong_count: number;
  consecutive_correct: number;
  cognitive_node_ids: string[];
  created_at: string;
  question_stem: string;
  question_type: string;
  difficulty: number;
  correct_answer: string[];
}

/** 获取答题历史 */
export async function getAnswerHistory(options?: {
  question_id?: string;
  session_id?: string;
  limit?: number;
  offset?: number;
}): Promise<{ items: AnswerHistoryItem[]; total: number; limit: number; offset: number }> {
  const params = new URLSearchParams();
  if (options?.question_id) params.set("question_id", options.question_id);
  if (options?.session_id) params.set("session_id", options.session_id);
  if (options?.limit) params.set("limit", String(options.limit));
  if (options?.offset) params.set("offset", String(options.offset));
  const qs = params.toString();
  return apiFetch(`/history/answers${qs ? `?${qs}` : ""}`);
}

// ── 错题分布 ──

/** 获取错题分布统计 */
export async function getErrorDistribution(): Promise<{
  by_difficulty: Record<string, number>;
  by_type: Record<string, number>;
  by_node: { node_id: string; label: string; count: number }[];
  total_errors: number;
}> {
  return apiFetch("/stats/errors");
}

// ── 秘书提案 ──

export interface SecretaryProposal {
  id: string;
  emoji: string;
  title: string;
  description: string;
  action_type: string;
  payload: Record<string, any>;
  priority: number;
  created_at: number;
}

/** 获取秘书提案 */
export async function getSecretaryProposals(limit: number = 5): Promise<{ proposals: SecretaryProposal[] }> {
  return apiFetch(`/secretary/proposals?limit=${limit}`);
}

/** 接受秘书提案 */
export async function acceptProposal(proposalId: string): Promise<any> {
  return apiFetch(`/secretary/proposals/${proposalId}/accept`, { method: "POST" });
}

/** 忽略秘书提案 */
export async function dismissProposal(proposalId: string): Promise<any> {
  return apiFetch(`/secretary/proposals/${proposalId}/dismiss`, { method: "POST" });
}

// ── 题库 CRUD ──

/** 创建题库 */
export async function createBank(
  name: string,
  options?: { description?: string; ref_node_id?: string; ref_node_level?: string }
): Promise<V7Bank> {
  return apiFetch("/banks", {
    method: "POST",
    body: JSON.stringify({ name, ...options }),
  });
}

/** 更新题库 */
export async function updateBank(
  bankId: string,
  updates: { name?: string; description?: string }
): Promise<V7Bank> {
  return apiFetch(`/banks/${bankId}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

/** 删除题库 */
export async function deleteBank(bankId: string): Promise<{ deleted: string }> {
  return apiFetch(`/banks/${bankId}`, { method: "DELETE" });
}

// ── 题库详情与题目 CRUD ──

/** 获取题库详情 */
export async function getBank(bankId: string): Promise<V7Bank & { created_at?: string; ref_node_id?: string; ref_node_label?: string }> {
  return apiFetch(`/banks/${bankId}`);
}

/** 获取题库题目列表（分页） */
export async function getBankQuestions(
  bankId: string,
  options?: {
    page?: number;
    page_size?: number;
    question_type?: string;
    status?: string;
    cognitive_node_id?: string;
  }
): Promise<{ items: V7Question[]; total: number; page: number; page_size: number; total_pages: number }> {
  const params = new URLSearchParams();
  if (options?.page) params.set("page", String(options.page));
  if (options?.page_size) params.set("page_size", String(options.page_size));
  if (options?.question_type) params.set("question_type", options.question_type);
  if (options?.status) params.set("status", options.status);
  if (options?.cognitive_node_id) params.set("cognitive_node_id", options.cognitive_node_id);
  const qs = params.toString();
  return apiFetch(`/banks/${bankId}/questions${qs ? `?${qs}` : ""}`);
}

/** 手动添加题目到题库 */
export async function createQuestion(
  bankId: string,
  params: {
    question_type?: string;
    stem: string;
    answer: string[];
    options?: V7Option[];
    analysis?: string;
    difficulty?: number;
    cognitive_node_ids?: string[];
    source?: string;
    metadata?: Record<string, any>;
  }
): Promise<V7Question> {
  return apiFetch(`/banks/${bankId}/questions`, {
    method: "POST",
    body: JSON.stringify(params),
  });
}

/** 获取题目详情 */
export async function getQuestion(questionId: string): Promise<V7Question & { answer?: string[]; analysis?: string; source?: string; created_at?: string }> {
  return apiFetch(`/questions/${questionId}`);
}

/** 题目富预览：详情 + 相似题 + 关联资料 + 答题统计 + 知识点 */
export interface QuestionPreview extends V7Question {
  knowledge_nodes: { id: string; label: string }[];
  similar_questions: { id: string; stem: string; difficulty: number; question_type: string }[];
  related_materials: { id: string; name: string; type: string }[];
  attempt_stats: { total: number; correct: number; correct_rate: number };
}
export async function getQuestionPreview(
  questionId: string,
  options?: { include_similar?: boolean; include_materials?: boolean }
): Promise<QuestionPreview> {
  const params = new URLSearchParams();
  if (options?.include_similar !== undefined) params.set("include_similar", String(options.include_similar));
  if (options?.include_materials !== undefined) params.set("include_materials", String(options.include_materials));
  const qs = params.toString();
  return apiFetch(`/questions/${questionId}/preview${qs ? `?${qs}` : ""}`);
}

/** 更新题目 */
export async function updateQuestion(
  questionId: string,
  updates: {
    question_type?: string;
    stem?: string;
    answer?: string[];
    options?: V7Option[];
    analysis?: string;
    difficulty?: number;
    cognitive_node_ids?: string[];
  }
): Promise<V7Question> {
  return apiFetch(`/questions/${questionId}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

/** 删除题目 */
export async function deleteQuestion(questionId: string): Promise<{ deleted: string }> {
  return apiFetch(`/questions/${questionId}`, { method: "DELETE" });
}

/** 批量复制题目到题库 */
export async function copyQuestionsToBank(
  bankId: string,
  questionIds?: string[],
  sourceBankId?: string,
): Promise<{ copied: number; questions: V7Question[] }> {
  const body: Record<string, any> = {};
  if (questionIds?.length) body.question_ids = questionIds;
  if (sourceBankId) body.source_bank_id = sourceBankId;
  return apiFetch(`/banks/${bankId}/questions/copy`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** 重排题库题目顺序 */
export async function reorderQuestionsInBank(
  bankId: string,
  questionIds: string[],
): Promise<{ ok: boolean }> {
  return apiFetch(`/banks/${bankId}/questions/reorder`, {
    method: "PUT",
    body: JSON.stringify({ question_ids: questionIds }),
  });
}

// ── 题库解析 ──

/** 解析对话应归属的题库 */
export async function resolveBankForConversation(
  conversationId: string,
  userSpecifiedBankId?: string
): Promise<{ bank_id: string; bank: V7Bank }> {
  return apiFetch("/resolve/conversation", {
    method: "POST",
    body: JSON.stringify({
      conv_id: conversationId,
      bank_id: userSpecifiedBankId,
    }),
  });
}

// ── 会话控制操作 ──

/** 开始会话 */
export async function startSession(sessionId: string): Promise<any> {
  return apiFetch(`/sessions/${sessionId}/start`, { method: "PATCH" });
}

/** 暂停会话 */
export async function pauseSession(sessionId: string): Promise<any> {
  return apiFetch(`/sessions/${sessionId}/pause`, { method: "PATCH" });
}

/** 恢复会话 */
export async function resumeSession(sessionId: string): Promise<any> {
  return apiFetch(`/sessions/${sessionId}/resume`, { method: "PATCH" });
}

/** 取消/删除会话 */
export async function cancelSession(sessionId: string): Promise<any> {
  return apiFetch(`/sessions/${sessionId}`, { method: "DELETE" });
}

// ── 成就系统 ──

export interface Achievement {
  id: string;
  name: string;
  description: string;
  emoji: string;
  tier: number;
  max_tier: number;
  unlocked: boolean;
  unlocked_at: string | null;
  progress: number;
  progress_max: number;
}

/** 获取所有成就及进度 */
export async function getAchievements(): Promise<{ achievements: Achievement[] }> {
  return apiFetch("/achievements");
}

/** 最近解锁成就 */
export async function getRecentAchievements(limit: number = 5): Promise<{ unlocked: Achievement[] }> {
  return apiFetch(`/achievements/recent?limit=${limit}`);
}

/** 成就统计 */
export async function getAchievementStats(): Promise<{ total: number; unlocked: number; by_tier: Record<string, { unlocked: number; total: number }> }> {
  return apiFetch("/achievements/stats");
}

/** 手动触发成就检测 */
export async function checkAchievements(): Promise<{ newly_unlocked: Achievement[]; count: number }> {
  return apiFetch("/achievements/check", { method: "POST" });
}

// ── 题库导入 ──

export interface ImportPreviewItem {
  stem: string;
  question_type: string;
  answer: string[];
  options?: V7Option[];
  analysis?: string;
  difficulty?: number;
  confidence?: number;
  suggested_node_ids?: string[];
}

export interface ImportPreviewResult {
  questions: ImportPreviewItem[];
  stats: { total: number; high_confidence: number; low_confidence: number };
}

export interface ImportConfirmResult {
  imported: number;
  questions: V7Question[];
}

/** 上传文件解析预览 */
export async function uploadImport(
  filePath: string,
  fileType: string,
  bankId?: string
): Promise<ImportPreviewResult> {
  return apiFetch("/import/upload", {
    method: "POST",
    body: JSON.stringify({ file_path: filePath, file_type: fileType, bank_id: bankId }),
  });
}

/** 解析文本预览（无需上传文件） */
export async function previewImport(text: string): Promise<ImportPreviewResult> {
  return apiFetch("/import/preview", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

/** 确认导入题目到题库 */
export async function confirmImport(
  bankId: string,
  questions: ImportPreviewItem[]
): Promise<ImportConfirmResult> {
  return apiFetch("/import/confirm", {
    method: "POST",
    body: JSON.stringify({ bank_id: bankId, questions }),
  });
}

/** 批量导入题目（JSON） */
export async function batchImport(
  bankId: string,
  questions: any[]
): Promise<{ imported: number; questions: V7Question[] }> {
  return apiFetch("/import/batch", {
    method: "POST",
    body: JSON.stringify({ bank_id: bankId, questions }),
  });
}

/** 获取导入历史 */
export async function getImportHistory(options?: {
  bank_id?: string;
  limit?: number;
  offset?: number;
}): Promise<{ items: any[]; total: number }> {
  const params = new URLSearchParams();
  if (options?.bank_id) params.set("bank_id", options.bank_id);
  if (options?.limit) params.set("limit", String(options.limit));
  if (options?.offset) params.set("offset", String(options.offset));
  const qs = params.toString();
  return apiFetch(`/import/history${qs ? `?${qs}` : ""}`);
}

// ── 自适应选题 ──

/** 自适应选题 */
export async function adaptiveSelect(
  bankId: string,
  options?: {
    count?: number;
    mode?: string;
    cognitive_node_ids?: string[];
    exclude_ids?: string[];
  }
): Promise<{ selected: number; questions: V7Question[]; params: Record<string, any> }> {
  return apiFetch("/adaptive/select", {
    method: "POST",
    body: JSON.stringify({
      bank_id: bankId,
      count: options?.count ?? 10,
      mode: options?.mode ?? "adaptive",
      cognitive_node_ids: options?.cognitive_node_ids,
      exclude_ids: options?.exclude_ids,
    }),
  });
}

// ── 自信度校准报告 ──

export interface ConfidenceReportSubject {
  subject: string;
  sample_count: number;
  mean_bias: number;
  direction: "overconfident" | "underconfident" | "accurate";
}

export interface ConfidenceReport {
  user_id: string;
  days: number;
  overall_bias: number;
  by_subject: ConfidenceReportSubject[];
  suggestion: string;
}

/** 获取自信度校准报告 */
export async function fetchConfidenceReport(
  options?: { subject?: string; days?: number }
): Promise<ConfidenceReport> {
  const params = new URLSearchParams();
  if (options?.subject) params.set("subject", options.subject);
  if (options?.days) params.set("days", String(options.days ?? 30));
  const qs = params.toString();
  return apiFetch(`/confidence-report${qs ? `?${qs}` : ""}`);
}

// ── 自我解释评估（P0-R03）─

/** 提交自我解释并获取评估结果 */
export async function submitSelfExplain(req: SelfExplainRequest): Promise<SelfExplainResult> {
  return apiFetch<SelfExplainResult>("/self-explain", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

// ══════════════════════════════════════════════════════════════
//  Practice Service (aggregate object for convenience)
// ══════════════════════════════════════════════════════════════

export const practiceService = {
  acceptProposal,
  adaptiveSelect,
  batchImport,
  bulkGenerateQuestions,
  cancelSession,
  checkAchievements,
  clearMasteredErrors,
  completeSession,
  confirmImport,
  copyQuestionsToBank,
  createBank,
  createExam,
  createPracticeSession,
  createQuestion,
  deleteBank,
  deleteQuestion,
  dismissProposal,
  fetchConfidenceReport,
  generateFromConversation,
  generateFromMaterials,
  generateQuestions,
  generateSimilarQuestions,
  getAchievements,
  getAchievementStats,
  getAnswerHistory,
  getAttemptFeedback,
  getBank,
  getBankQuestions,
  getDailyTrend,
  getDueQuestions,
  getErrorBook,
  getErrorBookStats,
  getErrorDistribution,
  getErrorMaterials,
  getExamAnswerSheet,
  getExamResult,
  getExamTime,
  getImportHistory,
  getOverview,
  getQuestion,
  getQuestionExplanation,
  getQuestionHint,
  getQuestionPreview,
  getRecentAchievements,
  getRecommendations,
  getReviewStats,
  getSecretaryProposals,
  getSession,
  getSessionHistory,
  getSessionResult,
  getUnfinishedSessions,
  getWeakSkills,
  listBanks,
  listMaterials,
  listSessions,
  pauseSession,
  previewImport,
  reorderQuestionsInBank,
  resolveBankForConversation,
  resolveBankForNode,
  resumeSession,
  reviewErrorQuestion,
  searchReferences,
  searchReferencesForNode,
  searchReferencesForQuestion,
  startSession,
  submitAllExam,
  submitAnswer,
  submitExamAnswer,
  submitSelfExplain,
  toggleFavorite,
  toggleSlash,
  updateBank,
  updateQuestion,
  uploadImport,
};
