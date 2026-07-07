// LanguageRoom API 客户端
// 依据 docs/modules/language-room/overview.md + data-model.md + ADR 0004
import { API_BASE } from "./api";

// ── 枚举 ──

export type RoomType = "1v1" | "small" | "medium" | "large";
export type RoomStatus = "active" | "ended";
export type ParticipantType = "human" | "ai_companion" | "ai_assistant";
export type InvasivenessLevel = "low" | "medium" | "high";
export type CorrectionTendency = "none" | "occasional" | "proactive";
export type HelperType = "grammar" | "vocabulary" | "sentence_pattern";
export type ProficiencyLevel = "beginner" | "intermediate" | "advanced" | "native";
export type SpeechRate = "slow" | "normal" | "fast";
export type Behavior = "talkative" | "balanced" | "concise";
export type ScenarioCategory = "daily" | "academic" | "business";
export type MessageType = "text" | "link" | "spelling" | "note";
export type ErrorType = "grammar" | "vocabulary" | "pronunciation" | "coherence";

// ── 类型 ──

export interface LanguageRoom {
  id: string;
  owner_id: string;
  name: string;
  scenario_id: string;
  room_type: RoomType;
  max_participants: number;
  is_recording_enabled: boolean;
  is_transcript_enabled: boolean;
  ai_intrusion_level: InvasivenessLevel;
  status: RoomStatus;
  started_at: string | null;
  ended_at: string | null;
  settings: Record<string, any>;
  participant_count: number;
  created_at: string | null;
}

export interface RoomParticipant {
  id: string;
  room_id: string;
  user_id: string;
  participant_type: ParticipantType;
  ai_role_id: string;
  role_label: string;
  language: string;
  joined_at: string | null;
  left_at: string | null;
  speaking_time_seconds: number;
  is_muted: boolean;
  is_owner: boolean;
}

export interface RoomTranscript {
  id: string;
  room_id: string;
  participant_id: string;
  user_id: string;
  segment_index: number;
  text: string;
  language: string;
  started_at: string | null;
  ended_at: string | null;
  confidence: number;
  speaker_id: string;
  speaker_name: string;
  is_user_marked: boolean;
  is_error: boolean;
  error_entry_id: string;
  created_at: string | null;
}

export interface RoomScenario {
  id: string;
  user_id: string | null;
  name: string;
  description: string;
  category: string;
  roles: Array<Record<string, any>>;
  target_goals: string[];
  prompt_text: string;
  linked_node_ids: string[];
  cross_disciplinary: boolean;
  is_system: boolean;
  created_at: string | null;
}

export interface AIPersona {
  id: string;
  user_id: string | null;
  name: string;
  gender_voice: string;
  personality: string;
  target_language: string;
  proficiency: string;
  speech_rate: string;
  accent: string;
  behavior: string;
  correction_tendency: CorrectionTendency;
  is_topic_lead: boolean;
  is_system: boolean;
  background: string;
  created_at: string | null;
}

export interface InvasivenessConfig {
  user_id: string;
  room_id: string;
  invasiveness_level: InvasivenessLevel;
  helper_types: string[];
  correction_tendency: CorrectionTendency;
  response_style: string;
}

export interface VocabularyCapture {
  id: string;
  user_id: string;
  room_id: string;
  transcript_id: string;
  card_id: string;
  word: string;
  translation: string;
  context_sentence: string;
  language: string;
  captured_at: string | null;
}

export interface ErrorMark {
  error_entry_id: string;
  transcript_id: string;
  error_type: ErrorType;
  linked_node_ids: string[];
}

export interface RoomMessage {
  id: string;
  user_id: string;
  text: string;
  content?: string;
  message_type: MessageType;
  explain_card_id: string;
  posted_at: string | null;
}

export interface SessionReview {
  session_id: string;
  room_id: string;
  user_id: string;
  scenario: RoomScenario | null;
  duration_seconds: number;
  started_at: string | null;
  ended_at: string | null;
  transcript_count: number;
  errors_marked: number;
  cards_generated: number;
  ai_help_requests: number;
  vocabulary_captured: number;
  messages_posted: number;
  transcripts: RoomTranscript[];
  errors: Array<Record<string, any>>;
  vocabularies: VocabularyCapture[];
  messages: Array<Record<string, any>>;
}

export interface LiveKitToken {
  token: string;
  url: string;
  identity: string;
  room_name: string;
  expires_at: number;
}

export interface InvitationResponse {
  id: string;
  invitation_token: string;
  expires_hours: number;
}

// ── 常量 ──

export const ROOM_TYPE_LABELS: Record<RoomType, string> = {
  "1v1": "1v1 房间",
  small: "小型 (3-5)",
  medium: "中型 (6-10)",
  large: "大型 (11+)",
};

export const HELPER_TYPE_LABELS: Record<HelperType, string> = {
  grammar: "语法",
  vocabulary: "词汇",
  sentence_pattern: "句型",
};

export const PROFICIENCY_LABELS: Record<ProficiencyLevel, string> = {
  beginner: "初级",
  intermediate: "中级",
  advanced: "高级",
  native: "母语",
};

export const CORRECTION_TENDENCY_LABELS: Record<CorrectionTendency, string> = {
  none: "不纠错",
  occasional: "偶尔纠错",
  proactive: "主动纠错",
};

export const INVASIVENESS_LABELS: Record<InvasivenessLevel, string> = {
  low: "低 — 仅用户召唤",
  medium: "中 — 卡顿时提示",
  high: "高 — 主动建议",
};

// ── 工具 ──

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("access_token");
  if (token) return { Authorization: `Bearer ${token}` };
  return {};
}

async function liveroomApi<T,>(p: string, o?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/api/liveroom${p}`, {
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
      ...(o?.headers || {}),
    },
    credentials: "include",
    ...o,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

// ── API 方法 ──

export const liveroomService = {
  // 房间 CRUD
  createRoom: (body: Partial<LanguageRoom>) =>
    liveroomApi<LanguageRoom>("/rooms", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listRooms: (params: { status?: string; limit?: number; offset?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.status) q.set("status", params.status);
    if (params.limit) q.set("limit", String(params.limit));
    if (params.offset) q.set("offset", String(params.offset));
    return liveroomApi<LanguageRoom[]>(`/rooms?${q}`);
  },
  getRoom: (id: string) => liveroomApi<LanguageRoom>(`/rooms/${id}`),
  updateRoom: (id: string, body: Partial<LanguageRoom>) =>
    liveroomApi<LanguageRoom>(`/rooms/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  endRoom: (id: string) =>
    liveroomApi<LanguageRoom>(`/rooms/${id}/end`, { method: "POST" }),

  // 加入 / 退出
  joinRoom: (id: string, body: { invitation_token?: string; role_label?: string; language?: string }) =>
    liveroomApi<RoomParticipant>(`/rooms/${id}/join`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  leaveRoom: (id: string) =>
    liveroomApi<{ ok: boolean; participant_id: string }>(`/rooms/${id}/leave`, {
      method: "POST",
    }),
  listParticipants: (id: string) =>
    liveroomApi<RoomParticipant[]>(`/rooms/${id}/participants`),
  muteParticipant: (id: string, userId: string, muted: boolean = true) =>
    liveroomApi<{ ok: boolean }>(
      `/rooms/${id}/participants/${userId}/mute?muted=${muted}`,
      { method: "POST" },
    ),

  // 场景切换
  changeScenario: (id: string, scenarioId: string) =>
    liveroomApi<{ ok: boolean; scenario_id: string }>(`/rooms/${id}/scenario`, {
      method: "POST",
      body: JSON.stringify({ scenario_id: scenarioId }),
    }),

  // AI 角色
  addAIPersona: (id: string, personaId: string, roleLabel: string = "") => {
    const q = new URLSearchParams({ persona_id: personaId });
    if (roleLabel) q.set("role_label", roleLabel);
    return liveroomApi<{ ok: boolean; participant_id: string; persona: AIPersona }>(
      `/rooms/${id}/ai-persona?${q}`,
      { method: "POST" },
    );
  },
  removeAIPersona: (id: string, participantId: string) =>
    liveroomApi<{ ok: boolean }>(`/rooms/${id}/ai-persona/${participantId}`, {
      method: "DELETE",
    }),

  // AI 辅助者
  invokeAIHelper: (
    id: string,
    body: { helper_type: HelperType; query: string; context_text?: string },
  ) =>
    liveroomApi<{ ok: boolean; helper_type: string; response: string }>(
      `/rooms/${id}/ai-helper/invoke`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  getHelperConfig: (id: string) =>
    liveroomApi<InvasivenessConfig>(`/rooms/${id}/ai-helper/config`),
  updateHelperConfig: (id: string, body: Partial<InvasivenessConfig>) =>
    liveroomApi<InvasivenessConfig>(`/rooms/${id}/ai-helper/config`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  // 转写
  addTranscript: (
    id: string,
    body: { participant_id?: string; text: string; language?: string; confidence?: number },
  ) =>
    liveroomApi<{ transcript_id: string }>(`/rooms/${id}/transcripts`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listTranscripts: (
    id: string,
    params: { only_user?: boolean; only_errors?: boolean; limit?: number } = {},
  ) => {
    const q = new URLSearchParams();
    q.set("only_user", String(params.only_user ?? true));
    if (params.only_errors) q.set("only_errors", "true");
    if (params.limit) q.set("limit", String(params.limit));
    return liveroomApi<RoomTranscript[]>(`/rooms/${id}/transcripts?${q}`);
  },

  // 词汇便签 (复用 FlashCard)
  captureVocabulary: (
    id: string,
    body: { word: string; translation?: string; context_sentence?: string; language?: string; transcript_id?: string; linked_node_ids?: string[] },
  ) =>
    liveroomApi<VocabularyCapture>(`/rooms/${id}/vocabulary`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // 错误标记 (复用 ErrorBookEntry)
  markError: (
    id: string,
    body: { transcript_id: string; error_type: ErrorType; linked_node_ids?: string[]; user_note?: string },
  ) =>
    liveroomApi<ErrorMark>(`/rooms/${id}/error`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // 文字辅助 (复用 ExplainCard)
  postMessage: (
    id: string,
    body: { text: string; message_type?: MessageType; reference_url?: string },
  ) =>
    liveroomApi<RoomMessage>(`/rooms/${id}/messages`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listMessages: (id: string, limit: number = 50) =>
    liveroomApi<any[]>(`/rooms/${id}/messages?limit=${limit}`),

  // 录音
  startRecording: (id: string, format: string = "opus") =>
    liveroomApi<{ recording_id: string; started_at: string }>(
      `/rooms/${id}/recording/start`,
      { method: "POST", body: JSON.stringify({ format }) },
    ),
  stopRecording: (id: string, recordingId: string) =>
    liveroomApi<{ recording_id: string; duration_seconds: number; file_size_bytes: number }>(
      `/rooms/${id}/recording/stop`,
      { method: "POST", body: JSON.stringify({ recording_id: recordingId }) },
    ),

  // LiveKit Token
  issueToken: (id: string, displayName: string = "") =>
    liveroomApi<LiveKitToken>(`/rooms/${id}/token`, {
      method: "POST",
      body: JSON.stringify({ display_name: displayName }),
    }),

  // 场景管理
  createScenario: (body: Partial<RoomScenario>) =>
    liveroomApi<RoomScenario>("/scenarios", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listScenarios: (params: { category?: string; only_system?: boolean; limit?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.category) q.set("category", params.category);
    if (params.only_system) q.set("only_system", "true");
    if (params.limit) q.set("limit", String(params.limit));
    return liveroomApi<RoomScenario[]>(`/scenarios?${q}`);
  },
  getScenario: (id: string) => liveroomApi<RoomScenario>(`/scenarios/${id}`),

  // AI 角色库
  createPersona: (body: Partial<AIPersona>) =>
    liveroomApi<AIPersona>("/ai-personas", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listPersonas: (params: { language?: string; only_system?: boolean; limit?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.language) q.set("language", params.language);
    if (params.only_system) q.set("only_system", "true");
    if (params.limit) q.set("limit", String(params.limit));
    return liveroomApi<AIPersona[]>(`/ai-personas?${q}`);
  },
  getPersona: (id: string) => liveroomApi<AIPersona>(`/ai-personas/${id}`),

  // 会话回顾
  getSessionReview: (roomId: string, sessionId?: string) => {
    const q = sessionId ? `?session_id=${sessionId}` : "";
    return liveroomApi<SessionReview>(`/rooms/${roomId}/review${q}`);
  },
  getSessionReviewById: (sessionId: string) =>
    liveroomApi<SessionReview>(`/sessions/${sessionId}/review`),

  // 邀请
  createInvitation: (roomId: string, body: { invitee_id?: string; expires_hours?: number }) =>
    liveroomApi<InvitationResponse>(`/rooms/${roomId}/invitations`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
