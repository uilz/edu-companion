"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Paperclip, Image, Mic, Video } from "lucide-react";

interface ConversationChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export default function ConversationChatInput({
  onSend,
  disabled = false,
}: ConversationChatInputProps) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, []);

  useEffect(() => {
    autoResize();
  }, [text, autoResize]);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-[var(--color-border)] bg-[var(--color-bg)]">
      <div className="max-w-3xl mx-auto px-4 py-3">
        {/* Attachment buttons */}
        <div className="flex items-center gap-1 mb-2">
          <button
            disabled={disabled}
            className="p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] transition-colors disabled:opacity-30"
            title="上传图片"
          >
            <Image size={16} />
          </button>
          <button
            disabled={disabled}
            className="p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] transition-colors disabled:opacity-30"
            title="上传文件"
          >
            <Paperclip size={16} />
          </button>
          <button
            disabled={disabled}
            className="p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] transition-colors disabled:opacity-30"
            title="录制语音"
          >
            <Mic size={16} />
          </button>
          <button
            disabled={disabled}
            className="p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] transition-colors disabled:opacity-30"
            title="上传视频"
          >
            <Video size={16} />
          </button>
        </div>

        {/* Input area */}
        <div className="flex items-end gap-3">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder="输入你的问题... (Shift+Enter 换行)"
            rows={1}
            className="flex-1 resize-none bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] placeholder-[var(--color-text-muted)] px-4 py-3 text-sm focus:outline-none focus:border-[var(--color-border-hover)] disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={disabled || !text.trim()}
            className="flex-shrink-0 w-10 h-10 flex items-center justify-center bg-[var(--color-accent)] text-white disabled:opacity-30 hover:bg-[var(--color-accent-hover)] transition-colors"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
