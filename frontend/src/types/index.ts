// ── v4.0: 分区 → 领域 → 专题 → 对话 ──

/** 分区（Partition）：知识树的顶层分组，对应一个学科或方向 */
export interface Partition {
  id: string;                     // 分区唯一标识
  name: string;                   // 分区名称
  subject: string;                // 所属学科
  direction: string;              // 学习方向/细分领域
  emoji: string;                  // 用于展示的表情符号
  color: string;                  // 主题色（十六进制或 CSS 色值）
  root_id: string;                // 根节点 ID（对应知识树的起点）
  context_summary: string;        // 上下文摘要，用于 AI 理解对话背景
  tags: string[];                 // 标签列表
  created_at: number;             // 创建时间戳（毫秒）
  updated_at: number;             // 最后更新时间戳（毫秒）
  last_active_at: number;         // 最后活跃时间戳（毫秒）
  message_count: number;          // 消息总数
  total_tokens: number;           // 消耗的总 token 数
  domain_count?: number;          // 下属领域数量（可选）
}

/** 领域（Domain）：分区下的二级分类，对应一个子学科或专题集 */
export interface Domain {
  id: string;                     // 领域唯一标识
  partition_id: string;           // 所属分区 ID
  name: string;                   // 领域名称
  emoji: string;                  // 表情符号
  created_at: number;             // 创建时间戳（毫秒）
  updated_at: number;             // 最后更新时间戳（毫秒）
  topic_count?: number;           // 下属专题数量（可选）
}

/** 专题（Topic）：领域下的三级分类，对应一个具体学习话题 */
export interface Topic {
  id: string;                     // 专题唯一标识
  domain_id: string;              // 所属领域 ID
  name: string;                   // 专题名称
  emoji: string;                  // 表情符号
  active_conversation_id: string; // 当前活跃的对话 ID
  created_at: number;             // 创建时间戳（毫秒）
  updated_at: number;             // 最后更新时间戳（毫秒）
  conversation_count?: number;    // 下属对话数量（可选）
}

/** 对话（Conversation）：专题下的具体对话会话 */
export interface Conversation {
  id: string;                     // 对话唯一标识
  topic_id: string;               // 所属专题 ID
  name: string;                   // 对话名称
  path: string[];                 // 路径数组（分区/领域/专题层级标识）
  is_active: boolean;             // 是否为当前活跃对话
  is_archived: boolean;           // 是否已归档
  summary?: string;               // 对话摘要（可选）
  created_at: number;             // 创建时间戳（毫秒）
  last_message_at: number;        // 最后消息时间戳（毫秒）
  message_count?: number;         // 消息数量（可选）
  material_refs?: string[];       // 引用的资料 ID 列表（可选）
}

/** 内容块（ContentBlock）：消息中的单一内容单元，支持多种媒体类型 */
export interface ContentBlock {
  type: "text" | "image" | "audio" | "video" | "document" | "quote" | "file";  // 内容块类型
  text?: string;                                              // 文本内容（仅 text 类型）
  file_id?: string;                                           // 文件 ID（图片/音频/视频/文档类型）
  duration_ms?: number;                                       // 媒体时长（毫秒，音频/视频类型）
  transcription?: string;                                     // 语音转文字结果（音频类型）
  thumbnail_file_id?: string;                                 // 缩略图文件 ID（视频类型）
  document_kind?: string;                                     // 文档种类（如 pdf/docx 等）
  page_count?: number;                                        // 文档页数
  text_content?: string;                                      // 提取的文本内容（文档类型）
  preview_text?: string;                                      // 预览文本（文档类型）
  // QuoteBlock 字段
  source_message_id?: string;                                 // 被引用消息 ID（quote 类型）
  source_conversation_id?: string;                            // 被引用消息所在会话 ID（quote 类型）
  char_start?: number;                                        // 选中文本起始偏移（quote 类型）
  char_end?: number;                                          // 选中文本结束偏移（quote 类型）
  quoted_text?: string;                                       // 引用的原文（quote 类型）
  name?: string;                                              // 文件名（file/image 类型）
  material_id?: string;                                       // 资料库 ID（file/image 类型）
}

/** 子支引用锚点 */
export interface SubBranchRef {
  id: string;
  source_message_id: string;
  char_start: number;
  char_end: number;
  quoted_text: string;
  child_conversation_id: string;
  created_at: number;
}

/** 子支信息 */
export interface SubBranchInfo {
  conversation_id: string;
  quoted_text: string;
  message_count: number;
  summary: string;
  name: string;
}

/** 树节点（TreeNode）：知识树中的单个节点，对应一条消息及其变体 */
export interface TreeNode {
  id: string;                                // 节点唯一标识
  parent_id: string;                         // 父节点 ID
  children_ids: string[];                    // 子节点 ID 列表（替代版本，用于行内 <> 导航）
  partition_id: string;                      // 所属分区 ID
  conversation_id: string;                   // 所属对话 ID
  content_blocks: ContentBlock[];            // 内容块列表
  text_summary: string;                      // 文本摘要
  summary?: string;                          // 额外摘要（可选）
  role: "user" | "assistant";               // 角色：用户或助手
  timestamp: number;                         // 时间戳（毫秒）
  token_count: number;                       // token 数量
  is_deleted: boolean;                       // 是否已删除
  is_archived: boolean;                      // 是否已归档
  has_modified_version: boolean;             // 是否存在已修改的版本
  links_to?: string[];                       // 指向的其他节点 ID 列表（可选）
  linked_from?: string[];                    // 被哪些节点引用（可选）
  discussed_skill_ids?: string[];            // 涉及的能力/技能 ID 列表（可选）
  // 子支相关
  has_sub_branches?: boolean;                // 是否有子支
  sub_branch_ids?: string[];                 // 子支会话 ID 列表
  sub_branch_summaries?: {                   // 子支摘要列表
    conversation_id: string;
    quoted_text: string;
    summary: string;
  }[];
  // 认知分类关联
  cognitive_node_ids?: string[];              // 关联的 cognitive node IDs
  // 追问问题
  follow_up_questions?: string[];              // 3 个追问问题（最末 assistant 消息）
}

/** 响应块（ResponseBlock）：AI 返回消息中的独立功能块，支持多种展示类型 */
export interface ResponseBlock {
  id: string;                                // 响应块唯一标识
  message_id: string;                        // 所属消息 ID
  partition_id: string;                      // 所属分区 ID
  conversation_id: string;                   // 所属对话 ID
  type: "text" | "video" | "practice" | "image" | "audio" | "mindmap" | "document" | "secretary_suggestions" | "expand";  // 响应块类型
  status: "streaming" | "ready" | "generating" | "failed";                            // 处理状态
  content: Record<string, unknown>;          // 具体内容（格式取决于 type）
  order: number;                             // 显示顺序
  sources?: string[];                        // 来源引用列表（可选）
  created_at: number;                        // 创建时间戳（毫秒）
  updated_at: number;                        // 最后更新时间戳（毫秒）
}

/** 后台任务（BackgroundJob）：由工具触发的异步任务状态跟踪 */
export interface BackgroundJob {
  id: string;                                // 任务唯一标识
  tool_name: string;                         // 触发工具名称
  status: "queued" | "processing" | "done" | "failed";  // 任务状态
  params: Record<string, unknown>;           // 任务参数
  result: Record<string, unknown> | null;    // 任务结果（可为 null）
  progress: number;                          // 进度百分比（0-100）
  created_at: number;                        // 创建时间戳（毫秒）
  completed_at: number | null;               // 完成时间戳（可为 null）
  error: string | null;                      // 错误信息（可为 null）
}

/** 资料元信息（MaterialMeta）：已上传资料的完整元数据 */
export interface MaterialMeta {
  material_id: string;                       // 资料唯一标识
  file_name: string;                         // 文件名
  file_type: string;                         // 文件类型（MIME 或扩展名）
  file_size: number;                         // 文件大小（字节）
  partition_id: string;                      // 所属分区 ID
  purpose: string;                           // 用途说明
  status: string;                            // 处理状态
  chunk_count: number;                       // 分块数量
  skills_covered: string[];                  // 涉及的能力/知识点列表
  created_at: string;                        // 创建时间（ISO 字符串）
  indexed_at: string | null;                 // 索引完成时间（可为 null）
  expires_at: string | null;                 // 过期时间（可为 null）
}

/** 资料引用（MaterialRef）：对话中引用的资料摘要信息 */
export interface MaterialRef {
  material_id: string;                       // 资料唯一标识
  file_name: string;                         // 文件名
  file_type: string;                         // 文件类型
  file_size: number;                         // 文件大小（字节）
  status: string;                            // 处理状态
  skills_covered: string[];                  // 涉及的能力/知识点列表
  partition_id: string;                      // 所属分区 ID
}

// ── WebSocket Message Types ──

/** WebSocket 入站消息联合类型，涵盖所有服务端推送的消息格式 */
export type WSIncomingMessage =
  | { type: "status"; message: string }                                                             // 状态更新消息
  | { type: "user_message"; message: TreeNode }                                                     // 用户消息
  | { type: "token"; content: string; block_id?: string }                                           // 流式 token
  | { type: "tool_block"; block: ResponseBlock }                                                    // 工具响应块
  | { type: "done"; partition_id: string; assistant_message: TreeNode; response_blocks?: ResponseBlock[] }  // 生成完成
  | { type: "error"; message: string }                                                              // 错误消息
  | { type: "block_update"; block: ResponseBlock }                                                  // 响应块更新
  | { type: "job_update"; job: BackgroundJob }                                                      // 后台任务状态更新
  | { type: "context_switch"; partition_id: string; conversation_id: string; domain_name: string; topic_name: string; switch_detail: Record<string, string> }  // 上下文切换
  | { type: "resume"; content: string; conversation_id?: string }                                 // 断线续流：回放缓冲
  | { type: "resume_done"; message?: string }
  | { type: "pong" }                                                                                 // pong 心跳回复
  | { type: "secretary_update"; content: { reason: string[]; proposal_count: number } };  // 秘书系统更新通知

