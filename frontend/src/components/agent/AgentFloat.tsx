"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";
import { MessageCircle, X, ChevronDown } from "lucide-react";
import { getAgentStore, useAgentStore, type ToolCallEvent } from "@/store/agent/agent-store";
import { useChatStream } from "@/components/chat-shared/useChatStream";
import ChatMessages from "@/components/chat-shared/ChatMessages";
import ChatInputBar from "@/components/chat-shared/ChatInputBar";
import ToolCallConfirmation from "@/components/chat-shared/ToolCallConfirmation";
import { apiFetch } from "@/store/conversation/tree-helpers";

// ══════════════════════════════════════════════════════════════
//  Helpers — 秘书树操作
// ══════════════════════════════════════════════════════════════

const SECRETARY_DIR_NAME = "🤖 秘书对话";

/** 确保「秘书对话」目录存在，返回其 ID */
async function ensureSecretaryDir(): Promise<string | null> {
  try {
    const data = await apiFetch<{ directory_nodes: any[] }>("/tree/directory");
    const nodes = data.directory_nodes || [];
    const existing = nodes.find((n) => n.kind === "secretary");
    if (existing) return existing.id;

    // 创建新的秘书目录
    const created = await apiFetch<{ directory_node: { id: string } }>("/tree/directory", {
      method: "POST",
      body: JSON.stringify({ node_type: "dir", kind: "secretary", name: SECRETARY_DIR_NAME, emoji: "🤖" }),
    });
    return created.directory_node?.id || null;
  } catch {
    return null;
  }
}

/** 获取秘书目录下的所有对话 */
async function loadSecretaryConvs(dirId: string) {
  try {
    const data = await apiFetch<{ directory_nodes: any[] }>(`/tree/directory?parent_id=${dirId}`);
    const convs = (data.directory_nodes || [])
      .filter((n) => n.node_type === "conv")
      .map((n) => ({
        id: n.id,
        name: n.name || "秘书对话",
        messageCount: (n as any).message_count || 0,
        createdAt: (n as any).created_at || 0,
      }));
    return convs;
  } catch {
    return [];
  }
}

/** 在秘书目录下创建一个新对话（按日期命名） */
async function createSecretaryConv(dirId: string): Promise<string | null> {
  const today = new Date();
  const dateStr = `${today.getMonth() + 1}/${today.getDate()} ${today.getHours().toString().padStart(2, "0")}:${today.getMinutes().toString().padStart(2, "0")}`;
  try {
    const data = await apiFetch<{ directory_node: { id: string } }>("/tree/directory", {
      method: "POST",
      body: JSON.stringify({
        node_type: "conv",
        kind: "secretary",
        parent_id: dirId,
        name: dateStr,
      }),
    });
    return data.directory_node?.id || null;
  } catch {
    return null;
  }
}

/** 加载秘书对话的消息列表 */
async function loadSecretaryMessages(convId: string): Promise<{ role: "user" | "assistant"; content: string }[]> {
  try {
    const data = await apiFetch<{ messages: any[] }>(`/tree/conversation/${convId}/messages?limit=100&offset=0`);
    return (data.messages || [])
      .filter((m) => m.role === "user" || m.role === "assistant")
      .map((m) => ({
        role: m.role as "user" | "assistant",
        content: m.text_summary || m.content || "",
      }));
  } catch {
    return [];
  }
}

/** 保存一条消息到树对话 */
async function saveMessageToTreeConv(convId: string, role: "user" | "assistant", content: string): Promise<void> {
  try {
    await apiFetch(`/tree/conversation/${convId}/message`, {
      method: "POST",
      body: JSON.stringify({
        role,
        content_blocks: [{ type: "text", text: content }],
        text_summary: content,
      }),
    });
  } catch (e) {
    console.error(`[Secretary] 保存 ${role} 消息失败:`, e);
  }
}

// ══════════════════════════════════════════════════════════════
//  Component
// ══════════════════════════════════════════════════════════════

export default function AgentFloat() {
  const pathname = usePathname();
  const router = useRouter();
  const messages = useAgentStore((s) => s.messages);
  const currentToolCall = useAgentStore((s) => s.currentToolCall);
  const secretaryConvs = useAgentStore((s) => s.secretaryConvs);
  const activeConvId = useAgentStore((s) => s.activeConvId);
  const loadingSecretary = useAgentStore((s) => s.loadingSecretary);
  const loadingMessages = useAgentStore((s) => s.loadingMessages);
  const store = getAgentStore();
  const { streaming, send } = useChatStream();

  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const [showConvList, setShowConvList] = useState(false);

  // ── 浮现动画状态（防止刷新瞬移）──
  const [visible, setVisible] = useState(false);

  // ── 拖动状态 ──
  const floatRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const dragState = useRef({
    dragging: false,
    moved: false,
    startX: 0,
    startY: 0,
    startLeft: 0,
    startTop: 0,
  });

  // 用 ref 存储实时位置，避免拖动时频繁 setState 导致卡顿
  const posRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const snappedRef = useRef<"none" | "left" | "right">("right");
  // 仅在拖动结束时 setState 触发重渲染
  const [renderPos, setRenderPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [snapped, setSnapped] = useState<"none" | "left" | "right">("right");
  const [dragging, setDragging] = useState(false);

  // 位置持久化
  const POS_KEY = "agent-float-pos";

  const loadPos = (): { x: number; y: number } | null => {
    try {
      const saved = localStorage.getItem(POS_KEY);
      if (saved) return JSON.parse(saved);
    } catch {}
    return null;
  };

  // 初始化位置，延迟 0.5s 浮现（防止刷新瞬移）
  useEffect(() => {
    const saved = loadPos();
    const initial = saved || { x: window.innerWidth - 64, y: window.innerHeight - 200 };
    posRef.current = initial;
    setRenderPos(initial);

    const EDGE_ZONE = 60;
    let snapSide: "none" | "left" | "right" = "none";
    if (initial.x < EDGE_ZONE) snapSide = "left";
    else if (initial.x > window.innerWidth - 48 - EDGE_ZONE) snapSide = "right";
    snappedRef.current = snapSide;
    setSnapped(snapSide);

    // 延迟 0.5s 后浮现
    const timer = setTimeout(() => setVisible(true), 500);
    return () => clearTimeout(timer);
  }, []);

  // 吸附到最近的左/右边缘
  const EDGE_ZONE = 60;
  const snap = (x: number): { x: number; side: "left" | "right" } | null => {
    const vw = window.innerWidth;
    if (x < EDGE_ZONE) return { x: -24, side: "left" };
    if (x > vw - 48 - EDGE_ZONE) return { x: vw - 24, side: "right" };
    return null;
  };

  // 登录页不显示悬浮球
  if (pathname === "/login") return null;

  // 加载用户偏好
  useEffect(() => {
    import("@/lib/api/api").then(({ api }) => {
      api<any>("/api/secretary/agent/preferences")
        .then((data) => {
          if (data.confirm_mode) store.setConfirmMode(data.confirm_mode);
          if (data.auto_jump_threshold !== undefined) {
            store.setAutoJumpThreshold(data.auto_jump_threshold);
          }
        })
        .catch(() => { /* 使用默认偏好 */ });
    });
  }, []);

  // ── 打开面板时初始化秘书对话 ──
  const initSecretary = useCallback(async () => {
    if (store.secretaryDirId && store.activeConvId) return;

    store.setLoadingSecretary(true);
    try {
      // 1. 确保秘书目录存在
      let dirId = store.secretaryDirId;
      if (!dirId) {
        dirId = await ensureSecretaryDir();
        if (!dirId) { store.setLoadingSecretary(false); return; }
        store.setSecretaryDirId(dirId);
      }

      // 2. 获取对话列表
      const convs = await loadSecretaryConvs(dirId);
      store.setSecretaryConvs(convs);

      // 3. 使用最新对话（或创建新对话）
      let convId = store.activeConvId;
      if (!convId) {
        // 取最近的对话（有消息的），否则新建
        const active = convs.sort((a, b) => b.createdAt - a.createdAt)[0];
        if (active) {
          convId = active.id;
        } else {
          convId = await createSecretaryConv(dirId);
          if (!convId) { store.setLoadingSecretary(false); return; }
          // 刷新列表
          const updatedConvs = await loadSecretaryConvs(dirId);
          store.setSecretaryConvs(updatedConvs);
        }
        store.setActiveConvId(convId!);
        store.setConversationId(convId!);
      }

      // 4. 加载消息
      if (convId && store.messages.length === 0) {
        store.setLoadingMessages(true);
        const msgs = await loadSecretaryMessages(convId!);
        if (msgs.length > 0) {
          store.setMessagesFromTree(msgs);
        }
        store.setLoadingMessages(false);
      }
    } finally {
      store.setLoadingSecretary(false);
    }
  }, []);

  // 打开面板时初始化
  useEffect(() => {
    if (open) {
      initSecretary();
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open, initSecretary]);

  // ── 对话切换 ──
  const handleSwitchConv = useCallback(async (convId: string) => {
    store.switchConv(convId);
    setShowConvList(false);

    // 加载该对话的消息
    store.setLoadingMessages(true);
    const msgs = await loadSecretaryMessages(convId);
    if (msgs.length > 0) {
      store.setMessagesFromTree(msgs);
    }
    store.setLoadingMessages(false);
  }, [secretaryConvs]);

  // ── 新建对话 ──
  const handleNewConv = useCallback(async () => {
    const dirId = store.secretaryDirId;
    if (!dirId) return;
    store.setLoadingSecretary(true);
    const convId = await createSecretaryConv(dirId);
    if (convId) {
      store.setActiveConvId(convId);
      store.setConversationId(convId);
      store.setMessagesFromTree([]);
      // 刷新列表
      const convs = await loadSecretaryConvs(dirId);
      store.setSecretaryConvs(convs);
    }
    store.setLoadingSecretary(false);
    setShowConvList(false);
  }, []);

  // ── 拖动事件 ──
  const handleDragStart = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      e.preventDefault();
      const clientX = "touches" in e ? e.touches[0].clientX : e.clientX;
      const clientY = "touches" in e ? e.touches[0].clientY : e.clientY;

      let adjustedX = posRef.current.x;
      if (snappedRef.current === "left") adjustedX = 8;
      else if (snappedRef.current === "right") adjustedX = window.innerWidth - 56;
      if (adjustedX !== posRef.current.x) {
        posRef.current = { x: adjustedX, y: posRef.current.y };
        if (floatRef.current) {
          floatRef.current.style.left = `${adjustedX}px`;
        }
      }
      snappedRef.current = "none";
      if (floatRef.current) {
        floatRef.current.style.transition = "none";
      }
      dragState.current = {
        dragging: true,
        moved: false,
        startX: clientX,
        startY: clientY,
        startLeft: adjustedX,
        startTop: posRef.current.y,
      };
    },
    [],
  );

  // ── 面板拖拽 ──
  const handlePanelDragStart = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const clientX = "touches" in e ? e.touches[0].clientX : e.clientX;
      const clientY = "touches" in e ? e.touches[0].clientY : e.clientY;

      let adjustedX = posRef.current.x;
      if (snappedRef.current === "left") adjustedX = 8;
      else if (snappedRef.current === "right") adjustedX = window.innerWidth - 56;
      if (adjustedX !== posRef.current.x) {
        posRef.current = { x: adjustedX, y: posRef.current.y };
        if (floatRef.current) floatRef.current.style.left = `${adjustedX}px`;
      }
      snappedRef.current = "none";
      if (floatRef.current) floatRef.current.style.transition = "none";
      if (panelRef.current) panelRef.current.style.transition = "none";

      dragState.current = {
        dragging: true,
        moved: false,
        startX: clientX,
        startY: clientY,
        startLeft: adjustedX,
        startTop: posRef.current.y,
      };
    },
    [],
  );

  useEffect(() => {
    const handleDragMove = (e: MouseEvent | TouchEvent) => {
      if (!dragState.current.dragging) return;
      e.preventDefault();
      const clientX = "touches" in e ? e.touches[0].clientX : e.clientX;
      const clientY = "touches" in e ? e.touches[0].clientY : e.clientY;

      const dx = clientX - dragState.current.startX;
      const dy = clientY - dragState.current.startY;

      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
        dragState.current.moved = true;
      }

      const newX = Math.max(0, Math.min(window.innerWidth - 48, dragState.current.startLeft + dx));
      const newY = Math.max(0, Math.min(window.innerHeight - 48, dragState.current.startTop + dy));

      posRef.current = { x: newX, y: newY };
      if (floatRef.current) {
        floatRef.current.style.left = `${newX}px`;
        floatRef.current.style.top = `${newY}px`;
      }
      if (panelRef.current) {
        const panelWidth = 380;
        const panelLeft = Math.min(Math.max(newX, 12), window.innerWidth - panelWidth);
        panelRef.current.style.left = `${panelLeft}px`;
        const panelAbove = newY >= 520;
        if (panelAbove) {
          panelRef.current.style.bottom = `${window.innerHeight - newY + 8}px`;
          panelRef.current.style.top = "auto";
        } else {
          panelRef.current.style.top = `${newY + 56}px`;
          panelRef.current.style.bottom = "auto";
        }
      }
    };

    const handleDragEnd = () => {
      if (!dragState.current.dragging) return;
      const wasMoved = dragState.current.moved;
      dragState.current.dragging = false;

      if (floatRef.current) floatRef.current.style.transition = "";
      if (panelRef.current) panelRef.current.style.transition = "";

      if (!wasMoved) {
        setDragging(false);
        return;
      }

      const result = snap(posRef.current.x);
      if (result) {
        snappedRef.current = result.side;
        posRef.current = { x: result.x, y: posRef.current.y };
        setSnapped(result.side);
      } else {
        snappedRef.current = "none";
        setSnapped("none");
      }
      setDragging(false);
      setRenderPos({ ...posRef.current });
      try { localStorage.setItem(POS_KEY, JSON.stringify(posRef.current)); } catch {}
    };

    window.addEventListener("mousemove", handleDragMove);
    window.addEventListener("mouseup", handleDragEnd);
    window.addEventListener("touchmove", handleDragMove, { passive: false });
    window.addEventListener("touchend", handleDragEnd);

    return () => {
      window.removeEventListener("mousemove", handleDragMove);
      window.removeEventListener("mouseup", handleDragEnd);
      window.removeEventListener("touchmove", handleDragMove);
      window.removeEventListener("touchend", handleDragEnd);
    };
  }, []);

  // ── 工具调用处理 ──
  const handleToolCall = useCallback(
    (tc: ToolCallEvent) => {
      const { confirmMode, autoJumpThreshold } = store;

      if (confirmMode === "never") {
        store.appendAssistantChunk("\n\n✅ 已自动跳转。");
        if (tc.route) {
          const target = tc.route.target;
          const params = tc.route.params
            ? "?" + new URLSearchParams(tc.route.params).toString()
            : "";
          router.push(target + params);
        }
        store.setToolCall(null);
        return;
      }

      if (confirmMode === "always") {
        store.setToolCall(tc);
        return;
      }

      if (tc.confidence >= autoJumpThreshold && !tc.require_confirmation) {
        store.appendAssistantChunk("\n\n✅ 已自动跳转。");
        if (tc.route) {
          const target = tc.route.target;
          const params = tc.route.params
            ? "?" + new URLSearchParams(tc.route.params).toString()
            : "";
          router.push(target + params);
        }
        store.setToolCall(null);
        return;
      }

      store.setToolCall(tc);
    },
    [router],
  );

  // ── 发送消息 ──
  const handleSubmit = useCallback(async () => {
    const msg = input.trim();
    if (!msg || streaming) return;

    const convId = store.activeConvId;
    if (!convId) {
      store.appendAssistantChunk("⚠️ 暂未创建对话，请重新打开面板。");
      return;
    }

    setInput("");
    store.addUserMessage(msg);
    store.setStreaming(true);

    // 在发送 SSE 之前，先将用户消息持久化到树
    saveMessageToTreeConv(convId, "user", msg);

    let assistantText = "";

    await send(msg, {
      endpoint: "/api/secretary/agent/chat",
      bodyExtra: {
        current_page: pathname,
        conversation_id: convId,
      },
      onToken: (delta) => {
        assistantText += delta;
        store.appendAssistantChunk(delta);
      },
      onToolCall: (tc) => handleToolCall(tc),
      onConversationId: (id) => store.setConversationId(id),
      onError: (err) => store.appendAssistantChunk(err),
      onDone: async () => {
        store.setStreaming(false);

        // 流完成后，将助手回复持久化到树
        if (assistantText) {
          await saveMessageToTreeConv(convId, "assistant", assistantText);
        }

        // 刷新对话列表（消息计数更新）
        const dirId = store.secretaryDirId;
        if (dirId) {
          const convs = await loadSecretaryConvs(dirId);
          store.setSecretaryConvs(convs);
        }
      },
    });
  }, [input, streaming, pathname, send, handleToolCall, store]);

  const handleAcceptToolCall = () => {
    const tc = store.currentToolCall;
    if (tc?.route) {
      const target = tc.route.target;
      const params = tc.route.params
        ? "?" + new URLSearchParams(tc.route.params).toString()
        : "";
      router.push(target + params);
    }
    store.acceptToolCall();
  };

  const handleRejectToolCall = () => {
    store.rejectToolCall();
  };

  const handleFloatClick = () => {
    if (dragState.current.moved) {
      dragState.current.moved = false;
      return;
    }
    setOpen(!open);
  };

  // 吸附时 hover 恢复完整显示
  const [hovering, setHovering] = useState(false);
  const isSnapped = snapped !== "none";
  const showFull = !isSnapped || hovering || open;

  // 拖动时禁用 transition，避免位置延迟
  const pos = dragging ? posRef.current : renderPos;

  // 当前对话名
  const currentConvName = secretaryConvs.find((c) => c.id === activeConvId)?.name || "秘书对话";

  return (
    <>
      {/* ── 悬浮球按钮 ── */}
      <div
        ref={floatRef}
        onMouseDown={handleDragStart}
        onTouchStart={handleDragStart}
        onClick={handleFloatClick}
        onMouseEnter={() => setHovering(true)}
        onMouseLeave={() => setHovering(false)}
        className={`
          fixed z-50
          w-12 h-12 rounded-full
          flex items-center justify-center
          shadow-lg
          select-none overflow-hidden
          ${dragging ? "" : "transition-all duration-300"}
          ${visible ? "opacity-100" : "opacity-0"}
          ${open
            ? "bg-[var(--color-text-muted)] text-white scale-0 pointer-events-none"
            : "bg-[var(--color-accent)] text-white hover:scale-105 active:scale-95 cursor-grab active:cursor-grabbing"
          }
        `}
        style={{
          opacity: visible ? 1 : 0,
          transition: visible ? "opacity 0.5s ease-in-out, left 0.3s, top 0.3s, transform 0.3s" : "none",
          left: isSnapped
            ? (showFull ? (snapped === "left" ? 8 : pos.x - 16) : pos.x)
            : pos.x,
          top: `${pos.y}px`,
          transform: isSnapped && !showFull
            ? (snapped === "left" ? "scaleX(0.6)" : "scaleX(0.6)")
            : undefined,
          borderRadius: isSnapped && !showFull
            ? (snapped === "left" ? "50% 4px 4px 50%" : "4px 50% 50% 4px")
            : undefined,
        }}
        aria-label="AI 秘书"
      >
        <MessageCircle size={20} />
      </div>

      {/* ── 弹出面板 ── */}
      {open && (
        <div
          ref={panelRef}
          className="fixed z-50
            w-[calc(100vw-2rem)] max-w-[380px] max-h-[480px]
            bg-[var(--color-surface)] border border-[var(--color-border)]
            rounded-xl shadow-2xl flex flex-col overflow-hidden
            right-10"
          style={{
            left: `${Math.min(Math.max(pos.x, 12), window.innerWidth - 380)}px`,
            ...(pos.y >= 520
              ? { bottom: `${Math.max(8, Math.min(window.innerHeight - pos.y + 8, window.innerHeight - 480))}px` }
              : { top: `${pos.y + 56}px` }),
          }}
        >
          {/* ── 头部 — 可拖拽 + 对话切换 ── */}
          <div
            onMouseDown={handlePanelDragStart}
            onTouchStart={handlePanelDragStart}
            className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)] cursor-grab active:cursor-grabbing select-none"
          >
            <div className="flex items-center gap-2 min-w-0">
              {/* 对话选择器 */}
              <div className="relative">
                <button
                  onClick={(e) => { e.stopPropagation(); setShowConvList(!showConvList); }}
                  className="flex items-center gap-1 text-sm font-semibold text-[var(--color-text)] hover:text-[var(--color-accent)] truncate max-w-[180px]"
                >
                  <span className="truncate">{currentConvName}</span>
                  <ChevronDown size={14} className="shrink-0" />
                </button>

                {showConvList && (
                  <div
                    className="absolute top-full left-0 mt-1 w-56 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-xl z-[100] max-h-48 overflow-y-auto"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {loadingSecretary ? (
                      <div className="px-3 py-2 text-xs text-[var(--color-text-muted)]">加载中...</div>
                    ) : secretaryConvs.length === 0 ? (
                      <div className="px-3 py-2 text-xs text-[var(--color-text-muted)]">暂无对话</div>
                    ) : (
                      secretaryConvs.map((conv) => (
                        <button
                          key={conv.id}
                          onClick={() => handleSwitchConv(conv.id)}
                          className={`w-full text-left px-3 py-2 text-sm hover:bg-[var(--color-hover)] truncate ${conv.id === activeConvId ? "bg-[var(--color-accent)]/10 text-[var(--color-accent)]" : "text-[var(--color-text)]"}`}
                        >
                          {conv.name}
                          {conv.messageCount > 0 && (
                            <span className="ml-2 text-xs text-[var(--color-text-muted)]">{conv.messageCount} 条</span>
                          )}
                        </button>
                      ))
                    )}
                    <div className="border-t border-[var(--color-border)]">
                      <button
                        onClick={handleNewConv}
                        className="w-full text-left px-3 py-2 text-sm text-[var(--color-accent)] hover:bg-[var(--color-hover)]"
                      >
                        + 新建对话
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="p-1 rounded text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              aria-label="关闭"
            >
              <X size={16} />
            </button>
          </div>

          {/* ── 消息区域 ── */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            {loadingMessages ? (
              <div className="flex items-center justify-center py-8 text-sm text-[var(--color-text-muted)]">
                加载历史消息...
              </div>
            ) : (
              <ChatMessages
                messages={messages}
                showSpeak
                emptyText="输入学习需求，我来帮你导航"
              />
            )}

            {/* Tool Call 确认卡片 */}
            {currentToolCall && !loadingMessages && (
              <ToolCallConfirmation
                toolCall={currentToolCall}
                onAccept={handleAcceptToolCall}
                onReject={handleRejectToolCall}
              />
            )}
          </div>

          {/* ── 输入区域 ── */}
          <div className="px-4 py-3 border-t border-[var(--color-border)]">
            <ChatInputBar
              input={input}
              onInputChange={setInput}
              onSubmit={handleSubmit}
              loading={streaming || loadingMessages}
              showVoice
              placeholder="输入学习需求…"
            />
          </div>
        </div>
      )}
    </>
  );
}
