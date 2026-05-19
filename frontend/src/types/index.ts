export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

export interface Settings {
  apiEndpoint: string;
  apiKey: string;
  modelName: string;
  systemPrompt: string;
}

export interface ChatRequest {
  conversationId: string;
  message: string;
  settings: Settings;
}

export interface StreamEvent {
  type: "token" | "done" | "error";
  content?: string;
  conversationId?: string;
  messageId?: string;
}

// ── Conversation Tree System Types ──

export interface Partition {
  id: string;
  name: string;
  subject: string;
  direction: string;
  emoji: string;
  color: string;
  root_id: string;
  active_branch_id: string;
  context_summary: string;
  summary_branches: Record<string, string>;
  tags: string[];
  created_at: number;
  updated_at: number;
  last_active_at: number;
  message_count: number;
  total_tokens: number;
  branch_count?: number;
}

export interface Branch {
  id: string;
  partition_id: string;
  name: string;
  fork_point_id?: string;
  path: string[];
  is_active: boolean;
  is_archived: boolean;
  summary?: string;
  created_at: number;
  last_message_at: number;
  message_count?: number;
  material_refs?: string[];
}

// ── P5: 资料类型 ──

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
  children_ids: string[];
  partition_id: string;
  branch_id: string;
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
}

export interface ResponseBlock {
  id: string;
  message_id: string;
  partition_id: string;
  branch_id: string;
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

// ── WebSocket Message Types ──

export type WSIncomingMessage =
  | { type: "status"; message: string }
  | { type: "user_message"; message: TreeNode }
  | { type: "token"; content: string; block_id?: string }
  | { type: "done"; partition_id: string; assistant_message: TreeNode }
  | { type: "error"; message: string }
  | { type: "block_update"; block: ResponseBlock }
  | { type: "job_update"; job: BackgroundJob }
  | { type: "pong" };
