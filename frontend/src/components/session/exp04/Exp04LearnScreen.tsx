// ============================================================
// EXP-04 V3 · LEARN Screen — 全屏对话流
//
// 对齐 Vision (preview.html) 的 learn 阶段：
//   1. AI 逐条打字发送学习内容（带打字动画）
//   2. 对话区显示建议词条 pill（"为什么？""举个例子""我懂了"）
//   3. 用户可自由输入 / 点击 pill → AI 流式回复
//   4. 2+ 轮对话后 AI 主动引导"去练习"
//   5. 底部内嵌输入栏（非悬浮按钮）
//
// V4 升级：复用项目已有对话基础设施
//   - Virtuoso 虚拟滚动（替代原生 div 滚动）
//   - MarkdownRenderer 富文本渲染（替代纯文本）
//   - textarea 多行输入（替代单行 input）
// ============================================================

"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Virtuoso, type VirtuosoHandle } from "react-virtuoso";
import { Send, Loader2 } from "lucide-react";
import { createConversationEngine } from "@/lib/exp04/conversation-engine";
import { useInactivityDetection } from "@/lib/exp04/useInactivityDetection";
import { sendChatMessage } from "@/lib/exp04/session-chat-api";
import MarkdownRenderer from "@/components/conversation/blocks/MarkdownRenderer";
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
  isTyping?: boolean;
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
  onReflect?: () => void;
  onToolNudge?: () => void;
}

// ── 构建 AI 引导消息 ──

function buildIntroMessages(mission: { title: string; steps: MissionStep[] } | null): string[] {
  const topic = mission?.title || "今天的内容";
  const msgs: string[] = [];

  msgs.push(`今天我们一起来看看「${topic}」。`);

  if (mission?.steps?.length) {
    const explainSteps = mission.steps
      .sort((a, b) => a.order - b.order)
      .filter((s) => s.description?.trim());
    for (const step of explainSteps.slice(0, 2)) {
      msgs.push(step.description.trim());
    }
  }

  return msgs;
}

// ── 构建上下文建议词条 ──

function buildSuggestions(mission: { title: string } | null): string[] {
  const topic = mission?.title || "这个";
  return [
    `为什么${topic}是这样？`,
    "能举个具体例子吗",
    "我懂了",
  ];
}

const PROGRESSION_SUGGESTIONS = ["去练习"];

// ══════════════════════════════════════════════════════════════

export default function Exp04LearnScreen({
  engine,
  currentState,
  mission,
  onValidate,
  onStateTransition,
  transitioning,
  sessionId,
  convId,
  onReflect,
  onToolNudge,
}: LearnScreenProps) {
  // ── 对话状态 ──
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const chatRoundCount = useRef(0);
  const sendingRef = useRef(false);
  const virtuosoRef = useRef<VirtuosoHandle>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const introStarted = useRef(false);
  const nudgeTriggeredRef = useRef(false);

  // ── 停留检测 ──
  const handleCognitiveSearch = useCallback(() => {
    onStateTransition({ type: "INACTIVITY_DETECTED" });
  }, [onStateTransition]);
  const handleResume = useCallback(() => {
    onStateTransition({ type: "INTERACTION_RESUMED" });
  }, [onStateTransition]);

  useInactivityDetection({
    onCognitiveSearch: handleCognitiveSearch,
    onResume: handleResume,
    enabled: currentState === "LEARN" || currentState === "COGNITIVE_SEARCH",
    isInCognitiveSearch: currentState === "COGNITIVE_SEARCH",
  });

  const isCognitive = currentState === "COGNITIVE_SEARCH";

  // ── textarea 自适应高度 ──
  const autoResizeTextarea = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }, []);

  useEffect(() => {
    autoResizeTextarea();
  }, [input, autoResizeTextarea]);

  // ── 播放引导消息 ──
  useEffect(() => {
    if (introStarted.current) return;
    introStarted.current = true;

    const introMsgs = buildIntroMessages(mission);
    if (introMsgs.length === 0) {
      setSuggestions(buildSuggestions(mission));
      return;
    }

    const playNext = (idx: number) => {
      if (idx >= introMsgs.length) {
        setSuggestions(buildSuggestions(mission));
        return;
      }

      const text = introMsgs[idx];
      const msgId = `intro-${idx}-${Date.now()}`;

      setMessages((prev) => [...prev, { id: msgId, role: "assistant", content: "", isTyping: true }]);

      let charIdx = 0;
      const typeInterval = setInterval(() => {
        charIdx++;
        setMessages((prev) => {
          const copy = [...prev];
          const target = copy.find((m) => m.id === msgId);
          if (target) {
            target.content = text.slice(0, charIdx);
            if (charIdx >= text.length) {
              target.isTyping = false;
            }
          }
          return copy;
        });

        if (charIdx >= text.length) {
          clearInterval(typeInterval);
          setTimeout(() => playNext(idx + 1), 500);
        }
      }, 25);
    };

    setTimeout(() => playNext(0), 400);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 发送消息 ──
  const appendAndSend = useCallback(
    (text: string) => {
      if (sendingRef.current) return;
      sendingRef.current = true;

      const userMsg: ChatMsg = { id: `u-${Date.now()}`, role: "user", content: text };
      const placeholderId = `ai-${Date.now()}`;

      setMessages((prev) => [...prev, userMsg, { id: placeholderId, role: "assistant", content: "", isTyping: true }]);
      chatRoundCount.current += 1;

      const onChunk = (chunk: string) => {
        setMessages((prev) => {
          const copy = [...prev];
          const last = copy[copy.length - 1];
          if (last?.id === placeholderId) {
            copy[copy.length - 1] = { ...last, content: last.content + chunk, isTyping: true };
          }
          return copy;
        });
      };

      const finishWithProgression = () => {
        setMessages((prev) => {
          const copy = [...prev];
          const last = copy[copy.length - 1];
          if (last?.id === placeholderId) {
            copy[copy.length - 1] = { ...last, isTyping: false };
          }
          return copy;
        });

        if (chatRoundCount.current >= 2) {
          if (onToolNudge && !nudgeTriggeredRef.current) {
            nudgeTriggeredRef.current = true;
            onToolNudge();
          }
          setTimeout(() => {
            setMessages((prev) => [
              ...prev,
              {
                id: `nudge-${Date.now()}`,
                role: "assistant",
                content: "这个概念有点抽象。要不要把它在画布上摆开看？",
                isTyping: false,
              },
            ]);
            setSuggestions(["去练习", "打开画布看看", "今天就到这里"]);
          }, 800);
        } else {
          setSuggestions(buildSuggestions(mission));
        }
        sendingRef.current = false;
      };

      const onError = () => {
        setMessages((prev) => prev.filter((m) => m.id !== placeholderId));

        const engineOutput = engine.process(currentState as "LEARN", "USER_MESSAGE", text);
        if (engineOutput.shouldSpeak && engineOutput.message) {
          setMessages((prev) => [
            ...prev,
            { id: `ai-local-${Date.now()}`, role: "assistant", content: engineOutput.message },
          ]);
        }
        finishWithProgression();
      };

      if (convId && sessionId) {
        sendChatMessage(convId, sessionId, text, {
          onChunk,
          onDone: () => {
            setMessages((prev) => {
              const copy = [...prev];
              const last = copy[copy.length - 1];
              if (last?.id === placeholderId) {
                copy[copy.length - 1] = { ...last, isTyping: false };
              }
              return copy;
            });
            finishWithProgression();
          },
          onError,
        });
      } else {
        const engineOutput = engine.process(currentState as "LEARN", "USER_MESSAGE", text);
        setMessages((prev) => {
          const withoutPlaceholder = prev.filter((m) => m.id !== placeholderId);
          return engineOutput.shouldSpeak && engineOutput.message
            ? [...withoutPlaceholder, { id: `ai-local-${Date.now()}`, role: "assistant", content: engineOutput.message }]
            : withoutPlaceholder;
        });
        finishWithProgression();
      }
    },
    [convId, sessionId, engine, currentState, mission, onToolNudge],
  );

  // ── 处理建议词条点击 ──
  const handleSuggestionClick = useCallback(
    (text: string) => {
      if (text === "去练习") {
        onValidate();
        return;
      }
      if (text === "今天就到这里" && onReflect) {
        onReflect();
        return;
      }
      if (text === "打开画布看看") {
        setSuggestions([]);
        appendAndSend(text);
        return;
      }
      setSuggestions([]);
      appendAndSend(text);
    },
    [onValidate, onReflect, appendAndSend],
  );

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed) return;
    setInput("");
    setSuggestions([]);
    appendAndSend(trimmed);
  }, [input, appendAndSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  // ── Virtuoso itemContent ──
  const itemContent = useCallback(
    (_index: number, msg: ChatMsg) => <ChatBubble key={msg.id} msg={msg} />,
    [],
  );

  // ── Virtuoso Footer: 认知搜索提示 ──
  const Footer = useCallback(() => {
    if (!isCognitive) return null;
    return (
      <div className="flex justify-start px-5 pb-2">
        <div className="max-w-[85%] px-4 py-3 rounded-2xl rounded-bl-md bg-[#FFF6E8] text-sm text-[#A96F00] leading-relaxed">
          你好像在想什么。没关系，不用着急——想到了随时可以告诉我。
        </div>
      </div>
    );
  }, [isCognitive]);

  // ── Empty placeholder ──
  const EmptyPlaceholder = useCallback(() => {
    if (messages.length > 0) return null;
    return (
      <div className="flex items-center justify-center h-full text-ink-muted text-sm">
        苹果果正在准备今天的内容...
      </div>
    );
  }, [messages.length]);

  return (
    <div className="flex flex-col h-full">
      {/* ── 消息列表（Virtuoso 虚拟滚动）── */}
      <div className="flex-1 min-h-0">
        <Virtuoso
          ref={virtuosoRef}
          style={{ height: "100%" }}
          data={messages}
          itemContent={itemContent}
          followOutput="smooth"
          overscan={200}
          components={{
            Footer,
            EmptyPlaceholder,
          }}
          className="scrollbar-thin"
        />
      </div>

      {/* ── 建议词条 ── */}
      {suggestions.length > 0 && !isCognitive && (
        <div className="flex gap-2 flex-wrap px-5 pb-2 max-w-lg mx-auto w-full">
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => handleSuggestionClick(s)}
              className={`px-3.5 py-2 rounded-full text-[13px] transition-colors ${
                s === "去练习"
                  ? "bg-[#F4B400]/10 border border-[#F4B400]/40 text-[#C79100] font-semibold hover:bg-[#F4B400]/20"
                  : "bg-surface border border-border/60 text-ink-secondary hover:border-ink-muted hover:text-ink-primary"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* ── 输入栏（textarea 多行）── */}
      <div className="border-t border-border/50 px-5 py-3 bg-page/95 backdrop-blur">
        <div className="max-w-lg mx-auto flex items-end gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isCognitive ? "想到了什么？" : "问苹果果……"}
            disabled={sendingRef.current}
            rows={1}
            className="flex-1 resize-none px-4 py-2.5 text-sm rounded-xl bg-surface border border-border/60 outline-none focus:border-[#F4B400] transition-colors disabled:opacity-50 placeholder:text-ink-muted leading-relaxed max-h-[120px]"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || sendingRef.current}
            className="w-10 h-10 rounded-full bg-[#F4B400] text-white flex items-center justify-center flex-shrink-0 disabled:opacity-40 hover:bg-[#e5a800] transition-colors mb-0.5"
          >
            {sendingRef.current ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Send size={16} />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 消息气泡子组件 ──

function ChatBubble({ msg }: { msg: ChatMsg }) {
  const isAI = msg.role === "assistant";
  const hasContent = msg.content.length > 0;

  return (
    <div className={`flex gap-2.5 px-5 py-1.5 ${isAI ? "justify-start" : "justify-end"}`}>
      {/* AI 头像 */}
      {isAI && (
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#c4a3d4] to-[#7a5a8c] flex items-center justify-center flex-shrink-0 text-xs font-semibold text-white mt-1">
          🍎
        </div>
      )}

      {/* 气泡 */}
      <div
        className={`max-w-[80%] px-4 py-2.5 text-[15px] leading-relaxed ${
          isAI
            ? "bg-[#f7f3ea] rounded-bl-md rounded-2xl"
            : "bg-[#ebe7dd] rounded-br-md rounded-2xl"
        }`}
      >
        {hasContent ? (
          <>
            <MarkdownRenderer content={msg.content} />
            {msg.isTyping && <span className="typing-cursor" />}
          </>
        ) : msg.isTyping ? (
          <ThinkingDots />
        ) : (
          "…"
        )}
      </div>

      {/* 用户头像 */}
      {!isAI && (
        <div className="w-7 h-7 rounded-lg bg-[#0a84ff] flex items-center justify-center flex-shrink-0 text-xs font-semibold text-white mt-1">
          你
        </div>
      )}
    </div>
  );
}

// ── 思考中三点跳动 ──

function ThinkingDots() {
  return (
    <span className="inline-flex gap-1 items-end h-5">
      <span className="w-1.5 h-1.5 rounded-full bg-ink-muted animate-bounce" style={{ animationDelay: "0ms" }} />
      <span className="w-1.5 h-1.5 rounded-full bg-ink-muted animate-bounce" style={{ animationDelay: "150ms" }} />
      <span className="w-1.5 h-1.5 rounded-full bg-ink-muted animate-bounce" style={{ animationDelay: "300ms" }} />
    </span>
  );
}
