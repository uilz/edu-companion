"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  Menu, X, Bot, ChevronLeft, ChevronRight,
} from "lucide-react";
import { useRouter } from "next/navigation";
import type {
  Partition,
  TreeNode,
  ResponseBlock,
  WSIncomingMessage,
} from "@/types";
import PartitionSidebar from "@/components/conversation/PartitionSidebar";
import MessageList from "@/components/conversation/MessageList";
import ConversationChatInput from "@/components/conversation/ChatInput";

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
  onContextSwitch: (data: { partition_id: string; conversation_id: string; domain_name: string; topic_name: string; switch_detail: Record<string, string> }) => void;
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

// ── New partition dialog ──
function NewPartitionDialog({
  open,
  onClose,
  onCreate,
}: {
  open: boolean;
  onClose: () => void;
  onCreate: (name: string, emoji: string) => void;
}) {
  const [name, setName] = useState("");
  const [emoji, setEmoji] = useState("📐");

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-[var(--color-bg)] border border-[var(--color-border)] w-full max-w-sm mx-4 rounded-xl" onClick={(e) => e.stopPropagation()}>
        <div className="px-4 py-3 border-b border-[var(--color-border)] flex items-center justify-between">
          <h3 className="text-sm font-semibold text-[var(--color-text)]">
            新建分区
          </h3>
          <button onClick={onClose} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            <X size={16} />
          </button>
        </div>
        <div className="px-4 py-4 space-y-3">
          <div>
            <label className="text-xs text-[var(--color-text-muted)] block mb-1">分区名称</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如: 高等数学-极限"
              className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 rounded-lg focus:outline-none focus:border-[var(--color-border-hover)]"
              autoFocus
            />
          </div>
          <div>
            <label className="text-xs text-[var(--color-text-muted)] block mb-1">Emoji</label>
            <input value={emoji} onChange={(e) => setEmoji(e.target.value)} className="w-16 bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 text-center rounded-lg" />
          </div>
        </div>
        <div className="px-4 py-3 border-t border-[var(--color-border)] flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-1.5 text-xs text-[var(--color-text-secondary)]">取消</button>
          <button onClick={() => { if (name.trim()) { onCreate(name.trim(), emoji); setName(""); setEmoji("📐"); onClose(); } }} disabled={!name.trim()} className="px-3 py-1.5 text-xs bg-[var(--color-accent)] text-white rounded-lg disabled:opacity-30">
            创建
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Context switch banner ──
function SwitchBanner({
  domainName, topicName, onSwitch, onDismiss,
}: {
  domainName: string;
  topicName: string;
  onSwitch: () => void;
  onDismiss: () => void;
}) {
  return (
    <div className="mx-4 mt-2 px-4 py-3 bg-[var(--color-accent)]/10 border border-[var(--color-accent)]/30 rounded-lg">
      <div className="flex items-start gap-3">
        <span className="text-lg">🔀</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-[var(--color-text)] leading-relaxed">
            检测到你在聊 <strong>{domainName}{topicName ? ` → ${topicName}` : ""}</strong>，要切换到对应会话吗？
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={onSwitch}
            className="px-3 py-1.5 text-xs bg-[var(--color-accent)] text-white hover:bg-[var(--color-accent-hover)] rounded-lg transition-colors"
          >
            切换
          </button>
          <button
            onClick={onDismiss}
            className="px-2 py-1.5 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            留在此处
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main page ──
export default function LearnPage() {
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
  const [loadingMessages, setLoadingMessages] = useState(false);

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
      const data = await apiFetch<{ partitions: Partition[] }>("/conversations/partitions");
      setPartitions(data.partitions || []);
    } catch (e) {
      console.error("Failed to load partitions:", e);
    } finally {
      setLoadingPartitions(false);
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
    } catch (e) {
      console.error("Failed to load messages:", e);
    } finally {
      setLoadingMessages(false);
    }
  }, []);

  // ── Load messages when conversation selected ──
  const msgInitialRender = useRef(true);
  useEffect(() => {
    if (msgInitialRender.current) { msgInitialRender.current = false; return; }
    if (activeConversationId) {
      loadMessages(activeConversationId);
    } else {
      setMessages([]);
      setResponseBlocks([]);
    }
  }, [activeConversationId, loadMessages]);

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
                ? { ...m, content_blocks: [{ type: "text", text: buffer }], text_summary: buffer }
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
                content_blocks: [{ type: "text", text: "（助手返回了空回复）" }],
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
          content_blocks: [{ type: "text", text: `❌ ${msg}` }] as TreeNode["content_blocks"],
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
          content_blocks: [{ type: "text", text: "❌ 无法创建对话，请检查后端连接" }] as TreeNode["content_blocks"],
          text_summary: "", role: "assistant", timestamp: Date.now(),
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
        content_blocks: [{ type: "text", text: "" }],
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
                ? { ...m, content_blocks: [{ type: "text", text: replyText }], text_summary: replyText }
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
            content_blocks: [{ type: "text", text: `❌ ${errMsg}` }] as TreeNode["content_blocks"],
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
                content_blocks: [{ type: "text", text: targetText || "(空)" }],
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
        await loadPartitions();

        // On mobile, close sidebar
        setShowPartitionSidebar(false);
      } catch (e) {
        console.error("New conversation failed:", e);
      }
    },
    [loadPartitions]
  );

  // ── Mobile layout ──
  if (!isDesktop) {
    return (
      <div
        className="fixed inset-0 bg-[var(--color-bg)] z-30 flex flex-col"
        style={{ bottom: "var(--bottom-nav-height)" }}
      >
        <div className="flex-shrink-0 border-b border-[var(--color-border)] px-4 py-3 flex items-center gap-3">
          <button
            onClick={() => setShowPartitionSidebar(true)}
            className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            <Menu size={20} />
          </button>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold text-[var(--color-text)] truncate">
              {activePartition
                ? `${activePartition.emoji} ${activePartition.name}`
                : "对话"}
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-hidden flex flex-col">
          {switchBanner && (
            <SwitchBanner
              domainName={switchBanner.domainName}
              topicName={switchBanner.topicName}
              onSwitch={handleSwitchConfirm}
              onDismiss={handleSwitchDismiss}
            />
          )}
          <MessageList
            messages={messages}
            responseBlocks={responseBlocks}
            isLoading={isLoading}
            statusMessage={statusMessage}
            onDeleteMessage={handleDeleteMessage}
            onEditMessage={handleEditMessage}
            onVersionSwitch={handleVersionSwitch}
          />
          <ConversationChatInput
            onSend={handleSend}
            disabled={isLoading}
            conversationId={activeConversationId}
          />
        </div>

        {showPartitionSidebar && (
          <MobileBottomSheet onClose={() => setShowPartitionSidebar(false)}>
            <PartitionSidebar
              partitions={partitions}
              selectedPartitionId={selectedPartitionId}
              activeConversationId={activeConversationId}
              onSelectConversation={handleSelectConversation}
              onCreatePartition={() => {
                setShowPartitionSidebar(false);
                setShowNewPartition(true);
              }}
              onRenamePartition={handleRenamePartition}
              onDeletePartition={handleDeletePartition}
              loading={loadingPartitions}
              onNewConversation={handleNewConversation}
              onTreeChanged={loadPartitions}
            />
          </MobileBottomSheet>
        )}

        <NewPartitionDialog
          open={showNewPartition}
          onClose={() => setShowNewPartition(false)}
          onCreate={handleCreatePartition}
        />
      </div>
    );
  }

  // ── Desktop layout: merged sidebar ──
  const SIDEBAR_WIDTH = 260;

  return (
    <div className="fixed inset-0 bg-[var(--color-bg)] z-30 flex">
      {/* Merged sidebar: nav links + partition tree */}
      <div
        className="flex-shrink-0 flex flex-col border-r border-[var(--color-border)] transition-all duration-200"
        style={{ width: sidebarCollapsed ? "0px" : `${SIDEBAR_WIDTH}px`, overflow: "hidden" }}
      >
        {!sidebarCollapsed && (
          <div className="flex flex-col h-full">
            {/* Mini header with back to dashboard link */}
            <div className="flex items-center justify-between px-3 py-2.5 border-b border-[var(--color-border)]">
              <a
                href="/dashboard"
                className="flex items-center gap-1.5 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
              >
                <ChevronLeft size={14} />
                <span>驾驶舱</span>
              </a>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => {
                    if (selectedPartitionId) {
                      handleNewConversation("partition", selectedPartitionId);
                    } else {
                      // No partition selected — create default first
                      handleNewConversation("default", "");
                    }
                  }}
                  className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] rounded"
                  title="新建会话"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                </button>
                <button
                  onClick={() => setShowNewPartition(true)}
                  className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] rounded"
                  title="新建分区"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M12 5v14M5 12h14"/></svg>
                </button>
                <button
                  onClick={() => setSidebarCollapsed(true)}
                  className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)] rounded"
                  title="收起侧栏"
                >
                  <ChevronLeft size={14} />
                </button>
              </div>
            </div>

            {/* Partition tree */}
            <div className="flex-1 overflow-hidden">
              <PartitionSidebar
                partitions={partitions}
                selectedPartitionId={selectedPartitionId}
                activeConversationId={activeConversationId}
                onSelectConversation={handleSelectConversation}
                onCreatePartition={() => setShowNewPartition(true)}
                onRenamePartition={handleRenamePartition}
                onDeletePartition={handleDeletePartition}
                loading={loadingPartitions}
                compact
                onNewConversation={handleNewConversation}
                onTreeChanged={loadPartitions}
              />
            </div>
          </div>
        )}
      </div>

      {/* Collapse toggle when sidebar hidden */}
      {sidebarCollapsed && (
        <button
          onClick={() => setSidebarCollapsed(false)}
          className="flex-shrink-0 w-6 border-r border-[var(--color-border)] flex items-center justify-center text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)] transition-colors"
          title="展开侧栏"
        >
          <ChevronRight size={14} />
        </button>
      )}

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {selectedPartitionId && activePartition && (
          <div className="flex-shrink-0 border-b border-[var(--color-border)] px-6 py-3 flex items-center gap-3">
            <Bot size={18} className="text-[var(--color-accent)]" />
            <div>
              <div className="text-sm font-semibold text-[var(--color-text)]">
                {activePartition.emoji} {activePartition.name}
              </div>
            </div>
          </div>
        )}

        {switchBanner && (
          <SwitchBanner
            domainName={switchBanner.domainName}
            topicName={switchBanner.topicName}
            onSwitch={handleSwitchConfirm}
            onDismiss={handleSwitchDismiss}
          />
        )}

        <MessageList
          messages={messages}
          responseBlocks={responseBlocks}
          isLoading={isLoading}
          statusMessage={statusMessage}
          onDeleteMessage={handleDeleteMessage}
          onEditMessage={handleEditMessage}
          onVersionSwitch={handleVersionSwitch}
        />

        <ConversationChatInput
          onSend={handleSend}
          disabled={isLoading}
          conversationId={activeConversationId}
        />
      </div>

      <NewPartitionDialog
        open={showNewPartition}
        onClose={() => setShowNewPartition(false)}
        onCreate={handleCreatePartition}
      />
    </div>
  );
}

// ── Mobile bottom sheet ──
function MobileBottomSheet({
  children,
  onClose,
}: {
  children: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-[var(--color-bg)] border-t border-[var(--color-border)] max-h-[70vh] flex flex-col rounded-t-xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
          <span className="text-sm font-semibold text-[var(--color-text)]">导航</span>
          <button onClick={onClose} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-hidden">{children}</div>
      </div>
    </div>
  );
}
