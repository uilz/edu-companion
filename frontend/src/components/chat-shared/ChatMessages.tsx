"use client";

import SpeakButton from "@/components/conversation/media/SpeakButton";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface ChatMessagesProps {
  messages: ChatMessage[];
  /** 是否对助手消息显示朗读按钮 */
  showSpeak?: boolean;
  emptyText?: string;
}

export default function ChatMessages({
  messages,
  showSpeak = true,
  emptyText = "输入学习需求，我来帮你导航",
}: ChatMessagesProps) {
  if (messages.length === 0) {
    return (
      <p className="text-xs text-[var(--color-text-muted)] text-center py-4">
        {emptyText}
      </p>
    );
  }

  return (
    <>
      {messages.map((msg, i) => (
        <div
          key={i}
          className={`text-sm ${
            msg.role === "user"
              ? "text-right text-[var(--color-text)]"
              : "text-left text-[var(--color-text)]"
          }`}
        >
          <div className="flex items-start gap-1">
            <span
              className={`inline-block px-3 py-2 rounded-lg max-w-[85%] ${
                msg.role === "user"
                  ? "bg-[var(--color-accent)]/10 ml-auto"
                  : "bg-[var(--color-surface-hover)]"
              }`}
            >
              {msg.content}
            </span>
            {msg.role === "assistant" && showSpeak && msg.content.length >= 50 && (
              <div className="flex-shrink-0 mt-1">
                <SpeakButton text={msg.content} />
              </div>
            )}
          </div>
        </div>
      ))}
    </>
  );
}