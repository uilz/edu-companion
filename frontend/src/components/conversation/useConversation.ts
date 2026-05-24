"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import type { Partition, TreeNode, ResponseBlock, WSIncomingMessage } from "@/types";

// ══════════════════ 工具函数: 响应式断点检测══════════════════
function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia(query);
    setMatches(mq.matches);
    const listener = (e: MediaQueryListEvent) => setMatches(e.matches);
    mq.addEventListener("change", listener);
    return () => mq.removeEventListener("change", listener);
  }, [query]);
  return matches;
}

// ══════════════════ API 封装 ══════════════════
async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`/api/conversations${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    cache: 'no-store',
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

// ══════════════════ WebSocket 管理器: 单连接 + 指数退避重连 (保持不变) ══════════════════
type WSCallbacks = {
  onToken: (content: string, blockId?: string) => void;
  onDone: (partitionId: string, assistantMessage: TreeNode, responseBlocks?: ResponseBlock[]) => void;
  onError: (msg: string) => void;
  onBlockUpdate: (block: ResponseBlock) => void;
  onContextSwitch: (data: {
    partition_id: string; conversation_id: string;
    domain_name: string; topic_name: string;
    switch_detail: Record<string, string>;
  }) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
};

class ConversationWS {
  private ws: WebSocket | null = null;
  private callbacks: WSCallbacks | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private attempts = 0;
  private destroyed = false;

  /** 建立 WebSocket 连接 */
  connect(cbs: WSCallbacks) {
    this.callbacks = cbs;
    if (this.ws && this.ws.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/api/conversations/ws`;

    try {
      this.ws = new WebSocket(url);
      this.ws.onopen = () => { this.attempts = 0; this.callbacks?.onConnect?.(); };
      this.ws.onmessage = (event) => {
        try {
          const data: WSIncomingMessage = JSON.parse(event.data);
          switch (data.type) {
            case "token":        // AI 输出流式 token
              this.callbacks?.onToken(data.content, data.block_id);
              break;
            case "tool_block":   // 工具调用结果块
            case "block_update": // 块状态更新
              this.callbacks?.onBlockUpdate(data.block);
              break;
            case "done":         // AI 回复完成
              this.callbacks?.onDone(data.partition_id, data.assistant_message, data.response_blocks);
              break;
            case "error":
              this.callbacks?.onError(data.message);
              break;
            case "context_switch": // 上下文切换通知
              this.callbacks?.onContextSwitch(data);
              break;
            // user_message, pong, status — 无需处理
          }
        } catch { /* 忽略解析错误 */ }
      };
      this.ws.onerror = () => { }; // onclose 处理重连
      this.ws.onclose = () => {
        if (this.destroyed) return;
        this.callbacks?.onDisconnect?.();
        this.ws = null;
        // 指数退避: 1s → 2s → 4s → ... → 30s 上限
        const delay = Math.min(1000 * Math.pow(2, this.attempts), 30000);
        this.attempts++;
        this.reconnectTimer = setTimeout(() => {
          if (this.callbacks) this.connect(this.callbacks);
        }, delay);
      };
    } catch {
      this.ws = null;
    }
  }

  /** 发送消息到 WebSocket */
  send(data: Record<string, unknown>): boolean {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
      return true;
    }
    return false;
  }

  /** 销毁连接（组件卸载时调用） */
  destroy() {
    this.destroyed = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
    this.callbacks = null;
    this.attempts = 0;
  }
}

// ══════════════════════════════════════════════════════════════
//  Hook 返回值类型定义 (不变)
// ══════════════════════════════════════════════════════════════
export interface UseConversationReturn {
  partitions: Partition[];
  selectedPartitionId: string | null;
  activeConversationId: string | null;
  messages: TreeNode[];
  responseBlocks: ResponseBlock[];
  isLoading: boolean;
  statusMessage: string;
  switchBanner: {
    partitionId: string; conversationId: string;
    domainName: string; topicName: string;
  } | null;
  showPartitionSidebar: boolean;
  sidebarCollapsed: boolean;
  showNewPartition: boolean;
  loadingPartitions: boolean;
  loadingMessages: boolean;
  convError: string | null;
  isDesktop: boolean;
  activePartition: Partition | undefined;
  wsConnected: boolean;

  handleSelectConversation: (pid: string, cid: string) => void;
  handleNewConversation: (level: string, parentId: string) => Promise<void>;
  handleSend: (text: string, files?: { name: string; type: string; materialId?: string }[]) => Promise<void>;
  handleDeleteMessage: (messageId: string) => Promise<void>;
  handleEditMessage: (messageId: string, newText: string) => Promise<number>;
  handleVersionSwitch: (messageId: string, direction: "prev" | "next") => Promise<{ index: number; total: number } | null>;
  handleCreatePartition: (name: string, emoji: string) => Promise<void>;
  handleRenamePartition: (id: string, name: string) => Promise<void>;
  handleSwitchConfirm: () => void;
  handleSwitchDismiss: () => void;
  setShowPartitionSidebar: (v: boolean) => void;
  setShowNewPartition: (v: boolean) => void;
  setSidebarCollapsed: (v: boolean) => void;
  loadPartitions: () => Promise<void>;
}

// ══════════════════════════════════════════════════════════════
//  
// ══════════════════创建对话链 (归一化后)══════════════════
async function createConversationChain(
  partitionId?: string | null,
): Promise<{ partitionId: string; conversationId: string } | null> {
  try {
    let pId = partitionId || undefined;
    if (!pId) {
      // 1. 获取分区列表，若无则创建默认分区
      const pData = await apiFetch<{ partitions: Partition[] }>("/tree/partition");
      if (pData.partitions?.length > 0) {
        pId = pData.partitions[0].id;
      } else {
        const newP = await apiFetch<{ partition: Partition; conversation_id?: string }>("/tree/partition", {
          method: "POST",
          body: JSON.stringify({ name: "默认分区", emoji: "💬" }),
        });
        pId = newP.partition.id;
      }
    }

    // 2. 找或创建领域 domain
    const domainData = await apiFetch<{ domains: { id: string }[] }>(`/tree/domain?parent_id=${pId}`);
    let domainId: string;
    if (domainData.domains?.length > 0) {
      domainId = domainData.domains[0].id;
    } else {
      const newD = await apiFetch<{ domain: { id: string }; conversation_id?: string }>("/tree/domain", {
        method: "POST",
        body: JSON.stringify({ parent_id: pId, name: "默认领域", emoji: "📚" }),
      });
      domainId = newD.domain.id;
    }

    // 3. 找或创建专题 topic
    const topicData = await apiFetch<{ topics: { id: string }[] }>(`/tree/topic?parent_id=${domainId}`);
    let topicId: string;
    if (topicData.topics?.length > 0) {
      topicId = topicData.topics[0].id;
    } else {
      const newT = await apiFetch<{ topic: { id: string }; conversation_id?: string }>("/tree/topic", {
        method: "POST",
        body: JSON.stringify({ parent_id: domainId, name: "默认专题", emoji: "📝" }),
      });
      topicId = newT.topic.id;
    }

    // 4. 创建对话
    const convData = await apiFetch<{ conversation: { id: string } }>("/tree/conversation", {
      method: "POST",
      body: JSON.stringify({ parent_id: topicId, name: "" }),
    });
    return { partitionId: pId, conversationId: convData.conversation.id };
  } catch (e) {
    console.error("[createConversationChain] 创建对话链失败:", e);
    return null;
  }
}

// ══════════════════════════════════════════════════════════════
//  useConversation — 对话系统核心 Hook (归一化版)
// ══════════════════════════════════════════════════════════════
export function useConversation(): UseConversationReturn {
  const isDesktop = useMediaQuery("(min-width: 768px)");
  const router = useRouter();

  // ── 状态 ──
  const [partitions, setPartitions] = useState<Partition[]>([]);
  const [selectedPartitionId, setSelectedPartitionId] = useState<string | null>(null);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<TreeNode[]>([]);
  const [responseBlocks, setResponseBlocks] = useState<ResponseBlock[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [switchBanner, setSwitchBanner] = useState<{
    partitionId: string; conversationId: string;
    domainName: string; topicName: string;
  } | null>(null);
  const [showPartitionSidebar, setShowPartitionSidebar] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [showNewPartition, setShowNewPartition] = useState(false);
  const [loadingPartitions, setLoadingPartitions] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [convError, setConvError] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [urlInitialized, setUrlInitialized] = useState(false);

  // ── Refs ──
  const wsRef = useRef<ConversationWS | null>(null);
  const activeConvIdRef = useRef<string | null>(null);
  const activePartIdRef = useRef<string | null>(null);
  const streamingPartIdRef = useRef<string | null>(null);
  const streamingConvIdRef = useRef<string | null>(null);
  const streamingMsgIdRef = useRef<string | null>(null);
  const streamBufferRef = useRef("");
  const loadPartitionsRef = useRef<() => Promise<void>>(() => Promise.resolve());

  // 如果 URL 有 ?panel=graph，跳转到仪表盘知识图谱页
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      if (params.get("panel") === "graph") {
        const pId = params.get("p") || params.get("partition_id");
        router.replace(pId ? `/dashboard?tab=graph&partition_id=${pId}` : "/dashboard?tab=graph");
      }
    } catch { }
  }, [router]);

  // URL / localStorage 恢复状态 (合并为一个 effect)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const pId = params.get("p") || params.get("partition_id");
    const cId = params.get("c") || params.get("conversation_id");
    if (pId) {
      setSelectedPartitionId(pId);
      if (cId) setActiveConversationId(cId);
    } else {
      try {
        const saved = localStorage.getItem("learn-page-state");
        if (saved) {
          const { partitionId, conversationId } = JSON.parse(saved);
          if (partitionId) setSelectedPartitionId(partitionId);
          if (conversationId) setActiveConversationId(conversationId);
        }
      } catch { }
    }
    setUrlInitialized(true);  // 完成后同步 URL
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── 状态同步 → URL + localStorage ──
  // 每次 selectedPartitionId / activeConversationId 变化时更新浏览器地址栏和本地存储
  useEffect(() => {
    if (!urlInitialized) return;
    try {
      const params = new URLSearchParams();
      if (selectedPartitionId) params.set("p", selectedPartitionId);
      if (activeConversationId) params.set("c", activeConversationId);
      const qs = params.toString();
      window.history.replaceState(null, "", qs ? `${window.location.pathname}?${qs}` : window.location.pathname);
      localStorage.setItem("learn-page-state", JSON.stringify({
        partitionId: selectedPartitionId,
        conversationId: activeConversationId,
      }));
    } catch { }
  }, [selectedPartitionId, activeConversationId, urlInitialized]);

  // ── ref 同步 ──
  useEffect(() => { activeConvIdRef.current = activeConversationId; }, [activeConversationId]);
  useEffect(() => { activePartIdRef.current = selectedPartitionId; }, [selectedPartitionId]);

  // ── 锁定 body 滚动 ──
  useEffect(() => { document.body.style.overflow = "hidden"; return () => { document.body.style.overflow = ""; }; }, []);

  // ── 加载分区列表 ──
  const loadPartitions = useCallback(async () => {
    setLoadingPartitions(true);
    try {
      const data = await apiFetch<{ partitions: Partition[] }>("/tree/partition");
      setPartitions(data.partitions || []);
    } catch (e) { console.error(e); }
    finally { setLoadingPartitions(false); }
  }, []);
  loadPartitionsRef.current = loadPartitions;

  // ── 加载消息 (归一化路径) ──
  const loadMessages = useCallback(async (conversationId: string) => {
    setLoadingMessages(true);
    setConvError(null);
    try {
      const [msgData, blocksData] = await Promise.all([
        apiFetch<{ messages: TreeNode[]; total: number }>(`/tree/conversation/${conversationId}/messages?limit=50&offset=0`),
        apiFetch<{ blocks: ResponseBlock[] }>(`/tree/conversation/${conversationId}/blocks?limit=100`).catch(() => ({ blocks: [] })),
      ]);
      setMessages(msgData.messages || []);
      setResponseBlocks(blocksData.blocks || []);
    } catch (e: any) {
      if (e.message.includes("404")) {
        setConvError("该对话已被删除");
        setActiveConversationId(null);
      } else {
        setConvError("加载失败");
      }
      setMessages([]);
      setResponseBlocks([]);
    } finally { setLoadingMessages(false); }
  }, []);

  // ── 选中对话时加载消息 ──
  useEffect(() => { if (activeConversationId) loadMessages(activeConversationId); else { setMessages([]); setResponseBlocks([]); } }, [activeConversationId, loadMessages]);

  // ── WebSocket 初始化 ──
  useEffect(() => {
    const wsClient = new ConversationWS();
    wsRef.current = wsClient;
    wsClient.connect({
      // 流式 token 回调: 实时更新消息内容
      onToken: (content) => {
        if (!streamingMsgIdRef.current) return;
        // 检查流式上下文是否仍有效（用 ref 避免闭包过期）
        if (streamingPartIdRef.current !== activePartIdRef.current ||
          streamingConvIdRef.current !== activeConvIdRef.current) return;

        streamBufferRef.current += content;
        const text = streamBufferRef.current;
        const msgId = streamingMsgIdRef.current;

        setMessages((prev) =>
          prev.map((m) =>
            m.id === msgId
              ? { ...m, content_blocks: [{ type: "text" as const, text }], text_summary: text }
              : m
          )
        );
      },
      // AI 回复完成回调
      onDone: (_partId, assistantMessage, responseBlocks) => {
        setIsLoading(false);
        setStatusMessage("");

        const streamPid = streamingPartIdRef.current;
        const streamCid = streamingConvIdRef.current;
        const streamMsgId = streamingMsgIdRef.current;
        streamingPartIdRef.current = null;
        streamingConvIdRef.current = null;
        streamingMsgIdRef.current = null;
        streamBufferRef.current = "";

        // 如果用户已切换对话，丢弃这个过时的流式消息
        if (streamPid !== activePartIdRef.current || streamCid !== activeConvIdRef.current) {
          if (streamMsgId) {
            setMessages((prev) => prev.filter((m) => m.id !== streamMsgId));
          }
          return;
        }

        // 用最终消息替换占位符
        if (assistantMessage) {
          const textBlock = assistantMessage.content_blocks?.find((b: { type: string }) => b.type === "text");
          const hasContent = textBlock?.text?.trim();
          setMessages((prev) => {
            const idx = prev.findIndex((m) => m.id === streamMsgId || m.id === assistantMessage.id);
            if (idx >= 0) {
              const updated = [...prev];
              updated[idx] = hasContent ? assistantMessage : {
                ...assistantMessage,
                content_blocks: [{ type: "text" as const, text: "（助手返回了空回复）" }],
                text_summary: "（助手返回了空回复）",
              };
              return updated;
            }
            return prev;
          });
        } else if (streamMsgId) {
          setMessages((prev) => prev.filter((m) => m.id !== streamMsgId));
        }

        // 添加回复块（视频/练习/图片等）
        if (responseBlocks?.length) {
          setResponseBlocks((prev) => {
            const existing = new Set(prev.map((b) => b.id));
            const newBlocks = responseBlocks.filter((b) => !existing.has(b.id));
            return newBlocks.length ? [...prev, ...newBlocks] : prev;
          });
        }

        // 延迟刷新侧栏 + 消息列表
        setTimeout(() => loadPartitionsRef.current(), 300);
        setTimeout(() => {
          const cid = activeConvIdRef.current;
          if (cid && cid === streamCid) loadMessages(cid);
        }, 500);
      },
      // 错误回调: 显示错误消息
      onError: (msg) => {
        setIsLoading(false);
        setStatusMessage("");
        const errorNode: TreeNode = {
          id: "err-" + Date.now(),
          parent_id: "", children_ids: [],
          partition_id: activePartIdRef.current || "",
          conversation_id: activeConvIdRef.current || "",
          content_blocks: [{ type: "text" as const, text: `❌ ${msg}` }],
          text_summary: msg,
          role: "assistant", timestamp: Date.now(),
          token_count: 0, is_deleted: false, is_archived: false, has_modified_version: false,
        };
        if (streamingMsgIdRef.current) {
          setMessages((prev) =>
            prev.map((m) => m.id === streamingMsgIdRef.current ? errorNode : m)
          );
        } else {
          setMessages((prev) => [...prev, errorNode]);
        }
        streamingMsgIdRef.current = null;
        streamBufferRef.current = "";
      },
      // 回复块更新（如工具调用完成）
      onBlockUpdate: (block) => {
        setResponseBlocks((prev) => {
          const idx = prev.findIndex((b) => b.id === block.id);
          if (idx >= 0) {
            const updated = [...prev];
            updated[idx] = block;
            return updated;
          }
          return [...prev, block];
        });
      },
      // 上下文切换通知: AI 判断应切换到不同分区/对话
      onContextSwitch: (data) => {
        setSwitchBanner({
          partitionId: data.partition_id,
          conversationId: data.conversation_id,
          domainName: data.domain_name || "",
          topicName: data.topic_name || "",
        });
      },
      onConnect: () => setWsConnected(true),
      onDisconnect: () => setWsConnected(false),
    });

    return () => {
      wsClient.destroy();
      wsRef.current = null;
    };
  }, []); // 只挂载/卸载一次 — WS 内部处理重连

  // ── 初始加载 ──
  useEffect(() => { loadPartitions(); }, [loadPartitions]);

  // ── 定期轮询消息 ──
  useEffect(() => { /* ... */ }, [activeConversationId, loadMessages]);

  // ── 校验分区是否存在 ──
  useEffect(() => { /* ... */ }, [urlInitialized, loadingPartitions, partitions, selectedPartitionId]);

  // ── 发送消息 ──
  const handleSend = useCallback(
    async (text: string, files?: { name: string; type: string; materialId?: string }[]) => {
      if (!text.trim() || isLoading) return;

      // 确保有目标对话
      let pId = selectedPartitionId;
      let cId = activeConversationId;

      if (!pId || !cId) {
        const chain = await createConversationChain(selectedPartitionId);
        if (!chain) {
          setMessages((prev) => [...prev, {
            id: "err-" + Date.now(), parent_id: "", children_ids: [],
            partition_id: "", conversation_id: "",
            content_blocks: [{ type: "text" as const, text: "❌ 无法创建对话，请检查后端连接" }],
            text_summary: "", role: "assistant" as const,
            timestamp: Date.now(), token_count: 0,
            is_deleted: false, is_archived: false, has_modified_version: false,
          }]);
          return;
        }
        pId = chain.partitionId;
        cId = chain.conversationId;
        setSelectedPartitionId(pId);
        setActiveConversationId(cId);
        setConvError(null);
        await loadPartitions();
      }

      // 构建用户消息
      const userMsgId = Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
      const userMsg: TreeNode = {
        id: userMsgId, parent_id: pId || "virtual_root",
        children_ids: [], partition_id: pId || "", conversation_id: cId || "",
        content_blocks: [
          { type: "text", text },
          ...(files?.map((f) => ({ type: f.type === "image" ? "image" as const : "file" as const, name: f.name })) || []),
        ] as TreeNode["content_blocks"],
        text_summary: text, role: "user", timestamp: Date.now(),
        token_count: 0, is_deleted: false, is_archived: false, has_modified_version: false,
      };

      // 助手占位消息（等待流式或 HTTP 回复）
      const asstId = Date.now().toString(36) + "a" + Math.random().toString(36).substr(2, 9);
      streamingMsgIdRef.current = asstId;
      streamBufferRef.current = "";
      streamingPartIdRef.current = pId;
      streamingConvIdRef.current = cId;

      setMessages((prev) => [...prev, userMsg, {
        id: asstId, parent_id: userMsgId, children_ids: [],
        partition_id: pId || "", conversation_id: cId || "",
        content_blocks: [{ type: "text" as const, text: "" }],
        text_summary: "", role: "assistant", timestamp: Date.now(),
        token_count: 0, is_deleted: false, is_archived: false, has_modified_version: false,
      }]);
      setIsLoading(true);
      setStatusMessage("正在思考...");

      // 优先 WebSocket，失败则降级到 HTTP
      const sent = wsRef.current?.send({
        text, partition_id: pId, conversation_id: cId,
      });
      if (!sent) {
        setStatusMessage("WebSocket 未连接，尝试 HTTP...");
        try {
          const data = await apiFetch<any>(`/tree/conversation/${cId}/message`, {
            method: "POST",
            body: JSON.stringify({ text, partition_id: pId }),
          });
          const replyText = data.assistant_message?.text_summary ||
            data.assistant_message?.content_blocks?.find((b: { type: string }) => b.type === "text")?.text ||
            "（回复获取成功但没有显示内容）";
          streamingMsgIdRef.current = null;
          streamBufferRef.current = "";
          streamingPartIdRef.current = null;
          streamingConvIdRef.current = null;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === asstId
                ? { ...m, content_blocks: [{ type: "text" as const, text: replyText }], text_summary: replyText }
                : m
            )
          );
          setIsLoading(false);
          setStatusMessage("");
          setTimeout(() => loadPartitionsRef.current(), 300);
        } catch (httpErr: any) {
          const errMsg = `无法连接服务器：${httpErr?.message || "未知错误"}`;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === asstId
                ? {
                  ...m, id: "err-" + Date.now(),
                  content_blocks: [{ type: "text" as const, text: `❌ ${errMsg}` }],
                  text_summary: errMsg,
                }
                : m
            )
          );
          streamingMsgIdRef.current = null;
          streamBufferRef.current = "";
          streamingPartIdRef.current = null;
          streamingConvIdRef.current = null;
          setIsLoading(false);
          setStatusMessage("");
        }
      }
    }, [isLoading, selectedPartitionId, activeConversationId, loadPartitions]);

  // ── 选中对话 ──
  const handleSelectConversation = useCallback(
    (partitionId: string, conversationId: string) => {
      setSelectedPartitionId(partitionId || null);
      setActiveConversationId(conversationId || null);
      setConvError(null);
      setShowPartitionSidebar(false);
      setSwitchBanner(null);
    }, [],
  );

  // ── 上下文切换 ──
  const handleSwitchConfirm = useCallback(async () => {
    if (switchBanner) {
      await loadPartitions();
      setSelectedPartitionId(switchBanner.partitionId);
      setActiveConversationId(switchBanner.conversationId);
      setConvError(null);
      setSwitchBanner(null);
    }
  }, [switchBanner, loadPartitions]);

  const handleSwitchDismiss = useCallback(() => setSwitchBanner(null), []);

  // ── 删除消息 ──
  const handleDeleteMessage = useCallback(async (messageId: string) => {
    try {
      await apiFetch(`/tree/message/${messageId}`, { method: "DELETE" });
      setMessages(prev => prev.filter(m => m.id !== messageId));
      setResponseBlocks(prev => prev.filter(b => b.message_id !== messageId));
    } catch (e) { console.error("删除消息失败:", e); }
  }, []);

  // ── 编辑消息 ──
  const handleEditMessage = useCallback(async (messageId: string, newText: string): Promise<number> => {
    const data = await apiFetch<{ node: TreeNode; version_count: number }>(`/tree/message/${messageId}`, {
      method: "PUT",
      body: JSON.stringify({
        content_blocks: [{ type: "text", text: newText }],
        text_summary: newText,
      }),
    });
    return data.version_count || 0;
  }, []);

  // ── 版本切换（< > 按钮）──
  const handleVersionSwitch = useCallback(async (messageId: string, direction: "prev" | "next") => {
    try {
      const data = await apiFetch<{ versions: string[] }>(`/tree/message/${messageId}`);
      const versions: string[] = data.versions || [];
      if (versions.length <= 1) return { index: 1, total: 1 };

      const curIdx = versions.indexOf(messageId);
      if (curIdx === -1) return null;

      const newIdx = direction === "prev"
        ? (curIdx - 1 + versions.length) % versions.length
        : (curIdx + 1) % versions.length;

      const targetId = versions[newIdx];
      const targetRes = await apiFetch<{ message: TreeNode }>(`/tree/message/${targetId}`);
      const targetMsg = targetRes.message;
      if (!targetMsg) return null;

      const targetText = (targetMsg.content_blocks || [])
        .filter((b: any) => b.type === "text")
        .map((b: any) => b.text || "")
        .join("\n\n");

      setMessages(prev =>
        prev.map(m =>
          m.id === messageId
            ? { ...targetMsg, id: messageId, content_blocks: [{ type: "text" as const, text: targetText || "(空)" }], text_summary: targetText }
            : m
        )
      );
      return { index: newIdx + 1, total: versions.length };
    } catch (e) {
      console.error("版本切换失败:", e);
      return null;
    }
  }, []);

  // ── 分区 CRUD (归一化) ──
  const handleCreatePartition = useCallback(async (name: string, emoji: string) => {
    try {
      const res = await apiFetch<{ partition: Partition; conversation_id?: string }>("/tree/partition", {
        method: "POST",
        body: JSON.stringify({ name, emoji }),
      });
      // 创建成功后跳转到默认对话
      if (res.conversation_id) {
        handleSelectConversation(res.partition.id, res.conversation_id);
      }
      await loadPartitions();
    } catch (e) { console.error("创建分区失败:", e); }
  }, [loadPartitions, handleSelectConversation]);

  const handleRenamePartition = useCallback(async (id: string, name: string) => {
    try {
      await apiFetch(`/tree/partition/${id}`, { method: "PATCH", body: JSON.stringify({ name }) });
      await loadPartitions();
    } catch (e) { console.error(e); }
  }, [loadPartitions]);

  // ── 新建对话 ──
  const handleNewConversation = useCallback(async (level: string, parentId: string) => {
    try {
      let pId = selectedPartitionId;
      if (level === "default") {
        if (!pId) {
          if (partitions.length > 0) pId = partitions[0].id;
          else {
            const pData = await apiFetch<{ partition: Partition; conversation_id?: string }>("/tree/partition", {
              method: "POST",
              body: JSON.stringify({ name: "默认分区", emoji: "💬" }),
            });
            pId = pData.partition.id;
            if (pData.conversation_id) {
              handleSelectConversation(pId, pData.conversation_id);
            }
            await loadPartitions();
            return;
          }
          setSelectedPartitionId(pId);
        }
        return handleNewConversation("partition", pId);
      }

      const chain = await createConversationChain(level === "partition" ? parentId : pId);
      if (!chain) return;

      handleSelectConversation(chain.partitionId, chain.conversationId);
      await loadPartitions();
      setShowPartitionSidebar(false);
    } catch (e) {
      console.error("新建对话失败:", e);
    }
  }, [selectedPartitionId, partitions, loadPartitions, handleSelectConversation]);

  const activePartition = partitions.find((p) => p.id === selectedPartitionId);

  return {
    partitions, selectedPartitionId, activeConversationId,
    messages, responseBlocks, isLoading, statusMessage,
    switchBanner, showPartitionSidebar, sidebarCollapsed,
    showNewPartition, loadingPartitions, loadingMessages,
    convError, isDesktop, activePartition, wsConnected,
    handleSelectConversation, handleNewConversation, handleSend,
    handleDeleteMessage, handleEditMessage, handleVersionSwitch,
    handleCreatePartition, handleRenamePartition,
    handleSwitchConfirm, handleSwitchDismiss,
    setShowPartitionSidebar, setShowNewPartition, setSidebarCollapsed,
    loadPartitions,
  };
} 