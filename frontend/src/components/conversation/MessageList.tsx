"use client";

import { useEffect, useRef, useMemo, useState, useCallback } from "react";
import { User, Bot, Trash2, Pencil, Check, X, ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import ResponseBlockRenderer from "./ResponseBlockRenderer";
import SpeakButton from "./SpeakButton";
import { useRenderedContent } from "@/lib/useRenderedContent";
import type { TreeNode, ResponseBlock } from "@/types";

interface MessageListProps {
  messages: TreeNode[];
  responseBlocks: ResponseBlock[];
  isLoading?: boolean;
  statusMessage?: string;
  onDeleteMessage?: (messageId: string) => void;
  onEditMessage?: (messageId: string, newText: string) => Promise<void>;
  onVersionSwitch?: (messageId: string, direction: "prev" | "next") => void;
}

// Local map of edited message text, keyed by message ID.
// This bypasses parent state propagation issues.
type EditedMap = Record<string, string>;

export default function MessageList({
  messages,
  responseBlocks,
  isLoading = false,
  statusMessage,
  onDeleteMessage,
  onEditMessage,
  onVersionSwitch,
}: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingText, setEditingText] = useState("");
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [editedTexts, setEditedTexts] = useState<EditedMap>({});

  const handleDeleteMessage = (messageId: string) => {
    if (onDeleteMessage) onDeleteMessage(messageId);
  };

  const handleStartEdit = (msgId: string, currentText: string) => {
    setEditingId(msgId);
    setEditingText(currentText);
  };

  const handleSaveEdit = async () => {
    const msgId = editingId;
    const newText = editingText.trim();
    if (!msgId || !newText) {
      setEditingId(null);
      setEditingText("");
      return;
    }

    // Immediately show new text locally
    setEditedTexts(prev => ({ ...prev, [msgId]: newText }));
    setEditingId(null);
    setEditingText("");

    // Persist to backend
    if (onEditMessage) {
      console.log("[MsgEdit] saving:", msgId, newText.slice(0, 50));
      try {
        await onEditMessage(msgId, newText);
        console.log("[MsgEdit] saved OK");
      } catch (e) {
        console.error("[MsgEdit] save failed:", e);
        // Rollback local edit on failure
        setEditedTexts(prev => {
          const next = { ...prev };
          delete next[msgId];
          return next;
        });
      }
    }
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

  // Auto-scroll to bottom only if user is already near bottom
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

          // Use locally edited text if available, otherwise from content_blocks
          const displayText = editedTexts[message.id]
            || (message.content_blocks || [])
                .filter((b) => b.type === "text")
                .map((b) => b.text || "")
                .join("\n\n");

          // Version info
          const hasVersions = message.has_modified_version || !!editedTexts[message.id];

          return (
            <div key={message.id} className={`flex gap-4 ${isUser ? "flex-row-reverse" : ""}`}>
              {/* Avatar */}
              <div
                className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                  isUser
                    ? "bg-blue-500 text-white"
                    : "bg-[var(--color-surface)] text-[var(--color-accent)] border border-[var(--color-border)]"
                }`}
              >
                {isUser ? <User size={16} /> : <Bot size={16} />}
              </div>

              {/* Content */}
              <div className={`flex-1 min-w-0 ${isUser ? "flex justify-end" : ""}`}>
                <div className={`max-w-[85%] ${isUser ? "" : "space-y-0"}`}>
                  {/* User message bubble */}
                  {isUser ? (
                    <div className="bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 px-4 py-2.5 rounded-2xl rounded-tr-md">
                      {isEditing ? (
                        <div className="space-y-2 min-w-[200px]">
                          <textarea
                            value={editingText}
                            onChange={(e) => setEditingText(e.target.value)}
                            className="w-full bg-white dark:bg-gray-900 border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 resize-none rounded-lg"
                            rows={3}
                            autoFocus
                          />
                          <div className="flex justify-end gap-2">
                            <button onClick={handleCancelEdit} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                              <X size={14} />
                            </button>
                            <button onClick={handleSaveEdit} className="p-1 text-green-500 hover:text-green-600">
                              <Check size={14} />
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="text-sm leading-relaxed text-gray-800 dark:text-gray-200 whitespace-pre-wrap break-words">
                          {displayText}
                        </div>
                      )}
                    </div>
                  ) : (
                    /* AI message */
                    <div className="bg-[var(--color-surface)] text-[var(--color-text)] px-4 py-3 rounded-2xl rounded-tl-md">
                      {isEditing ? (
                        <div className="space-y-2 min-w-[200px]">
                          <textarea
                            value={editingText}
                            onChange={(e) => setEditingText(e.target.value)}
                            className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 resize-none rounded-lg"
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
                        <div className="message-content text-sm leading-relaxed
                          [&_p]:mb-2 [&_p:last-child]:mb-0
                          [&_h1]:text-lg [&_h1]:font-bold [&_h1]:mb-2 [&_h1]:mt-3
                          [&_h2]:text-base [&_h2]:font-semibold [&_h2]:mb-2 [&_h2]:mt-3
                          [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:mb-1.5 [&_h3]:mt-2
                          [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-2 [&_ul]:space-y-0.5
                          [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-2 [&_ol]:space-y-0.5
                          [&_li]:leading-relaxed
                          [&_blockquote]:border-l-3 [&_blockquote]:border-[var(--color-accent)] [&_blockquote]:pl-3 [&_blockquote]:py-1 [&_blockquote]:my-2 [&_blockquote]:text-[var(--color-text-secondary)] [&_blockquote]:italic
                          [&_a]:text-[var(--color-accent)] [&_a]:underline [&_a]:underline-offset-2
                          [&_hr]:border-[var(--color-border)] [&_hr]:my-3
                          [&_table]:w-full [&_table]:border-collapse [&_table]:my-2
                          [&_th]:border [&_th]:border-[var(--color-border)] [&_th]:px-3 [&_th]:py-1.5 [&_th]:bg-[var(--color-bg-elevated)] [&_th]:text-left [&_th]:text-xs [&_th]:font-semibold
                          [&_td]:border [&_td]:border-[var(--color-border)] [&_td]:px-3 [&_td]:py-1.5 [&_td]:text-sm
                          [&_pre]:bg-[var(--color-bg-elevated)] [&_pre]:p-3 [&_pre]:rounded-lg [&_pre]:overflow-x-auto [&_pre]:my-2 [&_pre]:text-xs
                          [&_code]:bg-[var(--color-bg-elevated)] [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-xs [&_code]:font-mono
                          [&_pre_code]:bg-transparent [&_pre_code]:p-0
                          [&_img]:max-w-full [&_img]:rounded-lg [&_img]:my-2
                          [&_strong]:font-semibold
                          [&_em]:italic
                          [&_del]:line-through [&_del]:opacity-60
                        "
                        >
                          <MessageContent text={displayText} />
                        </div>
                      )}
                    </div>
                  )}

                  {/* Message footer: time + version switch + actions */}
                  <div
                    className={`flex items-center gap-2 mt-1.5 px-1 ${
                      isUser ? "justify-end" : "justify-start"
                    }`}
                  >
                    <span
                      className="text-[10px] text-[var(--color-text-muted)] select-none"
                      title={new Date(message.timestamp * 1000).toLocaleString("zh-CN")}
                    >
                      {new Date(message.timestamp * 1000).toLocaleTimeString("zh-CN", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>

                    {/* Version switch — shown on any message with edits */}
                    {!isUser && hasVersions && onVersionSwitch && (
                      <div className="flex items-center gap-0.5 ml-1">
                        <button
                          onClick={() => onVersionSwitch(message.id, "prev")}
                          className="p-0.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] rounded"
                          title="上一版本"
                        >
                          <ChevronLeft size={11} />
                        </button>
                        <span className="text-[9px] text-[var(--color-text-muted)] select-none">改</span>
                        <button
                          onClick={() => onVersionSwitch(message.id, "next")}
                          className="p-0.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] rounded"
                          title="下一版本"
                        >
                          <ChevronRight size={11} />
                        </button>
                      </div>
                    )}

                    {/* Actions */}
                    {!isUser && <SpeakButton text={displayText} />}
                    {isUser && onEditMessage && (
                      <button
                        onClick={() => handleStartEdit(message.id, displayText)}
                        className="p-0.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] rounded"
                        title="编辑"
                      >
                        <Pencil size={12} />
                      </button>
                    )}
                    {isUser && onDeleteMessage && (
                      <button
                        onClick={() => handleDeleteMessage(message.id)}
                        className="p-0.5 text-[var(--color-text-muted)] hover:text-red-400 rounded"
                        title="删除"
                      >
                        <Trash2 size={12} />
                      </button>
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
            </div>
          );
        })}

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex gap-4">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-[var(--color-surface)] border border-[var(--color-border)] flex items-center justify-center text-[var(--color-accent)]">
              <Bot size={16} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="inline-block bg-[var(--color-surface)] text-[var(--color-text-secondary)] px-4 py-3 rounded-2xl rounded-tl-md">
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
          className="absolute bottom-4 right-6 w-9 h-9 bg-[var(--color-surface)] border border-[var(--color-border)] shadow-lg rounded-full flex items-center justify-center text-[var(--color-text-secondary)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-elevated)] transition-all z-10"
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
  return <div dangerouslySetInnerHTML={{ __html: html }} />;
}
