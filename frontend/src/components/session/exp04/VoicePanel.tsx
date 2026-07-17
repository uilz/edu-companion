"use client";

import { useState, useCallback } from "react";
import { X, Mic, Square } from "lucide-react";

// ── Props ──────────────────────────────────────────────────

interface Props {
  open: boolean;
  onClose: () => void;
}

// ── Quick reply map ───────────────────────────────────────

const REPLY_MAP: Record<string, string> = {
  "我想介绍一下我自己": "Nice. It takes courage to introduce yourself in a new language. Where are you from?",
  "今天天气怎么样": "Good icebreaker. Do you prefer sunny or rainy days when you study?",
  "我最近在学线性代数": "Linear algebra. What part feels hardest right now?",
  "我在学递归": "Recursion! That's a fun one. What's your mental model for how it works?",
};

// ── Transcript line ───────────────────────────────────────

interface TranscriptLine {
  role: "ai" | "user";
  text: string;
}

// ── Component ─────────────────────────────────────────────

export default function VoicePanel({ open, onClose }: Props) {
  const [speaking, setSpeaking] = useState(false);
  const [transcript, setTranscript] = useState<TranscriptLine[]>([
    { role: "ai", text: "还没开始。准备好了点下面的按钮。" },
  ]);

  const toggleSpeaking = useCallback(() => {
    if (!speaking) {
      // Start: add AI greeting
      setSpeaking(true);
      setTranscript((prev) => [
        ...prev,
        { role: "ai", text: "Hello. Tell me, what are you studying these days?" },
      ]);
    } else {
      setSpeaking(false);
    }
  }, [speaking]);

  const handleQuickReply = useCallback((text: string) => {
    setTranscript((prev) => [...prev, { role: "user", text }]);

    const reply = REPLY_MAP[text] || "Interesting. Tell me more.";
    setTimeout(() => {
      setTranscript((prev) => [...prev, { role: "ai", text: reply }]);
    }, 600);
  }, []);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] bg-black/30 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200">
      <div className="bg-surface rounded-2xl shadow-xl border border-border/50 w-full max-w-sm relative animate-in zoom-in-95 duration-300">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-ink-muted hover:text-ink-secondary transition-colors z-10"
          aria-label="关闭语音"
        >
          <X size={18} />
        </button>

        <div className="flex flex-col items-center p-6 pt-8">
          {/* Orb */}
          <div
            className="relative w-32 h-32 rounded-full grid place-items-center mb-6 transition-all duration-300"
            style={{
              background: speaking
                ? "radial-gradient(circle at 30% 30%, var(--color-accent), var(--color-accent-hover))"
                : "rgba(160,160,171,0.15)",
            }}
          >
            {speaking && (
              <>
                <span className="absolute inset-0 rounded-full border-2 border-accent/50 animate-ping" />
                <span className="absolute inset-0 rounded-full border-2 border-accent/30 animate-ping [animation-delay:0.6s]" />
              </>
            )}
            <span className="text-4xl drop-shadow-md select-none">🍎</span>
          </div>

          {/* Status */}
          <p className="text-base font-semibold text-ink-primary mb-1">
            {speaking ? "苹果果在说……" : "点下面开始对话"}
          </p>
          <p className="text-sm text-ink-muted mb-5">
            {speaking ? "它在等你接话" : "苹果果会先说一句，你来接"}
          </p>

          {/* Wave */}
          <div className="flex items-center gap-[3px] h-8 mb-5">
            {Array.from({ length: 9 }).map((_, i) => (
              <span
                key={i}
                className={`w-[3px] rounded-full bg-accent transition-all duration-300 ${
                  speaking
                    ? "animate-pulse"
                    : "h-1 opacity-30"
                }`}
                style={
                  speaking
                    ? {
                        height: `${4 + Math.sin(i * 0.8 + Date.now() * 0.003) * 12}px`,
                        animationDuration: `${0.6 + Math.random() * 0.4}s`,
                      }
                    : undefined
                }
              />
            ))}
          </div>

          {/* Transcript */}
          <div className="w-full max-h-40 overflow-y-auto mb-5 bg-page rounded-xl p-3 border border-border/40 space-y-2">
            {transcript.map((line, i) => (
              <p key={i} className="text-sm leading-relaxed">
                <strong className={line.role === "ai" ? "text-accent" : "text-ink-secondary"}>
                  {line.role === "ai" ? "🍎 苹果果：" : "你："}
                </strong>
                {line.text}
              </p>
            ))}
          </div>

          {/* Controls */}
          <div className="flex items-center gap-3 mb-4">
            <button
              onClick={toggleSpeaking}
              className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium transition-all ${
                speaking
                  ? "bg-ink-primary text-white hover:opacity-90"
                  : "bg-accent text-white shadow-md hover:opacity-90"
              }`}
            >
              {speaking ? (
                <>
                  <Square size={14} fill="currentColor" />
                  结束对话
                </>
              ) : (
                <>
                  <Mic size={14} />
                  开始对话
                </>
              )}
            </button>
            <button
              onClick={onClose}
              className="px-4 py-2.5 rounded-full border border-border/60 text-ink-secondary text-sm hover:bg-surface-hover transition-colors"
            >
              结束
            </button>
          </div>

          {/* Quick replies (only when speaking) */}
          {speaking && (
            <div className="flex flex-wrap gap-2 justify-center">
              {Object.keys(REPLY_MAP).map((text) => (
                <button
                  key={text}
                  onClick={() => handleQuickReply(text)}
                  className="px-3 py-1.5 rounded-full border border-border/50 text-xs text-ink-secondary hover:bg-surface-hover hover:border-ink-muted transition-colors"
                >
                  {text}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
