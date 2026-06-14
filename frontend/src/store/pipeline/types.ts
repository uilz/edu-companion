// ══════════════════════════════════════════════════════════════
//  StreamPipeline — Type Definitions
//
//  流输出管线的所有类型定义。StreamPipeline 对外通过 subscribe()
//  发射的事件在此定义。状态机、SSE 源接口、事件映射统一在此维护。
// ══════════════════════════════════════════════════════════════

import type {
  MessageNode,
  ResponseBlock,
  BackgroundJob,
} from "@/types";
import type { SecretaryNotification } from "@/store/notification/types";

// ── 状态机 ──

/** StreamPipeline 生命周期阶段 */
export type StreamPhase = "idle" | "streaming" | "paused" | "completing";

// ── SSE 源接口（依赖注入，解耦网络 I/O） ──

/** SSE 事件回调——StreamPipeline 内部使用 */
export type SSERawEventHandler = (data: Record<string, unknown>) => void;

/** SSE 源抽象——生产用 EventSource，测试用 Mock */
export interface SSESource {
  /** 连接到指定会话的 SSE 流。返回 cleanup 函数 */
  connect(convId: string, onEvent: SSERawEventHandler): () => void;
  /** 断开当前连接 */
  disconnect(): void;
  /** 当前是否已连接 */
  isConnected(): boolean;
}

// ── StreamPipeline 发射的事件映射 ──

export interface StreamEventMap {
  /** 状态变更 */
  phase_change: StreamPhase;

  /** token 累积后节流 flush */
  token: { msgId: string; text: string };

  /** 流完成 */
  done: {
    dirId: string;
    convId: string;
    /** 占位符消息 ID，用于在 store 中定位并替换 */
    placeholderMsgId: string;
    assistantMessage: MessageNode;
    responseBlocks?: ResponseBlock[];
  };

  /** 流错误 */
  error: string;

  /** 响应块更新 */
  block_update: ResponseBlock;

  // ── SSE 透传事件（StreamPipeline 只中转，不处理业务逻辑） ──

  conversation_created: { conversationId: string };

  context_switch: {
    dirId: string;
    convId: string;
    targetDirId: string;
    targetDomainName: string;
    targetTopicName: string;
    fullPath: string;
  };

  tree_recommendation: {
    dirId: string;
    message: string;
    dirName?: string;
    nodeCount?: number;
    edgeCount?: number;
    needsGenerate?: boolean;
  };

  temp_recommendation: {
    recType: string;
    message: string;
    dirId?: string;
    dirName?: string;
    needsGenerate?: boolean;
    createConversation?: boolean;
  };

  secretary_inline: SecretaryNotification;

  secretary_update: { id: string; status: string; until?: number | null };

  job_update: BackgroundJob;

  user_message: { conversationId: string };

  /** 流正常结束（SSE stream_end 事件），用于 completing→idle 转换 */
  stream_end: void;
}

/** 订阅回调类型 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type StreamEventCallback<K extends keyof StreamEventMap> = (data: StreamEventMap[K]) => void;

/** 取消订阅函数 */
export type Unsubscribe = () => void;
