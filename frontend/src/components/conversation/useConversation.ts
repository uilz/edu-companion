"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import type {
  Partition,
  TreeNode,
  ResponseBlock,
  WSIncomingMessage,
} from "@/types";

// ── Media query hook ──
function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const media = window.matchMedia(query);
    setMatches(media.matches);
    const listener = (e: MediaQueryListEvent) => setMatches(e.matches);
    media.addEventListener("change", listener);
    return () => media.removeEventListener("change", listener);
  }, [query]);
  return matches;
}

// ── API helpers ──
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

// ── WebSocket manager ──
type WSCallbacks = {
  onStatus: (msg: string) => void;
  onToken: (content: string, blockId?: string) => void;
  onDone: (partitionId: string, assistantMessage: TreeNode) => void;
  onError: (msg: string) => void;
  onBlockUpdate: (block: ResponseBlock) => void;
  onContextSwitch: (data: {
    partition_id: string;
    conversation_id: string;
    domain_name: string;
    topic_name: string;
    switch_detail: Record<string, string>;
  }) => void;
};

let ws: WebSocket | null = null;
let wsCallbacks: WSCallbacks | null = null;
let wsReconnectTimer: ReturnType<typeof setTimeout> | null = null;
let wsReconnectAttempts = 0;

function connectConversationWS(callbacks: WSCallbacks) {
  wsCallbacks = callbacks;

  if (ws && ws.readyState === WebSocket.OPEN) return;

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/api/conversations/ws`;

  try {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      wsReconnectAttempts = 0;
      console.log("[ConvWS] connected");
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data: WSIncomingMessage = JSON.parse(event.data);
        switch (data.type) {
          case "status":
            wsCallbacks?.onStatus(data.message);
            break;
          case "token":
            wsCallbacks?.onToken(data.content, data.block_id);
            break;
          case "tool_block":
            wsCallbacks?.onBlockUpdate(data.block);
            break;
          case "done":
            wsCallbacks?.onDone(data.partition_id, data.assistant_message);
            if (data.response_blocks) {
              for (const rb of data.response_blocks) {
                wsCallbacks?.onBlockUpdate(rb);
              }
            }
            break;
          case "error":
            wsCallbacks?.onError(data.message);
            break;
          case "block_update":
            wsCallbacks?.onBlockUpdate(data.block);
            break;
          case "context_switch":
            wsCallbacks?.onContextSwitch(data);
            break;
          case "user_message":
          case "pong":
            break;
        }
      } catch (e) {
        // ignore parse errors
      }
    };

    ws.onerror = () => {
      // Don't show error to user unless persistent — onclose handles reconnection
    };

    ws.onclose = () => {
      ws = null;
      // Exponential backoff reconnect
      const delay = Math.min(1000 * Math.pow(2, wsReconnectAttempts), 30000);
      wsReconnectAttempts++;
      wsReconnectTimer = setTimeout(() => {
        if (wsCallbacks) connectConversationWS(wsCallbacks);
      }, delay);
    };
  } catch (e) {
    // Connection failed, will retry via onclose path
    ws = null;
  }
}

function sendWSMessage(data: Record<string, unknown>): boolean {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
    return true;
  }
  return false;
}

function disconnectWS() {
  if (wsReconnectTimer) {
    clearTimeout(wsReconnectTimer);
    wsReconnectTimer = null;
  }
  if (ws) {
    ws.onclose = null; // prevent reconnect
    ws.close();
    ws = null;
  }
  wsCallbacks = null;
  wsReconnectAttempts = 0;
}

// ── Hook return type ──
export interface UseConversationReturn {
  // State
  partitions: Partition[];
  selectedPartitionId: string | null;
  activeConversationId: string | null;
  messages: TreeNode[];
  responseBlocks: ResponseBlock[];
  isLoading: boolean;
  statusMessage: string;
  switchBanner: {
    partitionId: string;
    conversationId: string;
    domainName: string;
    topicName: string;
  } | null;
  showPartitionSidebar: boolean;
  sidebarCollapsed: boolean;
  showNewPartition: boolean;
  loadingPartitions: boolean;
  isLoadingPartitions: boolean;
  loadingMessages: boolean;
  convError: string | null;
  isDesktop: boolean;
  activePartition: Partition | undefined;

  // Handlers
  handleSelectConversation: (partitionId: string, conversationId: string) => void;
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

export function useConversation(): UseConversationReturn {
  const isDesktop = useMediaQuery("(min-width: 768px)");

  // ── State ──
  const [partitions, setPartitions] = useState<Partition[]>([]);
  const [selectedPartitionId, setSelectedPartitionId] = useState<string | null>(null);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<TreeNode[]>([]);
  const [responseBlocks, setResponseBlocks] = useState<ResponseBlock[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");

  // Context switch banner
  const [switchBanner, setSwitchBanner] = useState<{
    partitionId: string;
    conversationId: string;
    domainName: string;
    topicName: string;
  } | null>(null);

  // Mobile sidebar state
  const [showPartitionSidebar, setShowPartitionSidebar] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [showNewPartition, setShowNewPartition] = useState(false);
  const [loadingPartitions, setLoadingPartitions] = useState(true);
  const [isLoadingPartitions, setIsLoadingPartitions] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [convError, setConvError] = useState<string | null>(null);

  const router = useRouter();

  // ── panel=graph → redirect ──
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      if (params.get("panel") === "graph") {
        const pId = params.get("p") || params.get("partition_id");
        router.replace(pId ? `/dashboard?tab=graph&partition_id=${pId}` : "/dashboard?tab=graph");
      }
    } catch {}
  }, [router]);

  // Stream buffer refs
  const streamBufferRef = useRef("");
  const streamingMsgIdRef = useRef<string | null>(null);
  const streamingContextRef = useRef<{ partitionId: string; conversationId: string } | null>(null);

  // ── URL / localStorage restore ──
  const [urlInitialized, setUrlInitialized] = useState(false);
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
      const newUrl = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
      window.history.replaceState(null, "", newUrl);

      localStorage.setItem("learn-page-state", JSON.stringify({
        partitionId: selectedPartitionId,
        conversationId: activeConversationId,
      }));
    } catch {}
  }, [selectedPartitionId, activeConversationId, urlInitialized]);

  // Lock body scroll
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, []);

  // ── Load partitions ──
  const loadPartitions = useCallback(async () => {
    try {
      setLoadingPartitions(true);
      setIsLoadingPartitions(true);
      const data = await apiFetch<{ partitions: Partition[] }>("/conversations/partitions");
      setPartitions(data.partitions || []);
    } catch (e) {
      console.error("Failed to load partitions:", e);
    } finally {
      setLoadingPartitions(false);
      setIsLoadingPartitions(false);
    }
  }, []);

  // ── Load messages for conversation ──
  const loadMessages = useCallback(async (conversationId: string) => {
    streamingMsgIdRef.current = null;
    streamBufferRef.current = "";
    streamingContextRef.current = null;
    try {
      setLoadingMessages(true);
      const data = await apiFetch<{ messages: TreeNode[] }>(
        `/conversations/conversations/${conversationId}/messages?limit=50&offset=0`
      );
      setMessages(data.messages || []);

      const assistantMsgs = (data.messages || []).filter((m) => m.role === "assistant");
      const allBlocks: ResponseBlock[] = [];
      for (const msg of assistantMsgs) {
        try {
          const blockData = await apiFetch<{ blocks: ResponseBlock[] }>(
            `/conversations/messages/${msg.id}/blocks`
          );
          allBlocks.push(...(blockData.blocks || []));
        } catch {}
      }
      setResponseBlocks(allBlocks);
    } catch (e: any) {
      console.error("Failed to load messages:", e);
      // If conversation was deleted (404), show error but keep convId
      const errMsg = e?.message || "";
      if (errMsg.includes("404")) {
        setConvError("该对话已被删除");
        setMessages([]);
        setResponseBlocks([]);
        // Do NOT clear activeConversationId - let the user see the error
      } else if (errMsg.includes("403") || errMsg.includes("401")) {
        setConvError("无权访问该对话");
        setMessages([]);
        setResponseBlocks([]);
      } else {
        setConvError("加载失败: " + errMsg.slice(0, 80));
      }
    } finally {
      setLoadingMessages(false);
    }
  }, []);

  // ── Load messages when conversation selected ──
  useEffect(() => {
    if (!urlInitialized || isLoadingPartitions) return;
    if (activeConversationId) {
      setConvError(null);
      loadMessages(activeConversationId);
    } else {
      setMessages([]);
      setResponseBlocks([]);
      setConvError(null);
    }
  }, [activeConversationId, loadMessages, urlInitialized, isLoadingPartitions]);

  // ── WebSocket callbacks ──
  useEffect(() => {
    connectConversationWS({
      onStatus: (msg) => setStatusMessage(msg),
      onToken: (content, _blockId) => {
        const ctx = streamingContextRef.current;
        if (!ctx || ctx.partitionId !== selectedPartitionId || ctx.conversationId !== activeConversationId) return;

        streamBufferRef.current += content;
        const buffer = streamBufferRef.current;
        const msgId = streamingMsgIdRef.current;

        if (msgId) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === msgId
                ? { ...m, content_blocks: [{ type: "text" as const, text: buffer }], text_summary: buffer }
                : m
            )
          );
        }
      },
      onDone: (_partitionId, assistantMessage) => {
        setIsLoading(false);
        setStatusMessage("");

        const ctx = streamingContextRef.current;
        streamingContextRef.current = null;
        if (ctx && (ctx.partitionId !== selectedPartitionId || ctx.conversationId !== activeConversationId)) {
          setMessages((prev) => prev.filter((m) => m.id !== streamingMsgIdRef.current));
          streamingMsgIdRef.current = null;
          streamBufferRef.current = "";
          return;
        }

        const currentStreamingId = streamingMsgIdRef.current;
        streamingMsgIdRef.current = null;
        streamBufferRef.current = "";

        if (assistantMessage) {
          const textBlock = assistantMessage.content_blocks?.find((b: { type: string }) => b.type === "text");
          const hasContent = textBlock?.text?.trim();

          setMessages((prev) => {
            const idx = prev.findIndex((m) => m.id === currentStreamingId || m.id === assistantMessage.id);
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
        } else if (currentStreamingId) {
          setMessages((prev) => prev.filter((m) => m.id !== currentStreamingId));
        }

        setTimeout(() => loadPartitions(), 300);
        // 流完成后从服务端刷新消息，确保数据一致
        setTimeout(() => {
          if (activeConversationId) loadMessages(activeConversationId);
        }, 500);
      },
      onError: (msg) => {
        setIsLoading(false);
        setStatusMessage("");
        // Don't add error node for transient WS errors during reconnection
        const errorNode: TreeNode = {
          id: "err-" + Date.now(),
          parent_id: selectedPartitionId || "",
          children_ids: [],
          partition_id: selectedPartitionId || "",
          conversation_id: activeConversationId || "",
          content_blocks: [{ type: "text" as const, text: `❌ ${msg}` }],
          text_summary: msg,
          role: "assistant",
          timestamp: Date.now(),
          token_count: 0,
          is_deleted: false,
          is_archived: false,
          has_modified_version: false,
        };
        if (streamingMsgIdRef.current) {
          setMessages((prev) => prev.map((m) => m.id === streamingMsgIdRef.current ? errorNode : m));
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
    });

    return () => disconnectWS();
  }, [activeConversationId, loadMessages, loadPartitions, selectedPartitionId]);

  // ── Initial load ──
  useEffect(() => { loadPartitions(); }, [loadPartitions]);

  // ── Periodic polling for real-time updates ──
  useEffect(() => {
    if (!activeConversationId) return;
    const interval = setInterval(() => {
      loadMessages(activeConversationId);
    }, 30000);
    return () => clearInterval(interval);
  }, [activeConversationId, loadMessages]);

  // ── Validate URL params ──
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

  // ── Auto-create conversation when sending without one ──
  const ensureConversation = useCallback(async (): Promise<{ partitionId: string; conversationId: string } | null> => {
    // If already have both, return them
    if (selectedPartitionId && activeConversationId) {
      return { partitionId: selectedPartitionId, conversationId: activeConversationId };
    }

    try {
      let pId = selectedPartitionId;

      // Auto-create partition if none selected
      if (!pId) {
        if (partitions.length > 0) {
          pId = partitions[0].id;
        } else {
          const data = await apiFetch<{ partition: Partition }>("/conversations/partitions", {
            method: "POST",
            body: JSON.stringify({ name: "默认分区", subject: "默认", emoji: "💬" }),
          });
          pId = data.partition.id;
          await loadPartitions();
        }
      }

      // Auto-create conversation — need a topic first, so create full chain if needed
      // Try to find or create: domain → topic → conversation
      let topicId = "";

      // Check if partition has any domains
      const domainsData = await apiFetch<{ domains: { id: string }[] }>(`/conversations/partitions/${pId}/domains`);
      const domains = domainsData.domains || [];

      if (domains.length > 0) {
        // Check first domain for topics
        const topicsData = await apiFetch<{ topics: { id: string }[] }>(`/conversations/domains/${domains[0].id}/topics`);
        if (topicsData.topics?.length > 0) {
          topicId = topicsData.topics[0].id;
        } else {
          const newTopic = await apiFetch<{ topic: { id: string } }>("/conversations/topics", {
            method: "POST",
            body: JSON.stringify({ domain_id: domains[0].id, name: "默认专题", emoji: "📝" }),
          });
          topicId = newTopic.topic.id;
        }
      } else {
        const newDomain = await apiFetch<{ domain: { id: string } }>("/conversations/domains", {
          method: "POST",
          body: JSON.stringify({ partition_id: pId, name: "默认领域", emoji: "📚" }),
        });
        const newTopic = await apiFetch<{ topic: { id: string } }>("/conversations/topics", {
          method: "POST",
          body: JSON.stringify({ domain_id: newDomain.domain.id, name: "默认专题", emoji: "📝" }),
        });
        topicId = newTopic.topic.id;
      }

      const convData = await apiFetch<{ conversation: { id: string } }>("/conversations/conversations", {
        method: "POST",
        body: JSON.stringify({ topic_id: topicId, name: "" }),
      });

      const cId = convData.conversation.id;
      setSelectedPartitionId(pId);
      setActiveConversationId(cId);
      setConvError(null);
      return { partitionId: pId, conversationId: cId };
    } catch (e) {
      console.error("Auto-create conversation failed:", e);
      return null;
    }
  }, [selectedPartitionId, activeConversationId, partitions, loadPartitions]);

  // ── Handle send ──
  const handleSend = useCallback(
    async (text: string, files?: { name: string; type: string; materialId?: string }[]) => {
      if (!text.trim() || isLoading) return;

      // Auto-create conversation if needed
      const ctx = await ensureConversation();
      if (!ctx) {
        setMessages((prev) => [...prev, {
          id: "err-" + Date.now(),
          parent_id: "", children_ids: [], partition_id: "", conversation_id: "",
          content_blocks: [{ type: "text" as const, text: "❌ 无法创建对话，请检查后端连接" }],
          text_summary: "", role: "assistant" as const, timestamp: Date.now(),
          token_count: 0, is_deleted: false, is_archived: false, has_modified_version: false,
        }]);
        return;
      }

      const { partitionId, conversationId } = ctx;

      const userMsgId = Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
      const blocks: { type: string; text?: string; url?: string; name?: string }[] = [{ type: "text", text }];
      if (files) {
        for (const f of files) {
          blocks.push({ type: f.type === "image" ? "image" : "file", name: f.name });
        }
      }

      const userMsg: TreeNode = {
        id: userMsgId,
        parent_id: partitionId || "virtual_root",
        children_ids: [],
        partition_id: partitionId || "",
        conversation_id: conversationId || "",
        content_blocks: blocks as TreeNode["content_blocks"],
        text_summary: text,
        role: "user",
        timestamp: Date.now(),
        token_count: 0,
        is_deleted: false,
        is_archived: false,
        has_modified_version: false,
      };

      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);
      setStatusMessage("正在思考...");

      const assistantMsgId = Date.now().toString(36) + "a" + Math.random().toString(36).substr(2, 9);
      streamingMsgIdRef.current = assistantMsgId;
      streamBufferRef.current = "";
      streamingContextRef.current = {
        partitionId: partitionId || "",
        conversationId: conversationId || "",
      };
      const assistantPlaceholder: TreeNode = {
        id: assistantMsgId,
        parent_id: userMsgId,
        children_ids: [],
        partition_id: partitionId || "",
        conversation_id: conversationId || "",
        content_blocks: [{ type: "text" as const, text: "" }],
        text_summary: "",
        role: "assistant",
        timestamp: Date.now(),
        token_count: 0,
        is_deleted: false,
        is_archived: false,
        has_modified_version: false,
      };

      setMessages((prev) => [...prev, assistantPlaceholder]);

      const sent = sendWSMessage({
        text,
        partition_id: partitionId || undefined,
        conversation_id: conversationId || undefined,
      });
      if (!sent) {
        setStatusMessage("WebSocket 未连接，尝试 HTTP...");
        try {
          const res = await fetch("/api/conversations/message", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text, partition_id: partitionId, conversation_id: conversationId }),
          });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const data = await res.json();
          const replyText = data.assistant_message?.text_summary ||
            data.assistant_message?.content_blocks?.find((b: { type: string }) => b.type === "text")?.text ||
            "（回复获取成功但没有显示内容）";
          streamingMsgIdRef.current = null;
          streamBufferRef.current = "";
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? { ...m, content_blocks: [{ type: "text" as const, text: replyText }], text_summary: replyText }
                : m
            )
          );
          setIsLoading(false);
          setStatusMessage("");
          setTimeout(() => loadPartitions(), 300);
        } catch (httpErr) {
          const errMsg = `无法连接服务器：${httpErr instanceof Error ? httpErr.message : "未知错误"}`;
          const errNode: TreeNode = {
            id: "err-" + Date.now(),
            parent_id: partitionId || "",
            children_ids: [],
            partition_id: partitionId || "",
            conversation_id: conversationId || "",
            content_blocks: [{ type: "text" as const, text: `❌ ${errMsg}` }],
            text_summary: errMsg,
            role: "assistant",
            timestamp: Date.now(),
            token_count: 0,
            is_deleted: false,
            is_archived: false,
            has_modified_version: false,
          };
          setMessages((prev) => prev.map((m) => (m.id === assistantMsgId ? errNode : m)));
          streamingMsgIdRef.current = null;
          streamBufferRef.current = "";
          setIsLoading(false);
          setStatusMessage("");
        }
      }
    },
    [isLoading, loadPartitions, ensureConversation]
  );

  // ── Handle conversation selection ──
  const handleSelectConversation = useCallback(
    (partitionId: string, conversationId: string) => {
      setSelectedPartitionId(partitionId);
      setActiveConversationId(conversationId);
      setConvError(null);
      setShowPartitionSidebar(false);
      setSwitchBanner(null);
    },
    []
  );

  // ── Handle switch banner ──
  const handleSwitchConfirm = useCallback(() => {
    if (switchBanner) {
      setSelectedPartitionId(switchBanner.partitionId);
      setActiveConversationId(switchBanner.conversationId);
      setConvError(null);
      setSwitchBanner(null);
    }
  }, [switchBanner]);

  const handleSwitchDismiss = useCallback(() => {
    setSwitchBanner(null);
  }, []);

  // ── Handle delete message ──
  const handleDeleteMessage = useCallback(async (messageId: string) => {
    try {
      await fetch("/api/conversations/messages/" + messageId, { method: "DELETE" });
      setMessages((prev) => prev.filter((m) => m.id !== messageId));
    } catch (e) {
      console.error("Delete failed:", e);
    }
  }, []);

  // ── Handle edit message (v4: inline version, no new branch) ──
  // Returns version_count for MessageList to update version counter
  const handleEditMessage = useCallback(async (messageId: string, newText: string) => {
    const res = await fetch("/api/conversations/messages/" + messageId, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content_blocks: [{ type: "text", text: newText }],
        text_summary: newText,
      }),
    });
    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new Error(`Edit failed ${res.status}: ${errText}`);
    }
    const data = await res.json();
    return data.version_count || 0;
  }, []);

  // ── Handle version switch ──
  // Returns { index, total } for the MessageList to display version counter
  const handleVersionSwitch = useCallback(async (messageId: string, direction: "prev" | "next") => {
    try {
      // Fetch message + versions list (backend now filters by same role)
      const msgRes = await fetch(`/api/conversations/messages/${messageId}`);
      if (!msgRes.ok) return null;
      const msgData = await msgRes.json();
      const versions: string[] = msgData.versions || [];
      if (versions.length <= 1) return { index: 1, total: 1 };

      // Find current position in versions list
      const curIdx = versions.indexOf(messageId);
      if (curIdx === -1) return null;

      const newIdx = direction === "prev"
        ? (curIdx - 1 + versions.length) % versions.length
        : (curIdx + 1) % versions.length;
      const targetId = versions[newIdx];

      // Load target version
      const targetRes = await fetch(`/api/conversations/messages/${targetId}`);
      if (!targetRes.ok) return null;
      const targetData = await targetRes.json();
      const targetMsg = targetData.message;
      if (!targetMsg) return null;

      // Extract text from target version's content_blocks
      const targetText = (targetMsg.content_blocks || [])
        .filter((b: any) => b.type === "text")
        .map((b: any) => b.text || "")
        .join("\n\n");

      // Update the message in-place with the target version's content
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId
            ? {
                ...targetMsg,
                id: messageId, // keep same ID so React doesn't remount
                content_blocks: [{ type: "text" as const, text: targetText || "(空)" }],
                text_summary: targetText,
              }
            : m
        )
      );

      return { index: newIdx + 1, total: versions.length };
    } catch (e) {
      console.error("Version switch failed:", e);
      return null;
    }
  }, []);

  // ── Handle new partition ──
  const handleCreatePartition = useCallback(
    async (name: string, emoji: string) => {
      try {
        await apiFetch("/conversations/partitions", {
          method: "POST",
          body: JSON.stringify({ name, subject: name, emoji }),
        });
        await loadPartitions();
      } catch (e) {
        console.error("Failed to create partition:", e);
      }
    },
    [loadPartitions]
  );

  // ── Handle rename / delete partition ──
  const handleRenamePartition = useCallback(
    async (id: string, name: string) => {
      try {
        await apiFetch(`/conversations/partitions/${id}`, { method: "PATCH", body: JSON.stringify({ name }) });
        await loadPartitions();
      } catch (e) { console.error(e); }
    },
    [loadPartitions]
  );

  const handleDeletePartition = useCallback(
    async (id: string) => {
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
    },
    [selectedPartitionId, loadPartitions]
  );

  // ── Active partition for header ──
  const activePartition = partitions.find((p) => p.id === selectedPartitionId);

  // ── Handle new conversation (partition / domain / topic level) ──
  const handleNewConversation = useCallback(
    async (level: string, parentId: string) => {
      try {
        let topicId = "";

        if (level === "default") {
          // No partition selected — use or create default partition
          let pId = selectedPartitionId;
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
          // Now proceed as partition level
          return handleNewConversation("partition", pId);
        }

        if (level === "topic") {
          // Direct: create conversation under this topic
          topicId = parentId;
        } else {
          // Need to find or create a topic under this partition/domain
          const endpoint = level === "domain"
            ? `/conversations/domains/${parentId}/topics`
            : `/conversations/partitions/${parentId}/domains`;

          const data = await apiFetch<any>(endpoint);
          const items = data?.domains || data?.topics || [];

          if (items.length > 0) {
            // Use first item
            if (level === "partition") {
              // Got domains, need first domain's first topic
              const domainId = items[0].id;
              const topicData = await apiFetch<{ topics: any[] }>(`/conversations/domains/${domainId}/topics`);
              if (topicData.topics?.length > 0) {
                topicId = topicData.topics[0].id;
              } else {
                // Create default topic under first domain
                const newTopic = await apiFetch<{ topic: { id: string } }>("/conversations/topics", {
                  method: "POST",
                  body: JSON.stringify({ domain_id: domainId, name: "默认专题", emoji: "📝" }),
                });
                topicId = newTopic.topic.id;
              }
            } else {
              // domain level: got topics directly
              topicId = items[0].id;
            }
          } else {
            // No items — create default chain
            if (level === "partition") {
              const newDomain = await apiFetch<{ domain: { id: string } }>("/conversations/domains", {
                method: "POST",
                body: JSON.stringify({ partition_id: parentId, name: "默认领域", emoji: "📚" }),
              });
              const newTopic = await apiFetch<{ topic: { id: string } }>("/conversations/topics", {
                method: "POST",
                body: JSON.stringify({ domain_id: newDomain.domain.id, name: "默认专题", emoji: "📝" }),
              });
              topicId = newTopic.topic.id;
            } else {
              const newTopic = await apiFetch<{ topic: { id: string } }>("/conversations/topics", {
                method: "POST",
                body: JSON.stringify({ domain_id: parentId, name: "默认专题", emoji: "📝" }),
              });
              topicId = newTopic.topic.id;
            }
          }
        }

        // Set partition_id for context
        if (level === "partition") setSelectedPartitionId(parentId);

        // Create conversation
        const convData = await apiFetch<{ conversation: { id: string } }>("/conversations/conversations", {
          method: "POST",
          body: JSON.stringify({ topic_id: topicId, name: "" }),
        });
        setActiveConversationId(convData.conversation.id);
        setConvError(null);
        await loadPartitions();

        // On mobile, close sidebar
        setShowPartitionSidebar(false);
      } catch (e) {
        console.error("New conversation failed:", e);
      }
    },
    [loadPartitions]
  );

  return {
    // State
    partitions,
    selectedPartitionId,
    activeConversationId,
    messages,
    responseBlocks,
    isLoading,
    statusMessage,
    switchBanner,
    showPartitionSidebar,
    sidebarCollapsed,
    showNewPartition,
    loadingPartitions,
    isLoadingPartitions,
    loadingMessages,
    convError,
    isDesktop,
    activePartition,

    // Handlers
    handleSelectConversation,
    handleNewConversation,
    handleSend,
    handleDeleteMessage,
    handleEditMessage,
    handleVersionSwitch,
    handleCreatePartition,
    handleRenamePartition,
    handleDeletePartition,
    handleSwitchConfirm,
    handleSwitchDismiss,
    setShowPartitionSidebar,
    setShowNewPartition,
    setSidebarCollapsed,
    loadPartitions,
  };
}
