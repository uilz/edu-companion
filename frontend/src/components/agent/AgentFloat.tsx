"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";
import { MessageCircle, X } from "lucide-react";
import { getAgentStore, type ToolCallEvent } from "@/store/agent/agent-store";
import { useChatStream } from "@/components/chat-shared/useChatStream";
import ChatMessages from "@/components/chat-shared/ChatMessages";
import ChatInputBar from "@/components/chat-shared/ChatInputBar";
import ToolCallConfirmation from "@/components/chat-shared/ToolCallConfirmation";

export default function AgentFloat() {
  const pathname = usePathname();
  const router = useRouter();
  const store = getAgentStore();
  const { streaming, send } = useChatStream();

  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  // ── 拖动状态 ──
  const floatRef = useRef<HTMLDivElement>(null);
  const dragState = useRef({
    dragging: false,
    moved: false,
    startX: 0,
    startY: 0,
    startLeft: 0,
    startTop: 0,
  });

  // 位置持久化 & 吸附
  const SNAP_THRESHOLD = 30; // 距边缘多少像素内视为吸附
  const POS_KEY = "agent-float-pos";

  const loadPos = (): { x: number; y: number } | null => {
    try {
      const saved = localStorage.getItem(POS_KEY);
      if (saved) return JSON.parse(saved);
    } catch {}
    return null;
  };

  const [pos, setPos] = useState<{ x: number; y: number }>(() => {
    const saved = loadPos();
    if (saved) return saved;
    return { x: typeof window !== "undefined" ? window.innerWidth - 64 : 0, y: typeof window !== "undefined" ? window.innerHeight - 200 : 0 };
  });

  // 是否吸附到边缘
  const [snapped, setSnapped] = useState<"none" | "left" | "right">(() => {
    const saved = loadPos();
    if (!saved) return "right";
    if (saved.x <= SNAP_THRESHOLD) return "left";
    if (saved.x >= window.innerWidth - 48 - SNAP_THRESHOLD) return "right";
    return "none";
  });

  // 吸附到最近的左/右边缘 — 仅当靠近边缘时吸附
  const EDGE_ZONE = 60; // 距边缘多少像素内触发吸附
  const snap = (x: number): { x: number; side: "left" | "right" } | null => {
    const vw = window.innerWidth;
    if (x < EDGE_ZONE) return { x: -24, side: "left" };
    if (x > vw - 48 - EDGE_ZONE) return { x: vw - 24, side: "right" };
    return null; // 不靠近边缘，不吸附
  };

  // 登录页不显示悬浮球
  if (pathname === "/login") return null;

  // 加载用户偏好
  useEffect(() => {
    fetch("/api/secretary/agent/preferences")
      .then((r) => r.json())
      .then((data) => {
        if (data.confirm_mode) store.setConfirmMode(data.confirm_mode);
        if (data.auto_jump_threshold !== undefined) {
          store.setAutoJumpThreshold(data.auto_jump_threshold);
        }
      })
      .catch(() => { /* 使用默认偏好 */ });
  }, []);

  // ── 拖动事件 ──
  const handleDragStart = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      // 阻止默认行为，防止文本选中
      e.preventDefault();
      const clientX = "touches" in e ? e.touches[0].clientX : e.clientX;
      const clientY = "touches" in e ? e.touches[0].clientY : e.clientY;

      // 如果当前吸附，先脱离吸附，调整到完全可见位置
      let adjustedX = pos.x;
      if (snapped === "left") adjustedX = 8;
      else if (snapped === "right") adjustedX = window.innerWidth - 56;
      if (adjustedX !== pos.x) {
        setPos({ x: adjustedX, y: pos.y });
      }
      setSnapped("none");

      dragState.current = {
        dragging: true,
        moved: false,
        startX: clientX,
        startY: clientY,
        startLeft: adjustedX,
        startTop: pos.y,
      };
    },
    [pos, snapped],
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

      setPos({ x: newX, y: newY });
    };

    const handleDragEnd = () => {
      if (!dragState.current.dragging) return;
      const wasMoved = dragState.current.moved;
      dragState.current.dragging = false;

      if (!wasMoved) {
        // 没有移动，视为点击
        return;
      }

      // 吸附到边缘（仅靠近边缘时）
      setPos((prev) => {
        const result = snap(prev.x);
        if (result) {
          setSnapped(result.side);
          const s = { x: result.x, y: prev.y };
          try { localStorage.setItem(POS_KEY, JSON.stringify(s)); } catch {}
          return s;
        }
        // 不靠近边缘，保持自由位置
        setSnapped("none");
        try { localStorage.setItem(POS_KEY, JSON.stringify(prev)); } catch {}
        return prev;
      });
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

    setInput("");
    store.addUserMessage(msg);
    store.setStreaming(true);

    await send(msg, {
      endpoint: "/api/secretary/agent/chat",
      bodyExtra: {
        current_page: pathname,
        conversation_id: store.conversationId,
      },
      onToken: (delta) => store.appendAssistantChunk(delta),
      onToolCall: (tc) => handleToolCall(tc),
      onConversationId: (id) => store.setConversationId(id),
      onError: (err) => store.appendAssistantChunk(err),
      onDone: () => store.setStreaming(false),
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
    // 如果刚拖动完，不触发点击
    if (dragState.current.moved) {
      dragState.current.moved = false;
      return;
    }
    setOpen(!open);
  };

  // 焦点管理
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  // 吸附时 hover 恢复完整显示
  const [hovering, setHovering] = useState(false);
  const isSnapped = snapped !== "none";
  const showFull = !isSnapped || hovering || open;

  return (
    <>
      {/* 悬浮球按钮 — 可拖动，吸附时贴边只露一半 */}
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
          shadow-lg transition-all duration-300
          select-none overflow-hidden
          ${open
            ? "bg-[var(--color-text-muted)] text-white scale-0 pointer-events-none"
            : "bg-[var(--color-accent)] text-white hover:scale-105 active:scale-95 cursor-grab active:cursor-grabbing"
          }
        `}
        style={{
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

      {/* 弹出面板 — 跟随悬浮球位置 */}
      {open && (
        <div
          className="fixed z-50
            w-[calc(100vw-2rem)] max-w-[380px] max-h-[480px]
            bg-[var(--color-surface)] border border-[var(--color-border)]
            rounded-xl shadow-2xl flex flex-col overflow-hidden
            animate-in slide-in-from-bottom-4 duration-200"
          style={{
            left: `${Math.min(snapped === "left" ? 12 : pos.x, window.innerWidth - 400)}px`,
            bottom: `${window.innerHeight - pos.y + 8}px`,
          }}
        >
          {/* 头部 */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
            <span className="text-sm font-semibold text-[var(--color-text)]">
              AI 秘书
            </span>
            <button
              onClick={() => setOpen(false)}
              className="p-1 rounded text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              aria-label="关闭"
            >
              <X size={16} />
            </button>
          </div>

          {/* 消息区域 */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            <ChatMessages
              messages={store.messages}
              showSpeak
              emptyText="输入学习需求，我来帮你导航"
            />

            {/* Tool Call 确认卡片 */}
            {store.currentToolCall && (
              <ToolCallConfirmation
                toolCall={store.currentToolCall}
                onAccept={handleAcceptToolCall}
                onReject={handleRejectToolCall}
              />
            )}
          </div>

          {/* 输入区域 */}
          <div className="px-4 py-3 border-t border-[var(--color-border)]">
            <ChatInputBar
              input={input}
              onInputChange={setInput}
              onSubmit={handleSubmit}
              loading={streaming}
              showVoice
              placeholder="输入学习需求…"
            />
          </div>
        </div>
      )}
    </>
  );
}