// Reading API 客户端
// 依据 docs/modules/reading/overview.md + data-model.md + ADR 0003
import { authedFetch } from "./api";

// ── 枚举 ──

export type AnnotationColor = "yellow" | "blue" | "green" | "purple" | "orange";
export type AnnotationIntent =
  | "important_concept" | "data_fact" | "quotable" | "doubt" | "conflict";
export type ReadingMode = "intensive" | "skim" | "review";

// ── 类型 ──

export interface ReadingAnnotation {
  id: string;
  user_id: string;
  material_id: string;
  chunk_id: string | null;
  start_offset: number | null;
  end_offset: number | null;
  color: AnnotationColor;
  intent: AnnotationIntent;
  text: string | null;
  note: string | null;
  linked_node_id: string | null;
  is_processed: boolean;
  followup: {
    label?: string;
    intent?: string;
    suggestion?: string;
    next_action?: string;
  };
  created_at: string;
  updated_at: string;
}

export interface ReadingSession {
  id: string;
  user_id: string;
  material_id: string;
  mode: ReadingMode;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number | null;
  chapters_visited: string[];
  annotations_created: number;
  notes_created: number;
  cards_generated: number;
  linked_node_ids: string[];
  state_snapshot: Record<string, any>;
  last_active_at: string | null;
}

export interface ReadingPrefs {
  user_id: string;
  default_mode: ReadingMode;
  highlight_mastered: boolean;
  highlight_weak: boolean;
  auto_open_sidebar: boolean;
  sync_scroll_default: boolean;
  review_reminder_days: number[];
}

export interface ReviewReminderResult {
  plan_item_id: string;
  material_id: string;
  review_after_days: number;
  scheduled_for: string;
  plan_item: Record<string, any>;
}

export interface ComparePayload {
  material_id_left: string;
  material_id_right: string;
  sync_scroll: boolean;
  left: {
    material_id: string;
    annotations: ReadingAnnotation[];
    annotations_count: number;
    by_color: Record<AnnotationColor, number>;
  };
  right: {
    material_id: string;
    annotations: ReadingAnnotation[];
    annotations_count: number;
    by_color: Record<AnnotationColor, number>;
  };
}

export interface ColorFollowup {
  color_intent_map: Record<AnnotationColor, AnnotationIntent>;
  color_followup: Record<
    AnnotationColor,
    { label: string; intent: AnnotationIntent; suggestion: string; next_action: string }
  >;
}

// ── 工具 ──

const PREFIX = "/api/reading";

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

function readingApi<T,>(p: string, o?: RequestInit): Promise<T> {
  return authedFetch(`${PREFIX}${p}`, o).then(jsonOrThrow<T>);
}

// ── API 方法 ──

export const readingService = {
  // 会话
  startSession: (body: { material_id: string; mode?: ReadingMode }) =>
    readingApi<ReadingSession>("/sessions", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  endSession: (sessionId: string, duration_seconds?: number) =>
    readingApi<ReadingSession>(`/sessions/${sessionId}/end`, {
      method: "POST",
      body: JSON.stringify({ duration_seconds }),
    }),

  getSession: (sessionId: string) =>
    readingApi<ReadingSession>(`/sessions/${sessionId}`),

  getActiveSession: (materialId: string) =>
    readingApi<ReadingSession>(`/sessions/active?material_id=${encodeURIComponent(materialId)}`),

  listSessions: (params: { material_id?: string; limit?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.material_id) q.set("material_id", params.material_id);
    if (params.limit) q.set("limit", String(params.limit));
    const qs = q.toString();
    return readingApi<{ items: ReadingSession[]; total: number }>(
      `/sessions${qs ? "?" + qs : ""}`,
    );
  },

  changeMode: (sessionId: string, mode: ReadingMode) =>
    readingApi<ReadingSession>(`/sessions/${sessionId}/mode`, {
      method: "POST",
      body: JSON.stringify({ mode }),
    }),

  updateActivity: (
    sessionId: string,
    payload: {
      chapter_visited?: string;
      state_snapshot?: Record<string, any>;
      annotations_delta?: number;
      notes_delta?: number;
      cards_delta?: number;
      node_linked?: string;
    },
  ) =>
    readingApi<ReadingSession>(`/sessions/${sessionId}/activity`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // 标注
  createAnnotation: (body: {
    material_id: string;
    color: AnnotationColor;
    intent?: AnnotationIntent;
    chunk_id?: string;
    start_offset?: number;
    end_offset?: number;
    text?: string;
    note?: string;
    linked_node_id?: string;
  }) =>
    readingApi<ReadingAnnotation>("/annotations", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  updateAnnotation: (id: string, body: Partial<ReadingAnnotation>) =>
    readingApi<ReadingAnnotation>(`/annotations/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  deleteAnnotation: (id: string) =>
    readingApi<{ deleted: boolean; annotation_id: string }>(`/annotations/${id}`, {
      method: "DELETE",
    }),

  processAnnotation: (id: string, target_module: "flashcard" | "conversation" | "cognitive_node" | "project", target_ref_id: string) =>
    readingApi<ReadingAnnotation>(`/annotations/${id}/process`, {
      method: "POST",
      body: JSON.stringify({ target_module, target_ref_id }),
    }),

  listAnnotations: (params: {
    material_id: string;
    color?: AnnotationColor;
    chunk_id?: string;
    grouped?: boolean;
    limit?: number;
  }) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") {
        q.set(k, String(v));
      }
    });
    return readingApi<
      | { items: ReadingAnnotation[]; total: number }
      | { material_id: string; grouped: Record<AnnotationColor, ReadingAnnotation[]>; total: number }
    >(`/materials/${encodeURIComponent(params.material_id)}/annotations?${q.toString()}`);
  },

  // 笔记 (复用 FlashCard 反思型)
  createNote: (body: {
    material_id: string;
    front_text: string;
    back_text?: string;
    back_context?: string;
    linked_node_ids: string[];
    chunk_id?: string;
    chunk_id_range?: string[];
    tags?: string[];
    language?: string;
    session_id?: string;
  }) =>
    readingApi<any>("/notes", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listNotes: (params: { material_id?: string; limit?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.material_id) q.set("material_id", params.material_id);
    if (params.limit) q.set("limit", String(params.limit));
    const qs = q.toString();
    return readingApi<{
      items: any[];
      total: number;
      source: string;
      note: string;
    }>(`/notes${qs ? "?" + qs : ""}`);
  },

  // 回顾提醒 (复用 PlanItem)
  createReviewReminder: (body: {
    material_id: string;
    review_after_days: number;
    title?: string;
    description?: string;
    estimated_minutes?: number;
  }) =>
    readingApi<ReviewReminderResult>("/review-reminder", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listReviewReminders: (material_id?: string) => {
    const q = material_id ? `?material_id=${encodeURIComponent(material_id)}` : "";
    return readingApi<{ items: any[]; total: number }>(`/review-reminder${q}`);
  },

  cancelReviewReminder: (planItemId: string) =>
    readingApi<{ deleted: boolean; plan_item_id: string }>(`/review-reminder/${planItemId}`, {
      method: "DELETE",
    }),

  // 偏好
  getPrefs: () => readingApi<ReadingPrefs>("/prefs"),
  updatePrefs: (body: Partial<ReadingPrefs>) =>
    readingApi<ReadingPrefs>("/prefs", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  // 对比
  buildCompare: (params: { material_id_left: string; material_id_right: string; sync_scroll?: boolean }) => {
    const q = new URLSearchParams();
    q.set("material_id_left", params.material_id_left);
    q.set("material_id_right", params.material_id_right);
    if (params.sync_scroll !== undefined) q.set("sync_scroll", String(params.sync_scroll));
    return readingApi<ComparePayload>(`/compare?${q.toString()}`);
  },

  createCompare: (body: { material_id_left: string; material_id_right: string; sync_scroll?: boolean }) =>
    readingApi<any>("/compare", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // 元数据
  getColorFollowup: () => readingApi<ColorFollowup>("/meta/colors"),
};

// ── 标签 ──

export const COLOR_LABELS: Record<AnnotationColor, string> = {
  yellow: "重要概念",
  blue: "数据/事实",
  green: "可引用",
  purple: "疑问/反驳",
  orange: "冲突",
};

export const INTENT_LABELS: Record<AnnotationIntent, string> = {
  important_concept: "重要概念",
  data_fact: "数据/事实",
  quotable: "可引用",
  doubt: "疑问/反驳",
  conflict: "冲突",
};

export const MODE_LABELS: Record<ReadingMode, string> = {
  intensive: "精读",
  skim: "略读",
  review: "回顾",
};

export const COLOR_HEX: Record<AnnotationColor, string> = {
  yellow: "#fbbf24",
  blue: "#3b82f6",
  green: "#10b981",
  purple: "#a855f7",
  orange: "#f97316",
};
