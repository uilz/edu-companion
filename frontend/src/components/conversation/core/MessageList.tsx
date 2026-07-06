"use client";

import React, { useEffect, useRef, useMemo, useState, useCallback } from "react";
import { Bot, ChevronDown, ChevronUp, BookOpen } from "lucide-react";
import { Virtuoso, type VirtuosoHandle } from "react-virtuoso";
import { MessageItem } from "./MessageItem";
import TextSelectionToolbar from "./../input/TextSelectionToolbar";
import { useTextSelection } from "./../hooks/useTextSelection";
import NoteCard from "./../cards/NoteCard";
import { useExplainStore, getCardsForMessage } from "@/store/explain/explain-store";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import EmptyState from "@/components/ui/EmptyState";
import { useConversationStore, useMessageStore } from "@/store/conversation/conversation-store";
import type { MessageNode } from "@/types";
import type { FeynmanEval } from "./MessageItem";

// ══════════════════════════════════════════════════════════════
//  MessageList — 消息列表（react-virtuoso 虚拟化）
//  性能特性：
//  - 动态高度（消息长度自适应）
//  - 流式追加（followOutput="smooth"）
//  - 首尾渲染窗口（overscan: 400）
//  - 滚动到指定位置 API（scrollToIndex）
//  - 上下文选择工具栏 + 笔记卡片层叠
// ══════════════════════════════════════════════════════════════

type EditedMap = Record<string, string>;

export interface MessageListProps {
  messages: MessageNode[];
  isLoading?: boolean;
  statusMessage?: string;
  replyingToId?: string | null;
  conversationId?: string | null;
  isFeynmanMode?: boolean;
  onDeleteMessage?: (messageId: string) => void;
  onEditMessage?: (messageId: string, newText: string) => Promise<number>;
  onSend?: (text: string) => void;
  onFeynmanTeach?: (messageId: string, messageText: string, conversationId: string) => void;
}

export default function MessageList({
  messages,
  isLoading = false,
  statusMessage,
  replyingToId,
  conversationId,
  isFeynmanMode = false,
  onDeleteMessage,
  onEditMessage,
  onSend,
  onFeynmanTeach,
}: MessageListProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingText, setEditingText] = useState("");
  const virtuosoRef = useRef<VirtuosoHandle>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [scrollDir, setScrollDir] = useState<"up" | "down">("down");
  const [atBottom, setAtBottom] = useState(true);
  const lastWheelDeltaYRef = useRef(0);
  const initialLoadDoneRef = useRef(false);
  const [noteCard, setNoteCard] = useState<{ text: string; position: { x: number; y: number } } | null>(null);

  const setPendingQuote = useConversationStore((s) => s.setPendingQuote);

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

  const handleCopyMessage = useCallback(async (text: string) => {
    try { await navigator.clipboard.writeText(text); }
    catch {
      const ta = document.createElement("textarea");
      ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select(); document.execCommand("copy"); document.body.removeChild(ta);
    }
  }, []);

  // ── 费曼评估解析 ──
  const parseFeynmanEvaluation = useCallback((text: string): FeynmanEval | null => {
    try {
      const jsonMatch = text.match(/\{[\s\S]*"feynman_evaluation"[\s\S]*\}/);
      if (!jsonMatch) return null;
      const parsed = JSON.parse(jsonMatch[0]);
      if (parsed.feynman_evaluation) {
        return parsed.feynman_evaluation as FeynmanEval;
      }
    } catch { /* not valid JSON */ }
    return null;
  }, []);

  const latestEval = useMemo(() => {
    if (!isFeynmanMode) return null;
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.role === "assistant") {
        const fromBlocks = msg.content_blocks?.filter((b: any) => b.type === "text").map((b: any) => b.text || "").join("\n\n") || "";
        const text = fromBlocks || msg.content || "";
        const ev = parseFeynmanEvaluation(text);
        if (ev) return ev;
      }
    }
    return null;
  }, [messages, isFeynmanMode, parseFeynmanEvaluation]);

  // ── 版本切换：基于 nodeMap 的 DFS 遍历 ──
  const handleVersionNav = useCallback((messageId: string, direction: "prev" | "next") => {
    const store = useMessageStore.getState();
    const msg = store.nodeMap[messageId];
    if (!msg) return;
    const parentId = msg.parent_id || "__root__";
    const role = msg.role;
    // 同一 parent + 同 role 的兄弟消息
    const siblings = Object.values(store.nodeMap)
      .filter(m => (m.parent_id || "__root__") === parentId && m.role === role && !m.is_deleted)
      .sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));
    if (siblings.length <= 1) return;
    const idx = siblings.findIndex(m => m.id === messageId);
    if (idx < 0) return;
    const newIdx = direction === "prev"
      ? (idx - 1 + siblings.length) % siblings.length
      : (idx + 1) % siblings.length;
    const targetMsg = siblings[newIdx];
    if (targetMsg) {
      store.switchBranch(targetMsg.id);
    }
  }, []);

  const handleStartEdit = useCallback((msgId: string, currentText: string) => {
    setEditingId(msgId);
    setEditingText(currentText);
  }, []);

  const handleSaveEdit = useCallback(async () => {
    const msgId = editingId; const newText = editingText.trim();
    if (!msgId || !newText) { setEditingId(null); return; }
    if (onEditMessage) {
      try {
        await onEditMessage(msgId, newText);
        // 触发 updates 通过 store.messages
      } catch {}
    }
    setEditingId(null);
  }, [editingId, editingText, onEditMessage]);

  const handleCancelEdit = useCallback(() => setEditingId(null), []);

  // ── 屏幕外预加载：Virtuoso 滚动/渲染时触发 ──
  //   ★ 关键：用户滚动前预加载相邻消息，避免滚动时卡顿
  //   PREFETCH_BEFORE / PREFETCH_AFTER 控制预加载窗口
  const PREFETCH_BEFORE = 3;
  const PREFETCH_AFTER = 5;
  const lastPrefetchRangeRef = useRef<{ start: number; end: number }>({ start: -1, end: -1 });

  const handleRangeChanged = useCallback((range: { startIndex: number; endIndex: number }) => {
    const { startIndex, endIndex } = range;
    // 去重：避免重复触发同一范围
    const last = lastPrefetchRangeRef.current;
    if (last.start === startIndex && last.end === endIndex) return;
    lastPrefetchRangeRef.current = { start: startIndex, end: endIndex };

    const messages = getMessageList();
    if (messages.length === 0) return;

    // 预加载窗口：[startIndex - PREFETCH_BEFORE, endIndex + PREFETCH_AFTER]
    const lo = Math.max(0, startIndex - PREFETCH_BEFORE);
    const hi = Math.min(messages.length - 1, endIndex + PREFETCH_AFTER);
    const prefetchIds: string[] = [];
    for (let i = lo; i <= hi; i++) {
      const m = messages[i];
      if (m) prefetchIds.push(m.id);
    }
    if (prefetchIds.length > 0) {
      void useMessageStore.getState().loadVisibleContent(prefetchIds);
    }
  }, []);

  // 暴露 getMessageList 给上面用（避免循环依赖）
  // 注意：getMessageList 实际读取当前 props.messages
  const getMessageList = useCallback(() => {
    // 通过 ref 读取最新 messages（避免闭包过期）
    return messagesRef.current;
  }, []);

  const messagesRef = useRef<MessageNode[]>([]);
  // 同步最新 messages 到 ref，供 rangeChanged 使用
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  // ── 内容加载检查：骨架 vs 完整消息（骨架 content_blocks=[]，无正文）──
  //   ★ 关键：失败消息 content/content_blocks 为空但 text_summary 有错误信息，
  //     也算"已加载"（getDisplayText 会用 text_summary）
  const isContentLoaded = useCallback((msgId: string) => {
    const state = useMessageStore.getState();
    if (state.streamingId === msgId) return true;
    // 临时消息（乐观写入、流式占位）视为已加载
    if (msgId.startsWith("t_") || msgId.startsWith("a_") || msgId.startsWith("err-")) return true;
    // 根占位（content=空）视为已加载（不显示）
    const n = state.nodeMap[msgId];
    if (!n) return false;
    if (!n.parent_id && n.role === "assistant" && !n.content) return true;
    // 必须有正文（content / content_blocks / text_summary 任一非空）才算 loaded
    if (n.content && n.content.length > 0) return true;
    if (n.content_blocks && n.content_blocks.length > 0) return true;
    if (n.text_summary && n.text_summary.length > 0) return true;
    return false;
  }, []);

  // ── 加载设置（尊重用户的"加载时滚动到底部"设置）──
  const [autoScrollOnLoad, setAutoScrollOnLoad] = useState(true);
  useEffect(() => {
    try {
      const saved = localStorage.getItem("edu-companion-settings-prefs");
      if (saved) {
        const parsed = JSON.parse(saved);
        setAutoScrollOnLoad(parsed.autoScrollOnLoad ?? true);
      }
    } catch { /* ignore */ }
  }, []);

  // ── Auto-scroll on load：使用 Virtuoso 的 scrollToIndex ──
  useEffect(() => {
    if (messages.length === 0) return;
    if (initialLoadDoneRef.current) return;
    initialLoadDoneRef.current = true;
    if (!autoScrollOnLoad) return;
    // 跳到最后一条
    requestAnimationFrame(() => {
      virtuosoRef.current?.scrollToIndex({
        index: messages.length - 1,
        align: "end",
        behavior: "auto",
      });
    });
  }, [messages.length, autoScrollOnLoad]);

  // ── 滚动方向检测：用户主动向上滑时显示"滚到底部"按钮 ──
  useEffect(() => {
    const el = virtuosoRef.current?.scrollTo; // 仅类型占位
    // 监听 wheel 事件
    const onWheel = (e: WheelEvent) => {
      lastWheelDeltaYRef.current = e.deltaY;
      if (e.deltaY < -1) {
        setScrollDir("up");
        setShowScrollButton(true);
      } else if (e.deltaY > 1) {
        setScrollDir("down");
      }
    };
    document.addEventListener("wheel", onWheel, { passive: true });
    return () => document.removeEventListener("wheel", onWheel);
  }, []);

  // 隐藏 scroll button 的定时器
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    return () => {
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    };
  }, []);

  // ── 版本感知显示（基于 nodeMap） ──
  const nodeMap = useMessageStore((s) => s.nodeMap);
  const { versionGroups, versionGroupByMessage } = useMemo(() => {
    type GroupKey = string;
    const messages = Object.values(nodeMap);
    const messageGroupKey = new Map<string, GroupKey>();
    for (const m of messages) {
      if (m.is_deleted) continue;
      messageGroupKey.set(m.id, `${m.parent_id}::${m.role}`);
    }
    const groupIds = new Map<GroupKey, string[]>();
    for (const m of messages) {
      if (m.is_deleted) continue;
      const gk = messageGroupKey.get(m.id)!;
      if (!groupIds.has(gk)) groupIds.set(gk, []);
      groupIds.get(gk)!.push(m.id);
    }
    const vg: Record<GroupKey, { ids: string[]; activeIndex: number; total: number }> = {};
    groupIds.forEach((ids, gk) => {
      if (ids.length > 1) {
        vg[gk] = { ids, activeIndex: ids.length - 1, total: ids.length };
      }
    });
    const vgbm: Record<string, string> = {};
    messageGroupKey.forEach((gk, mid) => { vgbm[mid] = gk; });
    return { versionGroups: vg, versionGroupByMessage: vgbm };
  }, [nodeMap]);

  // Get display text
  const getDisplayText = useCallback((msg: MessageNode) => {
    const fromBlocks = msg.content_blocks?.filter(b => b.type === "text").map(b => b.text || "").join("\n\n") || "";
    if (fromBlocks) return fromBlocks;
    if (msg.content) return msg.content;
    // ★ 失败消息：content/content_blocks 为空但 text_summary 有错误信息
    if (msg.text_summary) return msg.text_summary;
    return "";
  }, []);

  // ── 渲染单条消息的回调（useCallback 避免 Virtuoso 重新构造）──
  const itemContent = useCallback((index: number, message: MessageNode) => {
    const isUser = message.role === "user";
    const isEditing = editingId === message.id;
    const loaded = isContentLoaded(message.id);

    // ── 触发懒加载：骨架但无正文时加载完整消息 ──
    if (!loaded && !message.id.startsWith("t_") && !message.id.startsWith("a_") && !message.id.startsWith("err-")) {
      void useMessageStore.getState().loadFullContent(message.id);
    }

    const displayText = loaded ? getDisplayText(message) : "";
    const groupKey = versionGroupByMessage[message.id];
    const group = groupKey ? versionGroups[groupKey] : undefined;
    const hasVersions = !!group && group.total > 1;
    const vInfo = hasVersions
      ? { index: group.activeIndex + 1, total: group.total }
      : { index: 1, total: 1 };
    const cardsForMsg = getCardsForMessage(message.id, explainCards);

    return (
      <div data-lazy-id={message.id} className="py-1.5">
        <MessageItem
          message={message}
          isFeynmanMode={isFeynmanMode}
          isEditing={isEditing}
          editingText={editingText}
          vInfo={vInfo}
          hasVersions={hasVersions}
          loaded={loaded}
          displayText={displayText}
          cardsForMsg={cardsForMsg}
          replyingToId={replyingToId ?? null}
          isLoading={isLoading}
          onStartEdit={handleStartEdit}
          onEditTextChange={setEditingText}
          onSaveEdit={handleSaveEdit}
          onCancelEdit={handleCancelEdit}
          onDelete={() => onDeleteMessage?.(message.id)}
          onCopy={() => handleCopyMessage(displayText)}
          onVersionNav={(dir) => handleVersionNav(message.id, dir)}
          onFeynmanTeach={onFeynmanTeach ? () => onFeynmanTeach(message.id, displayText, message.conv_id || "") : undefined}
          handleTextMouseDown={handleTextMouseDown}
          handleTextMouseUp={handleTextMouseUp}
          handleTextContextMenu={handleTextContextMenu}
          handleTextClick={handleTextClick}
          onBadgeClick={(id) => {
            const c = useExplainStore.getState().cards.find(c => c.id === id);
            if (c) useExplainStore.getState().toggleCollapse(id, !c.collapsed);
          }}
        />
      </div>
    );
  }, [
    editingId, editingText, isContentLoaded, getDisplayText,
    versionGroupByMessage, versionGroups, explainCards,
    replyingToId, isLoading, isFeynmanMode,
    handleStartEdit, handleSaveEdit, handleCancelEdit,
    handleCopyMessage, handleVersionNav, onDeleteMessage, onFeynmanTeach,
    handleTextMouseDown, handleTextMouseUp, handleTextContextMenu, handleTextClick,
  ]);

  // ── Loading indicator ──
  const loadingIndicator = useMemo(() => statusMessage ? (
    <div className="flex gap-4 px-4">
      <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-[var(--color-surface)] text-[var(--color-accent)] border border-[var(--color-border)]">
        <Bot size={16} />
      </div>
      <div className="flex items-center gap-2 px-4 py-2.5">
        <div className="flex gap-1.5 items-center">
          <span className="w-2 h-2 bg-[var(--color-text-muted)] rounded-full animate-pulse" style={{ animationDelay: "0ms" }} />
          <span className="w-2 h-2 bg-[var(--color-text-muted)] rounded-full animate-pulse" style={{ animationDelay: "200ms" }} />
          <span className="w-2 h-2 bg-[var(--color-text-muted)] rounded-full animate-pulse" style={{ animationDelay: "400ms" }} />
        </div>
        <span className="text-xs text-[var(--color-text-muted)] ml-1">{statusMessage}</span>
      </div>
    </div>
  ) : null, [statusMessage]);

  // ── Virtuoso Footer (Loading indicator) ──
  const Footer = useCallback(() => {
    if (!isLoading) return null;
    if (replyingToId || messages.some(m => m.role === "assistant")) return null;
    return <div className="px-4 py-2">{loadingIndicator}</div>;
  }, [isLoading, replyingToId, messages, loadingIndicator]);

  // ── 消息为空时的空状态 ──
  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col overflow-hidden relative">
        <ErrorBoundary>
          <div className="flex-1 flex items-center justify-center">
            <EmptyState
              icon="💬"
              title="开始一段对话"
              description="在下方输入框提问，AI 助手会基于你的学习空间内容回答"
            />
          </div>
        </ErrorBoundary>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden relative">
      <ErrorBoundary>
      <Virtuoso
        ref={virtuosoRef}
        style={{ height: "100%" }}
        data={messages}
        itemContent={itemContent}
        followOutput={atBottom ? "smooth" : false}
        atBottomStateChange={setAtBottom}
        initialTopMostItemIndex={messages.length - 1}
        overscan={400}
        rangeChanged={handleRangeChanged}
        components={{
          Footer: Footer,
        }}
        className="scrollbar-thin"
        data-testid="message-virtuoso"
      />
      </ErrorBoundary>

      {/* Text Selection Toolbar */}
      {selection && (
        <div data-testid="text-selection-toolbar">
        <TextSelectionToolbar position={selection.position} visible={true} onQuote={handleQuote} onCopy={handleSelectionCopy}
          level={selection.level} source={selection.source}
          onExplain={() => {
            if (!selection) return;
            const text = selection.text;
            if (!text) return;

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

            const cardPos = toBubblePos(selection.position.x, selection.position.y);
            let badgePos = cardPos;
            if (selection.messageId) {
              const msgEl = document.querySelector(`[data-message-id="${selection.messageId}"]`);
              if (msgEl) {
                try {
                  const walker = document.createTreeWalker(msgEl, NodeFilter.SHOW_TEXT, null);
                  const fullText = msgEl.textContent || '';
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
                } catch { /* fallback */ }
              }
            }

            createCard({
              conv_id: selection.sourceConversationId,
              message_id: selection.messageId,
              depth: 1,
              selected_text: text,
              char_start: selection.charStart,
              pos_x: cardPos.x,
              pos_y: cardPos.y,
              badge_x: badgePos.x,
              badge_y: badgePos.y,
            });
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
        </div>
      )}

      {/* Note Card */}
      <div data-selection-card>
        <NoteCard
          selectedText={noteCard?.text || ""}
          position={noteCard?.position || { x: 0, y: 0 }}
          visible={!!noteCard}
          onClose={() => setNoteCard(null)}
          onSaveNote={(note) => {
            console.log("Note saved:", note);
            setNoteCard(null);
          }}
        />
      </div>

      {/* Scroll navigation button */}
      <button
        onClick={() => {
          if (scrollDir === "up") {
            virtuosoRef.current?.scrollToIndex({ index: 0, align: "start", behavior: "smooth" });
          } else {
            virtuosoRef.current?.scrollToIndex({ index: messages.length - 1, align: "end", behavior: "smooth" });
            setAtBottom(true);
          }
        }}
        className={`
          absolute bottom-4 right-4
          bg-[var(--color-surface)]/85 backdrop-blur-md
          border border-[var(--color-border)]
          rounded-2xl p-2.5
          shadow-[var(--shadow-sm)]
          hover:bg-[var(--color-surface-hover)] hover:scale-105
          active:scale-95
          transition-all duration-300 z-10
          ${showScrollButton ? "opacity-100 translate-y-0 pointer-events-auto" : "opacity-0 translate-y-2 pointer-events-none"}
        `}
        aria-label={scrollDir === "up" ? "滚动到顶部" : "滚动到底部"}
        data-testid="message-list-scroll-btn"
      >
        {scrollDir === "up" ? (
          <ChevronUp size={20} className="text-[var(--color-text-secondary)]" />
        ) : (
          <ChevronDown size={20} className="text-[var(--color-text-secondary)]" />
        )}
      </button>

      {/* Feynman evaluation card — fixed position at top after last assistant message */}
      {latestEval && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 w-[90%] max-w-md p-3 rounded-xl border border-emerald-500/30 bg-emerald-500/5 shadow-md">
          <div className="flex items-center gap-2 mb-2">
            <BookOpen size={14} className="text-emerald-500" />
            <span className="text-xs font-semibold text-emerald-600">费曼评估报告</span>
            <span className={`ml-auto text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
              latestEval.mastery_level === "high" ? "bg-emerald-100 text-emerald-700" :
              latestEval.mastery_level === "medium" ? "bg-amber-100 text-amber-700" :
              "bg-red-100 text-red-700"
            }`}>
              掌握度: {latestEval.mastery_level === "high" ? "高" : latestEval.mastery_level === "medium" ? "中" : "低"}
            </span>
          </div>
          {latestEval.summary && (
            <p className="text-[11px] text-[var(--color-text-secondary)] italic">{latestEval.summary}</p>
          )}
        </div>
      )}
    </div>
  );
}
