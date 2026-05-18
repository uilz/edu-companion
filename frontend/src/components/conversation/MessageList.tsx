"use client";

import { useEffect, useRef, useMemo, useState } from "react";
import { User, Bot, Trash2, Pencil, Check, X } from "lucide-react";
import MathContent from "@/components/ui/MathContent";
import ResponseBlockRenderer from "./ResponseBlockRenderer";
import SpeakButton from "./SpeakButton";
import { renderContent } from "@/lib/math";
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
      <div className="flex-1 flex flex-col items-center justify-center text-center px-6">
        <div className="w-12 h-12 border border-[var(--color-border)] flex items-center justify-center mb-4">
          <Bot size={20} className="text-[var(--color-accent)]" />
        </div>
        <h2 className="text-xl font-bold text-[var(--color-text)] mb-2">
          开始对话
        </h2>
        <p className="text-sm text-[var(--color-text-muted)] max-w-md">
          选择一个分区开始学习，或直接发送消息
          <br />
          系统会自动为你分类和组织对话。
        </p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6">
        {messages.map((msg) => {
          const isUser = msg.role === "user";
          const blocks = blocksByMessage.get(msg.id) || [];
          const textBlock = msg.content_blocks?.find((b) => b.type === "text");
          const text = textBlock?.text || msg.text_summary || "";
          const isEditing = editingId === msg.id;

          return (
            <div
              key={msg.id}
              className={`flex mb-4 group ${isUser ? "justify-end" : "justify-start"}`}
            >
              {/* Avatar */}
              {!isUser && (
                <div className="flex-shrink-0 w-7 h-7 bg-[var(--color-accent)] flex items-center justify-center mr-2.5 mt-1">
                  <Bot size={14} className="text-white" />
                </div>
              )}

              <div
                className={`max-w-[85%] ${isUser ? "items-end" : "items-start"} flex flex-col`}
              >
                {/* Message bubble — or inline editor */}
                {isEditing ? (
                  <div className="w-full bg-[var(--color-accent)] px-4 py-3">
                    <textarea
                      value={editingText}
                      onChange={(e) => setEditingText(e.target.value)}
                      className="w-full bg-transparent text-white text-sm leading-relaxed resize-none focus:outline-none"
                      rows={Math.max(2, editingText.split("\n").length)}
                      autoFocus
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                          handleSaveEdit();
                        }
                        if (e.key === "Escape") {
                          handleCancelEdit();
                        }
                      }}
                    />
                    <div className="flex items-center justify-end gap-2 mt-2 text-xs text-white/70">
                      <span>⌘+Enter 保存 · Esc 取消</span>
                      <button
                        onClick={handleCancelEdit}
                        className="p-1 hover:text-white transition-colors"
                        title="取消"
                      >
                        <X size={14} />
                      </button>
                      <button
                        onClick={handleSaveEdit}
                        className="p-1 hover:text-white transition-colors"
                        title="保存"
                      >
                        <Check size={14} />
                      </button>
                    </div>
                  </div>
                ) : (
                  text && (
                    <div
                      className={`px-4 py-3 ${
                        isUser
                          ? "bg-[var(--color-accent)] text-white"
                          : "bg-[var(--color-surface)] text-[var(--color-text)]"
                      }`}
                    >
                      {isUser ? (
                        <div className="text-sm leading-relaxed">{text}</div>
                      ) : (
                        <MessageContent text={text} />
                      )}
                    </div>
                  )
                )}

                {/* Non-text content blocks from user */}
                {isUser &&
                  msg.content_blocks
                    ?.filter((b) => b.type !== "text")
                    .map((block, i) => (
                      <div
                        key={i}
                        className="mt-1 px-3 py-2 bg-[var(--color-accent)]/80 text-white/80 text-xs"
                      >
                        {block.type === "image" && "📷 图片"}
                        {block.type === "audio" && "🎤 语音"}
                        {block.type === "video" && "🎬 视频"}
                        {block.type === "document" && "📄 文档"}
                      </div>
                    ))}

                {/* Response blocks for assistant */}
                {!isUser && blocks.length > 0 && (
                  <div className="mt-1">
                    {blocks.map((block) => (
                      <ResponseBlockRenderer key={block.id} block={block} />
                    ))}
                  </div>
                )}

                {/* Timestamp + Speak + Edit + Delete */}
                <div className="flex items-center gap-2 text-[10px] text-[var(--color-text-muted)] mt-1 px-1">
                  <span>
                    {new Date(msg.timestamp).toLocaleTimeString("zh-CN", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                  {!isUser && <SpeakButton text={text} />}
                  {!isEditing && isUser && onEditMessage && (
                    <button
                      onClick={() => handleStartEdit(msg.id, text)}
                      className="opacity-0 group-hover:opacity-100 hover:text-yellow-400 transition-all"
                      title="编辑消息"
                    >
                      <Pencil size={11} />
                    </button>
                  )}
                  {!isEditing && (
                    <button
                      onClick={() => handleDeleteMessage(msg.id)}
                      className="opacity-0 group-hover:opacity-100 hover:text-red-400 transition-all"
                      title="删除消息"
                    >
                      <Trash2 size={11} />
                    </button>
                  )}
                </div>
              </div>

              {isUser && (
                <div className="flex-shrink-0 w-7 h-7 bg-[var(--color-text-muted)] flex items-center justify-center ml-2.5 mt-1">
                  <User size={14} className="text-[var(--color-bg)]" />
                </div>
              )}
            </div>
          );
        })}

        {/* Status message */}
        {statusMessage && isLoading && (
          <div className="flex justify-start mb-4">
            <div className="flex-shrink-0 w-7 h-7 bg-[var(--color-accent)] flex items-center justify-center mr-2.5 mt-1">
              <Bot size={14} className="text-white" />
            </div>
            <div className="bg-[var(--color-surface)] px-4 py-3 flex items-center gap-2">
              <div className="flex gap-1">
                <div className="w-1.5 h-1.5 rounded-full bg-[var(--color-text-muted)] typing-dot" />
                <div className="w-1.5 h-1.5 rounded-full bg-[var(--color-text-muted)] typing-dot" />
                <div className="w-1.5 h-1.5 rounded-full bg-[var(--color-text-muted)] typing-dot" />
              </div>
              <span className="text-xs text-[var(--color-text-muted)]">
                {statusMessage}
              </span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}

function MessageContent({ text }: { text: string }) {
  const html = useMemo(() => renderContent(text), [text]);

  return (
    <div
      className="message-content text-sm leading-relaxed [&_p]:mb-2 [&_p:last-child]:mb-0"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
