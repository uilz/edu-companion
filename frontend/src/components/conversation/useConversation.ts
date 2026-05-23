"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import type { Partition, TreeNode, ResponseBlock, WSIncomingMessage } from "@/types";

// ─────────────────────────────────────────────
//  Media query helper
// ─────────────────────────────────────────────
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

// ─────────────────────────────────────────────
//  API helper
// ─────────────────────────────────────────────
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

// ─────────────────────────────────────────────
//  WebSocket manager — class-based, not module-level singleton
// ─────────────────────────────────────────────
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
            case "token":
              this.callbacks?.onToken(data.content, data.block_id);
              break;
            case "tool_block":
            case "block_update":
              this.callbacks?.onBlockUpdate(data.block);
              break;
            case "done":
              this.callbacks?.onDone(data.partition_id, data.assistant_message, data.response_blocks);
              break;
            case "error":
              this.callbacks?.onError(data.message);
              break;
            case "context_switch":
              this.callbacks?.onContextSwitch(data);
              break;
            // user_message, pong, status — no-op
          }
        } catch { /* ignore parse errors */ }
      };
      this.ws.onerror = () => {}; // onclose handles retry
      this.ws.onclose = () => {
        if (this.destroyed) return;
        this.callbacks?.onDisconnect?.();
        this.ws = null;
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

  send(data: Record<string, unknown>): boolean {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
      return true;
    }
    return false;
  }

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

// ─────────────────────────────────────────────
//  Hook return type
// ─────────────────────────────────────────────
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

// ─────────────────────────────────────────────
//  createConversationChain — single source of truth
//  For a given partition (or auto-create one), ensure domain→topic→conversation exist.
// ─────────────────────────────────────────────
async function createConversationChain(
  partitionId?: string | null,
): Promise<{ partitionId: string; conversationId: string } | null> {
  try {
    let pId = partitionId || undefined;
    if (!pId) {
      // Check if any partition exists at all
      const pData = await apiFetch<{ partitions: Partition[] }>("/conversations/partitions");
      if (pData.partitions?.length > 0) {
        pId = pData.partitions[0].id;
      } else {
        // Create default partition
        const newP = await apiFetch<{ partition: Partition }>("/conversations/partitions", {
          method: "POST",
          body: JSON.stringify({ name: "默认分区", subject: "默认", emoji: "💬" }),
        });
        pId = newP.partition.id;
      }
    }

    // Find or create domain → topic under pId
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

    // Find or create topic under domainId
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

    // Create conversation
    const convData = await apiFetch<{ conversation: { id: string } }>("/conversations/conversations", {
      method: "POST",
      body: JSON.stringify({ topic_id: topicId, name: "" }),
    });
    return { partitionId: pId, conversationId: convData.conversation.id };
  } catch (e) {
    console.error("[createConversationChain] failed:", e);
    return null;
  }
}

// ─────────────────────────────────────────────
//  useConversation hook
// ─────────────────────────────────────────────
export function useConversation(): UseConversationReturn {
  const isDesktop = useMediaQuery("(min-width: 768px)");
  const router = useRouter();

  // ── State ──
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

  // ── Refs (no stale closure issues) ──
  const wsRef = useRef<ConversationWS | null>(null);
  const activeConvIdRef = useRef<string | null>(null);
  const activePartIdRef = useRef<string | null>(null);
  const streamingPartIdRef = useRef<string | null>(null);
  const streamingConvIdRef = useRef<string | null>(null);
  const streamingMsgIdRef = useRef<string | null>(null);
  const streamBufferRef = useRef("");
  const loadPartitionsRef = useRef<() => Promise<void>>(() => Promise.resolve());

  // ── panel=graph redirect ──
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      if (params.get("panel") === "graph") {
        const pId = params.get("p") || params.get("partition_id");
        router.replace(pId ? `/dashboard?tab=graph&partition_id=${pId}` : "/dashboard?tab=graph");
      }
    } catch {}
  }, [router]);

  // ── URL / localStorage restore ──
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const pId = params.get("p") || params.get("partition_id");
      const cId = params.get("c") || params.get("conversation_id");
      if (pId) {
        setSelectedPartitionId(pId);
        if (cId) setActiveConversationId(cId);
      } else {
        const saved = localStorage.getItem("learn-page-state");
        if (saved) {
          const { partitionId, conversationId } = JSON.parse(saved);
          if (partitionId) setSelectedPartitionId(partitionId);
          if (conversationId) setActiveConversationId(conversationId);
        }
      }
    } catch {}
    setUrlInitialized(true);
  }, []);

  // Sync state → URL + localStorage
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

  // Keep refs in sync with state
  useEffect(() => { activeConvIdRef.current = activeConversationId; }, [activeConversationId]);
  useEffect(() => { activePartIdRef.current = selectedPartitionId; }, [selectedPartitionId]);

  // Lock body scroll
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, []);

  // ── Load partitions ──
  const loadPartitions = useCallback(async () => {
    try {
      setLoadingPartitions(true);
      const data = await apiFetch<{ partitions: Partition[] }>("/conversations/partitions");
      setPartitions(data.partitions || []);
    } catch (e) {
      console.error("Failed to load partitions:", e);
    } finally {
      setLoadingPartitions(false);
    }
  }, []);

  loadPartitionsRef.current = loadPartitions; // keep ref fresh for WS callbacks

  // ── Load messages (single batch: messages + blocks) ──
  const loadMessages = useCallback(async (conversationId: string) => {
    streamingMsgIdRef.current = null;
    streamBufferRef.current = "";
    streamingPartIdRef.current = null;
    streamingConvIdRef.current = null;
    try {
      setLoadingMessages(true);
      setConvError(null);
      // Load both messages and blocks in parallel
      const [msgData, allBlocks] = await Promise.all([
        apiFetch<{ messages: TreeNode[] }>(
          `/conversations/conversations/${conversationId}/messages?limit=50&offset=0`
        ),
        // Fetch blocks for all assistant messages in a single call
        apiFetch<{ blocks: ResponseBlock[] }>(
          `/conversations/conversations/${conversationId}/blocks?limit=100`
        ).catch(() => ({ blocks: [] as ResponseBlock[] })),
      ]);
      setMessages(msgData.messages || []);
      setResponseBlocks(allBlocks.blocks || []);
    } catch (e: any) {
      console.error("Failed to load messages:", e);
      const errMsg = e?.message || "";
      if (errMsg.includes("404")) {
        setConvError("该对话已被删除");
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
  }, []);

  // ── Load messages when conversation selected ──
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

  // ── WebSocket ──
  useEffect(() => {
    const wsClient = new ConversationWS();
    wsRef.current = wsClient;
    wsClient.connect({
      onToken: (content) => {
        if (!streamingMsgIdRef.current) return;
        // Check if this streaming context is still current (use refs, not closure state)
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

        // If user switched conversations during streaming, discard the stale message
        if (streamPid !== activePartIdRef.current || streamCid !== activeConvIdRef.current) {
          if (streamMsgId) {
            setMessages((prev) => prev.filter((m) => m.id !== streamMsgId));
          }
          return;
        }

        // Replace placeholder with final message
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

        // Add response blocks from done message
        if (responseBlocks?.length) {
          setResponseBlocks((prev) => {
            const existing = new Set(prev.map((b) => b.id));
            const newBlocks = responseBlocks.filter((b) => !existing.has(b.id));
            return newBlocks.length ? [...prev, ...newBlocks] : prev;
          });
        }

        // Refresh sidebar + messages after a short delay
        setTimeout(() => loadPartitionsRef.current(), 300);
        setTimeout(() => {
          const cid = activeConvIdRef.current;
          if (cid && cid === streamCid) loadMessages(cid);
        }, 500);
      },
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
  }, []); // Only mount/unmount once — WS reconnection handled internally

  // ── Initial load ──
  useEffect(() => { loadPartitions(); }, [loadPartitions]);

  // ── Periodic polling ──
  useEffect(() => {
    if (!activeConversationId) return;
    const interval = setInterval(() => {
      loadMessages(activeConversationId);
    }, 30000);
    return () => clearInterval(interval);
  }, [activeConversationId, loadMessages]);

  // ── Validate URL partition ──
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

  // ── Handle send ──
  const handleSend = useCallback(
    async (text: string, files?: { name: string; type: string; materialId?: string }[]) => {
      if (!text.trim() || isLoading) return;

      // Ensure we have a conversation to send to
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

      // Build user message
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

      // Assistant placeholder
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

      // Try WebSocket first, fallback to HTTP
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

  // ── Handle conversation selection ──
  const handleSelectConversation = useCallback(
    (partitionId: string, conversationId: string) => {
      setSelectedPartitionId(partitionId || null);
      setActiveConversationId(conversationId || null);
      setConvError(null);
      setShowPartitionSidebar(false);
      setSwitchBanner(null);
    }, [],
  );

  // ── Handle switch banner ──
  const handleSwitchConfirm = useCallback(async () => {
    if (switchBanner) {
      // Refresh partitions first so the sidebar has the target partition
      await loadPartitions();
      setSelectedPartitionId(switchBanner.partitionId);
      setActiveConversationId(switchBanner.conversationId);
      setConvError(null);
      setSwitchBanner(null);
    }
  }, [switchBanner, loadPartitions]);

  const handleSwitchDismiss = useCallback(() => {
    setSwitchBanner(null);
  }, []);

  // ── Handle delete message ──
  const handleDeleteMessage = useCallback(async (messageId: string) => {
    try {
      await fetch("/api/conversations/messages/" + messageId, { method: "DELETE" });
      setMessages((prev) => prev.filter((m) => m.id !== messageId));
      setResponseBlocks((prev) => prev.filter((b) => b.message_id !== messageId));
    } catch (e) { console.error("Delete failed:", e); }
  }, []);

  // ── Handle edit message ──
  const handleEditMessage = useCallback(async (messageId: string, newText: string) => {
    const res = await fetch("/api/conversations/messages/" + messageId, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content_blocks: [{ type: "text", text: newText }],
        text_summary: newText,
      }),
    });
    if (!res.ok) throw new Error(`Edit failed ${res.status}: ${await res.text().catch(() => "")}`);
    const data = await res.json();
    return data.version_count || 0;
  }, []);

  // ── Handle version switch ──
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
      console.error("Version switch failed:", e);
      return null;
    }
  }, []);

  // ── Partition CRUD ──
  const handleCreatePartition = useCallback(async (name: string, emoji: string) => {
    try {
      await apiFetch("/conversations/partitions", {
        method: "POST",
        body: JSON.stringify({ name, subject: name, emoji }),
      });
      await loadPartitions();
    } catch (e) { console.error("Failed to create partition:", e); }
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

  // ── Handle new conversation ──
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

      // For partition/domain/topic level: create chain and return the conversation
      const chain = await createConversationChain(level === "partition" ? parentId : pId);
      if (!chain) return;

      if (level === "partition") setSelectedPartitionId(parentId);
      setActiveConversationId(chain.conversationId);
      setConvError(null);
      await loadPartitions();
      setShowPartitionSidebar(false);
    } catch (e) {
      console.error("New conversation failed:", e);
    }
  }, [selectedPartitionId, partitions, loadPartitions]);

  // ── Active partition for header ──
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
