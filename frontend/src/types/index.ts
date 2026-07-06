// ── 新 DirectoryNode 架构（node_type: "dir" | "conv" + kind）─

/** 消息节点（MessageNode）：知识树中的单个消息节点 */
export interface MessageNode {
  id: string;                                // 节点唯一标识
  directory_id: string;                      // 所属 conv 节点 ID
  parent_id: string | null;                  // 父节点 ID
  children_ids: string[];                    // 子节点 ID 列表

  // 内容
  role: "user" | "assistant";               // 角色：用户或助手
  content: string;                           // 纯文本内容
  content_blocks: any[];                     // 内容块列表（兼容 ContentBlock）
  text_summary: string;                      // 文本摘要
  summary?: string;                          // 额外摘要（可选）

  // 元信息
  timestamp: number;                         // 时间戳
  token_count: number;                       // token 数量
  version: number;                           // 版本号
  is_deleted: boolean;                       // 是否已删除
  is_archived: boolean;                      // 是否已归档

  // ── 加载状态（前端视图）──
  //   placeholder: 只有骨架（content="" content_blocks=[]），未调过 /tree/message/{id}
  //   loading:     正在 fetch /tree/message/{id}
  //   loaded:      完整正文已加载（content/content_blocks 非空，或 text_summary 兜底）
  //   broken:      加载失败（API 错误）
  //   ★ 与后端 status 字段正交：
  //     - 后端 status: "streaming" / "done" / "orphaned" 描述生成状态
  //     - 前端 loadState: "placeholder" / "loading" / "loaded" / "broken" 描述加载状态
  //   ★ 流式消息（status="streaming"）的 loadState="loaded"（内容在持续追加）
  load_state?: "placeholder" | "loading" | "loaded" | "broken";
  load_error?: string;                       // 加载错误信息

  // 链接
  links_to?: string[];                       // 指向的其他节点 ID 列表
  linked_from?: string[];                    // 被哪些节点引用

  // 多 Agent 体系
  agent_label?: string;                      // "orchestrator" | "tutor" | "coach" | "secretary"

  // 子支
  has_sub_branches?: boolean;                // 是否有子支
  sub_branch_ids?: string[];                 // 子支会话 ID 列表
  sub_branch_summaries?: {                   // 子支摘要列表
    conv_id: string;
    quoted_text: string;
    summary: string;
  }[];

  // 认知分类关联
  cognitive_node_ids?: string[];             // 关联的 cognitive node IDs

  // 追问
  follow_up_questions?: string[];            // 追问问题（最末 assistant 消息）

  // ── 向后兼容字段 ──
  dir_id?: string;
  conv_id?: string;
}

/** 工具调用块（ToolBlock）：AI 工具调用的全生命周期状态 */
export interface ToolBlock {
  type: "tool";
  tool_call_id: string;
  tool_name: string;
  display_name?: string;  // 中文显示名（如 "搜索学习资源"）
  icon?: string;           // 工具图标
  arguments: Record<string, unknown>;
  status: "pending" | "running" | "done" | "error";
  result_block_type?: string;
  result_content?: Record<string, unknown>;
  error?: string;
  tool_round: number;
}

/** 推理思考块（ReasoningBlock）：LLM 的推理过程流式展示 */
export interface ReasoningBlock {
  type: "reasoning";
  text: string;
  status: "streaming" | "done";
}

/** 内容块（ContentBlock）：消息中的单一内容单元，支持多种媒体类型 */
export interface ContentBlock {
  type: "text" | "image" | "audio" | "video" | "document" | "quote" | "file" | "tool" | "reasoning";  // 内容块类型
  text?: string;                                              // 文本内容（仅 text 类型）
  file_id?: string;                                           // 文件 ID
  duration_ms?: number;                                       // 媒体时长（毫秒）
  transcription?: string;                                     // 语音转文字结果
  thumbnail_file_id?: string;                                 // 缩略图文件 ID
  document_kind?: string;                                     // 文档种类
  page_count?: number;                                        // 文档页数
  text_content?: string;                                      // 提取的文本内容
  preview_text?: string;                                      // 预览文本
  source_message_id?: string;                                 // 被引用消息 ID（quote 类型）
  source_conv_id?: string;                            // 被引用消息所在会话 ID
  char_start?: number;                                        // 选中文本起始偏移
  char_end?: number;                                          // 选中文本结束偏移
  quoted_text?: string;                                       // 引用的原文
  name?: string;                                              // 文件名
  material_id?: string;                                       // 资料库 ID
}

/** 子支引用锚点 */
export interface SubBranchRef {
  id: string;
  source_message_id: string;
  char_start: number;
  char_end: number;
  quoted_text: string;
  child_conv_id: string;
  created_at: number;
}

/** 子支信息 */
export interface SubBranchInfo {
  conv_id: string;
  quoted_text: string;
  message_count: number;
  summary: string;
  name: string;
}

/** 响应块（ResponseBlock）：AI 返回消息中的独立功能块 */
export interface ResponseBlock {
  id: string;                                // 响应块唯一标识
  message_id: string;                        // 所属消息 ID
  dir_id: string;                      // 所属分区 ID
  conv_id: string;                   // 所属对话 ID
  type: "text" | "video" | "practice" | "image" | "audio" | "mindmap" | "document" | "secretary_suggestions" | "expand" | "question";
  status: "streaming" | "ready" | "generating" | "failed";
  content: Record<string, unknown>;
  order: number;
  sources?: string[];
  created_at: number;
  updated_at: number;
}

/** 自我解释评估结果（SelfExplainResult）：P0-R03 */
export interface SelfExplainResult {
  accuracy: "A" | "B" | "C";
  completeness: "完整" | "部分" | "缺失核心";
  clarity: "清晰" | "模糊" | "混乱";
  feedback: string;
  concept_name: string;
}

/** 自我解释提示类型 */
export type SelfExplainPromptType = "retell" | "example" | "contrast";

/** 自我解释评估请求 */
export interface SelfExplainRequest {
  explanation_text: string;
  knowledge_node_id: string;
  prompt_type: SelfExplainPromptType;
}

/** 后台任务（BackgroundJob）：由工具触发的异步任务状态跟踪 */
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

/** 资料元信息（MaterialMeta）：已上传资料的完整元数据 */
export interface MaterialMeta {
  material_id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  dir_id: string;
  purpose: string;
  status: string;
  chunk_count: number;
  skills_covered: string[];
  created_at: string;
  indexed_at: string | null;
  expires_at: string | null;
}

/** 资料引用（MaterialRef）：对话中引用的资料摘要信息 */
export interface MaterialRef {
  material_id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  status: string;
  skills_covered: string[];
  dir_id: string;
}

// ── WebSocket Message Types ──

/** WebSocket 入站消息联合类型 */
export type WSIncomingMessage =
  | { type: "status"; message: string }
  | { type: "user_message"; message: MessageNode }
  | { type: "token"; content: string; block_id?: string }
  | { type: "tool_block"; block: ResponseBlock }
  | { type: "done"; dir_id: string; assistant_message: MessageNode; response_blocks?: ResponseBlock[] }
  | { type: "error"; message: string }
  | { type: "block_update"; block: ResponseBlock }
  | { type: "job_update"; job: BackgroundJob }
  | { type: "context_switch"; dir_id: string; conv_id: string; domain_name: string; topic_name: string; switch_detail: Record<string, string> }
  | { type: "resume"; content: string; conv_id?: string }
  | { type: "resume_done"; message?: string }
  | { type: "pong" }
  | { type: "secretary_update"; content: { reason: string[]; proposal_count: number } }
  | { type: "secretary_inline"; proposal: import("../store/notification/types").SecretaryNotification }
  | { type: "secretary_proposal_update"; content: { id: string; status: string; until?: number | null } }
  // ── 双向推荐 ──
  | { type: "tree_recommendation"; dir_id: string; message: string; node_count?: number; edge_count?: number; partition_name?: string; needs_generate?: boolean }
  | { type: "temp_recommendation"; rec_type: string; message: string; dir_id?: string; partition_name?: string; needs_generate?: boolean; create_conversation?: boolean }
  | { type: "conversation_created"; data: { conv_id: string } };
