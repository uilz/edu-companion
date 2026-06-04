"use client";

import React, { Fragment, useEffect, useRef, useMemo, useState, useCallback } from "react";
import { User, Bot, ChevronDown } from "lucide-react";
import ResponseBlockRenderer from "./ResponseBlockRenderer";
import QuoteBlockRenderer from "./QuoteBlockRenderer";
import TextSelectionToolbar from "./TextSelectionToolbar";
import SubBranchInline from "./SubBranchInline";
import SpeakButton from "./SpeakButton";
import MarkdownRenderer from "./MarkdownRenderer";
import CognitiveTag from "./CognitiveTag";
import MessageActions from "./MessageActions";
import MessageEditArea from "./MessageEditArea";
import { useTextSelection } from "./useTextSelection";
import NoteCard from "./NoteCard";
import KnowledgeExplainCard from "./KnowledgeExplainCard";
import { useExplainStore, getCardsForMessage } from "@/store/explain-store";
import type { ExplainCardData } from "@/store/explain-store";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { useConversationStore } from "@/store/conversation-store";
import type { TreeNode, ResponseBlock, SubBranchInfo } from "@/types";

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
      const startIdx = fullText.indexOf(selText);
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
  const [dragging, setDragging] = useState(false);
  // Refs track the current drag state across renders (no closure issues)
  const dragRef = useRef({ active: false, startX: 0, startY: 0, origX: 0, origY: 0 });
  const posRef = useRef({ x: card.pos_x || 0, y: card.pos_y || 0 });

  // Sync from store when not dragging
  useEffect(() => {
    if (!dragRef.current.active) {
      posRef.current = { x: card.pos_x || 0, y: card.pos_y || 0 };
      setRenderPos({ x: card.pos_x || 0, y: card.pos_y || 0 });
    }
  }, [card.pos_x, card.pos_y]);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    // Only drag from data-drag-handle elements (the header)
    const target = e.target as HTMLElement;
    const handle = target.closest('[data-drag-handle="true"]');
    if (!handle) return;
    e.preventDefault();

    // Capture start state
    dragRef.current = {
      active: true,
      startX: e.clientX,
      startY: e.clientY,
      origX: posRef.current.x,
      origY: posRef.current.y,
    };
    setDragging(true);

    const onMove = (ev: MouseEvent) => {
      if (!dragRef.current.active) return;
      const dx = ev.clientX - dragRef.current.startX;
      const dy = ev.clientY - dragRef.current.startY;
      const newX = dragRef.current.origX + dx;
      const newY = dragRef.current.origY + dy;
      posRef.current = { x: newX, y: newY };
      setRenderPos({ x: newX, y: newY });
    };

    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      dragRef.current.active = false;
      setDragging(false);
      // Commit final position to store
      updateCard(card.id, {
        pos_x: Math.round(posRef.current.x),
        pos_y: Math.round(posRef.current.y),
      });
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [card.id, updateCard]);

  return (
    <div
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
  messages: TreeNode[];
  responseBlocks: ResponseBlock[];
  isLoading?: boolean;
  statusMessage?: string;
  replyingToId?: string | null;
  conversationId?: string | null;  // for explain cards loading
  onDeleteMessage?: (messageId: string) => void;
  onEditMessage?: (messageId: string, newText: string) => Promise<number>;
  onVersionSwitch?: (messageId: string, direction: "prev" | "next", currentIndex?: number) => Promise<{ index: number; total: number } | null>;
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
  onVersionSwitch,
  onSend,
}: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingText, setEditingText] = useState("");
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [editedTexts, setEditedTexts] = useState<EditedMap>({});
  const [versionMap, setVersionMap] = useState<Record<string, { index: number; total: number }>>({});
  const [subBranchData, setSubBranchData] = useState<Record<string, SubBranchInfo[]>>({});
  const [noteCard, setNoteCard] = useState<{ text: string; position: { x: number; y: number } } | null>(null);

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

  // Restore version map on refresh
  useEffect(() => {
    const modifiedIds = messages.filter(m => m.role === "user" && m.has_modified_version && !versionMap[m.id]).map(m => m.id);
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
        } catch { return { msgId, total: 0, index: 0 }; }
      })
    ).then(results => {
      if (cancelled) return;
      setVersionMap(prev => {
        const next = { ...prev };
        for (const r of results) { if (r.total > 1 && !prev[r.msgId]) next[r.msgId] = { index: r.index, total: r.total }; }
        return next;
      });
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.map(m => m.id).join(",")]);

  const handleCopyMessage = async (text: string) => {
    try { await navigator.clipboard.writeText(text); }
    catch {
      const ta = document.createElement("textarea");
      ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select(); document.execCommand("copy"); document.body.removeChild(ta);
    }
  };

  const handleVersionNav = async (messageId: string, direction: "prev" | "next") => {
    if (!onVersionSwitch) return;
    const currentIdx = versionMap[messageId]?.index;
    const result = await onVersionSwitch(messageId, direction, currentIdx);
    if (result) {
      const newUserMsg = messages.find(m => m.role === "user" && m.id !== messageId);
      const newMsgId = newUserMsg?.id || messageId;
      setVersionMap(prev => {
        const next = { ...prev };
        next[newMsgId] = result;
        if (newMsgId !== messageId) delete next[messageId];
        return next;
      });
    }
  };

  const handleDeleteMessage = (messageId: string) => onDeleteMessage?.(messageId);
  const handleStartEdit = (msgId: string, currentText: string) => { setEditingId(msgId); setEditingText(currentText); };

  const handleSaveEdit = async () => {
    const msgId = editingId; const newText = editingText.trim();
    if (!msgId || !newText) { setEditingId(null); return; }
    if (onEditMessage) {
      try {
        const result = await onEditMessage(msgId, newText);
        const verTotal = result > 0 ? result : 2;
        setEditedTexts(prev => ({ ...prev, [msgId]: newText }));
        setVersionMap(prev => ({ ...prev, [msgId]: { index: verTotal, total: verTotal } }));
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

  // Deduplicate messages
  const prevMsgsRef = useRef<{ len: number; lastId: string; result: TreeNode[] } | null>(null);
  const dedupedMessages = useMemo(() => {
    const lastId = messages.length > 0 ? messages[messages.length - 1].id : "";
    const prev = prevMsgsRef.current;
    if (prev && prev.len === messages.length && prev.lastId === lastId) return prev.result;
    const seen = new Map<string, TreeNode>();
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.is_deleted) continue;
      const existing = seen.get(m.id);
      if (!existing) { seen.set(m.id, m); }
      else {
        const existingText = existing.content_blocks?.find(b => b.type === "text")?.text || "";
        const currentText = m.content_blocks?.find(b => b.type === "text")?.text || "";
        if (currentText && !existingText) seen.set(m.id, m);
      }
    }
    const result = Array.from(seen.values()).reverse();
    prevMsgsRef.current = { len: messages.length, lastId, result };
    return result;
  }, [messages]);

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
  const getDisplayText = (msg: TreeNode) =>
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
        {dedupedMessages.map((message) => {
          const isUser = message.role === "user";
          const isEditing = editingId === message.id;
          const messageBlocks = blocksByMessage.get(message.id) || [];
          const displayText = getDisplayText(message);
          const hasVersions = message.has_modified_version || !!editedTexts[message.id];
          const vInfo = versionMap[message.id] || { index: 1, total: hasVersions ? 1 : 0 };
          const cardsForMsg = getCardsForMessage(message.id, explainCards);

          return (
            <Fragment key={message.id}>
              {/* AI Avatar + label — above the message for assistant */}
              {!isUser && (
                <div className="flex items-center gap-2 mb-1.5 px-1">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-[var(--color-surface)] text-[var(--color-accent)] border border-[var(--color-border)]">
                    <Bot size={16} />
                  </div>
                  <span className="text-xs font-medium text-[var(--color-text-muted)]">AI</span>
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
                            onMouseDown={handleTextMouseDown} onMouseUp={handleTextMouseUp} onContextMenu={handleTextContextMenu}
                            onClick={(e) => { e.stopPropagation(); handleTextClick(e, message.id, message.conversation_id, displayText); }}
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
                            onClick={(e) => { e.stopPropagation(); handleTextClick(e, message.id, message.conversation_id, displayText); }}
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
                      {/* Child cards (depth 2+) stay in flow */}
                      {cardsForMsg.filter(ec => ec.depth >= 2).map((ec) => (
                        <KnowledgeExplainCard key={ec.id} card={ec} />
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
                  const startIdx = fullText.indexOf(text);
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
