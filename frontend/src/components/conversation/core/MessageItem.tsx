"use client";

import React, { memo, useState, useEffect, useRef, useCallback, useMemo } from "react";
import { User, Bot, GraduationCap, BookOpen, ImageIcon, FileText, ExternalLink } from "lucide-react";
import ResponseBlockRenderer from "./../blocks/ResponseBlockRenderer";
import QuoteBlockRenderer from "./../blocks/QuoteBlockRenderer";
import { BLOCK_RENDERERS } from "@/components/conversation/blocks/registry";
import SubBranchInline from "./../blocks/SubBranchInline";
import MarkdownRenderer from "./../blocks/MarkdownRenderer";
import SelfExplainCard from "./../cards/SelfExplainCard";
import MessageActions from "./MessageActions";
import MessageEditArea from "./MessageEditArea";
import { useExplainStore, getCardsForMessage } from "@/store/explain/explain-store";
import type { ExplainCardData } from "@/store/explain/explain-store";
import KnowledgeExplainCard from "@/components/conversation/cards/KnowledgeExplainCard";
import type { MessageNode, SubBranchInfo } from "@/types";

// ── Feynman evaluation type ──
export interface FeynmanEval {
  highlights: string[];
  weaknesses: string[];
  mastery_level: "high" | "medium" | "low";
  summary: string;
}

// ── Inline explain markers — embeds badge(s) into rendered text via DOM injection ──
const ExplainMarkers = memo(function ExplainMarkers({
  text, cards, messageId, onBadgeClick,
}: {
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
    const containerRect = container.getBoundingClientRect();

    for (const card of validCards) {
      const selText = card.selected_text!;
      let startIdx = -1;
      if (card.char_start != null) {
        const searchFrom = Math.max(0, Math.min(card.char_start, fullText.length));
        startIdx = fullText.indexOf(selText, searchFrom);
        if (startIdx < 0) {
          startIdx = fullText.lastIndexOf(selText, searchFrom + selText.length);
        }
      }
      if (startIdx < 0) {
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
  }, [validCards, messageId]);

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
});

// ── Floating explain card (extracted for clarity) ──
const FloatingExplainCard = memo(function FloatingExplainCard({ card }: { card: ExplainCardData }) {
  const updateCard = useExplainStore((s) => s.updateCard);
  const [renderPos, setRenderPos] = useState({ x: card.pos_x || 0, y: card.pos_y || 0 });
  const posRef = useRef({ x: card.pos_x || 0, y: card.pos_y || 0 });
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    posRef.current = { x: card.pos_x || 0, y: card.pos_y || 0 };
    setRenderPos({ x: card.pos_x || 0, y: card.pos_y || 0 });
  }, [card.pos_x, card.pos_y]);

  if (card.collapsed) return <KnowledgeExplainCard card={card} />;

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    const handle = target.closest('[data-drag-handle="true"]');
    if (!handle) return;
    e.preventDefault();
    e.stopPropagation();

    if (wrapperRef.current) wrapperRef.current.style.transition = "none";

    const onMove = (ev: MouseEvent) => {
      const dx = ev.clientX - e.clientX;
      const dy = ev.clientY - e.clientY;
      const newX = posRef.current.x + dx;
      const newY = posRef.current.y + dy;
      if (wrapperRef.current) {
        wrapperRef.current.style.left = `${newX}px`;
        wrapperRef.current.style.top = `${newY}px`;
      }
    };

    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      if (wrapperRef.current) wrapperRef.current.style.transition = "";
      const finalX = parseInt(wrapperRef.current?.style.left || "0");
      const finalY = parseInt(wrapperRef.current?.style.top || "0");
      posRef.current = { x: finalX, y: finalY };
      setRenderPos({ x: finalX, y: finalY });
      updateCard(card.id, { pos_x: Math.round(finalX), pos_y: Math.round(finalY) });
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [card.id, updateCard]);

  return (
    <div ref={wrapperRef} className="absolute z-10 select-none" style={{ left: `${renderPos.x}px`, top: `${renderPos.y}px` }}>
      <div onMouseDown={onMouseDown}>
        <KnowledgeExplainCard card={card} />
      </div>
    </div>
  );
});

// ── MessageItem props ──
export interface MessageItemProps {
  message: MessageNode;
  isFeynmanMode: boolean;
  isEditing: boolean;
  editingText: string;
  vInfo: { index: number; total: number };
  hasVersions: boolean;
  loaded: boolean;
  displayText: string;
  cardsForMsg: ExplainCardData[];
  subBranches: SubBranchInfo[];
  replyingToId: string | null;
  isLoading: boolean;
  // Edit handlers
  onStartEdit: (msgId: string, currentText: string) => void;
  onEditTextChange: (text: string) => void;
  onSaveEdit: () => void;
  onCancelEdit: () => void;
  // Action handlers
  onDelete: () => void;
  onCopy: () => void;
  onVersionNav: (dir: "prev" | "next") => void;
  onFeynmanTeach?: () => void;
  onEnterSubBranch: (convId: string) => void;
  // Text selection handlers
  handleTextMouseDown: (e: React.MouseEvent) => void;
  handleTextMouseUp: (e: React.MouseEvent) => void;
  handleTextContextMenu: (e: React.MouseEvent) => void;
  handleTextClick: (e: React.MouseEvent, messageId: string, convId: string, blockText: string) => void;
  onBadgeClick: (cardId: string) => void;
}

// ── MessageItem — single message rendering (memoized) ──
function MessageItemInner({
  message,
  isFeynmanMode,
  isEditing,
  editingText,
  vInfo,
  hasVersions,
  loaded,
  displayText,
  cardsForMsg,
  subBranches,
  replyingToId,
  isLoading,
  onStartEdit,
  onEditTextChange,
  onSaveEdit,
  onCancelEdit,
  onDelete,
  onCopy,
  onVersionNav,
  onFeynmanTeach,
  onEnterSubBranch,
  handleTextMouseDown,
  handleTextMouseUp,
  handleTextContextMenu,
  handleTextClick,
  onBadgeClick,
}: MessageItemProps) {
  const isUser = message.role === "user";

  // Loading indicator
  const loadingIndicator = useMemo(() => (
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
      </div>
    </div>
  ), []);

  if (!loaded && !isEditing) {
    return (
      <div className={`flex gap-4 ${isUser ? "flex-row-reverse" : ""} animate-pulse`}>
        <div className={`flex-shrink-0 w-8 h-8 rounded-full ${isUser ? "bg-[var(--color-accent)]/30" : "bg-blue-500/30"}`} />
        <div className={`flex-1 min-w-0 ${isUser ? "flex justify-end" : ""}`}>
          <div className={`${isUser ? "max-w-[85%]" : ""} space-y-2 py-2`}>
            {isUser ? (
              <div className="h-4 bg-[var(--color-surface)] rounded-lg w-3/4" />
            ) : (
              <>
                <div className="h-4 bg-[var(--color-surface-alt)] rounded-lg w-full" />
                <div className="h-4 bg-[var(--color-surface-alt)] rounded-lg w-5/6" />
                <div className="h-4 bg-[var(--color-surface-alt)] rounded-lg w-2/3" />
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* AI Avatar + label — above the message for assistant */}
      {!isUser && (
        <div className="flex items-center gap-2 mb-1.5 px-1">
          <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-white ${isFeynmanMode ? "bg-emerald-500" : "bg-blue-500"}`}>
            {isFeynmanMode ? <BookOpen size={16} /> : <GraduationCap size={16} />}
          </div>
          <span className="text-xs font-medium text-[var(--color-text-muted)]">
            {isFeynmanMode ? "费曼学生" : "教学助手"}
          </span>
        </div>
      )}
      <div className={`message-enter ${isUser ? "flex gap-4 flex-row-reverse" : ""}`}>
        {isUser && (
          <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-[var(--color-accent)] text-white">
            <User size={16} />
          </div>
        )}

        <div className={`flex-1 min-w-0 ${isUser ? "flex justify-end" : ""}`}>
          <div className={`relative pb-7 ${isUser ? "max-w-[85%]" : ""}`}
            style={{ overflow: 'visible', scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
            <div className="group">
              {/* Quote blocks */}
              {(message.content_blocks || []).filter(b => b.type === "quote").map((b, qi) => (
                <QuoteBlockRenderer key={`quote-${qi}`} quotedText={b.quoted_text || ""}
                  sourceConversationId={b.source_conv_id} sourceMessageId={b.source_message_id} />
              ))}

              {/* Uploaded file attachments */}
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

              {/* Content bubble */}
              <div className={`relative ${isUser
                ? "bg-[var(--color-surface)] border border-[var(--color-border)] px-4 pb-2.5 pt-2.5 rounded-[14px] rounded-tr-[14px] rounded-br-none"
                : "bg-[var(--color-surface-alt)] text-[var(--color-text)] px-4 py-3 rounded-[14px] rounded-tl-[14px] rounded-bl-none"
              }`}>
                {isEditing ? (
                  <MessageEditArea text={editingText} onChange={onEditTextChange} onSave={onSaveEdit} onCancel={onCancelEdit} />
                ) : isUser ? (
                  <div data-message-id={message.id} data-conv-id={message.conv_id} data-full-text={displayText}
                    className="text-base leading-[1.65] text-[var(--color-text)] whitespace-pre-wrap break-words select-text">
                    <ExplainMarkers text={displayText} cards={cardsForMsg} messageId={message.id} onBadgeClick={onBadgeClick} />
                  </div>
                ) : (
                  <>
                    {(message.content_blocks || []).map((b, bi) => {
                      if (b.type === "text") {
                        const blockText = b.text || "";
                        if (!blockText) return null;
                        return (
                          <div key={`text-${bi}`}
                            data-message-id={message.id} data-conv-id={message.conv_id} data-full-text={blockText}
                            className="text-base leading-[1.65] whitespace-pre-wrap break-words select-text"
                            onMouseDown={handleTextMouseDown} onMouseUp={handleTextMouseUp} onContextMenu={handleTextContextMenu}
                            onClick={(e) => { e.stopPropagation(); handleTextClick(e, message.id, message.conv_id || "", blockText); }}
                          >
                            <ExplainMarkers text={blockText} cards={cardsForMsg} messageId={message.id} onBadgeClick={onBadgeClick} />
                          </div>
                        );
                      }
                      const Renderer = BLOCK_RENDERERS[b.type];
                      return Renderer ? <Renderer key={`block-${bi}`} block={b} /> : null;
                    })}
                    {!(message.content_blocks || []).some(b => b.type === "text") && isLoading && (
                      <div className="flex gap-1.5 items-center py-1 px-1">
                        <span className="w-2 h-2 bg-[var(--color-text-muted)] rounded-full animate-pulse" style={{ animationDelay: "0ms" }} />
                        <span className="w-2 h-2 bg-[var(--color-text-muted)] rounded-full animate-pulse" style={{ animationDelay: "200ms" }} />
                        <span className="w-2 h-2 bg-[var(--color-text-muted)] rounded-full animate-pulse" style={{ animationDelay: "400ms" }} />
                      </div>
                    )}
                  </>
                )}

                {/* Floating explain cards */}
                {cardsForMsg.filter(ec => ec.depth === 1).map((ec) => (
                  <FloatingExplainCard key={ec.id} card={ec} />
                ))}
                {cardsForMsg.filter(ec => ec.depth >= 2).map((ec) => (
                  <FloatingExplainCard key={ec.id} card={ec} />
                ))}

                {/* Self-explain card */}
                {!isUser && message.cognitive_node_ids && message.cognitive_node_ids.length > 0 && (
                  <SelfExplainCard
                    knowledgeNodeId={message.cognitive_node_ids[0]}
                    messageId={message.id}
                  />
                )}
              </div>

              {/* Sub-branch inline */}
              {subBranches.length > 0 && (
                <div className="mt-1">
                  <SubBranchInline messageId={message.id} subBranches={subBranches} onEnter={onEnterSubBranch} />
                </div>
              )}

              {/* Action buttons */}
              {!isEditing && (
                <MessageActions
                  role={isUser ? "user" : "assistant"}
                  vInfo={vInfo}
                  hasVersions={hasVersions}
                  text={displayText}
                  onEdit={isUser ? () => onStartEdit(message.id, displayText) : undefined}
                  onDelete={onDelete}
                  onCopy={onCopy}
                  onVersionNav={isUser ? onVersionNav : undefined}
                  onFeynmanTeach={(!isUser && !isFeynmanMode && onFeynmanTeach) ? onFeynmanTeach : undefined}
                />
              )}
            </div>
          </div>
        </div>
        {/* Loading indicator below the message being edited */}
        {replyingToId === message.id && loadingIndicator}
      </div>
    </div>
  );
}

// ── React.memo with shallow comparison ──
// 关键：version 切换 / 流式写入会更新 content，但 props 引用变化时仍能避免不必要重渲染
const areMessageItemPropsEqual = (prev: MessageItemProps, next: MessageItemProps) => {
  return (
    prev.message === next.message &&
    prev.isFeynmanMode === next.isFeynmanMode &&
    prev.isEditing === next.isEditing &&
    prev.editingText === next.editingText &&
    prev.vInfo.index === next.vInfo.index &&
    prev.vInfo.total === next.vInfo.total &&
    prev.hasVersions === next.hasVersions &&
    prev.loaded === next.loaded &&
    prev.displayText === next.displayText &&
    prev.cardsForMsg === next.cardsForMsg &&
    prev.subBranches === next.subBranches &&
    prev.replyingToId === next.replyingToId &&
    prev.isLoading === next.isLoading
  );
};

export const MessageItem = memo(MessageItemInner, areMessageItemPropsEqual);
