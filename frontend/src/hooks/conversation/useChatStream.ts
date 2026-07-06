/**
 * useChatStream — 流式聊天 Hook
 *
 * 替代 StreamPipeline + SSESource + setup.ts 的旧架构。
 * 用 fetch + ReadableStream 读取后端 SSE 响应，一条连接完成收发。
 *
 * 职责：
 *  - send(): POST { action:"send" } → 读 SSE 响应 → 分发事件
 *  - replay(): POST { action:"replay" } → 读 SSE 响应 → 分发事件
 *  - stop(): POST { action:"stop" } → 等待当前流 done 事件 → 截断内容自然到达
 *  - waitForDone(): 等待当前流完成（供中断后发新消息使用）
 *  - 事件分发：token / tool_calls / done / error / ... → 写入 Zustand stores
 *
 * 不再 abort fetch：stop 仅通知后端停止生成，前端持续接收事件直到 done 到达。
 * generation 机制防止新旧流事件交叉写入。
 */

import { useCallback, useRef, useMemo } from "react";
import { useMessageStore } from "@/store/conversation/message-store";
import { useNotificationStore } from "@/store/notification/notification-store";
import type { MessageNode, ToolBlock, ReasoningBlock, ResponseBlock, BackgroundJob } from "@/types";
import type { SecretaryNotification } from "@/store/notification/types";
import { hydrateMessage, createErrorMessage, isTempMessage, replaceMessageIdInState } from "@/store/conversation/actions/message-factory";

// ══════════════════════════════════════════════════════════════
//  SSE stream reader
// ══════════════════════════════════════════════════════════════

/**
 * 逐行解析 fetch response body 中的 SSE 事件，回调每个 JSON 事件。
 */
async function readSSEStream(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: Record<string, unknown>) => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      // 最后一个可能不完整，保留
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith("data:")) continue;
        const jsonStr = trimmed.slice(5).trim();
        if (!jsonStr) continue;

        try {
          const data = JSON.parse(jsonStr);
          onEvent(data);
        } catch {
          /* ignore parse errors */
        }
      }
    }

    // 处理残余
    if (buffer.trim().startsWith("data:")) {
      try {
        const data = JSON.parse(buffer.trim().slice(5).trim());
        onEvent(data);
      } catch {
        /* ignore */
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// ══════════════════════════════════════════════════════════════
//  useChatStream hook
// ══════════════════════════════════════════════════════════════

export function useChatStream() {
  /** 当前 send() 的 Promise，stop() 等待它完成后才返回 */
  const sendPromiseRef = useRef<Promise<void> | null>(null);
  /** 每轮 send 递增，事件处理时校验是否仍是最新 generation */
  const generationRef = useRef(0);
  /** stop() 设置此标志，事件循环中跳过后续 token/reasoning */
  const stoppedRef = useRef(false);
  /** replay 专用 promise，与 send 隔离 */
  const replayPromiseRef = useRef<Promise<void> | null>(null);
  const convIdRef = useRef<string | null>(null);
  const dirIdRef = useRef<string | null>(null);

  // ── Event dispatch ──

  function dispatchEvent(
    event: Record<string, unknown>,
    storeApi: { setState: (p: any) => void; getState: () => any },
  ) {
    switch (event.type) {
      case "token":
        _handleToken(event.content as string);
        break;
      case "tool_calls":
        _handleToolCalls(event as any);
        break;
      case "tool_call_update":
        _handleToolCallUpdate(event as any);
        break;
      case "block_update":
        _handleBlockUpdate(event as any);
        break;
      case "tool_block":
        _handleToolBlock(event as any);
        break;
      case "reasoning":
        _handleReasoning(event.content as string);
        break;
      case "done":
        _handleDone(event, storeApi);
        break;
      case "pending_msg":
        _handlePendingMsg(event);
        break;
      case "error":
        _handleError(event.message as string || "未知错误", storeApi);
        break;
      case "context_switch":
        _handleContextSwitch(event as any, storeApi);
        break;
      case "conversation_created":
        _handleConversationCreated(event, storeApi);
        break;
      case "tree_recommendation":
        _handleTreeRecommendation(event as any);
        break;
      case "temp_recommendation":
        _handleTempRecommendation(event as any);
        break;
      case "user_message":
        _handleUserMessage(event as any);
        break;
      case "stage":
        _handleStage(event, storeApi);
        break;
      case "secretary_inline":
        _handleSecretaryInline(event as any);
        break;
      case "secretary_proposal_update":
        _handleSecretaryUpdate(event as any);
        break;
      case "job_update":
        _handleJobUpdate(event as any);
        break;
      case "stream_end":
        // 流正常结束，不做额外处理
        break;
    }
  }

  // ── send / replay ──

  /**
   * 发送消息并接收流式回答。
   * 调用前需确保 convId/dirId 有效，且已在 MessageStore 中乐观写入。
   */
  const send = useCallback(async (text: string, convId: string, dirId: string, parentId?: string) => {
    convIdRef.current = convId;
    dirIdRef.current = dirId;

    // 递增 generation，旧 generation 的事件将被忽略
    const gen = ++generationRef.current;
    stoppedRef.current = false;

    const token = typeof window !== "undefined"
      ? localStorage.getItem("access_token") || ""
      : "";

    const storeApi = {
      setState: (p: any) => {
        const { useConversationStore } = require("@/store/conversation/conversation-store");
        useConversationStore.setState(p);
      },
      getState: () => {
        const { useConversationStore } = require("@/store/conversation/conversation-store");
        return useConversationStore.getState();
      },
    };

    const doSend = async () => {
      const body: Record<string, unknown> = {
        action: "send",
        text,
        dir_id: dirId,
      };
      // 传递 parent_id（分支回复用）
      if (parentId) {
        body.parent_id = parentId;
      }

      const res = await fetch(
        `/api/conversations/tree/conversation/${convId}/message`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(body),
        },
      );

      if (!res.ok) {
        const errText = await res.text().catch(() => "");
        throw new Error(`HTTP ${res.status}: ${errText.slice(0, 200)}`);
      }
      if (!res.body) throw new Error("No response body");

      await readSSEStream(res.body, (event) => {
        // 忽略旧 generation 的事件（新 send 已启动）
        if (generationRef.current !== gen) return;
        // 用户点击停止后：跳过后续 token/reasoning，但仍处理 done/error
        if (stoppedRef.current && (event.type === "token" || event.type === "reasoning")) return;
        dispatchEvent(event, storeApi);
      });
    };

    sendPromiseRef.current = doSend();
    try {
      await sendPromiseRef.current;
    } catch (err: unknown) {
      // 旧 generation 的错误不处理
      if (generationRef.current !== gen) return;
      const msg = err instanceof Error ? err.message : "未知错误";
      _handleError(`连接失败: ${msg}`, storeApi);
    }
  }, []);

  /**
   * 重连已有流（刷新页面后）。
   * 与 send 隔离，有自己的 promise 追踪。
   */
  const replay = useCallback(async (convId: string) => {
    convIdRef.current = convId;

    const token = typeof window !== "undefined"
      ? localStorage.getItem("access_token") || ""
      : "";

    const storeApi = {
      setState: (p: any) => {
        const { useConversationStore } = require("@/store/conversation/conversation-store");
        useConversationStore.setState(p);
      },
      getState: () => {
        const { useConversationStore } = require("@/store/conversation/conversation-store");
        return useConversationStore.getState();
      },
    };

    const doReplay = async () => {
      const res = await fetch(
        `/api/conversations/tree/conversation/${convId}/message`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ action: "replay" }),
        },
      );

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (!res.body) return;

      await readSSEStream(res.body, (event) => dispatchEvent(event, storeApi));
    };

    replayPromiseRef.current = doReplay();
    try {
      await replayPromiseRef.current;
    } catch (err: unknown) {
      console.error("[useChatStream] replay failed:", err);
    }
  }, []);

  /**
   * 提交工具结果（用户回答 ask_question），恢复挂起的管线。
   *
   * 方案A：不创建新的 SSE 连接，原 send() 的 SSE 连接保持打开，
   * 恢复后的事件通过原连接继续流式推送。本方法仅 POST 触发恢复。
   */
  const submitToolResult = useCallback(async (
    toolCallId: string,
    answers: string,
    convId: string,
  ) => {
    const token = typeof window !== "undefined"
      ? localStorage.getItem("access_token") || ""
      : "";

    const res = await fetch(
      `/api/conversations/tree/conversation/${convId}/tool-result`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          tool_call_id: toolCallId,
          answers,
        }),
      },
    );

    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status}: ${errText.slice(0, 200)}`);
    }

    return res.json();
  }, []);

  /**
   * 停止当前流式生成。
   *
   * 流程：POST {action:"stop"} → 通知后端停止 → 等待当前 send() 的
   * done 事件到达（后端现在在 CancelledError 后会跑 PostProcess + Done 阶段，
   * 持久化截断消息后再发 done）。
   *
   * 调用方需在 resolve 后自行清理 isLoading / streamingId 状态。
   */
  const stop = useCallback(async () => {
    stoppedRef.current = true;

    const convId = convIdRef.current;
    if (convId) {
      const token = typeof window !== "undefined"
        ? localStorage.getItem("access_token") || ""
        : "";
      try {
        await fetch(`/api/conversations/tree/conversation/${convId}/message`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ action: "stop" }),
        });
      } catch {
        /* best effort */
      }
    }

    // 等待当前 send() 完成 — 后端的 done(cancelled) 事件会到达
    if (sendPromiseRef.current) {
      try { await sendPromiseRef.current; } catch { /* _handleError 已处理 */ }
    }
  }, []);

  return useMemo(
    () => ({ send, replay, stop, submitToolResult }),
    [send, replay, stop, submitToolResult],
  );
}

// ════════════════════════════════════════════════
//  Event handlers — 直接写 Zustand stores（替代 setup.ts）
// ════════════════════════════════════════════════

/**
 * 启发式：切块时把上一个 streaming 的 reasoning 块翻成 done。
 *
 * 后端在 reasoning → text / reasoning → tool 切换时不会发"reasoning 结束"事件，
 * 只有整条流 done 时才会一次性翻 done（见 _handleDone），导致用户视觉上看到上一个
 * reasoning 块继续显示 spinner 与"思考中..."标签。
 *
 * 这里的启发式与后端的块顺序约定一致：流式阶段 reasoning 块永远只会被新 text/tool 块
 * 切走，不会出现 reasoning → reasoning 的连续（同类型后端会合并）。当且仅当
 * `lastBlock` 是 `status==="streaming"` 的 reasoning 时才翻 done。
 */
function _closeStreamingReasoning(blocks: Array<{ type: string; status?: string }>): typeof blocks {
  if (blocks.length === 0) return blocks;
  const last = blocks[blocks.length - 1];
  if (last.type === "reasoning" && last.status === "streaming") {
    return [...blocks.slice(0, -1), { ...last, status: "done" as const }];
  }
  return blocks;
}

/**
 * 合并流式阶段的 content_blocks 与服务端 responseBlocks：
 * - tool 块：用服务端数据更新（保留 user_answer），状态从 pending/running → done/error
 * - reasoning 块：翻 status="done"
 * - 其它块（text/quote/file/image）：保留流式阶段的内容
 * - 服务端多出的 tool 块：追加到末尾
 */
function _mergeFinalBlocks(
  streamingBlocks: any[],
  serverBlocks: ToolBlock[],
): any[] {
  let toolServerIdx = 0;
  const finalBlocks = streamingBlocks.map((b: any) => {
    if (b.type === "tool") {
      const serverBlock = serverBlocks[toolServerIdx];
      toolServerIdx++;
      const finalStatus: "done" | "error" =
        (b.status !== "pending" && b.status !== "running") ? b.status
        : serverBlock?.status === "error" ? "error"
        : "done";
      if (serverBlock) {
        const localRc = b.result_content || {};
        const preservedUserAnswer = localRc.user_answer;
        const preservedAnsweredAt = localRc.answered_at;
        return {
          ...serverBlock,
          status: finalStatus,
          result_content: {
            ...(serverBlock.result_content || {}),
            ...(preservedUserAnswer
              ? { user_answer: preservedUserAnswer, answered_at: preservedAnsweredAt }
              : {}),
          },
        };
      }
      return { ...b, status: finalStatus };
    }
    if (b.type === "reasoning") {
      return { ...b, status: "done" as const };
    }
    return b;
  });
  const extraTools = serverBlocks.slice(toolServerIdx);
  if (extraTools.length > 0) finalBlocks.push(...extraTools);
  return finalBlocks;
}

function _handleToken(content: string) {
  useMessageStore.setState((state: { messages: MessageNode[]; streamingId: string | null }) => {
    const sid = state.streamingId;
    if (!sid) return {};
    return {
      messages: state.messages.map((m) => {
        if (m.id !== sid) return m;
        let existingBlocks = [...(m.content_blocks || [])];
        const lastBlock = existingBlocks.length > 0 ? existingBlocks[existingBlocks.length - 1] : null;

        if (lastBlock && lastBlock.type === "text") {
          existingBlocks[existingBlocks.length - 1] = { ...lastBlock, text: lastBlock.text + content };
        } else {
          // 切到新 text 块：若上一个是 streaming 的 reasoning，先翻成 done
          existingBlocks = _closeStreamingReasoning(existingBlocks);
          existingBlocks.push({ type: "text" as const, text: content });
        }

        return {
          ...m,
          content_blocks: existingBlocks,
          text_summary: (m.text_summary || "") + content,
        };
      }),
    };
  });
}

function _handleToolCalls(data: { tool_calls: any[]; conv_id?: string }) {
  const convId = data.conv_id || "";
  useMessageStore.setState((state: { messages: MessageNode[]; streamingId: string | null }) => {
    const sid = state.streamingId;
    if (!sid) return {};

    const toolBlocks: ToolBlock[] = data.tool_calls.map((tc: any) => ({
      type: "tool" as const,
      tool_call_id: tc.tool_call_id,
      tool_name: tc.tool_name,
      display_name: tc.zh || tc.tool_name,
      icon: tc.icon || "🔧",
      arguments: tc.arguments,
      status: "pending" as const,
      tool_round: tc.tool_round || 0,
      conv_id: convId,
    }));

    return {
      messages: state.messages.map((msg) => {
        if (msg.id !== sid) return msg;
        // 切到 tool 块：若上一个是 streaming 的 reasoning，先翻成 done
        const closedBlocks = _closeStreamingReasoning(msg.content_blocks || []);
        return { ...msg, content_blocks: [...closedBlocks, ...toolBlocks] };
      }),
    };
  });
}

function _handleToolCallUpdate(data: { tool_call_id: string; status: string }) {
  useMessageStore.setState((state: { messages: MessageNode[]; streamingId: string | null }) => {
    const sid = state.streamingId;
    return {
      messages: state.messages.map((msg) => {
        // 仅更新当前流式消息，不广播到历史消息
        if (sid && msg.id !== sid) return msg;
        return {
          ...msg,
          content_blocks: msg.content_blocks?.map((b: any) =>
            b.type === "tool" && b.tool_call_id === data.tool_call_id
              ? { ...b, status: data.status }
              : b,
          ),
        };
      }),
    };
  });
}

function _handleBlockUpdate(block: any) {
  const tcId = block.tool_call_id || (block.data?.tool_call_id) || "";
  if (!tcId) {
    console.debug("[_handleBlockUpdate] 跳过：tcId 为空", { blockType: block.type });
    return;
  }

  const innerBlock = block.block || block;
  const isFailed = innerBlock.status === "failed" || innerBlock.status === "error";
  const blockStatus = isFailed ? "error" as const : "done" as const;

  useMessageStore.setState((state: { messages: MessageNode[]; streamingId: string | null }) => {
    const sid = state.streamingId;
    let matched = false;
    const result = {
      messages: state.messages.map((msg) => {
        // 仅更新当前流式消息，不广播到历史消息
        if (sid && msg.id !== sid) return msg;
        return {
          ...msg,
          content_blocks: msg.content_blocks?.map((b: any) => {
            if (b.type === "tool" && b.tool_call_id === tcId) {
              matched = true;
              return {
                ...b,
                status: blockStatus,
                result_block_type: block.result_block_type || innerBlock.type || null,
                result_content: block.result_content || innerBlock.content || null,
                conv_id: innerBlock.conv_id || b.conv_id || "",
                dir_id: innerBlock.dir_id || b.dir_id || "",
                error: isFailed ? (innerBlock.content?.error || "工具执行失败") : undefined,
              };
            }
            return b;
          }),
        };
      }),
    };
    if (!matched) {
      console.debug("[_handleBlockUpdate] 未匹配到 ToolBlock", { tcId, sid, innerBlockType: innerBlock.type, innerBlockConvId: innerBlock.conv_id });
    }
    return result;
  });
}

function _handleToolBlock(block: ResponseBlock) {
  // 兼容旧格式
  _handleBlockUpdate(block);
}

function _handleReasoning(content: string) {
  useMessageStore.setState((state: { messages: MessageNode[]; streamingId: string | null }) => {
    const sid = state.streamingId;
    if (!sid) return {};

    return {
      messages: state.messages.map((msg) => {
        if (msg.id !== sid) return msg;
        const existingBlocks = [...(msg.content_blocks || [])];
        const lastBlock = existingBlocks.length > 0 ? existingBlocks[existingBlocks.length - 1] : null;

        if (lastBlock && lastBlock.type === "reasoning") {
          // 最后一个块就是 reasoning → 追加到它
          existingBlocks[existingBlocks.length - 1] = {
            ...lastBlock,
            text: (lastBlock.text || "") + content,
            status: "streaming" as const,
          };
        } else {
          // 被 tool/text 块隔开了 → 创建新的 reasoning 块追加到末尾
          existingBlocks.push({
            type: "reasoning" as const,
            text: content,
            status: "streaming" as const,
          });
        }

        return { ...msg, content_blocks: existingBlocks };
      }),
    };
  });
}

function _handleDone(
  data: Record<string, unknown>,
  storeApi: { setState: (p: any) => void; getState: () => any },
) {
  storeApi.setState({ isLoading: false, statusMessage: "" });

  const replyData = (data.data || data) as Record<string, unknown>;
  const assistantMessage = replyData.assistant_message as MessageNode | undefined;
  const responseBlocks = (replyData.response_blocks || []) as Array<Record<string, unknown>>;
  const userMessage = replyData.user_message as MessageNode | undefined;

  const toolBlocksFromSSE: ToolBlock[] = responseBlocks.map((rb: any) => ({
    type: "tool" as const,
    tool_call_id: rb.id || rb._response_block_id || "",
    tool_name: rb.type || rb.block_type || "unknown",
    arguments: {} as Record<string, unknown>,
    status: (rb.status === "error" ? "error" : "done") as "done" | "error",
    result_block_type: rb.type || rb.block_type || null,
    result_content: rb.content || null,
    conv_id: rb.conv_id || "",
    dir_id: rb.dir_id || "",
    error: rb.error || null,
    tool_round: 0,
  }));

  useMessageStore.setState((state: { messages: MessageNode[]; streamingId: string | null; nodeMap: Record<string, MessageNode>; currentPath: string[]; pathPosMap: Map<string, number> }) => {
    const sid = state.streamingId;

    // ── Step 1: 计算合并后的 streaming 消息（流式 blocks + 服务端 responseBlocks）──
    const streamingMsg = sid ? (state.messages.find(m => m.id === sid) || state.nodeMap[sid]) : null;
    const mergedStreamingBlocks = streamingMsg
      ? _mergeFinalBlocks(streamingMsg.content_blocks || [], toolBlocksFromSSE)
      : toolBlocksFromSSE;

    // ── Step 2: 用 replaceMessageIdInState 替换 streaming 占位 → assistantMessage ──
    let next: any = { ...state };
    if (assistantMessage) {
      const hydratedAsst: MessageNode = hydrateMessage({
        ...assistantMessage,
        content_blocks: mergedStreamingBlocks as MessageNode["content_blocks"],
      });
      if (sid && sid !== hydratedAsst.id) {
        // 旧 sid（如 replay 路径的 a_xxx）→ 服务端真实 ID
        next = { ...next, ...replaceMessageIdInState(next, { oldId: sid, newMsg: hydratedAsst }) };
      } else {
        // sid === newAsstId（_handlePendingMsg 已替换）→ 仅 upsert
        next.nodeMap = { ...next.nodeMap, [hydratedAsst.id]: hydratedAsst };
        next.messages = next.messages.map((m: MessageNode) => (m.id === hydratedAsst.id ? hydratedAsst : m));
      }
    }

    // ── Step 3: 替换 user 临时消息 → userMessage（找到当前 user role 的临时消息）──
    if (userMessage) {
      const hydratedUser = hydrateMessage(userMessage);
      // 查找 user role 临时消息：先找 messages 数组，再找 nodeMap
      const nodeMapValues = Object.values(next.nodeMap as Record<string, MessageNode>);
      const tempUserMsg = next.messages.find(
        (m: MessageNode) => m.role === "user" && isTempMessage(m.id),
      ) || nodeMapValues.find(
        (m: MessageNode) => m.role === "user" && isTempMessage(m.id),
      );
      if (tempUserMsg && tempUserMsg.id !== hydratedUser.id) {
        next = { ...next, ...replaceMessageIdInState(next, { oldId: tempUserMsg.id, newMsg: hydratedUser }) };
      } else if (!tempUserMsg) {
        // 没找到临时 user 消息（如刷新页面后 done）→ 仅 upsert 到 nodeMap
        next.nodeMap = { ...next.nodeMap, [hydratedUser.id]: hydratedUser };
      }
    }

    // ── Step 4: 追加到 currentPath 末尾（如果尚未包含） ──
    let newPath = next.currentPath;
    if (assistantMessage && !newPath.includes(assistantMessage.id)) {
      newPath = [...newPath, assistantMessage.id];
    }
    if (userMessage && !newPath.includes(userMessage.id)) {
      // 找到用户消息应该插入的位置（在它的 parent_id 之后）
      const parentId = userMessage.parent_id;
      const insertIdx = parentId
        ? newPath.indexOf(parentId) + 1 || newPath.length
        : newPath.length;
      const newPathArr = [...newPath];
      if (!newPathArr.includes(userMessage.id)) {
        newPathArr.splice(insertIdx, 0, userMessage.id);
      }
      newPath = newPathArr;
    }

    return {
      nodeMap: next.nodeMap,
      currentPath: newPath,
      pathPosMap: next.pathPosMap,
      pathReady: true,
      messages: next.messages,
      streamingId: null,
    };
  });
}

function _handleError(
  msg: string,
  storeApi: { setState: (p: any) => void; getState: () => any },
) {
  storeApi.setState({ isLoading: false, statusMessage: "" });

  const state = storeApi.getState();
  const convId = state.selectedNode?.id || "";
  const dirId = state.selectedNode?.parent || "";

  // ★ 工厂构造错误消息（统一带 load_state: "loaded" + "❌" 前缀）
  const errorMessage = createErrorMessage({
    errMsg: msg,
    convId,
    dirId,
    parentId: "",
  });

  useMessageStore.setState((s: { messages: MessageNode[]; streamingId: string | null; sending: boolean }) => ({
    messages: [
      ...s.messages.filter(
        (m: MessageNode) => !(isTempMessage(m.id) || m.id === s.streamingId),
      ),
      errorMessage,
    ],
    streamingId: null,
    // 释放发送锁（防止 stale streaming 卡死）
    sending: false,
  }));
}

function _handleContextSwitch(
  data: { dirId: string; convId: string; targetDirId: string; targetDomainName: string; targetTopicName: string; fullPath: string },
  storeApi: { setState: (p: any) => void },
) {
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

  const id = `context_switch_${data.dirId}_${data.convId}`;
  const nStore = useNotificationStore.getState();
  if (nStore.notifications.some((n) => n.id === id)) return;
  nStore.addNotification({
    id, emoji: "🔀",
    title: "检测到话题切换",
    description: data.fullPath || `${data.targetDomainName}${data.targetTopicName ? ` → ${data.targetTopicName}` : ""}`,
    priority: 3,
    target: { pages: ["learn"], inlineConversationId: data.convId, actionPath: `/conversation?conv=${data.convId}` },
    source: "context_switch", sourceModule: "conversation",
    read: false, status: "pending", created_at: Date.now(),
  } as SecretaryNotification);
}

function _handleConversationCreated(
  event: Record<string, unknown>,
  storeApi: { setState: (p: any) => void; getState: () => any },
) {
  const convId = (event.data as any)?.conv_id || "";
  if (convId) {
    storeApi.setState((state: any) => ({
      selectedNode: {
        id: convId,
        level: "conv",
        parent: state.selectedNode?.parent || null,
        path: state.selectedNode?.path || [],
      },
    }));
  }
}

function _handleTreeRecommendation(data: any) {
  // Banner
  const { useConversationStore } = require("@/store/conversation/conversation-store");
  useConversationStore.setState({
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
  // Notification
  const id = `tree_rec_ws_${data.dirId}`;
  const store = useNotificationStore.getState();
  if (store.notifications.some((n) => n.id === id)) return;
  store.addNotification({
    id, emoji: "🌳",
    title: "知识树整理提醒",
    description: data.dirName ? `分区「${data.dirName}」${data.message}` : data.message,
    priority: 3,
    target: { pages: ["learn", "knowledge-tree"] },
    source: "tree_recommendation", sourceModule: "knowledge_tree",
    read: false, status: "pending", created_at: Date.now(),
  } as SecretaryNotification);
}

function _handleTempRecommendation(data: any) {
  const { useConversationStore } = require("@/store/conversation/conversation-store");
  useConversationStore.setState({
    recommendationBanner: {
      type: data.recType === "switch_to_learn" ? "learn" as const : "tree" as const,
      message: data.message,
      dirId: data.dirId || "",
      dirName: data.dirName || "",
      needsGenerate: data.needsGenerate,
      createConversation: data.createConversation,
    },
  });
  const id = `temp_rec_${data.recType}_${data.dirId || "global"}`;
  const store = useNotificationStore.getState();
  if (store.notifications.some((n) => n.id === id)) return;
  const isLearn = data.recType === "switch_to_learn";
  store.addNotification({
    id, emoji: isLearn ? "📚" : "🌳",
    title: isLearn ? "学习推荐" : "知识树推荐",
    description: data.message,
    priority: 2,
    target: { pages: ["learn"], actionPath: isLearn ? "/conversation" : "/knowledge-tree" },
    source: "temp_recommendation", sourceModule: "conversation",
    read: false, status: "pending", created_at: Date.now(),
  } as SecretaryNotification);
}

function _handleSecretaryInline(data: SecretaryNotification) {
  useNotificationStore.getState().addNotification(data);
}

function _handleSecretaryUpdate(data: { id: string; status: string; until?: number }) {
  const store = useNotificationStore.getState();
  switch (data.status) {
    case "accepted": store.acceptNotification(data.id); break;
    case "dismissed": store.dismissNotification(data.id); break;
    case "snoozed": if (data.until) store.snoozeNotification(data.id, data.until); break;
    case "deleted": store.removeNotification(data.id); break;
    case "restored": store.restoreNotification(data.id); break;
    default: store.updateNotification(data.id, { status: data.status as any }); break;
  }
}

function _handleJobUpdate(data: BackgroundJob) {
  const id = `job_${data.id}`;
  const store = useNotificationStore.getState();
  const isDone = data.status === "done";
  const isFailed = data.status === "failed";
  store.addNotification({
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
  } as SecretaryNotification);
}

function _handleUserMessage(data: { message: MessageNode }) {
  // ★ 关键：hydrateMessage 强制带 load_state: "loaded"
  // 否则乐观占位被服务端消息替换后，load_state 字段丢失，
  // 用户切换会话回来时会被当成 placeholder 重新触发 loadFullContent
  const hydrated = hydrateMessage(data.message);
  useMessageStore.setState((state: { messages: MessageNode[] }) => ({
    messages: state.messages.map((m: MessageNode) => {
      // 安全判断：m.id 可能为 undefined（旧数据 / 服务端缺字段），用 isTempMessage 防御
      if (!m.id || m.role !== "user" || !isTempMessage(m.id)) return m;
      return hydrated;
    }),
  }));
}

function _handlePendingMsg(data: Record<string, unknown>) {
  const msgId = (data.data as any)?.msg_id || "";
  if (!msgId) return;
  useMessageStore.setState((state: { messages: MessageNode[]; streamingId: string | null; nodeMap: Record<string, MessageNode>; currentPath: string[]; pathPosMap: Map<string, number> }) => {
    // 已有 streamingId 且不相同：用 replaceMessageIdInState 一次性同步
    // nodeMap（删旧 key 加新 key）、currentPath、pathPosMap、messages、streamingId
    if (state.streamingId && state.streamingId !== msgId) {
      const streamingMsg = state.messages.find(m => m.id === state.streamingId)
        || state.nodeMap[state.streamingId];
      if (streamingMsg) {
        const renamed: MessageNode = { ...streamingMsg, id: msgId, load_state: "loaded" };
        return replaceMessageIdInState(state, { oldId: state.streamingId, newMsg: renamed });
      }
      // 找不到旧消息对象 → 仅同步 streamingId
      return { streamingId: msgId };
    }
    // 没有 streamingId 或相同，存入即可
    return { streamingId: msgId };
  });
}

function _handleStage(
  event: Record<string, unknown>,
  storeApi: { setState: (p: any) => void },
) {
  const msgs: Record<string, string> = {
    classifying: "分类匹配中...",
    thinking: "正在思考...",
  };
  const text = msgs[event.stage as string] || "";
  if (text) storeApi.setState({ statusMessage: text });
}
