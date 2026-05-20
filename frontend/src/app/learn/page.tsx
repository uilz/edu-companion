"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  Menu,
  X,
  Plus,
  Bot,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useRouter } from "next/navigation";
import type {
  Partition,
  Branch,
  TreeNode,
  ResponseBlock,
  WSIncomingMessage,
} from "@/types";
import PartitionSidebar from "@/components/conversation/PartitionSidebar";
import BranchList from "@/components/conversation/BranchList";
import MessageList from "@/components/conversation/MessageList";
import ConversationChatInput from "@/components/conversation/ChatInput";
import WorkspacePanel from "@/components/conversation/WorkspacePanel";
import MaterialPanel from "@/components/materials/MaterialPanel";
import PracticeSuggestions from "@/components/conversation/PracticeSuggestions";

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
};

let ws: WebSocket | null = null;
let wsCallbacks: WSCallbacks | null = null;

function connectConversationWS(callbacks: WSCallbacks) {
  wsCallbacks = callbacks;

  if (ws && ws.readyState === WebSocket.OPEN) return;

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/api/conversations/ws`;

  try {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("[ConvWS] connected:", wsUrl);
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
          case "done":
            wsCallbacks?.onDone(data.partition_id, data.assistant_message);
            break;
          case "error":
            wsCallbacks?.onError(data.message);
            break;
          case "block_update":
            wsCallbacks?.onBlockUpdate(data.block);
            break;
          case "user_message":
            // Already handled optimistically
            break;
          case "pong":
            break;
        }
      } catch (e) {
        console.error("[ConvWS] parse error:", e);
      }
    };

    ws.onerror = (e) => {
      console.error("[ConvWS] error:", e);
      wsCallbacks?.onError("WebSocket 连接错误");
    };

    ws.onclose = () => {
      console.log("[ConvWS] closed");
      ws = null;
      // Auto-reconnect after 3s
      setTimeout(() => {
        if (wsCallbacks) connectConversationWS(wsCallbacks);
      }, 3000);
    };
  } catch (e) {
    console.error("[ConvWS] connect failed:", e);
    callbacks.onError("无法建立 WebSocket 连接");
  }
}

function sendWSMessage(data: Record<string, unknown>) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
  }
}

function disconnectWS() {
  if (ws) {
    ws.close();
    ws = null;
  }
  wsCallbacks = null;
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-[var(--color-bg)] border border-[var(--color-border)] w-full max-w-sm mx-4">
        <div className="px-4 py-3 border-b border-[var(--color-border)] flex items-center justify-between">
          <h3 className="text-sm font-semibold text-[var(--color-text)]">
            新建分区
          </h3>
          <button
            onClick={onClose}
            className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            <X size={16} />
          </button>
        </div>
        <div className="px-4 py-4 space-y-3">
          <div>
            <label className="text-xs text-[var(--color-text-muted)] block mb-1">
              分区名称
            </label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如: 高等数学-极限"
              className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 focus:outline-none focus:border-[var(--color-border-hover)]"
              autoFocus
            />
          </div>
          <div>
            <label className="text-xs text-[var(--color-text-muted)] block mb-1">
              Emoji
            </label>
            <input
              value={emoji}
              onChange={(e) => setEmoji(e.target.value)}
              className="w-16 bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 focus:outline-none focus:border-[var(--color-border-hover)] text-center"
            />
          </div>
        </div>
        <div className="px-4 py-3 border-t border-[var(--color-border)] flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text)] transition-colors"
          >
            取消
          </button>
          <button
            onClick={() => {
              if (name.trim()) {
                onCreate(name.trim(), emoji);
                setName("");
                setEmoji("📐");
                onClose();
              }
            }}
            disabled={!name.trim()}
            className="px-3 py-1.5 text-xs bg-[var(--color-accent)] text-white disabled:opacity-30 hover:bg-[var(--color-accent-hover)] transition-colors"
          >
            创建
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main page ──
export default function LearnPage() {
  const isDesktop = useMediaQuery("(min-width: 768px)");

  // State
  const [partitions, setPartitions] = useState<Partition[]>([]);
  const [selectedPartitionId, setSelectedPartitionId] = useState<string | null>(
    null
  );
  const [branches, setBranches] = useState<Branch[]>([]);
  const [activeBranchId, setActiveBranchId] = useState<string | null>(null);
  const [messages, setMessages] = useState<TreeNode[]>([]);
  const [responseBlocks, setResponseBlocks] = useState<ResponseBlock[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");

  // Mobile sidebar state
  const [showPartitionSidebar, setShowPartitionSidebar] = useState(false);
  const [showBranchSidebar, setShowBranchSidebar] = useState(false);

  // Desktop sidebar collapse state
  const [collapsedPartition, setCollapsedPartition] = useState(false);
  const [collapsedBranch, setCollapsedBranch] = useState(false);

  // New partition dialog
  const [showNewPartition, setShowNewPartition] = useState(false);

  // P5: Branch sidebar view mode
  const [branchViewMode, setBranchViewMode] = useState<"branches" | "materials">("branches");

  // Loading states
  const [loadingPartitions, setLoadingPartitions] = useState(true);
  const [loadingBranches, setLoadingBranches] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);

  const router = useRouter();

  // ── panel=graph → 重定向到图谱页（独立 effect，最先执行） ──
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      if (params.get("panel") === "graph") {
        const pId = params.get("p") || params.get("partition_id");
        router.replace(pId ? `/dashboard?tab=graph&partition_id=${pId}` : "/dashboard?tab=graph");
      }
    } catch {}
  }, [router]);

  // ── 刷新后恢复分区/分支状态：URL 参数为主，localStorage 为备份 ──
  const [urlInitialized, setUrlInitialized] = useState(false);

  // 从 URL 读取（刷新后 URL 参数保持不变）
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const pId = params.get("p") || params.get("partition_id");
      const bId = params.get("b");

      if (pId) {
        setSelectedPartitionId(pId);
        if (bId) setActiveBranchId(bId);
      } else {
        // 回退到 localStorage
        const saved = localStorage.getItem("learn-page-state");
        if (saved) {
          const { partitionId, branchId } = JSON.parse(saved);
          if (partitionId) setSelectedPartitionId(partitionId);
          if (branchId) setActiveBranchId(branchId);
        }
      }
    } catch {}
    setUrlInitialized(true);
  }, []);

  // 状态变化时同步到 URL + localStorage
  useEffect(() => {
    if (!urlInitialized) return;
    try {
      const params = new URLSearchParams();
      if (selectedPartitionId) params.set("p", selectedPartitionId);
      if (activeBranchId) params.set("b", activeBranchId);
      const qs = params.toString();
      const newUrl = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
      window.history.replaceState(null, "", newUrl);

      localStorage.setItem("learn-page-state", JSON.stringify({
        partitionId: selectedPartitionId,
        branchId: activeBranchId,
      }));
    } catch {}
  }, [selectedPartitionId, activeBranchId, urlInitialized]);

  // WS streaming buffer ref
  const streamBufferRef = useRef("");
  const streamingMsgIdRef = useRef<string | null>(null);

  // ── Lock body scroll ──
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, []);

  // ── Load partitions ──
  const loadPartitions = useCallback(async () => {
    try {
      setLoadingPartitions(true);
      const data = await apiFetch<{ partitions: Partition[] }>(
        "/conversations/partitions"
      );
      setPartitions(data.partitions || []);
    } catch (e) {
      console.error("Failed to load partitions:", e);
    } finally {
      setLoadingPartitions(false);
    }
  }, []);

  // ── Load branches for a partition ──
  const loadBranches = useCallback(async (partitionId: string) => {
    try {
      setLoadingBranches(true);
      const data = await apiFetch<{ branches: Branch[] }>(
        `/conversations/partitions/${partitionId}/branches`
      );
      setBranches(data.branches || []);
    } catch (e) {
      console.error("Failed to load branches:", e);
    } finally {
      setLoadingBranches(false);
    }
  }, []);

  // ── Load messages for a branch ──
  const loadMessages = useCallback(async (branchId: string) => {
    try {
      setLoadingMessages(true);
      const data = await apiFetch<{ messages: TreeNode[] }>(
        `/conversations/branches/${branchId}/messages?limit=50&offset=0`
      );
      setMessages(data.messages || []);

      // Load response blocks for assistant messages
      const assistantMsgs = (data.messages || []).filter(
        (m) => m.role === "assistant"
      );
      const allBlocks: ResponseBlock[] = [];
      for (const msg of assistantMsgs) {
        try {
          const blockData = await apiFetch<{ blocks: ResponseBlock[] }>(
            `/conversations/messages/${msg.id}/blocks`
          );
          allBlocks.push(...(blockData.blocks || []));
        } catch {
          // Some messages may not have blocks
        }
      }
      setResponseBlocks(allBlocks);
    } catch (e) {
      console.error("Failed to load messages:", e);
    } finally {
      setLoadingMessages(false);
    }
  }, []);

  // ── WebSocket callbacks ──
  useEffect(() => {
    connectConversationWS({
      onStatus: (msg) => {
        setStatusMessage(msg);
      },
      onToken: (content, _blockId) => {
        streamBufferRef.current += content;
        const currentBuffer = streamBufferRef.current;
        const msgId = streamingMsgIdRef.current;

        if (msgId) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === msgId
                ? {
                    ...m,
                    content_blocks: [
                      { type: "text", text: currentBuffer },
                    ],
                    text_summary: currentBuffer,
                  }
                : m
            )
          );
        }
      },
      onDone: (_partitionId, assistantMessage) => {
        setIsLoading(false);
        setStatusMessage("");

        // Replace streaming message with final version
        if (assistantMessage) {
          const currentStreamingId = streamingMsgIdRef.current;  // 先保存
          streamingMsgIdRef.current = null;
          streamBufferRef.current = "";

          setMessages((prev) => {
            const idx = prev.findIndex(
              (m) => m.id === currentStreamingId || m.id === assistantMessage.id
            );
            if (idx >= 0) {
              const updated = [...prev];
              updated[idx] = assistantMessage;
              return updated;
            }
            return [...prev, assistantMessage];
          });
        } else {
          streamingMsgIdRef.current = null;
          streamBufferRef.current = "";
        }

        // 轻轻刷新分区列表（不刷新消息，避免覆盖流式结果造成闪烁）
        setTimeout(() => loadPartitions(), 300);
      },
      onError: (msg) => {
        setIsLoading(false);
        setStatusMessage("");
        console.error("[ConvWS] error:", msg);
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
    });

    return () => disconnectWS();
  }, [activeBranchId, loadMessages, loadPartitions]);

  // ── Initial load ──
  useEffect(() => {
    loadPartitions();
  }, [loadPartitions]);

  // ── Load branches when partition selected ──
  // 用 ref 跳过首次渲染，避免与 URL 恢复竞态清空 activeBranchId
  const branchInitialRender = useRef(true);
  useEffect(() => {
    if (branchInitialRender.current) {
      branchInitialRender.current = false;
      return;
    }
    if (selectedPartitionId) {
      loadBranches(selectedPartitionId);
    } else {
      setBranches([]);
      setActiveBranchId(null);
    }
  }, [selectedPartitionId, loadBranches]);

  // ── Load messages when branch selected ──
  const msgInitialRender = useRef(true);
  useEffect(() => {
    if (msgInitialRender.current) {
      msgInitialRender.current = false;
      return;
    }
    if (activeBranchId) {
      loadMessages(activeBranchId);
    } else {
      setMessages([]);
      setResponseBlocks([]);
    }
  }, [activeBranchId, loadMessages]);

  // ── 校验 URL 参数：非法分区/分支重定向回默认页 ──
  const validatedRef = useRef(false);
  useEffect(() => {
    if (!urlInitialized || loadingPartitions || loadingBranches) return;
    if (validatedRef.current) return;

    // 分区不存在 → 清空 URL 并重置
    if (selectedPartitionId && partitions.length > 0 &&
        !partitions.some((p) => p.id === selectedPartitionId)) {
      validatedRef.current = true;
      setSelectedPartitionId(null);
      setActiveBranchId(null);
      window.history.replaceState(null, "", "/learn");
      return;
    }

    // 分支不存在 → 仅清空分支
    if (activeBranchId && branches.length > 0 &&
        !branches.some((b) => b.id === activeBranchId)) {
      validatedRef.current = true;
      setActiveBranchId(null);
      // 更新 URL 去掉 b 参数
      const params = new URLSearchParams();
      if (selectedPartitionId) params.set("p", selectedPartitionId);
      window.history.replaceState(null, "", params.toString() ? `?${params.toString()}` : window.location.pathname);
      return;
    }

    validatedRef.current = true;
  }, [urlInitialized, loadingPartitions, loadingBranches, partitions, branches, selectedPartitionId, activeBranchId]);

  // ── Handle send ──
  const handleSend = useCallback(
    (text: string, files?: { name: string; type: string; materialId?: string }[]) => {
      if (!text.trim() || isLoading) return;

      // Create optimistic user message
      const userMsgId = Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
      const blocks: { type: string; text?: string; url?: string; name?: string }[] = [
        { type: "text", text },
      ];
      // Attach uploaded file references
      if (files) {
        for (const f of files) {
          blocks.push({ type: f.type === "image" ? "image" : "file", name: f.name });
        }
      }
      const userMsg: TreeNode = {
        id: userMsgId,
        parent_id: selectedPartitionId || "virtual_root",
        children_ids: [],
        partition_id: selectedPartitionId || "",
        branch_id: activeBranchId || "",
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

      // Create placeholder for streaming assistant response
      const assistantMsgId = Date.now().toString(36) + "a" + Math.random().toString(36).substr(2, 9);
      streamingMsgIdRef.current = assistantMsgId;
      streamBufferRef.current = "";

      const assistantPlaceholder: TreeNode = {
        id: assistantMsgId,
        parent_id: userMsgId,
        children_ids: [],
        partition_id: selectedPartitionId || "",
        branch_id: activeBranchId || "",
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

      // Send via WebSocket
      sendWSMessage({
        text,
        partition_id: selectedPartitionId || undefined,
        branch_id: activeBranchId || undefined,
      });
    },
    [isLoading, selectedPartitionId, activeBranchId]
  );

  // ── Handle partition selection ──
  const handleSelectPartition = useCallback(
    (id: string) => {
      setSelectedPartitionId(id);
      setActiveBranchId(null);
      setShowPartitionSidebar(false);
    },
    []
  );

  // ── Handle delete message ──
  const handleDeleteMessage = useCallback(async (messageId: string) => {
    try {
      await fetch('/api/conversations/messages/' + messageId, { method: 'DELETE' });
      setMessages(prev => prev.filter(m => m.id !== messageId));
    } catch (e) {
      console.error('Delete failed:', e);
    }
  }, []);

  // ── Handle edit message (creates new branch) ──
  const handleEditMessage = useCallback(async (messageId: string, newText: string) => {
    try {
      const res = await fetch("/api/conversations/messages/" + messageId, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content_blocks: [{ type: "text", text: newText }],
          text_summary: newText,
        }),
      });
      if (!res.ok) throw new Error("Edit failed");
      const data = await res.json();
      const newBranchId = data.node?.branch_id;

      // Reload partitions (branch counts update) then branches
      await loadPartitions();
      if (selectedPartitionId) {
        await loadBranches(selectedPartitionId);
        // Navigate to the new branch
        if (newBranchId) {
          setActiveBranchId(newBranchId);
        }
      }
    } catch (e) {
      console.error("Edit failed:", e);
    }
  }, [loadPartitions, selectedPartitionId, loadBranches]);

  // ── Handle branch selection ──
  const handleSelectBranch = useCallback(
    (id: string) => {
      setActiveBranchId(id);
      setShowBranchSidebar(false);
    },
    []
  );

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

  // ── Handle new branch ──
  const handleCreateBranch = useCallback(async () => {
    if (!selectedPartitionId) return;
    try {
      const data = await apiFetch<{ branch: Branch }>(
        "/conversations/branches",
        {
          method: "POST",
          body: JSON.stringify({
            partition_id: selectedPartitionId,
            name: "新分支",
          }),
        }
      );
      if (data.branch) {
        await loadBranches(selectedPartitionId);
        setActiveBranchId(data.branch.id);
      }
    } catch (e) {
      console.error("Failed to create branch:", e);
    }
  }, [selectedPartitionId, loadBranches]);

  // ── Active partition name for header ──
  const activePartition = partitions.find((p) => p.id === selectedPartitionId);
  const activeBranch = branches.find((b) => b.id === activeBranchId);

  // ── Mobile layout ──
  if (!isDesktop) {
    return (
      <div
        className="fixed inset-0 bg-[var(--color-bg)] z-30 flex flex-col"
        style={{ bottom: "var(--bottom-nav-height)" }}
      >
        {/* Mobile header */}
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
            {activeBranch && (
              <div className="text-[10px] text-[var(--color-text-muted)]">
                🌿 {activeBranch.name}
              </div>
            )}
          </div>
          {activePartition && (
            <button
              onClick={() => setShowBranchSidebar(true)}
              className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            >
              <ChevronLeft size={20} className="rotate-180" />
            </button>
          )}
        </div>

        {/* Chat area */}
        <div className="flex-1 overflow-hidden flex flex-col">
          <MessageList
            messages={messages}
            responseBlocks={responseBlocks}
            isLoading={isLoading}
            statusMessage={statusMessage}
            onDeleteMessage={handleDeleteMessage}
            onEditMessage={handleEditMessage}
          />
          <ConversationChatInput
            onSend={handleSend}
            disabled={isLoading}
            branchId={activeBranchId}
          />
        </div>

        {/* Mobile partition bottom sheet */}
        {showPartitionSidebar && (
          <MobileBottomSheet
            onClose={() => setShowPartitionSidebar(false)}
          >
            <PartitionSidebar
              partitions={partitions}
              selectedPartitionId={selectedPartitionId}
              onSelectPartition={handleSelectPartition}
              onCreatePartition={() => {
                setShowPartitionSidebar(false);
                setShowNewPartition(true);
              }}
              loading={loadingPartitions}
            />
          </MobileBottomSheet>
        )}

        {/* Mobile branch bottom sheet */}
        {showBranchSidebar && (
          <MobileBottomSheet
            onClose={() => setShowBranchSidebar(false)}
          >
            <BranchList
              branches={branches}
              activeBranchId={activeBranchId}
              onSelectBranch={handleSelectBranch}
              onCreateBranch={handleCreateBranch}
              loading={loadingBranches}
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

  // ── Desktop layout ──
  return (
    <div
      className="fixed top-0 right-0 bottom-0 bg-[var(--color-bg)] z-30 flex"
      style={{ left: "var(--sidebar-width)" }}
    >
      {/* Partition sidebar */}
      {!collapsedPartition && (
      <div className="flex-shrink-0 relative" style={{ width: "200px" }}>
        <button
          onClick={() => setCollapsedPartition(true)}
          className="absolute -right-0.5 top-1/2 -translate-y-1/2 z-10 w-4 h-12 border border-[var(--color-border)] bg-[var(--color-bg)] hover:bg-[var(--color-surface)] flex items-center justify-center text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
          title="收起分区"
        ><ChevronLeft size={12} /></button>
        <PartitionSidebar
          partitions={partitions}
          selectedPartitionId={selectedPartitionId}
          onSelectPartition={handleSelectPartition}
          onCreatePartition={() => setShowNewPartition(true)}
          loading={loadingPartitions}
        />
      </div>
      )}

      {/* Collapsed partition toggle */}
      {collapsedPartition && (
        <button
          onClick={() => setCollapsedPartition(false)}
          className="flex-shrink-0 w-5 border-r border-[var(--color-border)] flex items-center justify-center text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)] transition-colors"
          title="展开分区"
        ><ChevronRight size={12} /></button>
      )}

      {/* Branch sidebar (shown when partition selected) */}
      {selectedPartitionId && !collapsedBranch && (
        <div className="flex-shrink-0 relative" style={{ width: "220px" }}>
          <button
            onClick={() => setCollapsedBranch(true)}
            className="absolute -right-0.5 top-1/2 -translate-y-1/2 z-10 w-4 h-12 border border-[var(--color-border)] bg-[var(--color-bg)] hover:bg-[var(--color-surface)] flex items-center justify-center text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
            title="收起分支"
          ><ChevronLeft size={12} /></button>

          {/* P5: Tab bar */}
          <div className="flex border-b border-[var(--color-border)]">
            <button
              onClick={() => setBranchViewMode("branches")}
              className={`flex-1 py-2 text-xs font-medium transition-colors ${
                branchViewMode === "branches"
                  ? "text-[var(--color-accent)] border-b-2 border-[var(--color-accent)]"
                  : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              }`}
            >
              🌿 分支
            </button>
            <button
              onClick={() => setBranchViewMode("materials")}
              className={`flex-1 py-2 text-xs font-medium transition-colors ${
                branchViewMode === "materials"
                  ? "text-[var(--color-accent)] border-b-2 border-[var(--color-accent)]"
                  : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              }`}
            >
              📁 资料
            </button>
          </div>

          {branchViewMode === "branches" ? (
            <>
              <BranchList
                branches={branches}
                activeBranchId={activeBranchId}
                onSelectBranch={handleSelectBranch}
                onCreateBranch={handleCreateBranch}
                loading={loadingBranches}
              />
              <WorkspacePanel branchId={activeBranchId} partitionId={selectedPartitionId} />
              <PracticeSuggestions branchId={activeBranchId} />
            </>
          ) : (
            <MaterialPanel partitionId={selectedPartitionId} />
          )}
        </div>
      )}

      {/* Collapsed branch toggle */}
      {selectedPartitionId && collapsedBranch && (
        <button
          onClick={() => setCollapsedBranch(false)}
          className="flex-shrink-0 w-5 border-r border-[var(--color-border)] flex items-center justify-center text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)] transition-colors"
          title="展开分支"
        ><ChevronRight size={12} /></button>
      )}

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Chat header */}
        {selectedPartitionId && activePartition && (
          <div className="flex-shrink-0 border-b border-[var(--color-border)] px-6 py-3 flex items-center gap-3">
            <Bot size={18} className="text-[var(--color-accent)]" />
            <div>
              <div className="text-sm font-semibold text-[var(--color-text)]">
                {activePartition.emoji} {activePartition.name}
              </div>
              {activeBranch && (
                <div className="text-[10px] text-[var(--color-text-muted)]">
                  🌿 {activeBranch.name}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Messages */}
        <MessageList
          messages={messages}
          responseBlocks={responseBlocks}
          isLoading={isLoading}
          statusMessage={statusMessage}
          onDeleteMessage={handleDeleteMessage}
          onEditMessage={handleEditMessage}
        />

        {/* Input */}
        <ConversationChatInput
          onSend={handleSend}
          disabled={isLoading}
          branchId={activeBranchId}
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
      <div className="relative bg-[var(--color-bg)] border-t border-[var(--color-border)] max-h-[70vh] flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
          <span className="text-sm font-semibold text-[var(--color-text)]">
            导航
          </span>
          <button
            onClick={onClose}
            className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-hidden">{children}</div>
      </div>
    </div>
  );
}
