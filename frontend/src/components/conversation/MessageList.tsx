"use client";

import React, { useEffect, useRef, useMemo, useState, useCallback } from "react";
import { User, Bot, Trash2, Pencil, Check, X, ChevronDown, ChevronLeft, ChevronRight, Copy } from "lucide-react";
import ResponseBlockRenderer from "./ResponseBlockRenderer";
import QuoteBlockRenderer from "./QuoteBlockRenderer";
import TextSelectionToolbar from "./TextSelectionToolbar";
import SubBranchInline from "./SubBranchInline";
import SpeakButton from "./SpeakButton";
import MarkdownRenderer from "./MarkdownRenderer";
import CognitiveTag from "./CognitiveTag";
import { useTextSelection } from "./useTextSelection";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { useConversationStore } from "@/store/conversation-store";
import type { TreeNode, ResponseBlock, SubBranchInfo } from "@/types";

// MessageList 组件属性接口
// messages: 消息树节点列表；responseBlocks: 响应块列表
// isLoading/statusMessage: 加载状态控制；onDeleteMessage/onEditMessage/onVersionSwitch: 消息增删改查回调
interface MessageListProps {
  messages: TreeNode[];
  responseBlocks: ResponseBlock[];
  isLoading?: boolean;
  statusMessage?: string;
  replyingToId?: string | null;  // 正在回复的消息 ID，loading 显示在该消息下方
  onDeleteMessage?: (messageId: string) => void;
  onEditMessage?: (messageId: string, newText: string) => Promise<number>;
  onVersionSwitch?: (messageId: string, direction: "prev" | "next", currentIndex?: number) => Promise<{ index: number; total: number } | null>;
}

// 已编辑消息文本的映射表：messageId -> 新文本
type EditedMap = Record<string, string>;

// 消息列表主组件：渲染用户和助手消息气泡，支持编辑/删除/版本切换/复制/语音
export default function MessageList({
  messages,
  responseBlocks,
  isLoading = false,
  statusMessage,
  replyingToId,
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

  // Store actions
  const setPendingQuote = useConversationStore((s) => s.setPendingQuote);
  const enterSubBranch = useConversationStore((s) => s.enterSubBranch);
  const loadSubBranches = useConversationStore((s) => s.loadSubBranches);

  // Text selection (extracted to useTextSelection hook)
  const {
    selection,
    handleTextMouseDown,
    handleTextClick,
    handleTextMouseUp,
    handleTextContextMenu,
    handleQuote,
    handleSelectionCopy,
  } = useTextSelection(setPendingQuote);

  // Sub-branch data per message
  const [subBranchData, setSubBranchData] = useState<Record<string, SubBranchInfo[]>>({});

  // Load sub-branches for messages that have them
  useEffect(() => {
    for (const msg of messages) {
      if (msg.has_sub_branches && !subBranchData[msg.id]) {
        loadSubBranches(msg.id).then((branches) => {
          if (branches.length > 0) {
            setSubBranchData((prev) => ({ ...prev, [msg.id]: branches }));
          }
        });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.map((m) => m.id).join(",")]);

  // 加载已修改消息的版本信息（页面刷新后恢复 versionMap）
  useEffect(() => {
    const modifiedIds = messages
      .filter(m => m.role === "user" && m.has_modified_version && !versionMap[m.id])
      .map(m => m.id);
    if (modifiedIds.length === 0) return;

    let cancelled = false;
    Promise.all(
      modifiedIds.map(async (msgId) => {
        try {
          const res = await fetch(`/api/conversations/tree/message/${msgId}`, { cache: "no-store" });
          if (!res.ok) return { msgId, total: 0, index: 0 };
          const data = await res.json();
          const versions: string[] = data.versions || [];
          const total = versions.length;
          const idx = versions.indexOf(msgId);
          return { msgId, total, index: idx >= 0 ? idx + 1 : total };
        } catch (e) {

          return { msgId, total: 0, index: 0 };
        }
      })
    ).then(results => {
      if (cancelled) return;
      setVersionMap(prev => {
        const next = { ...prev };
        for (const r of results) {
          if (r.total > 1 && !prev[r.msgId]) {
            next[r.msgId] = { index: r.index, total: r.total };
          }
        }
        return next;
      });
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.map(m => m.id).join(",")]);

  // 复制消息文本到剪贴板（优先使用 Clipboard API，降级方案为 textarea + execCommand）
  const handleCopyMessage = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (e) {

      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
  };

  // 版本导航处理：切换到上/下一个版本
  const handleVersionNav = async (messageId: string, direction: "prev" | "next") => {
    if (!onVersionSwitch) return;
    const currentIdx = versionMap[messageId]?.index;
    const result = await onVersionSwitch(messageId, direction, currentIdx);
    if (result) {
      // Backend returns full new messages list — find the new user message and update versionMap
      const newUserMsg = messages.find(
        m => m.role === "user" && m.id !== messageId
      );
      const newMsgId = newUserMsg?.id || messageId;
      setVersionMap(prev => {
        const next = { ...prev };
        next[newMsgId] = result;
        if (newMsgId !== messageId) delete next[messageId];
        return next;
      });
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
        // 始终记录编辑后的文本，确保 UI 显示最新内容
        const verTotal = result > 0 ? result : 2; // 编辑后至少有原版+新版
        setEditedTexts(prev => ({ ...prev, [msgId]: newText }));
        // index=verTotal 表示当前显示的是最新版本
        setVersionMap(prev => ({ ...prev, [msgId]: { index: verTotal, total: verTotal } }));
      } catch (e) {

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
  const prevMsgsRef = useRef<{ len: number; lastId: string; result: TreeNode[] } | null>(null);
  const dedupedMessages = useMemo(() => {
    const lastId = messages.length > 0 ? messages[messages.length - 1].id : "";
    const prev = prevMsgsRef.current;
    if (prev && prev.len === messages.length && prev.lastId === lastId) {
      return prev.result;
    }
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
    const result = Array.from(seen.values()).reverse();
    prevMsgsRef.current = { len: messages.length, lastId, result };
    return result;
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
  // Loading 动画组件（内联复用）
  const loadingIndicator = statusMessage ? (
    <div className="flex gap-4">
      <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-[var(--color-surface)] text-[var(--color-accent)] border border-[var(--color-border)]">
        <Bot size={16} />
      </div>
      <div className="flex items-center gap-2 px-4 py-2.5">
        <div className="flex gap-1.5 items-center">
          <span className="w-2 h-2 bg-[var(--color-text-muted)] rounded-full animate-pulse" style={{ animationDelay: "0ms" }} />
          <span className="w-2 h-2 bg-[var(--color-text-muted)] rounded-full animate-pulse" style={{ animationDelay: "200ms" }} />
          <span className="w-2 h-2 bg-[var(--color-text-muted)] rounded-full animate-pulse" style={{ animationDelay: "400ms" }} />
        </div>
        {statusMessage && <span className="text-xs text-[var(--color-text-muted)] ml-1">{statusMessage}</span>}
      </div>
    </div>
  ) : null;

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <ErrorBoundary>
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto px-4 pt-6 pb-2 space-y-6"
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
            <>
            <div key={message.id} className={`message-enter flex gap-4 ${isUser ? "flex-row-reverse" : ""}`}>
              {/* Avatar */}
              <div
                className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                  isUser
                    ? "bg-[var(--color-accent)] text-white"
                    : "bg-[var(--color-surface)] text-[var(--color-accent)] border border-[var(--color-border)]"
                }`}
              >
                {isUser ? <User size={16} /> : <Bot size={16} />}
              </div>

              {/* Content */}
              <div className={`flex-1 min-w-0 ${isUser ? "flex justify-end" : ""}`}>
                <div className={`relative max-w-[85%] pb-5 ${isUser ? "" : "space-y-0"}`}>
                  {isUser ? (
                    <div className="group">
                    {/* Render quote blocks from content_blocks */}
                    {(message.content_blocks || [])
                      .filter((b) => b.type === "quote")
                      .map((b, qi) => (
                        <QuoteBlockRenderer
                          key={`quote-${qi}`}
                          quotedText={b.quoted_text || ""}
                          sourceConversationId={b.source_conversation_id}
                          sourceMessageId={b.source_message_id}
                        />
                      ))}
                    <div className="bg-[var(--color-surface)] border border-[var(--color-border)] px-4 pb-2.5 pt-2.5 rounded-[14px] rounded-tr-[14px] rounded-br-none">
                      {isEditing ? (
                        <div className="space-y-2 min-w-[200px]">
                          <textarea
                            value={editingText}
                            onChange={(e) => setEditingText(e.target.value)}
                            className="w-full bg-white  border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 resize-none rounded-lg"
                            rows={3}
                            autoFocus
                          />
                          <div className="flex justify-end gap-2">
                            <button onClick={handleCancelEdit} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                              <X size={14} />
                            </button>
                            <button onClick={handleSaveEdit} className="p-1 text-[var(--color-success)] hover:text-[var(--color-success)]">
                              <Check size={14} />
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div
                          data-message-id={message.id}
                          data-conversation-id={message.conversation_id}
                          data-full-text={displayText}
                          className="text-base leading-[1.65] text-[var(--color-text)] whitespace-pre-wrap break-words select-text"
                          onMouseDown={handleTextMouseDown}
                          onMouseUp={handleTextMouseUp}
                          onContextMenu={handleTextContextMenu}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleTextClick(e, message.id, message.conversation_id, displayText);
                          }}
                        >
                          <MarkdownRenderer content={displayText} />
                        </div>
                      )}
                    </div>
                    {/* SubBranchInline for user messages */}
                    {subBranchData[message.id] && subBranchData[message.id].length > 0 && (
                      <div className="mt-1">
                        <SubBranchInline
                          messageId={message.id}
                          subBranches={subBranchData[message.id]}
                          onEnter={(convId) => enterSubBranch(convId)}
                        />
                      </div>
                    )}
                      {/* 用户消息操作按钮：编辑/删除/复制 — 在气泡下方 */}
                      {!isEditing && (
                        <div className="absolute bottom-0 right-0 flex items-center gap-1 bg-[var(--color-surface)] rounded-bl-md px-1 py-0.5 opacity-0 group-hover:opacity-100 max-lg:opacity-100 transition-opacity">
                          {/* 版本切换导航 */}
                          {vInfo.total > 1 && (
                            <div className="flex items-center gap-0.5 text-xs text-[var(--color-text-muted)] mr-1 border-r border-[var(--color-border)] pr-1">
                              <button onClick={() => handleVersionNav(message.id, "prev")} className="p-0.5 hover:text-[var(--color-text)]" title="上一版本">
                                <ChevronLeft size={12} />
                              </button>
                              <span className="min-w-[2em] text-center font-mono">{vInfo.index}/{vInfo.total}</span>
                              <button onClick={() => handleVersionNav(message.id, "next")} className="p-0.5 hover:text-[var(--color-text)]" title="下一版本">
                                <ChevronRight size={12} />
                              </button>
                            </div>
                          )}
                          <button onClick={() => handleStartEdit(message.id, displayText)} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]" title="编辑">
                            <Pencil size={12} />
                          </button>
                          <button onClick={() => handleDeleteMessage(message.id)} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-error)]" title="删除">
                            <Trash2 size={12} />
                          </button>
                          <button onClick={() => handleCopyMessage(displayText)} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]" title="复制">
                            <Copy size={12} />
                          </button>
                        </div>
                      )}
                    {/* CognitiveTag for user messages */}
                    <CognitiveTag messageId={message.id} messageText={displayText} initialNodeIds={message.cognitive_node_ids} />
                  </div>
                ) : (
                  <div className="group">
                    {/* Render quote blocks from content_blocks */}
                    {(message.content_blocks || [])
                      .filter((b) => b.type === "quote")
                      .map((b, qi) => (
                        <QuoteBlockRenderer
                          key={`quote-${qi}`}
                          quotedText={b.quoted_text || ""}
                          sourceConversationId={b.source_conversation_id}
                          sourceMessageId={b.source_message_id}
                        />
                      ))}
                    <div className="bg-[var(--color-surface-alt)] text-[var(--color-text)] px-4 py-3 rounded-[14px] rounded-tl-[14px] rounded-bl-none">
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
                            <button onClick={handleSaveEdit} className="p-1 text-[var(--color-success)] hover:text-[var(--color-success)]">
                              <Check size={14} />
                            </button>
                          </div>
                        </div>
                      ) : !displayText.trim() && messageBlocks.length === 0 && isLoading ? (
                        // 空占位消息 + 加载中 → 紧凑三点动画，不渲染空气泡
                        <div className="flex gap-1.5 items-center py-1 px-1">
                          <span className="w-2 h-2 bg-[var(--color-text-muted)] rounded-full animate-pulse" style={{ animationDelay: "0ms" }} />
                          <span className="w-2 h-2 bg-[var(--color-text-muted)] rounded-full animate-pulse" style={{ animationDelay: "200ms" }} />
                          <span className="w-2 h-2 bg-[var(--color-text-muted)] rounded-full animate-pulse" style={{ animationDelay: "400ms" }} />
                        </div>
                      ) : (
                        <>
                          <div
                            data-message-id={message.id}
                            data-conversation-id={message.conversation_id}
                            data-full-text={displayText}
                            className="text-base leading-[1.65] whitespace-pre-wrap break-words select-text"
                            onMouseDown={handleTextMouseDown}
                            onMouseUp={handleTextMouseUp}
                            onContextMenu={handleTextContextMenu}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleTextClick(e, message.id, message.conversation_id, displayText);
                            }}
                          >
                            <MarkdownRenderer content={displayText} />
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
                    {/* SubBranchInline for assistant messages */}
                    {subBranchData[message.id] && subBranchData[message.id].length > 0 && (
                      <div className="mt-1">
                        <SubBranchInline
                          messageId={message.id}
                          subBranches={subBranchData[message.id]}
                          onEnter={(convId) => enterSubBranch(convId)}
                        />
                      </div>
                    )}
                      {/* 消息操作按钮：删除/复制/语音 — 在气泡下方 */}
                      {!isEditing && (
                        <div className="absolute bottom-0 left-0 flex items-center gap-1 bg-[var(--color-surface)] rounded-br-md px-1 py-0.5 opacity-0 group-hover:opacity-100 max-lg:opacity-100 transition-opacity">
                          <button onClick={() => handleDeleteMessage(message.id)} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-error)]" title="删除">
                            <Trash2 size={12} />
                          </button>
                          <button onClick={() => handleCopyMessage(displayText)} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]" title="复制">
                            <Copy size={12} />
                          </button>
                          <SpeakButton text={displayText} />
                        </div>
                      )}
                    {/* CognitiveTag for assistant messages */}
                    <CognitiveTag messageId={message.id} messageText={displayText} initialNodeIds={message.cognitive_node_ids} />
                  </div>
                )}
                </div>
              </div>
            </div>
            {/* 编辑后 AI 重新回复时，loading 显示在被编辑消息的下方 */}
            {replyingToId === message.id && loadingIndicator}
            </>
          );
        })}

        {/* 加载中动画 — 发送新消息时（replyingToId 为空）显示在底部 */}
        {isLoading && !replyingToId && !messages.some(m => m.role === "assistant" && !(m.content_blocks?.find(b => b.type === "text")?.text || "").trim()) && loadingIndicator}

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
      </ErrorBoundary>

      {/* Text Selection Toolbar */}
      {selection && (
        <TextSelectionToolbar
          position={selection.position}
          visible={true}
          onQuote={handleQuote}
          onCopy={handleSelectionCopy}
          level={selection.level}
          source={selection.source}
        />
      )}

      {/* 滚动到底部按钮：用户向上滚动时出现，点击回到最新消息 */}
      {showScrollButton && (
        <div className="absolute bottom-20 right-4">
          <button
            onClick={() => bottomRef.current?.scrollIntoView({ behavior: "smooth" })}
            className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-full p-2 hover:bg-[var(--color-surface-hover)] transition-colors"
          >
            <ChevronDown size={20} />
          </button>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════
