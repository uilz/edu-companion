/**
 * message-factory — 消息构造工厂
 *
 *   集中所有 MessageNode 构造点，确保 load_state 字段始终被正确设置。
 *
 *   ── 2026-07-06 状态机一致性（按 message-store 显式 loadState 设计）──
 *
 *   load_state 语义：客户端内存中是否持有完整正文，与来源正交。
 *   - "placeholder": 仅骨架（head/tail 列表的预览），需要调 /tree/message/{id} 取完整正文
 *   - "loading":     正在请求 /tree/message/{id}
 *   - "loaded":      完整正文已在内存（无论是乐观写入还是 SSE 返回）
 *   - "broken":      请求失败
 *
 *   工厂职责：
 *   - 统一为新消息打上正确的 load_state
 *   - 统一临时 ID 生成（t_/a_/err- 前缀，MessageList 特判）
 *   - 统一 content_blocks 结构（quote/text/file/image 顺序）
 *   - 消除 send-message.ts 与 useChatStream.ts 中重复的错误消息构造
 *
 *   不在此处理：nodeMap/currentPath/pathPosMap 等 store 结构（由调用方负责）。
 */
import type { MessageNode } from "@/types";

// ══════════════════════════════════════════════════════════════
//  ID 生成
// ══════════════════════════════════════════════════════════════

/** 临时 ID 前缀 — MessageList 据此跳过懒加载与状态机判断 */
const TEMP_PREFIX = {
  user: "t_",          // 乐观写入的用户消息
  assistant: "a_",     // 乐观写入的 assistant 占位
  error: "err-",       // 错误消息
} as const;

function _newTempId(prefix: string): string {
  return prefix + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 11);
}

// ══════════════════════════════════════════════════════════════
//  工厂 1 — 乐观写入用户消息
// ══════════════════════════════════════════════════════════════

export interface CreateOptimisticUserParams {
  text: string;
  convId: string;
  dirId: string;
  parentId: string | null;
  files?: { name: string; type: string; materialId?: string }[];
  pendingQuote?: {
    quotedText: string;
    sourceMessageId: string;
    sourceConversationId: string;
  } | null;
}

/**
 * 构造乐观写入的用户消息节点。
 * load_state = "loaded"（内容已在内存，无需再请求）。
 */
export function createOptimisticUser(params: CreateOptimisticUserParams): MessageNode {
  const { text, convId, dirId, parentId, files, pendingQuote } = params;
  const id = _newTempId(TEMP_PREFIX.user);
  const contentBlocks: any[] = [
    ...(pendingQuote
      ? [{
          type: "quote" as const,
          quoted_text: pendingQuote.quotedText,
          source_message_id: pendingQuote.sourceMessageId,
          source_conv_id: pendingQuote.sourceConversationId,
        }]
      : []),
    { type: "text", text },
    ...(files?.map(f => ({
      type: (f.type === "image" ? "image" : "file") as "image" | "file",
      name: f.name,
      material_id: f.materialId,
    })) || []),
  ];
  return {
    id,
    directory_id: convId,
    content: text,
    version: 1,
    parent_id: parentId,
    children_ids: [],
    dir_id: dirId,
    conv_id: convId,
    content_blocks: contentBlocks as MessageNode["content_blocks"],
    text_summary: text,
    role: "user",
    timestamp: Date.now(),
    token_count: 0,
    is_deleted: false,
    is_archived: false,
    load_state: "loaded",
  };
}

// ══════════════════════════════════════════════════════════════
//  工厂 2 — 乐观写入 Assistant 占位
// ══════════════════════════════════════════════════════════════

export interface CreateAssistantPlaceholderParams {
  convId: string;
  dirId: string;
  parentId: string;
}

/**
 * 构造乐观写入的 assistant 占位（流式写入前）。
 * load_state = "loaded"（占位本身已"在内存"，SSE 后续追加 content_blocks）。
 * 渲染时通过 streamingId 识别"正在流式"，与 load_state 正交。
 */
export function createAssistantPlaceholder(params: CreateAssistantPlaceholderParams): MessageNode {
  const { convId, dirId, parentId } = params;
  return {
    id: _newTempId(TEMP_PREFIX.assistant),
    directory_id: convId,
    content: "",
    version: 1,
    parent_id: parentId,
    children_ids: [],
    dir_id: dirId,
    conv_id: convId,
    content_blocks: [] as MessageNode["content_blocks"],
    text_summary: "",
    role: "assistant",
    timestamp: Date.now(),
    token_count: 0,
    is_deleted: false,
    is_archived: false,
    load_state: "loaded",
  };
}

// ══════════════════════════════════════════════════════════════
//  工厂 3 — 错误消息
// ══════════════════════════════════════════════════════════════

export interface CreateErrorMessageParams {
  errMsg: string;
  convId: string;
  dirId: string;
  parentId?: string | null;
  /** 错误前缀符号，默认 "❌" */
  prefix?: string;
}

/**
 * 构造错误提示消息（用户/网络/服务异常）。
 * load_state = "loaded"（错误内容已在内存）。
 * 错误消息以 assistant 角色写入 currentPath（与流式错误 _handleError 一致）。
 */
export function createErrorMessage(params: CreateErrorMessageParams): MessageNode {
  const { errMsg, convId, dirId, parentId = "", prefix = "❌" } = params;
  const id = _newTempId(TEMP_PREFIX.error);
  const fullText = `${prefix} ${errMsg}`;
  return {
    id,
    directory_id: convId,
    content: errMsg,
    version: 1,
    parent_id: parentId,
    children_ids: [],
    dir_id: dirId,
    conv_id: convId,
    content_blocks: [{ type: "text" as const, text: fullText }] as MessageNode["content_blocks"],
    text_summary: errMsg,
    role: "assistant",
    timestamp: Date.now(),
    token_count: 0,
    is_deleted: false,
    is_archived: false,
    load_state: "loaded",
  };
}

// ══════════════════════════════════════════════════════════════
//  工厂 4 — 注入/水合服务端消息
// ══════════════════════════════════════════════════════════════

/**
 * 把服务端返回的 MessageNode 转为前端节点：
 * - 若服务端字段缺失 load_state，补 "loaded"（完整正文已在内存）
 * - 保留所有服务端字段（content/content_blocks/timestamp/...）
 *
 * 用于 _handleDone / _handleUserMessage 把持久化消息写入 nodeMap。
 */
export function hydrateMessage(serverMsg: MessageNode): MessageNode {
  return {
    ...serverMsg,
    load_state: serverMsg.load_state ?? "loaded",
  };
}

// ══════════════════════════════════════════════════════════════
//  工具：判断是否为临时消息
// ══════════════════════════════════════════════════════════════

/**
 * 是否为临时消息（乐观写入、错误占位）。
 * MessageList 与 message-store.loadFullContent 据此跳过懒加载与状态机判断。
 */
export function isTempMessage(id: string): boolean {
  return id.startsWith(TEMP_PREFIX.user)
      || id.startsWith(TEMP_PREFIX.assistant)
      || id.startsWith(TEMP_PREFIX.error);
}

// ══════════════════════════════════════════════════════════════
//  工厂 5 — 替换消息 ID（集中状态机一致性的关键操作）
// ══════════════════════════════════════════════════════════════

/**
 * message-store 的最小快照（避免 message-factory 反向依赖 message-store）。
 * 任何 state 推导算法需要用到以上五个字段。
 */
export interface MessageStoreSnapshot {
  nodeMap: Record<string, MessageNode>;
  currentPath: string[];
  pathPosMap: Map<string, number>;
  messages: MessageNode[];
  streamingId: string | null;
}

export interface ReplaceMessageIdParams {
  /** 旧 ID（通常是临时消息的 t_/a_/err- 前缀） */
  oldId: string;
  /** 新消息节点（已 hydrate 的服务端消息，load_state: "loaded"） */
  newMsg: MessageNode;
}

/**
 * 替换消息 ID —— 处理"临时消息被服务端真实 ID 替换"的统一操作。
 *
 * 调用场景：
 *   - _handlePendingMsg：SSE 携带真实 msg_id 替换临时 a_ 占位
 *   - _handleDone：SSE done 事件携带 assistant_message / user_message 替换乐观写入
 *
 * 一致性保证（必须同步 5 处）：
 *   1. nodeMap：删除旧 key、加入新 key
 *   2. currentPath：将 oldId 替换为 newId
 *   3. pathPosMap：迁移位置索引
 *   4. messages：替换消息对象本身
 *   5. streamingId：若等于 oldId，同步替换为 newId
 *
 * 设计原则：纯函数（不直接调 setState），返回 Partial<MessageStoreSnapshot>
 *   由调用方 setState 写入；这样可在 React/Zustand 之外复用（如 useChatStream）。
 *
 * 边缘场景：
 *   - oldId === newId：仅 upsert newMsg 到 nodeMap
 *   - oldId 不在 state 中：仅 upsert newMsg 到 nodeMap
 *   - newId 已在 nodeMap：覆盖（以 newMsg 为准）
 */
export function replaceMessageIdInState(
  state: MessageStoreSnapshot,
  params: ReplaceMessageIdParams,
): Partial<MessageStoreSnapshot> {
  const { oldId, newMsg } = params;
  const newId = newMsg.id;

  // nodeMap
  const newNodeMap: Record<string, MessageNode> = { ...state.nodeMap };
  if (oldId !== newId && oldId in newNodeMap) {
    delete newNodeMap[oldId];
  }
  newNodeMap[newId] = newMsg;

  // currentPath
  const newPath = state.currentPath.map(id => (id === oldId ? newId : id));

  // pathPosMap
  const newPathPosMap = new Map(state.pathPosMap);
  if (oldId !== newId) {
    const oldIdx = newPathPosMap.get(oldId);
    if (oldIdx !== undefined) {
      newPathPosMap.delete(oldId);
      newPathPosMap.set(newId, oldIdx);
    }
  }

  // messages
  const newMessages = state.messages.map(m => (m.id === oldId ? newMsg : m));

  // streamingId
  const newStreamingId = state.streamingId === oldId ? newId : state.streamingId;

  return {
    nodeMap: newNodeMap,
    currentPath: newPath,
    pathPosMap: newPathPosMap,
    messages: newMessages,
    streamingId: newStreamingId,
  };
}
