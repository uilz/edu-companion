"use client";

import React, { memo, useState, useEffect, useRef, useCallback, useMemo } from "react";
import { GraduationCap, BookOpen, ImageIcon, FileText, ExternalLink, Quote as QuoteIcon, X, Copy, Trash2 } from "lucide-react";
import { BLOCK_RENDERERS } from "@/components/conversation/blocks/registry";
import MarkdownRenderer from "./../blocks/MarkdownRenderer";
import SelfExplainCard from "./../cards/SelfExplainCard";
import MessageActions from "./MessageActions";
import MessageEditArea from "./MessageEditArea";
import SpeakButton from "./../media/SpeakButton";
import { useExplainStore, getCardsForMessage } from "@/store/explain/explain-store";
import type { ExplainCardData } from "@/store/explain/explain-store";
import KnowledgeExplainCard from "@/components/conversation/cards/KnowledgeExplainCard";
import { useAuth } from "@/contexts/AuthContext";
import { useMessageStore } from "@/store/conversation/message-store";
import type { MessageNode, ContentBlock } from "@/types";

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

// ── User avatar initial (从 useAuth.user 取首字符) ──
function getUserInitial(displayName?: string | null, username?: string | null, email?: string | null): string {
  const s = (displayName || username || email || "U").trim();
  if (!s) return "U";
  // 优先取 display_name 首字符；含中文/emoji 时直接用第一个字符
  return Array.from(s)[0]!.toUpperCase();
}

// ── MessageItem props ──
export interface MessageItemProps {
  message: MessageNode;
  isFeynmanMode: boolean;
  isEditing: boolean;
  editingText: string;
  vInfo: { index: number; total: number };
  hasVersions: boolean;
  // ★ 显式加载状态（区分 placeholder/loading/loaded/streaming/broken）
  loadState: "placeholder" | "loading" | "loaded" | "streaming" | "broken";
  displayText: string;
  cardsForMsg: ExplainCardData[];
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
  // Text selection handlers
  handleTextMouseDown: (e: React.MouseEvent) => void;
  handleTextMouseUp: (e: React.MouseEvent) => void;
  handleTextContextMenu: (e: React.MouseEvent) => void;
  handleTextClick: (e: React.MouseEvent, messageId: string, convId: string, blockText: string) => void;
  onBadgeClick: (cardId: string) => void;
}

// ── 分组 content_blocks 方便后续按类型渲染 ──
function groupBlocks(blocks: ContentBlock[] | undefined) {
  const result = { quotes: [] as ContentBlock[], images: [] as ContentBlock[], files: [] as ContentBlock[], others: [] as ContentBlock[] };
  if (!blocks) return result;
  for (const b of blocks) {
    if (b.type === "quote") result.quotes.push(b);
    else if (b.type === "image") result.images.push(b);
    else if (b.type === "file") result.files.push(b);
    else if (b.type !== "text") result.others.push(b);
  }
  return result;
}

// ── User 多输入片段：缩略图 ──
const UserImageThumbs = memo(function UserImageThumbs({ images }: { images: ContentBlock[] }) {
  if (images.length === 0) return null;
  const MAX_VISIBLE = 4;
  const visible = images.slice(0, MAX_VISIBLE);
  const more = images.length - visible.length;
  return (
    <div className="flex flex-wrap gap-1.5">
      {visible.map((img, idx) => {
        const name = img.name || img.preview_text || "图片";
        return (
          <div key={idx} className="user-thumb" title={name}>
            <ImageIcon size={20} />
            {more > 0 && idx === visible.length - 1 && (
              <span className="more-count">+{more}</span>
            )}
          </div>
        );
      })}
    </div>
  );
});

// ── User 多输入片段：文件 chip ──
const UserFileChips = memo(function UserFileChips({ files }: { files: ContentBlock[] }) {
  if (files.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {files.map((f, idx) => {
        const name = f.name || "未命名文件";
        const mid = f.material_id;
        return (
          <a
            key={idx}
            href={mid ? `/files/${mid}` : undefined}
            target={mid ? "_blank" : undefined}
            rel="noreferrer"
            className="user-file-chip"
            title={name}
          >
            <FileText size={11} />
            <span className="truncate" style={{ maxWidth: 140 }}>{name}</span>
            {mid ? <ExternalLink size={9} className="opacity-60" /> : (
              <span className="text-[9px] text-[var(--color-text-muted)]">索引中</span>
            )}
          </a>
        );
      })}
    </div>
  );
});

// ── User 多输入片段：引用片段 ──
const UserQuoteStrip = memo(function UserQuoteStrip({ quote }: { quote: ContentBlock }) {
  const text = quote.quoted_text || quote.preview_text || quote.text_content || "";
  if (!text) return null;
  const trimmed = text.length > 80 ? text.slice(0, 80) + "…" : text;
  return (
    <div className="user-quote-strip" title={text}>
      <QuoteIcon size={11} className="shrink-0" />
      <span className="text">{trimmed}</span>
    </div>
  );
});

// ── MessageItem — single message rendering (memoized) ──
function MessageItemInner({
  message,
  isFeynmanMode,
  isEditing,
  editingText,
  vInfo,
  hasVersions,
  loadState,
  displayText,
  cardsForMsg,
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
  handleTextMouseDown,
  handleTextMouseUp,
  handleTextContextMenu,
  handleTextClick,
  onBadgeClick,
}: MessageItemProps) {
  const isUser = message.role === "user";
  const { user } = useAuth();
  const userInitial = isUser ? getUserInitial(user?.display_name, user?.username, user?.email) : "";

  const grouped = useMemo(() => groupBlocks(message.content_blocks as ContentBlock[] | undefined), [message.content_blocks]);

  // ── 显式状态渲染：placeholder / loading / streaming / broken / loaded ──
  // ★ 关键：placeholder（未触发过加载）和 loading（正在加载）状态 UI 一致（skeleton）
  //   broken 状态显示错误信息 + 重试按钮
  //   streaming/loaded 状态显示实际内容

  // 1) placeholder / loading 状态 → skeleton 占位
  if ((loadState === "placeholder" || loadState === "loading") && !isEditing) {
    return (
      <div className={`${isUser ? "flex justify-end" : ""}`}>
        <div className={`${isUser ? "w-full max-w-[85%]" : "w-full"}`}>
          <div className={`${isUser ? "ai-msg-paper" : "ai-msg-paper"} animate-pulse space-y-2`}>
            {isUser ? (
              <div className="h-4 bg-[var(--color-page)] rounded-lg w-3/4" />
            ) : (
              <>
                <div className="h-4 bg-[var(--color-page-secondary)] rounded-lg w-full" />
                <div className="h-4 bg-[var(--color-page-secondary)] rounded-lg w-5/6" />
                <div className="h-4 bg-[var(--color-page-secondary)] rounded-lg w-2/3" />
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  // 2) broken 状态 → 显示错误 + 重试
  if (loadState === "broken" && !isEditing) {
    return (
      <div className={`${isUser ? "flex justify-end" : ""}`}>
        <div className={`${isUser ? "w-full max-w-[85%]" : "w-full"}`}>
          <div className="ai-msg-paper border border-[var(--color-error)]/30 bg-[var(--color-error)]/5 px-3 py-2 space-y-1">
            <div className="text-xs text-[var(--color-error)]">⚠️ 加载失败</div>
            <div className="text-xs text-[var(--color-text-muted)]">{message.load_error || "无法加载此消息"}</div>
            <button
              onClick={() => {
                // ★ 重试：调用 store action 清除 _loadAttempted 标记 + 重新加载
                useMessageStore.getState().retryLoadContent(message.id);
              }}
              className="text-xs text-[var(--color-primary)] hover:underline"
            >
              重试
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="group">
      {/* Avatar row: 独立成行，不再与内容同行（解决挤压宽度问题） */}
      {isUser ? (
        <div className="flex items-center gap-1.5 mb-1.5 px-1 justify-end">
          <span className="text-xs font-medium text-[var(--color-text-muted)]">{user?.display_name || user?.username || "你"}</span>
          <div className="user-avatar-chip" aria-label={user?.display_name || user?.username || "你"}>
            {userInitial}
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-1.5 mb-1.5 px-1">
          <div className={`ai-avatar-chip`}>
            {isFeynmanMode ? <BookOpen size={13} /> : <GraduationCap size={13} />}
          </div>
          <span className="text-xs font-medium text-[var(--color-text-muted)]">
            {isFeynmanMode ? "费曼学生" : "教学助手"}
          </span>
          <span className="text-[10px] text-[var(--color-text-muted)] opacity-0 group-hover:opacity-100 transition-opacity">
            · {new Date(message.timestamp || Date.now()).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}
          </span>
          <span className="flex-1" />
          {/* 名称行操作按钮 */}
          <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 max-lg:opacity-100 transition-opacity">
            <SpeakButton text={displayText} />
            {onCopy && (
              <button onClick={onCopy} className="p-1 rounded text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]" title="复制">
                <Copy size={12} />
              </button>
            )}
            {onDelete && (
              <button onClick={onDelete} className="p-1 rounded text-[var(--color-text-muted)] hover:text-[var(--color-error)] hover:bg-[var(--color-surface-hover)]" title="删除">
                <Trash2 size={12} />
              </button>
            )}
          </div>
        </div>
      )}

      <div className="message-enter">
        <div className={`${isUser ? "flex justify-end" : ""}`}
          style={{ overflow: 'visible', scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
          <div className={`relative pb-7 ${isUser ? "max-w-[85%]" : "max-w-full"}`}>
            {/* === AI 消息：paper-ink 风格，文本与工具块米色一致 === */}
            {!isUser && (
              <div className="ai-msg-paper space-y-1">
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
                  if (!Renderer) return null;
                  return (
                    <div key={`block-${bi}`} className="ai-tool-block">
                      <Renderer block={b} />
                    </div>
                  );
                })}
                {/* ★ 兜底：content_blocks 没有 type="text" 时，用 displayText 显示 */}
                {!(message.content_blocks || []).some(b => b.type === "text") && displayText && !isLoading && (
                  <div data-message-id={message.id} data-conv-id={message.conv_id} data-full-text={displayText}
                    className="text-base leading-[1.65] whitespace-pre-wrap break-words select-text"
                    onMouseDown={handleTextMouseDown} onMouseUp={handleTextMouseUp} onContextMenu={handleTextContextMenu}
                    onClick={(e) => { e.stopPropagation(); handleTextClick(e, message.id, message.conv_id || "", displayText); }}
                  >
                    <ExplainMarkers text={displayText} cards={cardsForMsg} messageId={message.id} onBadgeClick={onBadgeClick} />
                  </div>
                )}
                {/* 加载中：content_blocks 为空且没 displayText 文本时显示 dots */}
                {!(message.content_blocks || []).some(b => b.type === "text") && !displayText && isLoading && (
                  <div className="flex gap-1.5 items-center py-1 px-1">
                    <span className="w-2 h-2 bg-[var(--color-text-muted)] rounded-full animate-pulse" style={{ animationDelay: "0ms" }} />
                    <span className="w-2 h-2 bg-[var(--color-text-muted)] rounded-full animate-pulse" style={{ animationDelay: "200ms" }} />
                    <span className="w-2 h-2 bg-[var(--color-text-muted)] rounded-full animate-pulse" style={{ animationDelay: "400ms" }} />
                  </div>
                )}

                {/* 自我解释卡（仅 AI） */}
                {message.cognitive_node_ids && message.cognitive_node_ids.length > 0 && (
                  <SelfExplainCard
                    knowledgeNodeId={message.cognitive_node_ids[0]}
                    messageId={message.id}
                  />
                )}
              </div>
            )}

            {/* === 用户消息：单气泡内集成引用/图片/文件/文本 === */}
            {isUser && (
              <div className="user-msg-bubble">
                {isEditing ? (
                  <MessageEditArea text={editingText} onChange={onEditTextChange} onSave={onSaveEdit} onCancel={onCancelEdit} />
                ) : (
                  <>
                    {/* 引用片段：紧凑条带 */}
                    {grouped.quotes.map((q, qi) => (
                      <UserQuoteStrip key={`uq-${qi}`} quote={q} />
                    ))}

                    {/* 图片缩略图：80x80 grid */}
                    {grouped.images.length > 0 && (
                      <UserImageThumbs images={grouped.images} />
                    )}

                    {/* 文件 chip */}
                    {grouped.files.length > 0 && (
                      <UserFileChips files={grouped.files} />
                    )}

                    {/* 文本气泡 */}
                    {displayText && (
                      <div data-message-id={message.id} data-conv-id={message.conv_id} data-full-text={displayText}
                        className="text-base leading-[1.65] text-[var(--color-text)] whitespace-pre-wrap break-words select-text">
                        <ExplainMarkers text={displayText} cards={cardsForMsg} messageId={message.id} onBadgeClick={onBadgeClick} />
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            {/* Floating explain cards (跨 AI/用户消息; 通常 AI) */}
            <div className="relative">
              {cardsForMsg.map((ec) => (
                <FloatingExplainCard key={ec.id} card={ec} />
              ))}
            </div>

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
    prev.loadState === next.loadState &&
    prev.displayText === next.displayText &&
    prev.cardsForMsg === next.cardsForMsg &&
    prev.replyingToId === next.replyingToId &&
    prev.isLoading === next.isLoading
  );
};

export const MessageItem = memo(MessageItemInner, areMessageItemPropsEqual);
