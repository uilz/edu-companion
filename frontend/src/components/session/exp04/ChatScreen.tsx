"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import type { Exp04State, SessionMode } from "@/lib/exp04/types";
import type { ToolKey } from "./ToolTray";
import StuckBanner from "./StuckBanner";
import BreakthroughCelebration from "./BreakthroughCelebration";
import ConceptCard from "./ConceptCard";
import PracticeInlineCard from "./PracticeInlineCard";

// ── 模拟练习题目 ──
const MOCK_QUESTION = {
  stem: "当你在学习一个新概念时，最有效的方式是什么？",
  options: [
    { letter: "A", text: "反复阅读教科书", is_correct: false },
    { letter: "B", text: "用自己的话解释给别人听", is_correct: true },
    { letter: "C", text: "做很多练习题", is_correct: false },
    { letter: "D", text: "看视频教程", is_correct: false },
  ],
  hint: "试试以教为学的方法——如果你能讲清楚，才是真理解。",
};

interface ChatScreenProps {
  engine: any;
  currentState: Exp04State;
  mission: { title: string } | null;
  lastTitle: string | null;
  onTransition: (event: any) => void;
  onSetMode: (mode: SessionMode) => void;
  onOpenTool: (tool: ToolKey) => void;
  sessionId?: string;
}

export default function ChatScreen({
  engine,
  currentState,
  mission,
  lastTitle,
  onTransition,
  onSetMode,
  onOpenTool,
  sessionId,
}: ChatScreenProps) {
  const [messages, setMessages] = useState<Array<{ role: "ai" | "user"; text: string }>>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [learnTurn, setLearnTurn] = useState(0);
  const [typing, setTyping] = useState(false);

  // Mode 检测状态
  const [showStuckBanner, setShowStuckBanner] = useState(false);
  const [showBreakthrough, setShowBreakthrough] = useState(false);
  const [showConceptCard, setShowConceptCard] = useState(false);
  const [showPractice, setShowPractice] = useState(false);

  const msgListRef = useRef<HTMLDivElement>(null);
  const inactivityTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const userMsgCount = useRef(0);

  // ── 滚动到底部 ──
  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      if (msgListRef.current) {
        msgListRef.current.scrollTop = msgListRef.current.scrollHeight;
      }
    });
  }, []);

  // ── 添加 AI 消息（打字动画） ──
  const appendAiMessage = useCallback((text: string, done?: () => void) => {
    setMessages((prev) => [...prev, { role: "ai", text: "" }]);
    setTyping(true);

    // 模拟打字动画：逐个字符显示
    let index = 0;
    const interval = setInterval(() => {
      index += 2;
      if (index >= text.length) {
        clearInterval(interval);
        setMessages((prev) => {
          const copy = [...prev];
          copy[copy.length - 1] = { ...copy[copy.length - 1], text };
          return copy;
        });
        setTyping(false);
        scrollToBottom();
        done?.();
      } else {
        setMessages((prev) => {
          const copy = [...prev];
          copy[copy.length - 1] = { role: "ai", text: text.slice(0, index) + "|" };
          return copy;
        });
        scrollToBottom();
      }
    }, 25);
  }, [scrollToBottom]);

  // ── 添加用户消息 ──
  const appendUserMessage = useCallback((text: string) => {
    setMessages((prev) => [...prev, { role: "user", text }]);
    userMsgCount.current += 1;
    scrollToBottom();
  }, [scrollToBottom]);

  // ── 模式检测 ──
  const detectMode = useCallback(() => {
    if (showStuckBanner || showBreakthrough) return; // 已经显示

    if (learnTurn >= 3 && currentState.mode === "normal") {
      // 用户追问轮次 >= 3 → deep_chat
      onSetMode("deep_chat");
      setSuggestions(["为什么？", "举个例子", "那如果……", "差不多了"]);
    }

    // silent 检测（此 demo 版本中由外部控制，通过 onSetMode 手动触发）
  }, [learnTurn, currentState.mode, showStuckBanner, showBreakthrough, onSetMode]);

  // ── 发送消息 ──
  const handleSend = useCallback((text: string) => {
    if (!text.trim() || typing) return;
    appendUserMessage(text);
    setSuggestions([]);
    setInputValue("");

    const newTurn = learnTurn + 1;
    setLearnTurn(newTurn);

    // 重置停留计时器
    if (inactivityTimer.current) clearTimeout(inactivityTimer.current);

    // AI 回复
    const defaultReplies: Record<string, string> = {
      default: "这个问题很有意思。让我想想……从你的角度看，你觉得这背后是什么原理？",
      "为什么？": "好的问题。让我换个角度解释——当你理解了背后的动机，一切就变得清晰了。",
      "举个例子": "比如现实生活中的一个简单例子……这样看是不是清楚多了？",
      "我懂了": "太好了。那你觉得这个想法还能用在什么地方？",
      "差不多了": "好的，那我们来检验一下理解？",
    };

    const reply = defaultReplies[text] || defaultReplies.default;
    appendAiMessage(reply, () => {
      detectMode();
      setSuggestions(["为什么？", "举个例子", "我懂了", "差不多了"]);
    });

    // 重新启动停留计时器（90s 后 stuck → 显示 stuck 横幅）
    inactivityTimer.current = setTimeout(() => {
      if (currentState.mode === "normal" || currentState.mode === "deep_chat") {
        onSetMode("stuck");
        setShowStuckBanner(true);
      }
    }, 90_000);
  }, [appendUserMessage, appendAiMessage, typing, learnTurn, detectMode, currentState, onSetMode]);

  // ── 处理建议词条点击 ──
  const handleSuggestionClick = useCallback((suggestion: string) => {
    handleSend(suggestion);
  }, [handleSend]);

  // ── 练习入口回调 ──
  const handleStartPractice = useCallback(() => {
    setShowPractice(true);
    onTransition({ type: "PRACTICE_STARTED" });
  }, [onTransition]);

  const handlePracticeDone = useCallback((correct: boolean) => {
    onTransition({ type: "PRACTICE_DONE", correct });
    if (showStuckBanner && correct) {
      // stuck 后答对 → breakthrough
      setShowStuckBanner(false);
      setShowBreakthrough(true);
      onSetMode("breakthrough");
    }
  }, [onTransition, showStuckBanner, onSetMode]);

  const handlePracticeComplete = useCallback(() => {
    setShowBreakthrough(false);
    onSetMode("normal");
    setSuggestions(["再聊聊这个主题", "差不多了"]);
  }, [onSetMode]);

  const handleCreateCard = useCallback(() => {
    onTransition({ type: "FLASHCARD_CREATED" });
  }, [onTransition]);

  // ── StuckBanner 操作 ──
  const handleStuckAction = useCallback((action: "retry" | "canvas" | "reflect") => {
    setShowStuckBanner(false);
    if (action === "reflect") {
      onTransition({ type: "REFLECTION_REQUESTED" });
      return;
    }
    if (action === "canvas") {
      onOpenTool("canvas");
      return;
    }
    // retry: AI 换角度再讲
    appendAiMessage("好，那我们换个角度。");

    // stuck → normal
    onSetMode("normal");
  }, [appendAiMessage, onSetMode, onOpenTool, onTransition]);

  // ── 初始化：AI 第一句问候 ──
  useEffect(() => {
    const greeting = lastTitle
      ? `上次我们就停在这里。今天继续。从哪里开始？`
      : `今天我们聊聊${mission?.title || '一个新话题'}。准备好了吗？`;
    appendAiMessage(greeting, () => {
      setSuggestions(["为什么？", "举个例子", "我懂了", "差不多了"]);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── 清理停留计时器 ──
  useEffect(() => {
    return () => {
      if (inactivityTimer.current) clearTimeout(inactivityTimer.current);
    };
  }, []);

  return (
    <div className="min-h-screen bg-page flex flex-col">
      {/* 对话区 */}
      <div className="flex-1 overflow-auto" ref={msgListRef}>
        <div className="flex flex-col max-w-[var(--content-max)] mx-auto w-full px-5 pt-5 pb-3">
          <div className="flex flex-col gap-4 pb-4">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex gap-2.5 items-end animate-in fade-in duration-300 ${
                  msg.role === "user" ? "flex-row-reverse" : ""
                }`}
              >
                <div
                  className="w-7 h-7 rounded-full flex-shrink-0 grid place-items-center text-[13px] font-semibold"
                  style={{
                    background: msg.role === "ai"
                      ? "linear-gradient(135deg,#c4a3d4 0%,#7a5a8c 100%)"
                      : "var(--color-accent)",
                    color: "#fff",
                    borderRadius: msg.role === "user" ? 8 : "50%",
                  }}
                >
                  {msg.role === "ai" ? "🍎" : "你"}
                </div>
                <div
                  className="max-w-[80%] px-4 py-3 text-[15px] leading-relaxed"
                  style={{
                    background: msg.role === "ai" ? "var(--color-ai-msg)" : "var(--color-user-msg)",
                    borderRadius: msg.role === "ai" ? "3px 18px 18px 18px" : "18px 18px 3px 18px",
                    fontFamily: msg.role === "ai" ? "var(--font-serif)" : undefined,
                  }}
                >
                  {msg.text}
                </div>
              </div>
            ))}

            {/* Stuck Banner */}
            {showStuckBanner && (
              <StuckBanner onAction={handleStuckAction} />
            )}

            {/* Breakthrough Celebration */}
            {showBreakthrough && (
              <BreakthroughCelebration onPractice={handleStartPractice} />
            )}

            {/* Concept Card (silent mode) */}
            {showConceptCard && (
              <ConceptCard
                title={mission?.title || "继续讲解"}
                content="昨天我们讲到矩阵乘法。它不像一般乘法那样是元素间的对应运算。它是行和列的组合。一组系数和一个向量之间的映射。"
                onContinue={() => {
                  setShowConceptCard(false);
                  onSetMode("normal");
                }}
                onAsk={(q) => handleSend(q)}
              />
            )}

            {/* Inline Practice Card */}
            {showPractice && (
              <PracticeInlineCard
                question={MOCK_QUESTION}
                onDone={handlePracticeDone}
                onCreateCard={handleCreateCard}
              />
            )}
          </div>
        </div>
      </div>

      {/* 建议词条 */}
      {suggestions.length > 0 && (
        <div className="flex gap-2 px-5 py-2 flex-wrap max-w-[var(--content-max)] mx-auto w-full">
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => handleSuggestionClick(s)}
              disabled={typing}
              className="px-3.5 py-2 rounded-full border border-border/60 text-[13px] text-ink-secondary hover:border-ink-muted hover:text-ink-primary transition-colors disabled:opacity-40"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* 输入栏 */}
      <div className="flex gap-2 px-5 py-3 border-t border-border bg-surface/80 backdrop-blur max-w-[var(--content-max)] mx-auto w-full">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend(inputValue)}
          placeholder={currentState.mode === "silent" ? "不想打字就点上面" : "跟苹果果说说……"}
          disabled={typing}
          className="flex-1 bg-page border border-border rounded-full px-4 py-3 text-[14px] outline-none focus:border-accent transition-colors disabled:opacity-40"
        />
        <button
          onClick={() => handleSend(inputValue)}
          disabled={!inputValue.trim() || typing}
          className="w-[42px] h-[42px] rounded-full bg-accent text-white grid place-items-center flex-shrink-0 hover:bg-accent-hover transition-colors disabled:opacity-40"
        >
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none">
            <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}
