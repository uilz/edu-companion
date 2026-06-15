/**
 * send-message — 发送消息（最复杂的 action）
 *
 * 流程：
 * 1. POST /tree/conversation/{cid}/message 触发后台 pipeline（立即返回）
 * 2. StreamPipeline 自动接收 SSE 流式事件并更新 messages
 * 3. SSE done 事件完成消息替换
 */
import type { MessageNode } from "@/types";
import { apiFetch, fireClassify } from "../tree-helpers";
import { getPipeline } from "@/store/pipeline";
import { useTreeStore } from "@/store/conversation/tree-store";

/**
 * 在"💬 临时"分区下创建临时对话（不创建领域→专题树）
 * 第一次发消息时，自动创建或复用临时分区 + 临时会话
 */
async function ensureTempConversation(set: any, get: any): Promise<{ pId: string; cId: string } | null> {
  let pId = get().selectedDirId;
  let cId = get().activeConversationId;
  if (pId && cId) return { pId, cId };

  try {
    // 查找或创建临时分区
    if (!pId) {
      try {
        // 优先使用新 API
        const dirData = await apiFetch<{ directory_nodes: any[] }>("/tree/directory");
        const tempNodes = (dirData as any).tree || dirData.directory_nodes || [];
        const tempP = Array.isArray(tempNodes)
          ? tempNodes.find((n: any) => n.kind === "temp")
          : null;
        if (tempP) {
          pId = tempP.id;
        } else {
          const rootId = useTreeStore.getState().rootId;
          const newP = await apiFetch<{ directory_node: any }>("/tree/directory", {
            method: "POST",
            body: JSON.stringify({ node_type: "dir", kind: "temp", parent_id: rootId || undefined, name: "💬 临时", emoji: "💬" }),
          });
          pId = newP.directory_node.id;
        }
      } catch {
        // 回退：旧 API
        const pData = await apiFetch<{ partitions: any[] }>("/tree/partition");
        const tempP = (pData.partitions || []).find(p => p.is_temp);
        if (tempP) {
          pId = tempP.id;
        } else {
          const newP = await apiFetch<{ partition: any }>("/tree/partition", {
            method: "POST",
            body: JSON.stringify({ name: "💬 临时", emoji: "💬" }),
          });
          pId = newP.partition.id;
        }
      }
    }

    // 在该分区下新建一个空会话（不创建领域→专题树）
    try {
      const newC = await apiFetch<{ directory_node: { id: string } }>("/tree/directory", {
        method: "POST",
        body: JSON.stringify({ node_type: "conv", kind: "temp", parent_id: pId, name: "" }),
      });
      cId = newC.directory_node.id;
    } catch {
      const newC = await apiFetch<{ conversation: { id: string } }>("/tree/conversation", {
        method: "POST",
        body: JSON.stringify({ parent_id: pId, name: "" }),
      });
      cId = newC.conversation.id;
    }

    // 标记发送中 —— StreamPipeline 的 phase 会管理流状态
    set({
      selectedDirId: pId,
      activeConversationId: cId,
      convError: null,
      postSendRedirect: cId,
    });
    // 刷新侧边栏树
    await useTreeStore.getState().loadRootNodes();
    await useTreeStore.getState().loadChildren(pId, "dir");
    await get().loadDirList();
    return { pId, cId };
  } catch (e) {
    set((state: { messages: MessageNode[] }) => ({
      messages: [...state.messages, {
        id: "err-" + Date.now(),
        parent_id: "", children_ids: [],
        partition_id: "", conversation_id: "",
        content_blocks: [{ type: "text" as const, text: "❌ 无法创建临时会话，请检查后端连接" }],
        text_summary: "", role: "assistant" as const,
        timestamp: Date.now(), token_count: 0,
        is_deleted: false, is_archived: false,
      }],
    }));
    return null;
  }
}

export async function sendMessageImpl(
  set: any, get: any,
  text: string,
  files?: { name: string; type: string; materialId?: string }[],
) {
  if (!text.trim()) return;
  if (get().isLoading) {
    const loadingSince = Date.now();
    const checkStuck = setInterval(() => {
      if (Date.now() - loadingSince > 30000) {
        set({ isLoading: false, statusMessage: "" });
        clearInterval(checkStuck);
      }
    }, 1000);
    return;
  }

  // 1. 确保目标会话
  let { pId, cId } = { pId: get().selectedDirId, cId: get().activeConversationId };
  if (!pId || !cId) {
    if (pId && !cId) {
      // 有目录无会话 → 在当前目录下新建一个会话
      try {
        // 从 childMap 获取父节点 kind
        let childKind = "general";
        const cm = useTreeStore.getState().childMap;
        cm.forEach((children) => {
          const found = children.find((c: any) => c.id === pId);
          if (found?.kind) childKind = found.kind;
        });
        const newC = await apiFetch<{ directory_node: { id: string } }>("/tree/directory", {
          method: "POST",
          body: JSON.stringify({ node_type: "conv", kind: childKind, parent_id: pId, name: "" }),
        });
        cId = newC.directory_node.id;
        set({
          activeConversationId: cId,
          convError: null,
          postSendRedirect: cId,
        });
        // 刷新侧边栏该目录的子节点
        await useTreeStore.getState().loadChildren(pId, "dir");
        await get().loadDirList();
      } catch {
        // 回退到临时目录
        const result = await ensureTempConversation(set, get);
        if (!result) return;
        pId = result.pId;
        cId = result.cId;
      }
    } else {
      // 无目录无会话 → 临时目录
      const result = await ensureTempConversation(set, get);
      if (!result) return;
      pId = result.pId;
      cId = result.cId;
    }
  }

  // 2. Build user message
  const userMsgId = Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
  const pq = get().pendingQuote;
  const userMsg: MessageNode = {
    id: userMsgId,
    directory_id: cId || "",
    content: text,
    version: 1,
    parent_id: "",
    children_ids: [],
    partition_id: pId || "",
    conversation_id: cId || "",
    content_blocks: [
      ...(pq ? [{ type: "quote" as const, quoted_text: pq.quotedText, source_message_id: pq.sourceMessageId, source_conversation_id: pq.sourceConversationId }] : []),
      { type: "text", text },
      ...(files?.map(f => ({ type: (f.type === "image" ? "image" : "file") as "image" | "file", name: f.name, material_id: f.materialId })) || []),
    ] as MessageNode["content_blocks"],
    text_summary: text,
    role: "user",
    timestamp: Date.now(),
    token_count: 0,
    is_deleted: false,
    is_archived: false,
  };

  // 3. Assistant placeholder（StreamPipeline 接收 SSE 流式事件实时更新此占位符）
  const asstId = Date.now().toString(36) + "a" + Math.random().toString(36).substr(2, 9);
  getPipeline().beginStream(cId || "", pId || "", asstId);

  set((state: { messages: MessageNode[] }) => ({
    messages: [...state.messages, userMsg, {
      id: asstId, parent_id: userMsgId, children_ids: [],
      partition_id: pId || "", conversation_id: cId || "",
      content_blocks: [{ type: "text" as const, text: "" }],
      text_summary: "", role: "assistant",
      timestamp: Date.now(), token_count: 0,
      is_deleted: false, is_archived: false,
    }],
  }));
  fireClassify(cId || "", text);
  set({ isLoading: true, statusMessage: "分类中...", replyingToId: null });

  // 延迟切换状态提示
  setTimeout(() => {
    const st = get().statusMessage;
    if (st === "分类中...") set({ statusMessage: "正在思考..." });
  }, 2000);

  // 4. 通过 HTTP POST 触发后台 pipeline
  //    SSE 会自动接收流式事件，更新占位符消息
  try {
    const payload: Record<string, unknown> = { text, partition_id: pId, conversation_id: cId };
    if (pq) {
      payload.pending_quote = {
        quoted_text: pq.quotedText, source_message_id: pq.sourceMessageId,
        source_conversation_id: pq.sourceConversationId,
        char_start: pq.charStart, char_end: pq.charEnd,
      };
    }
    // POST 立即返回 { ok: true }，不阻塞
    await apiFetch(`/tree/conversation/${cId}/message`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    // 注意：不在这里清除 streaming refs，StreamPipeline 的 onError 会处理
  } catch (httpErr: unknown) {
    const errMsg = `无法连接服务器：${httpErr instanceof Error ? httpErr.message : "未知错误"}`;
    set((state: { messages: MessageNode[] }) => ({
      messages: state.messages.map(m => m.id === asstId ? {
        ...m, id: "err-" + Date.now(),
        content_blocks: [{ type: "text" as const, text: `❌ ${errMsg}` }],
        text_summary: errMsg,
      } : m),
    }));
    set({ isLoading: false, statusMessage: "" });
  }
}
