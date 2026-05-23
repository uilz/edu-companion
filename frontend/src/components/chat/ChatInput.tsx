"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Send } from "lucide-react";

/** ChatInput 组件的属性接口 */
interface ChatInputProps {
  /** 发送消息的回调函数 */
  onSend: (message: string) => void;
  /** 是否禁用输入框和发送按钮 */
  disabled?: boolean;
}

/** 聊天输入框组件 — 提供文本输入、自动调整高度、Enter 发送等功能 */
export default function ChatInput({ onSend, disabled = false }: ChatInputProps) {
  // 输入框的文本内容状态
  const [text, setText] = useState("");
  // textarea DOM 元素的引用，用于自动调整高度
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  /** 根据内容自动调整 textarea 的高度，最大高度为 160px */
  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, []);

  // 当文本内容变化时，自动调整 textarea 高度
  useEffect(() => {
    autoResize();
  }, [text, autoResize]);

  /** 处理发送操作：去除首尾空格后调用 onSend 回调，并清空输入框 */
  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  };

  /** 键盘事件处理：Enter 发送消息（Shift+Enter 换行） */
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    /* 底部输入区域：包含文本框和发送按钮 */
    <div className="border-t border-[var(--color-border)] bg-[var(--color-bg)] p-4">
      <div className="flex items-end gap-3 max-w-3xl mx-auto">
        {/* 文本输入框 — 支持自动高度调整和 Enter 发送 */}
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder="输入你的问题..."
          rows={1}
          className="flex-1 resize-none bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] placeholder-[var(--color-text-muted)] px-4 py-3 text-sm focus:outline-none focus:border-[var(--color-border-hover)] disabled:opacity-50"
        />
        {/* 发送按钮 — 文本为空或 disabled 时禁用 */}
        <button
          onClick={handleSend}
          disabled={disabled || !text.trim()}
          className="flex-shrink-0 w-10 h-10 flex items-center justify-center bg-[var(--color-accent)] text-[#ffffff] disabled:opacity-30 hover:bg-[var(--color-accent-hover)] transition-colors"
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}
