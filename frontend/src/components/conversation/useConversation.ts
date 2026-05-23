"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import type { Partition, TreeNode, ResponseBlock, WSIncomingMessage } from "@/types";

// ══════════════════════════════════════════════════════════════
//  工具函数: 响应式断点检测
// ══════════════════════════════════════════════════════════════
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

// ══════════════════════════════════════════════════════════════
//  API 请求封装: 统一处理错误状态码
// ══════════════════════════════════════════════════════════════
async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

// ══════════════════════════════════════════════════════════════
//  WebSocket 管理器: 单连接 + 指数退避重连
// ══════════════════════════════════════════════════════════════
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
      this.ws.onerror = () => {}; // onclose 处理重连
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
//  Hook 返回值类型定义
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
  handleDeletePartition: (id: string) => Promise<void>;
  handleSwitchConfirm: () => void;
  handleSwitchDismiss: () => void;
  setShowPartitionSidebar: (v: boolean) => void;
  setShowNewPartition: (v: boolean) => void;
  setSidebarCollapsed: (v: boolean) => void;
  loadPartitions: () => Promise<void>;
}

// ══════════════════════════════════════════════════════════════
//  创建对话链: 确保 partition → domain → topic → conversation 存在
//  如果分区/领域/专题不存在则自动创建
// ══════════════════════════════════════════════════════════════
async function createConversationChain(
  partitionId?: string | null,
): Promise<{ partitionId: string; conversationId: string } | null> {
  try {
    let pId = partitionId || undefined;
    if (!pId) {
      // 如果没有分区，检查是否有现存分区
      const pData = await apiFetch<{ partitions: Partition[] }>("/conversations/partitions");
      if (pData.partitions?.length > 0) {
        pId = pData.partitions[0].id;
      } else {
        // 一个分区都没有 → 创建默认分区
        const newP = await apiFetch<{ partition: Partition }>("/conversations/partitions", {
          method: "POST",
          body: JSON.stringify({ name: "默认分区", subject: "默认", emoji: "💬" }),
        });
        pId = newP.partition.id;
      }
    }

    // 找或创建领域 domain
    const domainData = await apiFetch<{ domains: { id: string }[] }>(`/conversations/partitions/${pId}/domains`);
    let domainId: string;
    if (domainData.domains?.length > 0) {
      domainId = domainData.domains[0].id;
    } else {
      const newD = await apiFetch<{ domain: { id: string } }>("/conversations/domains", {
        method: "POST",
        body: JSON.stringify({ partition_id: pId, name: "默认领域", emoji: "📚" }),
      });
      domainId = newD.domain.id;
    }

    // 找或创建专题 topic
    const topicData = await apiFetch<{ topics: { id: string }[] }>(`/conversations/domains/${domainId}/topics`);
    let topicId: string;
    if (topicData.topics?.length > 0) {
      topicId = topicData.topics[0].id;
    } else {
      const newT = await apiFetch<{ topic: { id: string } }>("/conversations/topics", {
        method: "POST",
        body: JSON.stringify({ domain_id: domainId, name: "默认专题", emoji: "📝" }),
      });
      topicId = newT.topic.id;
    }

    // 创建对话
    const convData = await apiFetch<{ conversation: { id: string } }>("/conversations/conversations", {
      method: "POST",
      body: JSON.stringify({ topic_id: topicId, name: "" }),
    });
    return { partitionId: pId, conversationId: convData.conversation.id };
  } catch (e) {
    console.error("[createConversationChain] 创建对话链失败:", e);
    return null;
  }
}

// ══════════════════════════════════════════════════════════════
//  useConversation — 对话系统核心 Hook
//  管理: 分区列表、当前对话、消息、WebSocket、URL同步
// ══════════════════════════════════════════════════════════════
export function useConversation(): UseConversationReturn {
  const isDesktop = useMediaQuery("(min-width: 768px)");
  const router = useRouter();

  // ── 状态 ──
  const [partitions, setPartitions] = useState<Partition[]>([]);               // 全部分区
  const [selectedPartitionId, setSelectedPartitionId] = useState<string | null>(null); // 当前选中分区
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null); // 当前对话 ID
  const [messages, setMessages] = useState<TreeNode[]>([]);                    // 当前消息列表
  const [responseBlocks, setResponseBlocks] = useState<ResponseBlock[]>([]);   // 回复块（视频/练习等）
  const [isLoading, setIsLoading] = useState(false);                           // 是否正在等待 AI 回复
  const [statusMessage, setStatusMessage] = useState("");                      // 状态提示文字
  const [switchBanner, setSwitchBanner] = useState<{                          // 上下文切换横幅
    partitionId: string; conversationId: string;
    domainName: string; topicName: string;
  } | null>(null);
  const [showPartitionSidebar, setShowPartitionSidebar] = useState(false);     // 移动端侧栏显示
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);             // 桌面端侧栏折叠
  const [showNewPartition, setShowNewPartition] = useState(false);             // 新建分区弹窗
  const [loadingPartitions, setLoadingPartitions] = useState(true);            // 分区加载中
  const [loadingMessages, setLoadingMessages] = useState(false);               // 消息加载中
  const [convError, setConvError] = useState<string | null>(null);            // 对话加载错误
  const [wsConnected, setWsConnected] = useState(false);                      // WebSocket 连接状态
  const [urlInitialized, setUrlInitialized] = useState(false);                 // URL 初始化完成

  // ── Refs（避免闭包过期问题）──
  const wsRef = useRef<ConversationWS | null>(null);
  const activeConvIdRef = useRef<string | null>(null);
  const activePartIdRef = useRef<string | null>(null);
  const streamingPartIdRef = useRef<string | null>(null);   // 正在流式的分区 ID
  const streamingConvIdRef = useRef<string | null>(null);   // 正在流式的对话 ID
  const streamingMsgIdRef = useRef<string | null>(null);    // 正在流式的消息 ID（占位符）
  const streamBufferRef = useRef("");                        // 流式内容缓冲区
  const loadPartitionsRef = useRef<() => Promise<void>>(() => Promise.resolve());

  // ── panel=graph 重定向 ──
  // 如果 URL 有 ?panel=graph，跳转到仪表盘知识图谱页
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      if (params.get("panel") === "graph") {
        const pId = params.get("p") || params.get("partition_id");
        router.replace(pId ? `/dashboard?tab=graph&partition_id=${pId}` : "/dashboard?tab=graph");
      }
    } catch {}
  }, [router]);

  // ── 从 URL 参数 / localStorage 恢复状态 ──
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const pId = params.get("p") || params.get("partition_id");
      const cId = params.get("c") || params.get("conversation_id");
      if (pId) {
        setSelectedPartitionId(pId);
        if (cId) setActiveConversationId(cId);
      } else {
        // URL 无参数时从 localStorage 恢复
        const saved = localStorage.getItem("learn-page-state");
        if (saved) {
          const { partitionId, conversationId } = JSON.parse(saved);
          if (partitionId) setSelectedPartitionId(partitionId);
          if (conversationId) setActiveConversationId(conversationId);
        }
      }
    } catch {}
    setUrlInitialized(true); // 标记 URL 初始化完成，之后的状态变化才同步回 URL
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
    } catch {}
  }, [selectedPartitionId, activeConversationId, urlInitialized]);

  // ── ref 与 state 同步 ──
  useEffect(() => { activeConvIdRef.current = activeConversationId; }, [activeConversationId]);
  useEffect(() => { activePartIdRef.current = selectedPartitionId; }, [selectedPartitionId]);

  // ── 锁定 body 滚动（页面内滚动由独立区域处理）──
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, []);

  // ── 加载分区列表 ──
  const loadPartitions = useCallback(async () => {
    try {
      setLoadingPartitions(true);
      const data = await apiFetch<{ partitions: Partition[] }>("/conversations/partitions");
      setPartitions(data.partitions || []);
    } catch (e) {
      console.error("加载分区列表失败:", e);
    } finally {
      setLoadingPartitions(false);
    }
  }, []);

  loadPartitionsRef.current = loadPartitions; // 供 WS 回调使用（避免闭包过期）

  // ── 加载消息（一次性加载消息 + 回复块）──
  const loadMessages = useCallback(async (conversationId: string) => {
    // 清除流式状态
    streamingMsgIdRef.current = null;
    streamBufferRef.current = "";
    streamingPartIdRef.current = null;
    streamingConvIdRef.current = null;
    try {
      setLoadingMessages(true);
      setConvError(null);
      // 并行加载: 消息列表 + 回复块
      const [msgData, allBlocks] = await Promise.all([
        apiFetch<{ messages: TreeNode[] }>(
          `/conversations/conversations/${conversationId}/messages?limit=50&offset=0`
        ),
        apiFetch<{ blocks: ResponseBlock[] }>(
          `/conversations/conversations/${conversationId}/blocks?limit=100`
        ).catch(() => ({ blocks: [] as ResponseBlock[] })), // 块加载失败不阻塞
      ]);
      setMessages(msgData.messages || []);
      setResponseBlocks(allBlocks.blocks || []);
    } catch (e: any) {
      console.error("加载消息失败:", e);
      const errMsg = e?.message || "";
      if (errMsg.includes("404")) {
        setConvError("该对话已被删除");
        // 对话已删除 → 清除死引用，避免 URL/localStorage 残留
        setActiveConversationId(null);
        try {
          const params = new URLSearchParams(window.location.search);
          params.delete("c");
          window.history.replaceState(null, "", params.toString() ? `${window.location.pathname}?${params.toString()}` : window.location.pathname);
          localStorage.removeItem("learn-page-state");
        } catch {}
      } else if (errMsg.includes("403") || errMsg.includes("401")) {
        setConvError("无权访问该对话");
      } else {
        setConvError("加载失败: " + errMsg.slice(0, 80));
      }
      setMessages([]);
      setResponseBlocks([]);
    } finally {
      setLoadingMessages(false);
    }
  }, [setActiveConversationId]);

  // ── 选中对话时自动加载消息 ──
  useEffect(() => {
    if (!urlInitialized) return;
    if (activeConversationId) {
      setConvError(null);
      loadMessages(activeConversationId);
    } else {
      setMessages([]);
      setResponseBlocks([]);
      setConvError(null);
    }
  }, [activeConversationId, loadMessages, urlInitialized]);

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

  // ── 定期轮询消息（30s）──
  useEffect(() => {
    if (!activeConversationId) return;
    const interval = setInterval(() => {
      loadMessages(activeConversationId);
    }, 30000);
    return () => clearInterval(interval);
  }, [activeConversationId, loadMessages]);

  // ── 校验 URL 中的分区是否存在（防止死引用）──
  const validatedRef = useRef(false);
  useEffect(() => {
    if (!urlInitialized || loadingPartitions) return;
    if (validatedRef.current) return;
    if (selectedPartitionId && partitions.length > 0 &&
        !partitions.some((p) => p.id === selectedPartitionId)) {
      validatedRef.current = true;
      setSelectedPartitionId(null);
      setActiveConversationId(null);
      window.history.replaceState(null, "", "/learn");
      return;
    }
    validatedRef.current = true;
  }, [urlInitialized, loadingPartitions, partitions, selectedPartitionId]);

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
          const res = await fetch("/api/conversations/message", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text, partition_id: pId, conversation_id: cId }),
          });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const data = await res.json();
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
        } catch (httpErr) {
          const errMsg = `无法连接服务器：${httpErr instanceof Error ? httpErr.message : "未知错误"}`;
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
    },
    [isLoading, selectedPartitionId, activeConversationId, loadPartitions],
  );

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

  // ── 确认上下文切换 ──
  const handleSwitchConfirm = useCallback(async () => {
    if (switchBanner) {
      await loadPartitions();
      setSelectedPartitionId(switchBanner.partitionId);
      setActiveConversationId(switchBanner.conversationId);
      setConvError(null);
      setSwitchBanner(null);
    }
  }, [switchBanner, loadPartitions]);

  // ── 忽略上下文切换 ──
  const handleSwitchDismiss = useCallback(() => {
    setSwitchBanner(null);
  }, []);

  // ── 删除消息 ──
  const handleDeleteMessage = useCallback(async (messageId: string) => {
    try {
      await fetch("/api/conversations/messages/" + messageId, { method: "DELETE" });
      setMessages((prev) => prev.filter((m) => m.id !== messageId));
      setResponseBlocks((prev) => prev.filter((b) => b.message_id !== messageId));
    } catch (e) { console.error("删除消息失败:", e); }
  }, []);

  // ── 编辑消息 ──
  const handleEditMessage = useCallback(async (messageId: string, newText: string) => {
    const res = await fetch("/api/conversations/messages/" + messageId, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content_blocks: [{ type: "text", text: newText }],
        text_summary: newText,
      }),
    });
    if (!res.ok) throw new Error(`编辑失败 ${res.status}: ${await res.text().catch(() => "")}`);
    const data = await res.json();
    return data.version_count || 0;
  }, []);

  // ── 版本切换（< > 按钮）──
  const handleVersionSwitch = useCallback(async (messageId: string, direction: "prev" | "next") => {
    try {
      const msgRes = await fetch(`/api/conversations/messages/${messageId}`);
      if (!msgRes.ok) return null;
      const msgData = await msgRes.json();
      const versions: string[] = msgData.versions || [];
      if (versions.length <= 1) return { index: 1, total: 1 };
      const curIdx = versions.indexOf(messageId);
      if (curIdx === -1) return null;
      const newIdx = direction === "prev"
        ? (curIdx - 1 + versions.length) % versions.length
        : (curIdx + 1) % versions.length;
      const targetId = versions[newIdx];
      const targetRes = await fetch(`/api/conversations/messages/${targetId}`);
      if (!targetRes.ok) return null;
      const targetData = await targetRes.json();
      const targetMsg = targetData.message;
      if (!targetMsg) return null;
      const targetText = (targetMsg.content_blocks || [])
        .filter((b: any) => b.type === "text")
        .map((b: any) => b.text || "")
        .join("\n\n");
      setMessages((prev) =>
        prev.map((m) =>
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

  // ── 分区 CRUD ──
  const handleCreatePartition = useCallback(async (name: string, emoji: string) => {
    try {
      await apiFetch("/conversations/partitions", {
        method: "POST",
        body: JSON.stringify({ name, subject: name, emoji }),
      });
      await loadPartitions();
    } catch (e) { console.error("创建分区失败:", e); }
  }, [loadPartitions]);

  const handleRenamePartition = useCallback(async (id: string, name: string) => {
    try {
      await apiFetch(`/conversations/partitions/${id}`, { method: "PATCH", body: JSON.stringify({ name }) });
      await loadPartitions();
    } catch (e) { console.error(e); }
  }, [loadPartitions]);

  const handleDeletePartition = useCallback(async (id: string) => {
    try {
      await apiFetch(`/conversations/partitions/${id}`, { method: "DELETE" });
      if (id === selectedPartitionId) {
        setSelectedPartitionId(null);
        setActiveConversationId(null);
        setConvError(null);
        setMessages([]);
        setResponseBlocks([]);
      }
      await loadPartitions();
    } catch (e) { console.error(e); }
  }, [selectedPartitionId, loadPartitions]);

  // ── 新建对话 ──
  const handleNewConversation = useCallback(async (level: string, parentId: string) => {
    try {
      let pId = selectedPartitionId;
      if (level === "default") {
        if (!pId) {
          if (partitions.length > 0) {
            pId = partitions[0].id;
          } else {
            const pData = await apiFetch<{ partition: Partition }>("/conversations/partitions", {
              method: "POST",
              body: JSON.stringify({ name: "默认分区", subject: "默认", emoji: "💬" }),
            });
            pId = pData.partition.id;
            await loadPartitions();
          }
          setSelectedPartitionId(pId);
        }
        return handleNewConversation("partition", pId);
      }

      const chain = await createConversationChain(level === "partition" ? parentId : pId);
      if (!chain) return;

      if (level === "partition") setSelectedPartitionId(parentId);
      setActiveConversationId(chain.conversationId);
      setConvError(null);
      await loadPartitions();
      setShowPartitionSidebar(false);
    } catch (e) {
      console.error("新建对话失败:", e);
    }
  }, [selectedPartitionId, partitions, loadPartitions]);

  // ── 当前活跃分区（用于标头显示）──
  const activePartition = partitions.find((p) => p.id === selectedPartitionId);

  return {
    partitions, selectedPartitionId, activeConversationId,
    messages, responseBlocks, isLoading, statusMessage,
    switchBanner, showPartitionSidebar, sidebarCollapsed,
    showNewPartition, loadingPartitions, loadingMessages,
    convError, isDesktop, activePartition, wsConnected,
    handleSelectConversation, handleNewConversation, handleSend,
    handleDeleteMessage, handleEditMessage, handleVersionSwitch,
    handleCreatePartition, handleRenamePartition, handleDeletePartition,
    handleSwitchConfirm, handleSwitchDismiss,
    setShowPartitionSidebar, setShowNewPartition, setSidebarCollapsed,
    loadPartitions,
  };
}
