// InterestExplorer API 客户端
// 依据 docs/modules/interest-explorer/overview.md + data-model.md + ADR 0007
import { API_BASE, authedFetch } from "./api";

// ── 枚举 ──

export type TagLevel = 0 | 1 | 2;
export type TagWeight = 1 | 2; // 1=主要, 2=次要
export type TagSource = "manual" | "from_knowledge" | "from_reading";

export type SourceType =
  | "arxiv" | "biorxiv" | "rss" | "atom" | "opml" | "internal";

export type PushType = "research_object" | "research_method" | "hot_news";
export type PushFeedback = "read" | "later" | "dislike" | "imported";

export type PushFrequency = "daily" | "weekly" | "manual";

// 5 个目标模块（严格对应 CrossModuleTarget）
export type ImportTarget =
  | "reading" | "project" | "flashcard" | "cognitive_node" | "language_room";

// ── 类型 ──

export interface InterestTag {
  id: string;
  user_id: string;
  name: string;
  level: number;
  parent_id: string | null;
  weight: number;
  source: string;
  source_ref_id: string | null;
  color: string | null;
  created_at: string | null;
  dislike_score: number;
  children: InterestTag[];
}

export interface InterestPushPrefs {
  user_id: string;
  frequency: PushFrequency;
  push_time: string;
  timezone: string;
  daily_limit: number;
  research_object_pct: number;
  research_method_pct: number;
  hot_news_pct: number;
  cross_disciplinary: boolean;
  retention_days: number;
  is_enabled: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface InterestSource {
  id: string;
  user_id: string | null;
  name: string;
  type: SourceType;
  category: string | null;
  config: Record<string, any>;
  enabled: boolean;
  is_system: boolean;
  last_fetched_at: string | null;
  last_fetch_status: string | null;
  last_fetch_error: string | null;
  created_at: string | null;
}

export interface InterestPush {
  id: string;
  user_id: string;
  source_id: string | null;
  push_type: PushType;
  title: string;
  summary: string | null;
  url: string | null;
  author: string | null;
  published_at: string | null;
  matched_tags: string[];
  generated_at: string | null;
  feedback: PushFeedback | null;
}

export interface InterestWeightAdjustment {
  id: string;
  user_id: string;
  tag_id: string;
  tag_name: string | null;
  tag_level: number | null;
  dislike_score: number;
  adjustment_count: number;
  updated_at: string | null;
}

export interface InterestSamplingWeight {
  tag_id: string;
  tag_name: string | null;
  level: number | null;
  effective_weight: number;
}

// ── API ──

const PREFIX = "/api/interest";

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

export const interestService = {
  // ── 标签 ──
  listTags: async (): Promise<{ items: InterestTag[]; total: number }> => {
    const r = await authedFetch(`${PREFIX}/tags`);
    return jsonOrThrow(r);
  },
  createTag: async (body: {
    name: string;
    level?: TagLevel;
    parent_id?: string | null;
    weight?: TagWeight;
    color?: string;
    source?: TagSource;
    source_ref_id?: string;
  }): Promise<InterestTag> => {
    const r = await authedFetch(`${PREFIX}/tags`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    return jsonOrThrow(r);
  },
  updateTag: async (
    tag_id: string,
    body: { name?: string; weight?: TagWeight; color?: string; parent_id?: string },
  ): Promise<InterestTag> => {
    const r = await authedFetch(`${PREFIX}/tags/${tag_id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
    return jsonOrThrow(r);
  },
  deleteTag: async (tag_id: string): Promise<{ deleted: boolean; tag_id: string }> => {
    const r = await authedFetch(`${PREFIX}/tags/${tag_id}`, { method: "DELETE" });
    return jsonOrThrow(r);
  },
  createTagFromKnowledge: async (
    node_id: string,
    body: { weight?: TagWeight; level?: TagLevel; color?: string },
  ): Promise<{ tag: InterestTag; knowledge_node_id: string }> => {
    const r = await authedFetch(
      `${PREFIX}/tags/from-knowledge/${node_id}`,
      { method: "POST", body: JSON.stringify(body) },
    );
    return jsonOrThrow(r);
  },

  // ── 偏好 ──
  getPrefs: async (): Promise<InterestPushPrefs> => {
    const r = await authedFetch(`${PREFIX}/prefs`);
    return jsonOrThrow(r);
  },
  updatePrefs: async (
    body: Partial<InterestPushPrefs>,
  ): Promise<InterestPushPrefs> => {
    const r = await authedFetch(`${PREFIX}/prefs`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
    return jsonOrThrow(r);
  },

  // ── 信息源 ──
  listSources: async (): Promise<{ items: InterestSource[]; total: number }> => {
    const r = await authedFetch(`${PREFIX}/sources`);
    return jsonOrThrow(r);
  },
  createSource: async (body: {
    name: string;
    type: SourceType;
    category?: string;
    config: Record<string, any>;
    enabled?: boolean;
  }): Promise<InterestSource> => {
    const r = await authedFetch(`${PREFIX}/sources`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    return jsonOrThrow(r);
  },
  enableSource: async (
    source_id: string,
    enabled: boolean,
  ): Promise<InterestSource> => {
    const r = await authedFetch(`${PREFIX}/sources/${source_id}/enable`, {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    });
    return jsonOrThrow(r);
  },
  deleteSource: async (source_id: string): Promise<{ deleted: boolean }> => {
    const r = await authedFetch(`${PREFIX}/sources/${source_id}`, {
      method: "DELETE",
    });
    return jsonOrThrow(r);
  },
  importOPML: async (opml_xml: string): Promise<{
    imported: number;
    skipped: number;
    items: InterestSource[];
  }> => {
    const r = await authedFetch(`${PREFIX}/sources/import-opml`, {
      method: "POST",
      body: JSON.stringify({ opml_xml }),
    });
    return jsonOrThrow(r);
  },

  // ── 推送 ──
  getTodayPushes: async (): Promise<{
    user_id: string;
    date: string;
    items: InterestPush[];
    total: number;
  }> => {
    const r = await authedFetch(`${PREFIX}/push/today`);
    return jsonOrThrow(r);
  },
  getHistory: async (params: {
    push_type?: PushType;
    limit?: number;
    offset?: number;
  } = {}): Promise<{
    items: InterestPush[];
    total: number;
    limit: number;
    offset: number;
  }> => {
    const q = new URLSearchParams();
    if (params.push_type) q.set("push_type", params.push_type);
    if (params.limit) q.set("limit", String(params.limit));
    if (params.offset) q.set("offset", String(params.offset));
    const qs = q.toString();
    const r = await authedFetch(`${PREFIX}/push/history${qs ? "?" + qs : ""}`);
    return jsonOrThrow(r);
  },
  triggerPush: async (): Promise<{ pushed_count: number; by_type: Record<string, number> }> => {
    const r = await authedFetch(`${PREFIX}/push/today/trigger`, { method: "POST" });
    return jsonOrThrow(r);
  },
  triggerFetch: async (): Promise<any> => {
    const r = await authedFetch(`${PREFIX}/fetch-now`, { method: "POST" });
    return jsonOrThrow(r);
  },

  // ── 反馈 ──
  recordFeedback: async (
    push_id: string,
    body: {
      feedback: PushFeedback;
      target_module?: ImportTarget;
      target_ref_id?: string;
    },
  ): Promise<any> => {
    const r = await authedFetch(`${PREFIX}/push/${push_id}/feedback`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    return jsonOrThrow(r);
  },

  // ── 跨模块导入 ──
  importPush: async (
    push_id: string,
    target_module: ImportTarget,
  ): Promise<{
    imported: boolean;
    push_id: string;
    target_module: ImportTarget;
    target_ref_id: string;
  }> => {
    const r = await authedFetch(`${PREFIX}/push/${push_id}/import`, {
      method: "POST",
      body: JSON.stringify({ target_module }),
    });
    return jsonOrThrow(r);
  },

  // ── 本地权重 ──
  getWeightAdjustments: async (): Promise<{
    adjustments: InterestWeightAdjustment[];
    sampling_weights: InterestSamplingWeight[];
    principle: string;
  }> => {
    const r = await authedFetch(`${PREFIX}/weight-adjustments`);
    return jsonOrThrow(r);
  },
  resetWeights: async (): Promise<{ reset: boolean; cleared_count: number }> => {
    const r = await authedFetch(`${PREFIX}/weight-adjustments/reset`, {
      method: "POST",
    });
    return jsonOrThrow(r);
  },
};

// ── 标签 ──

export const PUSH_TYPE_LABELS: Record<PushType, string> = {
  research_object: "研究对象",
  research_method: "研究方法",
  hot_news: "热点日报",
};

export const PUSH_TYPE_COLORS: Record<PushType, string> = {
  research_object: "bg-info/10 text-info/80",
  research_method: "bg-accent/10 text-accent/80",
  hot_news: "bg-warning/10 text-warning/80",
};

export const FEEDBACK_LABELS: Record<PushFeedback, string> = {
  read: "已读",
  later: "稍后读",
  dislike: "不感兴趣",
  imported: "已导入",
};

export const FEEDBACK_COLORS: Record<PushFeedback, string> = {
  read: "bg-surface text-muted",
  later: "bg-warning/10 text-warning/80",
  dislike: "bg-danger/10 text-danger/80",
  imported: "bg-success/10 text-success/80",
};

export const IMPORT_TARGET_LABELS: Record<ImportTarget, string> = {
  reading: "阅读材料",
  project: "项目灵感",
  flashcard: "闪念卡",
  cognitive_node: "知识点",
  language_room: "语言房间",
};

export const IMPORT_TARGET_ICONS: Record<ImportTarget, string> = {
  reading: "📖",
  project: "📁",
  flashcard: "🎴",
  cognitive_node: "🧠",
  language_room: "🗣️",
};

export const FREQUENCY_LABELS: Record<PushFrequency, string> = {
  daily: "每日",
  weekly: "每周",
  manual: "手动",
};
