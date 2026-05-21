// ── v4.0: 分区 → 领域 → 专题 → 对话 ──

export interface Partition {
  id: string;
  name: string;
  subject: string;
  direction: string;
  emoji: string;
  color: string;
  root_id: string;
  context_summary: string;
  tags: string[];
  created_at: number;
  updated_at: number;
  last_active_at: number;
  message_count: number;
  total_tokens: number;
  domain_count?: number;
}

export interface Domain {
  id: string;
  partition_id: string;
  name: string;
  emoji: string;
  created_at: number;
  updated_at: number;
  topic_count?: number;
}

export interface Topic {
  id: string;
  domain_id: string;
  name: string;
  emoji: string;
  active_conversation_id: string;
  created_at: number;
  updated_at: number;
  conversation_count?: number;
}

export interface Conversation {
  id: string;
  topic_id: string;
  name: string;
  path: string[];
  is_active: boolean;
  is_archived: boolean;
  summary?: string;
  created_at: number;
  last_message_at: number;
  message_count?: number;
  material_refs?: string[];
}

export interface ContentBlock {
  type: "text" | "image" | "audio" | "video" | "document";
  text?: string;
  file_id?: string;
  duration_ms?: number;
  transcription?: string;
  thumbnail_file_id?: string;
  document_kind?: string;
  page_count?: number;
  text_content?: string;
  preview_text?: string;
}

export interface TreeNode {
  id: string;
  parent_id: string;
  children_ids: string[];  // alternative versions (for inline < > navigation)
  partition_id: string;
  conversation_id: string;
  content_blocks: ContentBlock[];
  text_summary: string;
  summary?: string;
  role: "user" | "assistant";
  timestamp: number;
  token_count: number;
  is_deleted: boolean;
  is_archived: boolean;
  has_modified_version: boolean;
  links_to?: string[];
  linked_from?: string[];
  discussed_skill_ids?: string[];
}

export interface ResponseBlock {
  id: string;
  message_id: string;
  partition_id: string;
  conversation_id: string;
  type: "text" | "video" | "practice" | "image" | "audio" | "mindmap" | "document";
  status: "streaming" | "ready" | "generating" | "failed";
  content: Record<string, unknown>;
  order: number;
  sources?: string[];
  created_at: number;
  updated_at: number;
}

export interface BackgroundJob {
  id: string;
  tool_name: string;
  status: "queued" | "processing" | "done" | "failed";
  params: Record<string, unknown>;
  result: Record<string, unknown> | null;
  progress: number;
  created_at: number;
  completed_at: number | null;
  error: string | null;
}

export interface MaterialMeta {
  material_id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  partition_id: string;
  purpose: string;
  status: string;
  chunk_count: number;
  skills_covered: string[];
  created_at: string;
  indexed_at: string | null;
  expires_at: string | null;
}

export interface MaterialRef {
  material_id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  status: string;
  skills_covered: string[];
  partition_id: string;
}

// ── WebSocket Message Types ──

export type WSIncomingMessage =
  | { type: "status"; message: string }
  | { type: "user_message"; message: TreeNode }
  | { type: "token"; content: string; block_id?: string }
  | { type: "tool_block"; block: ResponseBlock }
  | { type: "done"; partition_id: string; assistant_message: TreeNode; response_blocks?: ResponseBlock[] }
  | { type: "error"; message: string }
  | { type: "block_update"; block: ResponseBlock }
  | { type: "job_update"; job: BackgroundJob }
  | { type: "context_switch"; partition_id: string; conversation_id: string; domain_name: string; topic_name: string; switch_detail: Record<string, string> }
  | { type: "pong" };

// ── Legacy aliases (backward compat) ──
/** @deprecated Use Conversation instead */
export type Branch = Conversation;
