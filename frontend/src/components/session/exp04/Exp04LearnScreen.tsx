// ============================================================
// EXP-04 V2 · LEARN Screen
//
// "一本书正在陪你学习" — 全屏阅读体验
//
// V2 设计：
//   - 书页式阅读（干净、留白、居中）
//   - AI 默认沉默（P6）
//   - 💬 悬浮按钮（右下角，圆形，不打扰）
//   - 💬 点击展开迷你对话浮层
//   - 保留停留检测（COGNITIVE_SEARCH）
//   - 底部"验证理解"按钮
// ============================================================

"use client";

import { useState, useRef, useEffect, useMemo, useCallback } from "react";
import { Loader2, MessageCircle, X, Send, Sparkles } from "lucide-react";
import { createConversationEngine } from "@/lib/exp04/conversation-engine";
import { useInactivityDetection } from "@/lib/exp04/useInactivityDetection";
import { logMechanismEvent } from "@/lib/exp04/mechanism-logger";
import { sendChatMessage } from "@/lib/exp04/session-chat-api";
import type { Exp04State, StateEvent } from "@/lib/exp04/types";

// ── Types ──

interface MissionStep {
  order: number;
  description: string;
  type: "explain" | "practice" | "review";
}

interface ChatMsg {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface LearnScreenProps {
  engine: ReturnType<typeof createConversationEngine>;
  currentState: Exp04State;
  mission: { title: string; steps: MissionStep[] } | null;
  onValidate: () => void;
  onStateTransition: (event: StateEvent) => void;
  transitioning: boolean;
  sessionId?: string;
  convId?: string | null;
}

// ── 学习内容（从 Mission 步骤生成阅读内容） ──

function readingContentFromMission(mission: { title: string; steps: MissionStep[] } | null): string[] {
  if (!mission?.steps?.length) return [];
  return mission.steps
    .sort((a, b) => a.order - b.order)
    .map((s) => s.description)
    .filter(Boolean);
}

// ── 组件 ──

export default function Exp04LearnScreen({
  engine,
  currentState,
  mission,
  onValidate,
  onStateTransition,
  transitioning,
  sessionId,
  convId,
}: LearnScreenProps) {
  // ── 聊天状态 ──
  const [chatOpen, setChatOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const chatRoundCount = useRef(0);
  const sendingRef = useRef(false);

  // ── 停留检测 ──
  const inactivityTimedOut = useRef(false);
  const handleInactive = useCallback(() => {
    inactivityTimedOut.current = true;
    onStateTransition("INACTIVITY_DETECTED");
  }, [onStateTransition]);
  const handleResumed = useCallback(() => {
    onStateTransition("INTERACTION_RESUMED");
  }, [onStateTransition]);

  useInactivityDetection({
    onInactive: handleInactive,
    onResumed: handleResumed,
  });

  // ── 阅读内容 ──
  const contentLines = readingContentFromMission(mission);

  // ── 默认阅读内容 ──
  const fallbackContent = [
    "TCP 在发送真正的数据之前，",
    "双方需要先确认：",
    "你能收到吗？",
    "我能收到吗？",
    "我们现在开始。",
    "",
    "这三个动作，",
    "共同组成了大家熟悉的",
    "Three-way Handshake。",
  ];

  const displayContent = contentLines.length > 0 ? contentLines : fallbackContent;

  // ── 发送消息 ──
  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || chatRoundCount.current >= 1 || sendingRef.current) return;
    sendingRef.current = true;

    const userMsg: ChatMsg = { id: `u-${Date.now()}`, role: "user", content: trimmed };
    const placeholderId = `ai-${Date.now()}`;

    setMessages((prev) => [...prev, userMsg, { id: placeholderId, role: "assistant", content: "" }]);
    setInput("");
    chatRoundCount.current += 1;

    if (convId && sessionId) {
      sendChatMessage(convId, sessionId, trimmed, {
        onChunk: (chunk) => {
          setMessages((prev) => {
            const copy = [...prev];
            const last = copy[copy.length - 1];
            if (last?.id === placeholderId) copy[copy.length - 1] = { ...last, content: last.content + chunk };
            return copy;
          });
        },
        onDone: () => { sendingRef.current = false; },
        onError: () => {
          setMessages((prev) => {
            const withoutPlaceholder = prev.filter((m) => m.id !== placeholderId);
            const engineOutput = engine.process(currentState, "USER_MESSAGE", trimmed);
            return engineOutput.shouldSpeak && engineOutput.message
              ? [...withoutPlaceholder, { id: `ai-local-${Date.now()}`, role: "assistant" as const, content: engineOutput.message }]
              : withoutPlaceholder;
          });
          sendingRef.current = false;
        },
      });
    } else {
      const engineOutput = engine.process(currentState, "USER_MESSAGE", trimmed);
      setMessages((prev) => {
        const withoutPlaceholder = prev.filter((m) => m.id !== placeholderId);
        return engineOutput.shouldSpeak && engineOutput.message
          ? [...withoutPlaceholder, { id: `ai-local-${Date.now()}`, role: "assistant", content: engineOutput.message }]
          : withoutPlaceholder;
      });
      sendingRef.current = false;
    }
  }, [input, convId, sessionId, engine, currentState]);

  // ── 认知搜索状态 ──
  const isCognitive = currentState === "COGNITIVE_SEARCH";

  return (
    <div className="min-h-screen bg-page flex flex-col">
      {/* ── 阅读区 ── */}
      <div className="flex-1 overflow-auto">
        <div className="max-w-lg mx-auto px-5 pt-12 pb-24">
          {/* 标题 */}
          {mission?.title && (
            <h1 className="text-xl font-semibold text-ink-primary mb-8 tracking-tight">
              {mission.title}
            </h1>
          )}

          {/* 阅读内容 */}
          <div className="text-[20px] leading-[2] text-ink-primary">
            {displayContent.map((line, i) => {
              if (!line) return <br key={i} />;
              const isHighlight = line.includes("你能收到") || line.includes("我能收到") || line.includes("我们现在开始") || line.includes("Three-way");
              return (
                <span key={i}>
                  {isHighlight ? (
                    <span className="bg-[#fff0cc] px-1.5 py-0.5 rounded">{line}</span>
                  ) : (
                    line
                  )}
                  <br />
                </span>
              );
            })}
          </div>

          {/* 认知搜索提示 */}
          {isCognitive && (
            <div className="mt-8 p-4 rounded-xl bg-[#FFF6E8]/60 border border-[#FFF6E8]">
              <p className="text-sm text-[#A96F00] leading-relaxed">
                你好像在想什么。没关系，不用着急——如果想到了什么，可以点击右下角的 💬 告诉我。
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ── 底部操作栏 ── */}
      <div className="border-t border-border/50 px-5 py-4 bg-page/95 backdrop-blur">
        <div className="max-w-lg mx-auto">
          <button
            onClick={onValidate}
            disabled={transitioning}
            className="w-full h-14 rounded-xl bg-[#F4B400] text-white text-base font-semibold hover:bg-[#e5a800] transition-colors disabled:opacity-50"
          >
            {transitioning ? "准备中…" : "验证理解"}
          </button>
        </div>
      </div>

      {/* ── 💬 悬浮按钮 ── */}
      {!chatOpen && (
        <button
          onClick={() => setChatOpen(true)}
          className="fixed bottom-24 right-5 w-14 h-14 rounded-full bg-[#F4B400] text-white shadow-lg flex items-center justify-center hover:bg-[#e5a800] transition-all active:scale-95 z-40"
          aria-label="问苹果果"
        >
          <MessageCircle size={24} />
        </button>
      )}

      {/* ── 💬 迷你对话浮层 ── */}
      {chatOpen && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          {/* 背景遮罩 */}
          <div className="absolute inset-0 bg-black/20" onClick={() => setChatOpen(false)} />

          {/* 浮层 */}
          <div className="relative w-full max-w-md mx-4 mb-4 sm:mb-0 bg-white rounded-2xl shadow-xl border border-border/50 overflow-hidden max-h-[60vh] flex flex-col">
            {/* 头部 */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border/40">
              <span className="text-sm font-medium text-ink-primary">💬 问苹果果</span>
              <button onClick={() => setChatOpen(false)} className="p-1 rounded text-ink-muted hover:text-ink-primary">
                <X size={18} />
              </button>
            </div>

            {/* 消息列表 */}
            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-[200px] max-h-[300px]">
              {messages.length === 0 && (
                <p className="text-xs text-ink-muted text-center pt-8">有什么想知道的？</p>
              )}
              {messages.map((msg) => (
                <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[80%] px-3.5 py-2 rounded-xl text-sm leading-relaxed ${
                      msg.role === "user"
                        ? "bg-[#F4B400] text-white rounded-br-md"
                        : "bg-surface text-ink-primary rounded-bl-md"
                    }`}
                  >
                    {msg.content || (msg.role === "assistant" ? "..." : "")}
                  </div>
                </div>
              ))}
              {chatRoundCount.current >= 1 && (
                <p className="text-xs text-ink-muted text-center pt-2">已经聊过一轮了。</p>
              )}
            </div>

            {/* 输入 */}
            {chatRoundCount.current < 1 && (
              <div className="border-t border-border/40 px-3 py-2 flex gap-2">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSend()}
                  placeholder="输入你的问题…"
                  className="flex-1 px-3 py-2 text-sm rounded-lg bg-page border border-border/60 outline-none focus:border-[#F4B400] transition-colors"
                />
                <button
                  onClick={handleSend}
                  disabled={!input.trim()}
                  className="p-2 rounded-lg bg-[#F4B400] text-white disabled:opacity-40 hover:bg-[#e5a800] transition-colors"
                >
                  <Send size={16} />
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
