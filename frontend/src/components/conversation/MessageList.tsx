"use client";

import { useEffect, useRef, useMemo, useState, useCallback } from "react";
import { User, Bot, Trash2, Pencil, Check, X, ChevronDown } from "lucide-react";
import MathContent from "@/components/ui/MathContent";
import ResponseBlockRenderer from "./ResponseBlockRenderer";
import SpeakButton from "./SpeakButton";
import { renderContent } from "@/lib/math";
import { useRenderedContent } from "@/lib/useRenderedContent";
import type { TreeNode, ResponseBlock } from "@/types";

interface MessageListProps {
  messages: TreeNode[];
  responseBlocks: ResponseBlock[];
  isLoading?: boolean;
  statusMessage?: string;
  onDeleteMessage?: (messageId: string) => void;
  onEditMessage?: (messageId: string, newText: string) => void;
}

export default function MessageList({
  messages,
  responseBlocks,
  isLoading = false,
  statusMessage,
  onDeleteMessage,
  onEditMessage,
}: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingText, setEditingText] = useState("");
  const [showScrollButton, setShowScrollButton] = useState(false);

  const handleDeleteMessage = (messageId: string) => {
    if (onDeleteMessage) onDeleteMessage(messageId);
  };

  const handleStartEdit = (msgId: string, currentText: string) => {
    setEditingId(msgId);
    setEditingText(currentText);
  };

  const handleSaveEdit = () => {
    if (editingId && editingText.trim() && onEditMessage) {
      onEditMessage(editingId, editingText.trim());
    }
    setEditingId(null);
    setEditingText("");
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditingText("");
  };

  // Track scroll position for "scroll to bottom" button
  const handleScroll = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;
    const distFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    setShowScrollButton(distFromBottom > 300);
  }, []);

  // Auto-scroll to bottom only if user is already near bottom (within 150px)
  // This respects user's reading position when new messages arrive
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const isNearBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight < 150;

    if (isNearBottom && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, responseBlocks]);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  // Group blocks by message_id
  const blocksByMessage = useMemo(() => {
    const map = new Map<string, ResponseBlock[]>();
    for (const block of responseBlocks) {
      const existing = map.get(block.message_id) || [];
      existing.push(block);
      map.set(block.message_id, existing);
    }
    // Sort blocks within each message by order
    map.forEach((blocks) => {
      blocks.sort((a, b) => a.order - b.order);
    });
    return map;
  }, [responseBlocks]);

  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <Bot size={48} className="text-[var(--color-text-muted)] mx-auto mb-4 opacity-30" />
          <div className="text-sm text-[var(--color-text-secondary)]">
            开始新的对话
          </div>
          <div className="text-xs text-[var(--color-text-muted)] mt-1">
            输入你的问题，我会尽力帮助你
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-hidden relative">
      <div
        ref={containerRef}
        className="h-full overflow-y-auto px-4 py-6 space-y-6"
        onScroll={handleScroll}
      >
        {messages.map((message) => {
          if (message.is_deleted) return null;
          const isUser = message.role === "user";
          const isEditing = editingId === message.id;
          const messageBlocks = blocksByMessage.get(message.id) || [];

          // Extract text from content blocks
          const textBlocks = (message.content_blocks || [])
            .filter((b) => b.type === "text")
            .map((b) => b.text || "")
            .join("\n\n");

          return (
            <div key={message.id} className={`flex gap-4 ${isUser ? "flex-row-reverse" : ""}`}>
              {/* Avatar */}
              <div
                className={`flex-shrink-0 w-8 h-8 rounded flex items-center justify-center ${
                  isUser
                    ? "bg-[var(--color-accent)] text-white"
                    : "bg-[var(--color-surface)] text-[var(--color-accent)]"
                }`}
              >
                {isUser ? <User size={16} /> : <Bot size={16} />}
              </div>

              {/* Content */}
              <div className={`flex-1 min-w-0 ${isUser ? "flex justify-end" : ""}`}>
                <div
                  className={`inline-block max-w-[85%] ${
                    isUser
                      ? "bg-[var(--color-accent)] text-white"
                      : "bg-[var(--color-surface)] text-[var(--color-text)]"
                  } px-4 py-3`}
                >
                  {isEditing ? (
                    <div className="space-y-2 min-w-[200px]">
                      <textarea
                        value={editingText}
                        onChange={(e) => setEditingText(e.target.value)}
                        className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 resize-none"
                        rows={3}
                        autoFocus
                      />
                      <div className="flex justify-end gap-2">
                        <button onClick={handleCancelEdit} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                          <X size={14} />
                        </button>
                        <button onClick={handleSaveEdit} className="p-1 text-[var(--color-success)] hover:opacity-80">
                          <Check size={14} />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      {textBlocks && <MessageContent text={textBlocks} />}

                      {/* Multi-version navigation */}
                      {message.has_modified_version && message.children_ids?.length > 0 && (
                        <div className="flex items-center gap-1 mt-2 pt-2 border-t border-[var(--color-border)]">
                          <button className="p-0.5 text-[var(--color-text-muted)] hover:text-[var(--color-text)]" title="上一版本">
                            <ChevronDown size={12} className="rotate-90" />
                          </button>
                          <span className="text-[10px] text-[var(--color-text-muted)]">版本</span>
                          <button className="p-0.5 text-[var(--color-text-muted)] hover:text-[var(--color-text)]" title="下一版本">
                            <ChevronDown size={12} className="-rotate-90" />
                          </button>
                        </div>
                      )}

                      {/* Message actions */}
                      <div className="flex items-center gap-2 mt-2 pt-1 border-t border-[var(--color-border)]/30">
                        <span className="text-[10px] text-[var(--color-text-muted)]">
                          {new Date(message.timestamp * 1000).toLocaleTimeString("zh-CN", {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                        <div className="flex-1" />
                        {!isUser && <SpeakButton text={textBlocks} />}
                        {isUser && onEditMessage && (
                          <button
                            onClick={() => handleStartEdit(message.id, textBlocks)}
                            className="p-0.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)]"
                            title="编辑"
                          >
                            <Pencil size={12} />
                          </button>
                        )}
                        {isUser && onDeleteMessage && (
                          <button
                            onClick={() => handleDeleteMessage(message.id)}
                            className="p-0.5 text-[var(--color-text-muted)] hover:text-red-400"
                            title="删除"
                          >
                            <Trash2 size={12} />
                          </button>
                        )}
                      </div>
                    </>
                  )}
                </div>

                {/* Response blocks (tool cards, practices, etc.) */}
                {!isUser && messageBlocks.length > 0 && (
                  <div className="mt-2 space-y-2">
                    {messageBlocks.map((block) => (
                      <ResponseBlockRenderer key={block.id} block={block} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex gap-4">
            <div className="flex-shrink-0 w-8 h-8 rounded bg-[var(--color-surface)] flex items-center justify-center text-[var(--color-accent)]">
              <Bot size={16} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="inline-block bg-[var(--color-surface)] text-[var(--color-text-secondary)] px-4 py-3">
                {statusMessage || (
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 bg-[var(--color-accent)] rounded-full animate-bounce" />
                    <span className="w-2 h-2 bg-[var(--color-accent)] rounded-full animate-bounce" style={{ animationDelay: "0.2s" }} />
                    <span className="w-2 h-2 bg-[var(--color-accent)] rounded-full animate-bounce" style={{ animationDelay: "0.4s" }} />
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Scroll to bottom button */}
      {showScrollButton && (
        <button
          onClick={scrollToBottom}
          className="absolute bottom-4 right-6 w-9 h-9 bg-[var(--color-surface)] border border-[var(--color-border)] shadow-md flex items-center justify-center text-[var(--color-text-secondary)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-elevated)] transition-all z-10"
          title="滚动到底部"
        >
          <ChevronDown size={18} />
        </button>
      )}
    </div>
  );
}

function MessageContent({ text }: { text: string }) {
  const html = useRenderedContent(text);

  return (
    <div
      className="message-content text-sm leading-relaxed [&_p]:mb-2 [&_p:last-child]:mb-0"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
