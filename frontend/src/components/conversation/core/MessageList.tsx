"use client";

import React, { Fragment, useEffect, useRef, useMemo, useState, useCallback } from "react";
import { User, Bot, GraduationCap, ChevronDown, FileText, ImageIcon, ExternalLink } from "lucide-react";
import ResponseBlockRenderer from "./../blocks/ResponseBlockRenderer";
import QuoteBlockRenderer from "./../blocks/QuoteBlockRenderer";
import TextSelectionToolbar from "./../input/TextSelectionToolbar";
import SubBranchInline from "./../blocks/SubBranchInline";
import SpeakButton from "./../media/SpeakButton";
import MarkdownRenderer from "./../blocks/MarkdownRenderer";
import CognitiveTag from "./../cards/CognitiveTag";
import MessageActions from "./MessageActions";
import MessageEditArea from "./MessageEditArea";
import { useTextSelection } from "./../hooks/useTextSelection";
import NoteCard from "./../cards/NoteCard";
import KnowledgeExplainCard from "./../cards/KnowledgeExplainCard";
import { useExplainStore, getCardsForMessage } from "@/store/explain/explain-store";
import type { ExplainCardData } from "@/store/explain/explain-store";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { useConversationStore } from "@/store/conversation/conversation-store";
import type { MessageNode, ResponseBlock, SubBranchInfo } from "@/types";

// ── Inline explain markers — embeds badge(s) into rendered text via DOM injection ──
function ExplainMarkers({ text, cards, messageId, onBadgeClick }: {
  text: string;
  cards: ExplainCardData[];
  messageId: string;
  onBadgeClick?: (cardId: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [badgePositions, setBadgePositions] = useState<Array<{id:string;x:number;y:number;depth:number}>>([]);
  // 过滤有效卡片，减少循环
  const validCards = useMemo(() => cards.filter(c => c.depth === 1 && !!c.selected_text), [cards]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || validCards.length === 0) return;
    const posList: typeof badgePositions = [];
    const fullText = container.textContent || '';
    const containerRect = container.getBoundingClientRect(); // 只取一次容器坐标

    for (const card of validCards) {
      const selText = card.selected_text!;
      // 用 char_start 作为搜索起点（非绝对索引），避免 Markdown 渲染导致的长度差异
      let startIdx = -1;
      if (card.char_start != null) {
        // 从 char_start 近邻搜索，clamp 到 DOM 文本范围内
        const searchFrom = Math.max(0, Math.min(card.char_start, fullText.length));
        startIdx = fullText.indexOf(selText, searchFrom);
        // 如果往前没找到，尝试从 char_start 往回找
        if (startIdx < 0) {
          startIdx = fullText.lastIndexOf(selText, searchFrom + selText.length);
        }
      }
      if (startIdx < 0) {
        // fallback: 传统全文字符搜索
        startIdx = fullText.indexOf(selText);
      }
      if (startIdx < 0) continue;
      const endIdx = startIdx + selText.length;

      const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
      let node: Text | null = walker.firstChild() as Text | null;
      let charCount = 0;
      while (node) {
        const nodeLen = node.textContent?.length || 0;
        if (charCount + nodeLen >= endIdx) {
          const offset = endIdx - charCount;
          const range = document.createRange();
          range.setStart(node, offset);
          range.collapse(true);
          const rect = range.getBoundingClientRect();
          posList.push({
            id: card.id,
            x: rect.left - containerRect.left,
            y: rect.top - containerRect.top,
            depth: card.depth,
          });
          break;
        }
        charCount += nodeLen;
        node = walker.nextSibling() as Text | null;
      }
    }
    setBadgePositions(posList);
  }, [validCards, messageId]); // 去掉text依赖

  return (
    <div ref={containerRef} className="relative">
      <MarkdownRenderer content={text} />
      {badgePositions.map(item => (
        <sup
          key={item.id}
          className="explain-badge-sup absolute inline-flex items-center justify-center w-3 h-3 rounded-full bg-indigo-500 text-white text-[6px] font-bold cursor-pointer select-none hover:ring-1 hover:ring-white/60 transition-all z-[2]"
          style={{ left: item.x, top: item.y - 4 }}
          onClick={(e) => { e.stopPropagation(); onBadgeClick?.(item.id); }}
        >
          {item.depth}
        </sup>
      ))}
    </div>
  );
}

// ── Badge colors ──
const BADGE_COLORS = [
  "bg-indigo-500", "bg-emerald-500", "bg-amber-500",
  "bg-rose-500", "bg-cyan-500", "bg-violet-500",
];

// ── Floating explain card — draggable, with anchor badge ──
function FloatingExplainCard({ card }: { card: ExplainCardData }) {
  const updateCard = useExplainStore((s) => s.updateCard);
  const [renderPos, setRenderPos] = useState({ x: card.pos_x || 0, y: card.pos_y || 0 });
  const posRef = useRef({ x: card.pos_x || 0, y: card.pos_y || 0 });
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Sync from store when not dragging
  useEffect(() => {
    posRef.current = { x: card.pos_x || 0, y: card.pos_y || 0 };
    setRenderPos({ x: card.pos_x || 0, y: card.pos_y || 0 });
  }, [card.pos_x, card.pos_y]);

  // 卡片折叠时不渲染外层 wrapper（避免空 div 遮挡点击）
  if (card.collapsed) return <KnowledgeExplainCard card={card} />;

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    // Only drag from data-drag-handle elements (the header)
    const target = e.target as HTMLElement;
    const handle = target.closest('[data-drag-handle="true"]');
    if (!handle) return;
    e.preventDefault();
    e.stopPropagation(); // 阻止 KnowledgeExplainCard 内部的重复拖拽处理

    // 禁用 transition 避免拖动延迟
    if (wrapperRef.current) {
      wrapperRef.current.style.transition = "none";
    }

    const onMove = (ev: MouseEvent) => {
      const dx = ev.clientX - e.clientX;
      const dy = ev.clientY - e.clientY;
      const newX = posRef.current.x + dx;
      const newY = posRef.current.y + dy;
      // 直接操作 DOM，避免 setState 重渲染
      if (wrapperRef.current) {
        wrapperRef.current.style.left = `${newX}px`;
        wrapperRef.current.style.top = `${newY}px`;
      }
    };

    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      // 恢复 transition
      if (wrapperRef.current) {
        wrapperRef.current.style.transition = "";
      }
      // 读取最终位置并提交
      const finalX = parseInt(wrapperRef.current?.style.left || "0");
      const finalY = parseInt(wrapperRef.current?.style.top || "0");
      posRef.current = { x: finalX, y: finalY };
      setRenderPos({ x: finalX, y: finalY });
      updateCard(card.id, {
        pos_x: Math.round(finalX),
        pos_y: Math.round(finalY),
      });
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [card.id, updateCard]);

  return (
    <div
      ref={wrapperRef}
      className="absolute z-10 select-none"
      style={{ left: `${renderPos.x}px`, top: `${renderPos.y}px` }}
    >
      <div onMouseDown={onMouseDown}>
        <KnowledgeExplainCard card={card} />
      </div>
    </div>
  );
}

interface MessageListProps {
  messages: MessageNode[];
  responseBlocks: ResponseBlock[];
  isLoading?: boolean;
  statusMessage?: string;
  replyingToId?: string | null;
  conversationId?: string | null;  // for explain cards loading
  onDeleteMessage?: (messageId: string) => void;
  onEditMessage?: (messageId: string, newText: string) => Promise<number>;
  onSend?: (text: string) => void;
}

type EditedMap = Record<string, string>;

export default function MessageList({
  messages,
  responseBlocks,
  isLoading = false,
  statusMessage,
  replyingToId,
  conversationId,
  onDeleteMessage,
  onEditMessage,
  onSend,
}: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingText, setEditingText] = useState("");
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [editedTexts, setEditedTexts] = useState<EditedMap>({});
  const [subBranchData, setSubBranchData] = useState<Record<string, SubBranchInfo[]>>({});
  const [noteCard, setNoteCard] = useState<{ text: string; position: { x: number; y: number } } | null>(null);

  // ── 版本覆盖：用户点击 1/n 切换时，前端临时显示指定版本 ──
  // key = `${parent_id}::${role}`, value = 要显示的消息 ID
  const [versionOverrides, setVersionOverrides] = useState<Record<string, string>>({});

  const setPendingQuote = useConversationStore((s) => s.setPendingQuote);
  const enterSubBranch = useConversationStore((s) => s.enterSubBranch);
  const loadSubBranches = useConversationStore((s) => s.loadSubBranches);

  // ── Explain cards from store ──
  const explainCards = useExplainStore((s) => s.cards);
  const createCard = useExplainStore((s) => s.createCard);
  const loadFromConversation = useExplainStore((s) => s.loadFromConversation);

  // Load explain cards when conversation changes
  useEffect(() => {
    if (conversationId) {
      loadFromConversation(conversationId);
    } else {
      useExplainStore.getState().clearAll();
    }
  }, [conversationId, loadFromConversation]);

  const { selection, handleTextMouseDown, handleTextClick, handleTextMouseUp, handleTextContextMenu, handleQuote, handleSelectionCopy } = useTextSelection(setPendingQuote);

  // Load sub-branches
  useEffect(() => {
    for (const msg of messages) {
      if (msg.has_sub_branches && !subBranchData[msg.id]) {
        loadSubBranches(msg.id).then((branches) => {
          if (branches.length > 0) setSubBranchData((prev) => ({ ...prev, [msg.id]: branches }));
        });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.map((m) => m.id).join(",")]);

  const handleCopyMessage = async (text: string) => {
    try { await navigator.clipboard.writeText(text); }
    catch {
      const ta = document.createElement("textarea");
      ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select(); document.execCommand("copy"); document.body.removeChild(ta);
    }
  };

  // ── 版本切换：纯前端，不调后端 API ──
  // 在同一 parent_id+role 的版本组内切换
  const handleVersionNav = useCallback((messageId: string, _direction: "prev" | "next") => {
    const groupKey = versionGroupByMessage[messageId];
    if (!groupKey) return;
    const group = versionGroups[groupKey];
    if (!group || group.ids.length <= 1) return;
    const currentOverrideId = versionOverrides[groupKey];
    const allIds = group.ids;
    // 确定当前显示的是哪个版本
    let curIdx: number;
    if (currentOverrideId) {
      curIdx = allIds.indexOf(currentOverrideId);
    } else {
      curIdx = allIds.length - 1; // 默认显示最后（最新）
    }
    if (curIdx < 0) curIdx = allIds.length - 1;
    // 循环切换
    const newIdx = (curIdx - 1 + allIds.length) % allIds.length;
    const newId = allIds[newIdx];
    if (newIdx === allIds.length - 1) {
      // 回到最新版本 → 清除覆盖
      setVersionOverrides(prev => { const next = { ...prev }; delete next[groupKey]; return next; });
    } else {
      setVersionOverrides(prev => ({ ...prev, [groupKey]: newId }));
    }
  }, [versionOverrides]);

  const handleDeleteMessage = (messageId: string) => onDeleteMessage?.(messageId);
  const handleStartEdit = (msgId: string, currentText: string) => { setEditingId(msgId); setEditingText(currentText); };

  const handleSaveEdit = async () => {
    const msgId = editingId; const newText = editingText.trim();
    if (!msgId || !newText) { setEditingId(null); return; }
    if (onEditMessage) {
      try {
        await onEditMessage(msgId, newText);
        // 编辑后清除该消息旧版本的覆盖显示
        const groupKey = versionGroupByMessage[msgId];
        if (groupKey && versionOverrides[groupKey]) {
          setVersionOverrides(prev => { const next = { ...prev }; delete next[groupKey]; return next; });
        }
        setEditedTexts(prev => ({ ...prev, [msgId]: newText }));
      } catch {}
    }
    setEditingId(null);
  };

  const handleCancelEdit = () => setEditingId(null);

  // Auto-scroll
  useEffect(() => {
    if (bottomRef.current && !showScrollButton) bottomRef.current.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, messages[messages.length - 1]?.text_summary]);

  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    setShowScrollButton(scrollHeight - scrollTop - clientHeight > 300);
  }, []);

  // ── 版本感知显示 ──
  // 1) 构建版本组：groupKey = `${parent_id}::${role}`
  const { visibleMessages, versionGroups, versionGroupByMessage } = useMemo(() => {
    type GroupKey = string;
    // 收集每条消息的版本组 key
    const messageGroupKey = new Map<string, GroupKey>();
    for (const m of messages) {
      if (m.is_deleted) continue;
      messageGroupKey.set(m.id, `${m.parent_id}::${m.role}`);
    }
    // 每个组的所有消息 ID（按 conv.path 顺序）
    const groupIds = new Map<GroupKey, string[]>();
    for (const m of messages) {
      if (m.is_deleted) continue;
      const gk = messageGroupKey.get(m.id)!;
      if (!groupIds.has(gk)) groupIds.set(gk, []);
      groupIds.get(gk)!.push(m.id);
    }
    // 每个组的"活跃版本"：如果没有被覆盖显示，则取最后一个；否则取覆盖的版本
    const activeVersions = new Map<GroupKey, string>();
    groupIds.forEach((ids, gk) => {
      const overrideId = versionOverrides[gk];
      if (overrideId && ids.includes(overrideId)) {
        activeVersions.set(gk, overrideId);
      } else {
        activeVersions.set(gk, ids[ids.length - 1]);
      }
    });
    // 2) 确定可见消息：活跃版本 + 父节点也可见（递归）
    const activeIdSet = new Set<string>();
    // 所有消息 ID 集合（用于检测父节点是否被后端过滤，如根占位消息）
    const allMessageIds = new Set(messages.map(m => m.id));
    // 按 path 序遍历
    for (const m of messages) {
      if (m.is_deleted) continue;
      const gk = messageGroupKey.get(m.id)!;
      const activeId = activeVersions.get(gk);
      if (m.id !== activeId) continue; // 不是活跃版本，跳过
      // 父节点可见条件：
      // 1) 无父节点（根级消息），或
      // 2) 父节点已在 activeIdSet 中，或
      // 3) 父节点不存在于 messages 中（被后端过滤，如根占位消息）
      if (!m.parent_id || activeIdSet.has(m.parent_id) || !allMessageIds.has(m.parent_id)) {
        activeIdSet.add(m.id);
      }
    }
    // 按 path 顺序输出
    const vis = messages.filter(m => activeIdSet.has(m.id));
    // 版本组信息（用于 1/n 展示）
    const vg: Record<GroupKey, { ids: string[]; activeIndex: number; total: number }> = {};
    groupIds.forEach((ids, gk) => {
      if (ids.length > 1) {
        const active = activeVersions.get(gk)!;
        const activeIdx = ids.indexOf(active);
        vg[gk] = { ids, activeIndex: activeIdx >= 0 ? activeIdx : ids.length - 1, total: ids.length };
      }
    });
    // 每条消息 → 其版本组 key
    const vgbm: Record<string, string> = {};
    messageGroupKey.forEach((gk, mid) => {
      vgbm[mid] = gk;
    });
    return { visibleMessages: vis, versionGroups: vg, versionGroupByMessage: vgbm };
  }, [messages, versionOverrides]);

  // Group response blocks by message_id
  const blocksByMessage = useMemo(() => {
    const map = new Map<string, ResponseBlock[]>();
    for (const block of responseBlocks || []) {
      const id = block.message_id || "";
      if (!map.has(id)) map.set(id, []);
      map.get(id)!.push(block);
    }
    return map;
  }, [responseBlocks]);

  // Get display text from a message
  const getDisplayText = (msg: MessageNode) =>
    editedTexts[msg.id] || msg.content_blocks?.filter(b => b.type === "text").map(b => b.text || "").join("\n\n") || "";

  // Loading indicator
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
      <div ref={containerRef} className="flex-1 overflow-y-auto px-4 pt-6 pb-2 space-y-6" onScroll={handleScroll}>
        {visibleMessages.map((message) => {
          const isUser = message.role === "user";
          const isEditing = editingId === message.id;
          const messageBlocks = blocksByMessage.get(message.id) || [];
          const displayText = getDisplayText(message);
          const groupKey = versionGroupByMessage[message.id];
          const group = groupKey ? versionGroups[groupKey] : undefined;
          const hasVersions = !!group && group.total > 1;
          const vInfo = hasVersions
            ? { index: group.activeIndex + 1, total: group.total }
            : { index: 1, total: 1 };
          const cardsForMsg = getCardsForMessage(message.id, explainCards);

          return (
            <Fragment key={message.id}>
              {/* AI Avatar + label — above the message for assistant */}
              {!isUser && (
                <div className="flex items-center gap-2 mb-1.5 px-1">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-white bg-blue-500">
                    <GraduationCap size={16} />
                  </div>
                  <span className="text-xs font-medium text-[var(--color-text-muted)]">教学助手</span>
                </div>
              )}
              <div className={`message-enter ${isUser ? "flex gap-4 flex-row-reverse" : ""}`}>
              {/* User avatar — same row for user */}
              {isUser && (
              <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-[var(--color-accent)] text-white`}>
                <User size={16} />
              </div>
              )}

              {/* Content */}
              <div className={`flex-1 min-w-0 ${isUser ? "flex justify-end" : ""}`}>
                <div className={`relative pb-7 ${isUser ? "max-w-[85%]" : ""}`}
                  style={{ overflow: 'visible', scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
                  <div className="group">
                    {/* Quote blocks */}
                    {(message.content_blocks || []).filter(b => b.type === "quote").map((b, qi) => (
                      <QuoteBlockRenderer key={`quote-${qi}`} quotedText={b.quoted_text || ""}
                        sourceConversationId={b.source_conversation_id} sourceMessageId={b.source_message_id} />
                    ))}

                    {/* Uploaded file attachments — show for user messages */}
                    {(message.content_blocks || []).filter(b => b.type === "file" || b.type === "image").length > 0 && (
                      <div className="mb-2 flex flex-wrap gap-1.5">
                        {(message.content_blocks || []).filter(b => b.type === "file" || b.type === "image").map((b, fi) => {
                          const mid = (b as any).material_id;
                          return (
                            <div key={`file-${fi}`}
                              className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]/60 text-[11px] text-[var(--color-text-secondary)]">
                              {b.type === "image" ? <ImageIcon size={12} className="text-blue-500" /> : <FileText size={12} className="text-[var(--color-accent)]" />}
                              <span className="truncate max-w-[120px]">{b.name || "未命名文件"}</span>
                              {mid ? (
                                <a href={`/files/${mid}`} target="_blank" rel="noreferrer"
                                  className="text-[var(--color-text-muted)] hover:text-[var(--color-accent)] ml-0.5">
                                  <ExternalLink size={10} />
                                </a>
                              ) : (
                                <span className="text-[9px] text-green-500/70 animate-pulse">索引中</span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {/*
                    {/* Content bubble */}
                    <div className={`relative ${isUser
                      ? "bg-[var(--color-surface)] border border-[var(--color-border)] px-4 pb-2.5 pt-2.5 rounded-[14px] rounded-tr-[14px] rounded-br-none"
                      : "bg-[var(--color-surface-alt)] text-[var(--color-text)] px-4 py-3 rounded-[14px] rounded-tl-[14px] rounded-bl-none"
                    }`}>
                      {isEditing ? (
                        <MessageEditArea text={editingText} onChange={setEditingText} onSave={handleSaveEdit} onCancel={handleCancelEdit} />
                      ) : isUser ? (
                        <>
                          <div data-message-id={message.id} data-conversation-id={message.conversation_id} data-full-text={displayText}
                            className="text-base leading-[1.65] text-[var(--color-text)] whitespace-pre-wrap break-words select-text"
                          >
                            <ExplainMarkers text={displayText} cards={cardsForMsg} messageId={message.id} onBadgeClick={(id) => {
                              const c = useExplainStore.getState().cards.find(c => c.id === id);
                              if (c) useExplainStore.getState().toggleCollapse(id, !c.collapsed);
                            }} />
                          </div>
                        </>
                      ) : !displayText.trim() && messageBlocks.length === 0 && isLoading ? (
                        <div className="flex gap-1.5 items-center py-1 px-1">
                          <span className="w-2 h-2 bg-[var(--color-text-muted)] rounded-full animate-pulse" style={{ animationDelay: "0ms" }} />
                          <span className="w-2 h-2 bg-[var(--color-text-muted)] rounded-full animate-pulse" style={{ animationDelay: "200ms" }} />
                          <span className="w-2 h-2 bg-[var(--color-text-muted)] rounded-full animate-pulse" style={{ animationDelay: "400ms" }} />
                        </div>
                      ) : (
                        <>
                          <div data-message-id={message.id} data-conversation-id={message.conversation_id} data-full-text={displayText}
                            className="text-base leading-[1.65] whitespace-pre-wrap break-words select-text"
                            onMouseDown={handleTextMouseDown} onMouseUp={handleTextMouseUp} onContextMenu={handleTextContextMenu}
                            onClick={(e) => { e.stopPropagation(); handleTextClick(e, message.id, message.conversation_id || "", displayText); }}
                          >
                            <ExplainMarkers text={displayText} cards={cardsForMsg} messageId={message.id} onBadgeClick={(id) => {
                              const c = useExplainStore.getState().cards.find(c => c.id === id);
                              if (c) useExplainStore.getState().toggleCollapse(id, !c.collapsed);
                            }} />
                          </div>
                          {messageBlocks.length > 0 && (
                            <div className="mt-3 border-t border-[var(--color-border)] pt-3 space-y-2">
                              {messageBlocks.map(block => <ResponseBlockRenderer key={block.id} block={block} />)}
                            </div>
                          )}
                        </>
                      )}

                      {/* Floating explain cards — absolute positioned near selected text */}
                      {cardsForMsg.filter(ec => ec.depth === 1).map((ec) => (
                        <FloatingExplainCard key={ec.id} card={ec} />
                      ))}
                      {/* Child cards (depth 2+) — also use FloatingExplainCard for drag support */}
                      {cardsForMsg.filter(ec => ec.depth >= 2).map((ec) => (
                        <FloatingExplainCard key={ec.id} card={ec} />
                      ))}

                      {/* Explain cards inline */}
                      {/* Cognitive tag */}
                      <div className="flex justify-end mt-1">
                        <CognitiveTag messageId={message.id} messageText={displayText} initialNodeIds={message.cognitive_node_ids} />
                      </div>
                    </div>

                    {/* Sub-branch inline */}
                    {subBranchData[message.id]?.length > 0 && (
                      <div className="mt-1">
                        <SubBranchInline messageId={message.id} subBranches={subBranchData[message.id]} onEnter={(convId) => enterSubBranch(convId)} />
                      </div>
                    )}

                    {/* Action buttons */}
                    {!isEditing && (
                      <MessageActions
                        role={isUser ? "user" : "assistant"}
                        vInfo={vInfo}
                        hasVersions={hasVersions}
                        text={displayText}
                        onEdit={isUser ? () => handleStartEdit(message.id, displayText) : undefined}
                        onDelete={() => handleDeleteMessage(message.id)}
                        onCopy={() => handleCopyMessage(displayText)}
                        onVersionNav={isUser ? (dir) => handleVersionNav(message.id, dir) : undefined}
                      />
                    )}
                  </div>
                </div>
              </div>
              {/* Loading indicator below the message being edited */}
              {replyingToId === message.id && loadingIndicator}
            </div>
          </Fragment>
          );
        })}

        {/* Bottom loading indicator for new messages */}
        {isLoading && !replyingToId && !messages.some(m => m.role === "assistant" && !(m.content_blocks?.find(b => b.type === "text")?.text || "").trim()) && loadingIndicator}

        {/* Standalone response blocks when no messages */}
        {responseBlocks.length > 0 && messages.length === 0 && (
          <div className="space-y-2">{responseBlocks.map(block => <ResponseBlockRenderer key={block.id} block={block} />)}</div>
        )}

        <div ref={bottomRef} />
      </div>
      </ErrorBoundary>

      {/* Text Selection Toolbar */}
      {selection && (
        <TextSelectionToolbar position={selection.position} visible={true} onQuote={handleQuote} onCopy={handleSelectionCopy}
          level={selection.level} source={selection.source}
          onExplain={() => {
            if (!selection) return;
            const text = selection.text;
            if (!text) return;

            // Helper: convert viewport coords to bubble-relative
            const toBubblePos = (cx: number, cy: number) => {
              if (!selection.messageId) return { x: 0, y: 0 };
              const msgEl = document.querySelector(`[data-message-id="${selection.messageId}"]`);
              if (!msgEl) return { x: 0, y: 0 };
              const bubble = msgEl.closest('[class*="rounded-\\[14px\\]"]');
              if (!bubble) return { x: 0, y: 0 };
              const brect = bubble.getBoundingClientRect();
              const cs = window.getComputedStyle(bubble);
              const pl = parseFloat(cs.paddingLeft) || 0;
              const pt = parseFloat(cs.paddingTop) || 0;
              return {
                x: Math.round(cx - brect.left - pl),
                y: Math.round(cy - brect.top - pt),
              };
            };

            // Card position: from mouse cursor (where user released)
            const cardPos = toBubblePos(selection.position.x, selection.position.y);

            // Badge position: find selected text in message DOM via TreeWalker
            let badgePos = cardPos;
            if (selection.messageId) {
              const msgEl = document.querySelector(`[data-message-id="${selection.messageId}"]`);
              if (msgEl) {
                try {
                  const walker = document.createTreeWalker(
                    msgEl, NodeFilter.SHOW_TEXT, null
                  );
                  const fullText = msgEl.textContent || '';
                  // 用 charStart 作为搜索起点而非绝对索引（兼容 Markdown 渲染差异）
                  let startIdx = -1;
                  const searchFrom = Math.max(0, Math.min(selection.charStart, fullText.length));
                  startIdx = fullText.indexOf(text, searchFrom);
                  if (startIdx < 0) startIdx = fullText.lastIndexOf(text, searchFrom + text.length);
                  if (startIdx < 0) startIdx = fullText.indexOf(text);
                  if (startIdx >= 0) {
                    const endIdx = startIdx + text.length;
                    let node: Text | null = walker.firstChild() as Text | null;
                    let charCount = 0;
                    while (node) {
                      const nodeLen = node.textContent?.length || 0;
                      if (charCount + nodeLen >= endIdx) {
                        const range = document.createRange();
                        range.setStart(node, endIdx - charCount);
                        range.collapse(true);
                        const r = range.getBoundingClientRect();
                        if (r && r.left > 0 && r.top > 0) {
                          badgePos = toBubblePos(r.left, r.top);
                        }
                        break;
                      }
                      charCount += nodeLen;
                      node = walker.nextSibling() as Text | null;
                    }
                  }
                } catch { /* fallback to cardPos */ }
              }
            }

            createCard({
              conversation_id: selection.sourceConversationId,
              message_id: selection.messageId,
              depth: 1,
              selected_text: text,
              char_start: selection.charStart,
              pos_x: cardPos.x,
              pos_y: cardPos.y,
              badge_x: badgePos.x,
              badge_y: badgePos.y,
            });

            // Close selection toolbar
            window.getSelection()?.removeAllRanges();
          }}
          onNote={() => {
            const s = window.getSelection();
            if (s && !s.isCollapsed) {
              const r = s.getRangeAt(0);
              const rect = r.getBoundingClientRect();
              setNoteCard({ text: s.toString().trim(), position: { x: rect.left + rect.width / 2, y: rect.bottom } });
            }
          }}
        />
      )}

      {/* Note Card (笔记卡片) */}
      <div data-selection-card>
        <NoteCard
          selectedText={noteCard?.text || ""}
          position={noteCard?.position || { x: 0, y: 0 }}
          visible={!!noteCard}
          onClose={() => setNoteCard(null)}
          onSaveNote={(note) => {
            console.log("Note saved:", note);
            // TODO: persist note to backend
            setNoteCard(null);
          }}
        />
      </div>

      {/* Scroll-to-bottom button */}
      {showScrollButton && (
        <div className="absolute bottom-20 right-4">
          <button onClick={() => bottomRef.current?.scrollIntoView({ behavior: "smooth" })}
            className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-full p-2 hover:bg-[var(--color-surface-hover)] transition-colors">
            <ChevronDown size={20} />
          </button>
        </div>
      )}
    </div>
  );
}
