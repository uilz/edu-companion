// FlashCard API 客户端
// 依据 docs/modules/flashcard/overview.md + data-model.md
import { authedFetch } from "./api";

const PREFIX = "/api/flashcards";

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

export const flashcardApi = <T,>(p: string, o?: RequestInit): Promise<T> =>
  authedFetch(`${PREFIX}${p}`, o).then(jsonOrThrow<T>);

// ── 类型 ──

export type CardType = 1 | 2 | 3 | 4 | 5 | 6 | 7;
export type CardSource =
  | "manual" | "practice_error" | "reading_note" | "conversation"
  | "project" | "language_room" | "interest_explorer";
export type CardStatus =
  | "pending" | "later" | "processing" | "completed" | "suspended" | "archived";
export type SelfAssessment = "difficult" | "good" | "easy";

export interface FlashCard {
  id: string;
  user_id: string;
  type: CardType;
  source: CardSource;
  front_text: string;
  back_text: string;
  back_context: string;
  language: string;
  source_ref: Record<string, any>;
  status: CardStatus;
  suspended_at: string | null;
  is_resolved: boolean;
  stability: number | null;
  difficulty: number | null;
  forgetting_rate: number | null;
  last_review_at: string | null;
  next_review_at: string | null;
  review_count: number;
  lapse_count: number;
  target_retention: number;
  linked_node_ids: string[];
  node_link_roles: Record<string, "primary" | "secondary">;
  tags: string[];
  error_book_entry_id: string;
  response_history: any[];
  field_versions: Record<string, number>;
  created_at: string;
  updated_at: string;
}

export interface ReviewResult {
  card_id: string;
  self_assessment: SelfAssessment;
  stability_before: number;
  stability_after: number;
  difficulty_before: number;
  difficulty_after: number;
  forgetting_rate_after: number;
  interval_before: number;
  interval_after: number;
  elapsed_days: number;
  retrievability_before: number;
  next_review_at: string;
  reviewed_at: string;
  explanation: string;
  belief_deltas: Array<{
    node_id: string;
    alpha_delta: number;
    beta_delta: number;
  }>;
}

export interface FlashCardStats {
  total: number;
  by_type: Record<string, number>;
  by_source: Record<string, number>;
  by_status: Record<string, number>;
  due_today: number;
  due_7d: number;
  average_stability: number;
  average_difficulty: number;
  average_forgetting_rate: number;
}

export interface ImportPreviewItem {
  suggested_front: string;
  suggested_back: string;
  confidence: number;
  suggested_node_ids: string[];
}

export interface ImportFromErrorBookData {
  error_entry_id: string;
  suggested_front: string;
  suggested_back: string;
  question_id: string;
  skill_id: string;
  suggested_linked_node_ids: string[];
  already_imported: boolean;
  existing_card_id: string | null;
}

// ── API 方法 ──

export const flashcardService = {
  // 列表
  list: (params: {
    status?: CardStatus;
    type?: CardType;
    source?: CardSource;
    tag?: string;
    node_id?: string;
    limit?: number;
    offset?: number;
  } = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") {
        q.set(k, String(v));
      }
    });
    return flashcardApi<{ total: number; cards: FlashCard[]; limit: number; offset: number }>(
      `/?${q.toString()}`,
    );
  },

  get: (cardId: string) => flashcardApi<FlashCard>(`/${cardId}`),

  create: (body: Partial<FlashCard> & { front_text: string; linked_node_ids: string[] }) =>
    flashcardApi<FlashCard>("/", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  update: (cardId: string, body: Partial<FlashCard> & { reset_scheduling?: boolean }) =>
    flashcardApi<FlashCard>(`/${cardId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  delete: (cardId: string) =>
    flashcardApi<{ deleted: boolean; card_id: string }>(`/${cardId}`, { method: "DELETE" }),

  // 复习
  submitReview: (cardId: string, selfAssessment: SelfAssessment, sessionId = "") =>
    flashcardApi<ReviewResult>(`/${cardId}/review`, {
      method: "POST",
      body: JSON.stringify({ self_assessment: selfAssessment, session_id: sessionId }),
    }),

  previewReview: (cardId: string, selfAssessment: SelfAssessment) =>
    flashcardApi<{
      stability_after: number;
      difficulty_after: number;
      interval_days: number;
      next_review_at: string;
    }>(`/${cardId}/preview`, {
      method: "POST",
      body: JSON.stringify({ self_assessment: selfAssessment }),
    }),

  // FSRS 控制
  override: (
    cardId: string,
    params: { stability?: number; difficulty?: number; target_retention?: number; next_review_at?: string },
  ) =>
    flashcardApi<FlashCard>(`/${cardId}/override`, {
      method: "PATCH",
      body: JSON.stringify(params),
    }),

  suspend: (cardId: string) =>
    flashcardApi<FlashCard>(`/${cardId}/suspend`, { method: "POST" }),

  resume: (cardId: string) =>
    flashcardApi<FlashCard>(`/${cardId}/resume`, { method: "POST" }),

  reset: (cardId: string) =>
    flashcardApi<FlashCard>(`/${cardId}/reset`, { method: "POST" }),

  archive: (cardId: string) =>
    flashcardApi<FlashCard>(`/${cardId}/archive`, { method: "POST" }),

  // 到期
  getDue: (limit = 20, nodeId?: string) => {
    const q = new URLSearchParams();
    q.set("limit", String(limit));
    if (nodeId) q.set("node_id", nodeId);
    return flashcardApi<{ total: number; cards: FlashCard[] }>(`/list/due?${q.toString()}`);
  },

  // 会话
  startSession: (sourceModule = "manual", limit = 20) =>
    flashcardApi<{
      session_id: string;
      started_at: string;
      initial_card_count: number;
      cards: FlashCard[];
    }>(`/session/start`, {
      method: "POST",
      body: JSON.stringify({ source_module: sourceModule, limit }),
    }),

  endSession: (
    sessionId: string,
    stats: { difficult_count: number; good_count: number; easy_count: number; duration_seconds: number },
  ) =>
    flashcardApi<{ session_id: string; ended_at: string; total: number }>(
      `/session/${sessionId}/end`,
      { method: "POST", body: JSON.stringify(stats) },
    ),

  // 导入
  importFromErrorbook: (errorId: string) =>
    flashcardApi<ImportFromErrorBookData>(`/import-from-errorbook/${errorId}`),

  confirmImportFromErrorbook: (errorId: string, extra: Record<string, any> = {}) =>
    flashcardApi<FlashCard>(`/import-from-errorbook/${errorId}/confirm`, {
      method: "POST",
      body: JSON.stringify(extra),
    }),

  importFromText: (body: { text: string; type?: CardType; tags?: string[]; default_linked_node_ids?: string[] }) =>
    flashcardApi<{ items: ImportPreviewItem[]; total: number }>(`/import-from-text`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  confirmImportFromText: (body: {
    items: ImportPreviewItem[];
    type?: CardType;
    tags?: string[];
    default_linked_node_ids?: string[];
  }) =>
    flashcardApi<{ imported: number; cards: FlashCard[] }>(`/import-from-text/confirm`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // 统计
  getStats: () => flashcardApi<FlashCardStats>(`/stats/summary`),
};

// ── 工具函数 ──

export const CARD_TYPE_LABELS: Record<CardType, string> = {
  1: "基础问答",
  2: "填空",
  3: "对比",
  4: "流程",
  5: "应用场景",
  6: "错题溯源",
  7: "反思",
};

export const CARD_SOURCE_LABELS: Record<CardSource, string> = {
  manual: "手动",
  practice_error: "练习错题",
  reading_note: "阅读笔记",
  conversation: "对话",
  project: "项目",
  language_room: "语言房间",
  interest_explorer: "兴趣探索",
};

export const STATUS_LABELS: Record<CardStatus, string> = {
  pending: "待复习",
  later: "稍后",
  processing: "处理中",
  completed: "已完成",
  suspended: "已暂停",
  archived: "已归档",
};

export const ASSESSMENT_LABELS: Record<SelfAssessment, string> = {
  difficult: "困难",
  good: "良好",
  easy: "简单",
};
