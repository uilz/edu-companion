// ══════════════════════════════════════════════════════════════
//  StreamPipeline — 全局单例初始化
//
//  由 useConversation 在 mount 时调用。将 StreamPipeline 的事件
//  订阅到 Zustand store，完成 SSE 事件的 store 写入。
//
//  ⚡ 同时承担通知集成：将 pipeline 的非流式事件（context_switch
//  / tree_recommendation / temp_recommendation / job_update /
//  secretary_inline / secretary_proposal_update）写入
//  NotificationStore，使秘书系统能统一管理所有通知。
// ══════════════════════════════════════════════════════════════

import type { MessageNode, ResponseBlock } from "@/types";
import type { ConversationState } from "@/store/conversation/conversation-store";
import type { SecretaryNotification } from "@/store/notification/types";
import { EventSourceSSE } from "./SSESource";
import { StreamPipeline } from "./StreamPipeline";
import { useNotificationStore } from "@/store/notification/notification-store";

// ── 全局单例 ──
let _pipeline: StreamPipeline | null = null;

/**
 * 获取全局 StreamPipeline 单例。
 * 首次调用时自动创建，使用 EventSourceSSE 作为网络适配器。
 */
export function getPipeline(): StreamPipeline {
  if (!_pipeline) {
    _pipeline = new StreamPipeline(new EventSourceSSE());
  }
  return _pipeline;
}

/**
 * 将 StreamPipeline 事件订阅到 Zustand store。
 * 由 useConversation 在 mount 时调用一次。
 * 返回 cleanup 函数（组件卸载时调用）。
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function bindPipelineToStore(storeApi: { setState: (partial: any) => void; getState: () => any }): () => void {
  const pipeline = getPipeline();
  const unsubs: Array<() => void> = [];

  // ── Token flush → store messages ──
  unsubs.push(pipeline.subscribe("token", ({ msgId, text }) => {
    storeApi.setState((state: { messages: MessageNode[] }) => ({
      messages: state.messages.map((m) =>
        m.id === msgId
          ? {
              ...m,
              content_blocks: [{ type: "text" as const, text }],
              text_summary: text,
            }
          : m,
      ),
    }));
  }));

  // ── Done → 替换占位符 + 添加 responseBlocks ──
  unsubs.push(pipeline.subscribe("done", ({ dirId, convId, placeholderMsgId, assistantMessage, responseBlocks }) => {
    storeApi.setState({ isLoading: false, statusMessage: "" });

    // 如果用户已切换会话，刷新当前会话
    const state = storeApi.getState();
    const currentDirId = state.selectedDirId;
    const currentConvId = state.activeConversationId;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const store = storeApi as any;

    if (dirId !== currentDirId || convId !== currentConvId) {
      if (currentConvId) {
        setTimeout(() => store.loadMessages?.(currentConvId), 500);
      }
      return;
    }

    // 替换占位符或追加消息
    if (assistantMessage) {
      const assistantMsgAny = assistantMessage as unknown as Record<string, unknown>;
      const metadata = assistantMsgAny.metadata as Record<string, unknown> | undefined;
      if (metadata?.follow_up_questions) {
        assistantMsgAny.follow_up_questions = metadata.follow_up_questions;
      }
      const textBlock = assistantMessage.content_blocks?.find(
        (b: { type: string }) => b.type === "text",
      );
      const hasContent = textBlock?.text?.trim();
      storeApi.setState((state: { messages: MessageNode[] }) => {
        const idx = state.messages.findIndex(
          (m) => m.id === placeholderMsgId || m.id === assistantMessage.id,
        );
        if (idx >= 0) {
          const existing = state.messages[idx];
          const merged = hasContent
            ? { ...assistantMessage, parent_id: existing.parent_id }
            : {
                ...assistantMessage,
                parent_id: existing.parent_id,
                content_blocks: [
                  { type: "text" as const, text: "（助手返回了空回复）" },
                ],
                text_summary: "（助手返回了空回复）",
              };
          return { messages: Object.assign([], state.messages, { [idx]: merged }) };
        }
        const newMsg = hasContent
          ? assistantMessage
          : {
              ...assistantMessage,
              content_blocks: [
                { type: "text" as const, text: "（助手返回了空回复）" },
              ],
              text_summary: "（助手返回了空回复）",
            };
        setTimeout(() => {
          const cid = storeApi.getState().activeConversationId;
          if (cid) store.loadMessages?.(cid);
        }, 300);
        return { messages: [...state.messages, newMsg] };
      });
    } else if (placeholderMsgId) {
      storeApi.setState((state: { messages: MessageNode[] }) => ({
        messages: state.messages.filter((m) => m.id !== placeholderMsgId),
      }));
    }

    // 添加 responseBlocks
    if (responseBlocks?.length) {
      storeApi.setState((state: { responseBlocks: ResponseBlock[] }) => {
        const existing = new Set(state.responseBlocks.map((b) => b.id));
        const newBlocks = responseBlocks.filter((b) => !existing.has(b.id));
        return newBlocks.length
          ? { responseBlocks: [...state.responseBlocks, ...newBlocks] }
          : {};
      });
    }
  }));

  // ── Error → 显示错误消息 ──
  unsubs.push(pipeline.subscribe("error", (msg) => {
    storeApi.setState({ isLoading: false, statusMessage: "" });
    const errorNode: MessageNode = {
      id: "err-" + Date.now(),
      directory_id: storeApi.getState().activeConversationId || "",
      content: msg,
      version: 1,
      parent_id: "",
      children_ids: [],
      partition_id: storeApi.getState().selectedDirId || "",
      conversation_id: storeApi.getState().activeConversationId || "",
      content_blocks: [{ type: "text" as const, text: `❌ ${msg}` }],
      text_summary: msg,
      role: "assistant",
      timestamp: Date.now(),
      token_count: 0,
      is_deleted: false,
      is_archived: false,
    };
    storeApi.setState((state: { messages: MessageNode[] }) => ({
      messages: [...state.messages, errorNode],
    }));
  }));

  // ── Block update → store ──
  unsubs.push(pipeline.subscribe("block_update", (block) => {
    storeApi.setState((state: { responseBlocks: ResponseBlock[] }) => {
      const idx = state.responseBlocks.findIndex((b) => b.id === block.id);
      if (idx >= 0) {
        const updated = [...state.responseBlocks];
        updated[idx] = block;
        return { responseBlocks: updated };
      }
      return { responseBlocks: [...state.responseBlocks, block] };
    });
  }));

  // ── Context switch → SwitchBanner + Notification ──
  unsubs.push(pipeline.subscribe("context_switch", (data) => {
    storeApi.setState({
      switchBanner: {
        dirId: data.dirId,
        conversationId: data.convId,
        targetDirId: data.targetDirId,
        targetDomainName: data.targetDomainName,
        targetTopicName: data.targetTopicName,
        fullPath: data.fullPath,
      },
    });
    // 同时写入 NotificationStore（秘书系统管理）
    const id = `context_switch_${data.dirId}_${data.convId}`;
    const store = useNotificationStore.getState();
    if (store.notifications.some((n) => n.id === id)) return;
    const notif: SecretaryNotification = {
      id, emoji: "🔀",
      title: "检测到话题切换",
      description: data.fullPath || `${data.targetDomainName}${data.targetTopicName ? ` → ${data.targetTopicName}` : ""}`,
      priority: 3,
      target: { pages: ["learn"], inlineConversationId: data.convId, actionPath: `/conversation/${data.convId}` },
      source: "context_switch", sourceModule: "conversation",
      read: false, status: "pending", created_at: Date.now(),
    };
    store.addNotification(notif);
  }));

  // ── Conversation created → update activeConvId ──
  unsubs.push(pipeline.subscribe("conversation_created", ({ conversationId }) => {
    storeApi.setState({ activeConversationId: conversationId });
  }));

  // ── Tree recommendation → Banner + Notification ──
  unsubs.push(pipeline.subscribe("tree_recommendation", (data) => {
    storeApi.setState({
      recommendationBanner: {
        type: "tree" as const,
        message: data.message,
        dirId: data.dirId,
        dirName: data.dirName || "",
        nodeCount: data.nodeCount,
        edgeCount: data.edgeCount,
        needsGenerate: data.needsGenerate,
      },
    });
    // Notification 记录（去重）
    const id = `tree_rec_ws_${data.dirId}`;
    const store = useNotificationStore.getState();
    if (store.notifications.some((n) => n.id === id)) return;
    const notif: SecretaryNotification = {
      id, emoji: "🌳",
      title: "知识树整理提醒",
      description: data.dirName ? `分区「${data.dirName}」${data.message}` : data.message,
      priority: 3,
      target: { pages: ["learn", "knowledge-tree"] },
      source: "tree_recommendation", sourceModule: "knowledge_tree",
      read: false, status: "pending", created_at: Date.now(),
    };
    store.addNotification(notif);
  }));

  // ── Temp recommendation → Banner + Notification ──
  unsubs.push(pipeline.subscribe("temp_recommendation", (data) => {
    storeApi.setState({
      recommendationBanner: {
        type: data.recType === "switch_to_learn" ? "learn" as const : "tree" as const,
        message: data.message,
        dirId: data.dirId || "",
        dirName: data.dirName || "",
        needsGenerate: data.needsGenerate,
        createConversation: data.createConversation,
      },
    });
    // Notification 记录
    const id = `temp_rec_${data.recType}_${data.dirId || "global"}`;
    const store = useNotificationStore.getState();
    if (store.notifications.some((n) => n.id === id)) return;
    const isLearn = data.recType === "switch_to_learn";
    const notif: SecretaryNotification = {
      id, emoji: isLearn ? "📚" : "🌳",
      title: isLearn ? "学习推荐" : "知识树推荐",
      description: data.message,
      priority: 2,
      target: { pages: ["learn"], actionPath: isLearn ? "/learn" : "/knowledge-tree" },
      source: "temp_recommendation", sourceModule: "conversation",
      read: false, status: "pending", created_at: Date.now(),
    };
    store.addNotification(notif);
  }));

  // ── Job update → Notification ──
  unsubs.push(pipeline.subscribe("job_update", (data) => {
    const id = `job_${data.id}`;
    const store = useNotificationStore.getState();
    const isDone = data.status === "done";
    const isFailed = data.status === "failed";
    const notif: SecretaryNotification = {
      id,
      emoji: isDone ? "✅" : isFailed ? "❌" : "⏳",
      title: `后台任务: ${data.tool_name}`,
      description: `任务状态: ${data.status}${data.progress > 0 ? ` (${Math.round(data.progress * 100)}%)` : ""}`,
      priority: isDone ? 2 : isFailed ? 4 : 1,
      target: { pages: ["learn", "dashboard"] },
      source: "job_update", sourceModule: "background",
      read: false,
      status: isDone ? "accepted" : "pending",
      created_at: Date.now(),
    };
    store.addNotification(notif);
  }));

  // ── Secretary inline → 直接入 NotificationStore ──
  unsubs.push(pipeline.subscribe("secretary_inline", (data) => {
    useNotificationStore.getState().addNotification(data as SecretaryNotification);
  }));

  // ── Secretary proposal update → 同步状态到 NotificationStore ──
  unsubs.push(pipeline.subscribe("secretary_update", ({ id, status, until }) => {
    const store = useNotificationStore.getState();
    switch (status) {
      case "accepted": store.acceptNotification(id); break;
      case "dismissed": store.dismissNotification(id); break;
      case "snoozed": if (until) store.snoozeNotification(id, until); break;
      case "deleted": store.removeNotification(id); break;
      case "restored": store.restoreNotification(id); break;
      default: store.updateNotification(id, { status: status as SecretaryNotification["status"] }); break;
    }
  }));

  // ── Phase change → loading state ──
  unsubs.push(pipeline.subscribe("phase_change", (phase) => {
    storeApi.setState({
      isLoading: phase === "streaming" || phase === "completing",
      wsConnected: phase === "streaming" || phase === "paused",
    });
  }));

  return () => {
    for (const unsub of unsubs) unsub();
  };
}
