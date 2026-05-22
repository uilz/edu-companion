"use client";

import { useEffect, useRef, useMemo, useState, useCallback } from "react";
import { User, Bot, Trash2, Pencil, Check, X, ChevronDown, ChevronLeft, ChevronRight, Copy } from "lucide-react";
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
  onEditMessage?: (messageId: string, newText: string) => Promise<number>;
  onVersionSwitch?: (messageId: string, direction: "prev" | "next") => Promise<{ index: number; total: number } | null>;
}

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

  const [versionMap, setVersionMap] = useState<Record<string, { index: number; total: number }>>({});

  const handleCopyMessage = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
  };

  const handleVersionNav = async (messageId: string, direction: "prev" | "next") => {
    if (!onVersionSwitch) return;
    const result = await onVersionSwitch(messageId, direction);
    if (result) {
      setVersionMap(prev => ({ ...prev, [messageId]: result }));
    }
  };

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
      return;
    }
    if (onEditMessage) {
      try {
        const result = await onEditMessage(msgId, newText);
        if (result > 0) {
          setEditedTexts(prev => ({ ...prev, [msgId]: newText }));
          setVersionMap(prev => ({ ...prev, [msgId]: { index: result, total: result } }));
        }
      } catch (e) {
        console.error("Edit failed:", e);
      }
    }
    setEditingId(null);
  };

  const handleCancelEdit = () => {
    setEditingId(null);
  };

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (bottomRef.current && !showScrollButton) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages.length, messages[messages.length - 1]?.text_summary]);

  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    setShowScrollButton(scrollHeight - scrollTop - clientHeight > 300);
  }, []);

  // Deduplicate messages by ID (keep last occurrence with non-empty text)
  const dedupedMessages = useMemo(() => {
    const seen = new Map<string, TreeNode>();
    // Iterate in reverse so later (final) versions override earlier (streaming) ones
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.is_deleted) continue;
      const existing = seen.get(m.id);
      if (!existing) {
        seen.set(m.id, m);
      } else {
        // Prefer the one with content
        const existingText = existing.content_blocks?.find(b => b.type === "text")?.text || "";
        const currentText = m.content_blocks?.find(b => b.type === "text")?.text || "";
        if (currentText && !existingText) {
          seen.set(m.id, m);
        }
      }
    }
    return Array.from(seen.values()).reverse();
  }, [messages]);

  // Map response blocks to messages
  const blocksByMessage = useMemo(() => {
    const map = new Map<string, ResponseBlock[]>();
    for (const block of responseBlocks || []) {
      const id = block.message_id || "";
      if (!map.has(id)) map.set(id, []);
      map.get(id)!.push(block);
    }
    return map;
  }, [responseBlocks]);

  return (
    <div className="h-full flex flex-col">
      <div
        ref={containerRef}
        className="h-full overflow-y-auto px-4 py-6 space-y-6"
        onScroll={handleScroll}
      >
        {dedupedMessages.map((message) => {
          const isUser = message.role === "user";
          const isEditing = editingId === message.id;
          const messageBlocks = blocksByMessage.get(message.id) || [];

          const displayText = editedTexts[message.id]
            || (message.content_blocks || [])
                .filter((b) => b.type === "text")
                .map((b) => b.text || "")
                .join("\n\n");

          const hasVersions = message.has_modified_version || !!editedTexts[message.id];
          const vInfo = versionMap[message.id] || { index: 1, total: hasVersions ? 1 : 0 };

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
                          <MessageContent text={displayText} />
                        </div>
                      )}
                    </div>
                  ) : (
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
                            <button onClick={handleSaveEdit} className="p-1 text-green-500 hover:text-green-600">
                              <Check size={14} />
                            </button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <div className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                            <MessageContent text={displayText} />
                          </div>
                          {/* Version navigation */}
                          {vInfo.total > 0 && (
                            <div className="flex items-center gap-2 mt-2 text-xs text-[var(--color-text-muted)]">
                              <button
                                onClick={() => handleVersionNav(message.id, "prev")}
                                className="p-0.5 hover:text-[var(--color-text)]"
                              >
                                <ChevronLeft size={14} />
                              </button>
                              <span>{vInfo.index}/{vInfo.total}</span>
                              <button
                                onClick={() => handleVersionNav(message.id, "next")}
                                className="p-0.5 hover:text-[var(--color-text)]"
                              >
                                <ChevronRight size={14} />
                              </button>
                            </div>
                          )}
                          {/* Actions */}
                          <div className="flex items-center gap-1 mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button onClick={() => handleStartEdit(message.id, displayText)} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]" title="编辑">
                              <Pencil size={12} />
                            </button>
                            <button onClick={() => handleDeleteMessage(message.id)} className="p-1 text-[var(--color-text-muted)] hover:text-red-500" title="删除">
                              <Trash2 size={12} />
                            </button>
                            <button onClick={() => handleCopyMessage(displayText)} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]" title="复制">
                              <Copy size={12} />
                            </button>
                            <SpeakButton text={displayText} />
                          </div>
                          {/* Response blocks */}
                          {messageBlocks.length > 0 && (
                            <div className="mt-3 border-t border-[var(--color-border)] pt-3 space-y-2">
                              {messageBlocks.map(block => (
                                <ResponseBlockRenderer key={block.id} block={block} />
                              ))}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex justify-center py-4">
            <div className="flex items-center gap-2 text-[var(--color-text-muted)] text-sm">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-[var(--color-accent)] rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-2 h-2 bg-[var(--color-accent)] rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-2 h-2 bg-[var(--color-accent)] rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
              {statusMessage && <span>{statusMessage}</span>}
            </div>
          </div>
        )}

        {/* Inline response blocks at bottom */}
        {responseBlocks.length > 0 && messages.length === 0 && (
          <div className="space-y-2">
            {responseBlocks.map(block => (
              <ResponseBlockRenderer key={block.id} block={block} />
            ))}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Scroll to bottom button */}
      {showScrollButton && (
        <div className="absolute bottom-20 left-1/2 -translate-x-1/2">
          <button
            onClick={() => bottomRef.current?.scrollIntoView({ behavior: "smooth" })}
            className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-full p-2 shadow-lg hover:shadow-xl transition-shadow"
          >
            <ChevronDown size={20} />
          </button>
        </div>
      )}
    </div>
  );
}

// 直接从 displayText 渲染，useRenderedContent 用于 MathJax
const MessageContent = ({ text }: { text: string }) => {
  const html = useRenderedContent(text);
  return <div dangerouslySetInnerHTML={{ __html: html }} />;
};
