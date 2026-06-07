"use client";

import { Mic, Loader2 } from "lucide-react";
import VoiceRecorder from "@/components/conversation/input/VoiceRecorder";

interface ChatInputBarProps {
  input: string;
  onInputChange: (v: string) => void;
  onSubmit: () => void;
  loading: boolean;
  /** 是否显示语音输入 */
  showVoice?: boolean;
  placeholder?: string;
}

export default function ChatInputBar({
  input,
  onInputChange,
  onSubmit,
  loading,
  showVoice = true,
  placeholder = "输入学习需求…",
}: ChatInputBarProps) {
  const handleVoiceText = (text: string) => {
    onInputChange((input ? input + " " : "") + text);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <div className="flex items-center gap-2">
      {showVoice && (
        <VoiceRecorder onTranscription={handleVoiceText} disabled={loading} />
      )}
      <input
        type="text"
        value={input}
        onChange={(e) => onInputChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={loading ? "回复中…" : placeholder}
        disabled={loading}
        className="flex-1 px-3 py-2 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] outline-none focus:border-[var(--color-accent)] disabled:opacity-50"
      />
      <button
        onClick={onSubmit}
        disabled={loading || !input.trim()}
        className="p-2 rounded-lg bg-[var(--color-accent)] text-white disabled:opacity-40 hover:opacity-90 transition-opacity"
        aria-label="发送"
      >
        {loading ? (
          <Loader2 size={16} className="animate-spin" />
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        )}
      </button>
    </div>
  );
}