"use client";

import { useEffect, useRef, useMemo, useState, useCallback } from "react";
import { User, Bot, Trash2, Pencil, Check, X, ChevronDown, ChevronLeft, ChevronRight, Copy } from "lucide-react";
import ResponseBlockRenderer from "./ResponseBlockRenderer";
import SpeakButton from "./SpeakButton";
import { useRenderedContent } from "@/lib/useRenderedContent";
import type { TreeNode, ResponseBlock } from "@/types";

// MessageList 组件属性接口
// messages: 消息树节点列表；responseBlocks: 响应块列表
// isLoading/statusMessage: 加载状态控制；onDeleteMessage/onEditMessage/onVersionSwitch: 消息增删改查回调
interface MessageListProps {
  messages: TreeNode[];
  responseBlocks: ResponseBlock[];
  isLoading?: boolean;
  statusMessage?: string;
  onDeleteMessage?: (messageId: string) => void;
  onEditMessage?: (messageId: string, newText: string) => Promise<number>;
  onVersionSwitch?: (messageId: string, direction: "prev" | "next") => Promise<{ index: number; total: number } | null>;
}

// 已编辑消息文本的映射表：messageId -> 新文本
type EditedMap = Record<string, string>;

// 消息列表主组件：渲染用户和助手消息气泡，支持编辑/删除/版本切换/复制/语音
export default function MessageList({
  messages,
  responseBlocks,
  isLoading = false,
  statusMessage,
  onDeleteMessage,
  onEditMessage,
  onVersionSwitch,
}: MessageListProps) {
  // 容器 ref，用于滚动监听和定位
  const containerRef = useRef<HTMLDivElement>(null);
  // 底部锚点 ref，用于自动滚动到最新消息
  const bottomRef = useRef<HTMLDivElement>(null);

  // 当前正在编辑的消息 ID（null 表示未编辑）
  const [editingId, setEditingId] = useState<string | null>(null);
  // 编辑框中的当前文本
  const [editingText, setEditingText] = useState("");
  // 是否显示"滚动到底部"按钮
  const [showScrollButton, setShowScrollButton] = useState(false);
  // 已保存的编辑文本映射（持久化显示）
  const [editedTexts, setEditedTexts] = useState<EditedMap>({});

  // 版本导航状态：记录每条消息当前的版本索引和总数
  const [versionMap, setVersionMap] = useState<Record<string, { index: number; total: number }>>({});

  // 复制消息文本到剪贴板（优先使用 Clipboard API，降级方案为 textarea + execCommand）
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

  // 版本导航处理：切换到上/下一个版本，并更新版本映射状态
  const handleVersionNav = async (messageId: string, direction: "prev" | "next") => {
    if (!onVersionSwitch) return;
    const result = await onVersionSwitch(messageId, direction);
    if (result) {
      setVersionMap(prev => ({ ...prev, [messageId]: result }));
    }
  };

  // 删除消息（回调给父组件处理）
  const handleDeleteMessage = (messageId: string) => {
    if (onDeleteMessage) onDeleteMessage(messageId);
  };

  // 开始编辑消息：设置编辑 ID 和当前文本到编辑框
  const handleStartEdit = (msgId: string, currentText: string) => {
    setEditingId(msgId);
    setEditingText(currentText);
  };

  // 保存编辑：提交文本到父组件，成功后更新 editedTexts 和版本状态
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

  // 取消编辑：重置编辑状态
  const handleCancelEdit = () => {
    setEditingId(null);
  };

  // 自动滚动到底部：当新消息到达且用户未手动向上滚动时触发
  useEffect(() => {
    if (bottomRef.current && !showScrollButton) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages.length, messages[messages.length - 1]?.text_summary]);

  // 滚动事件处理：计算距离底部是否超过 300px，从而控制"滚动到底部"按钮显隐
  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    setShowScrollButton(scrollHeight - scrollTop - clientHeight > 300);
  }, []);

  // 消息去重：按 ID 去重，保留最后一条非空文本的消息（倒序遍历，优先保留有内容的消息）
  const dedupedMessages = useMemo(() => {
    const seen = new Map<string, TreeNode>();
    // 倒序遍历，让后续（最终完成的）版本覆盖前面（流式中间态）的版本
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.is_deleted) continue;
      const existing = seen.get(m.id);
      if (!existing) {
        seen.set(m.id, m);
      } else {
        // 如果已有记录，优先保留有文本内容的那一条
        const existingText = existing.content_blocks?.find(b => b.type === "text")?.text || "";
        const currentText = m.content_blocks?.find(b => b.type === "text")?.text || "";
        if (currentText && !existingText) {
          seen.set(m.id, m);
        }
      }
    }
    return Array.from(seen.values()).reverse();
  }, [messages]);

  // 按 message_id 将 responseBlocks 分组映射，便于在消息气泡下方展示
  const blocksByMessage = useMemo(() => {
    const map = new Map<string, ResponseBlock[]>();
    for (const block of responseBlocks || []) {
      const id = block.message_id || "";
      if (!map.has(id)) map.set(id, []);
      map.get(id)!.push(block);
    }
    return map;
  }, [responseBlocks]);

  // ==================== 渲染 JSX ====================
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto px-4 py-6 space-y-6"
        onScroll={handleScroll}
      >
        {dedupedMessages.map((message) => {
          // 判断消息角色：用户消息靠右显示，助手消息靠左显示
          const isUser = message.role === "user";
          // 判断当前消息是否处于编辑模式
          const isEditing = editingId === message.id;
          // 获取当前消息关联的响应块（如思维链、工具调用等）
          const messageBlocks = blocksByMessage.get(message.id) || [];

          // 获取展示文本：优先使用已编辑保存的文本，否则从 content_blocks 中拼接文本内容
          const displayText = editedTexts[message.id]
            || (message.content_blocks || [])
                .filter((b) => b.type === "text")
                .map((b) => b.text || "")
                .join("\n\n");

          // 判断是否有版本历史（已修改或已编辑）
          const hasVersions = message.has_modified_version || !!editedTexts[message.id];
          // 当前版本信息：index 当前版本号 / total 总版本数
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
                    <div className="group bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 px-4 pb-2.5 pt-2.5 rounded-2xl rounded-tr-md">
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
                      {/* 用户消息操作按钮：编辑/删除/复制 */}
                      {!isEditing && (
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button onClick={() => handleStartEdit(message.id, displayText)} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]" title="编辑">
                            <Pencil size={12} />
                          </button>
                          <button onClick={() => handleDeleteMessage(message.id)} className="p-1 text-[var(--color-text-muted)] hover:text-red-500" title="删除">
                            <Trash2 size={12} />
                          </button>
                          <button onClick={() => handleCopyMessage(displayText)} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]" title="复制">
                            <Copy size={12} />
                          </button>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="group bg-[var(--color-surface)] text-[var(--color-text)] px-4 py-3 rounded-2xl rounded-tl-md">
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
                          {/* 版本切换导航 */}
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
                          {/* 消息操作按钮：删除/复制/语音（AI 消息不可编辑） */}
                          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button onClick={() => handleDeleteMessage(message.id)} className="p-1 text-[var(--color-text-muted)] hover:text-red-500" title="删除">
                              <Trash2 size={12} />
                            </button>
                            <button onClick={() => handleCopyMessage(displayText)} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]" title="复制">
                              <Copy size={12} />
                            </button>
                            <SpeakButton text={displayText} />
                          </div>
                          {/* 响应块区域：思维链、工具调用结果等展示 */}
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

        {/* 加载中动画：三点跳动 + 状态消息 */}
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

        {/* 无消息但有响应块时，在底部内联展示 */}
        {responseBlocks.length > 0 && messages.length === 0 && (
          <div className="space-y-2">
            {responseBlocks.map(block => (
              <ResponseBlockRenderer key={block.id} block={block} />
            ))}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* 滚动到底部按钮：用户向上滚动时出现，点击回到最新消息 */}
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
