"use client";

import React, { Fragment, useEffect, useRef, useMemo, useState, useCallback } from "react";
import { User, Bot, GraduationCap, ChevronDown, ChevronUp, FileText, ImageIcon, ExternalLink, BookOpen } from "lucide-react";
import ResponseBlockRenderer from "./../blocks/ResponseBlockRenderer";
import QuoteBlockRenderer from "./../blocks/QuoteBlockRenderer";
import { BLOCK_RENDERERS } from "@/components/conversation/blocks/registry";
import TextSelectionToolbar from "./../input/TextSelectionToolbar";
import SubBranchInline from "./../blocks/SubBranchInline";
import SpeakButton from "./../media/SpeakButton";
import MarkdownRenderer from "./../blocks/MarkdownRenderer";
import SelfExplainCard from "./../cards/SelfExplainCard";
import MessageActions from "./MessageActions";
import MessageEditArea from "./MessageEditArea";
import { useTextSelection } from "./../hooks/useTextSelection";
import NoteCard from "./../cards/NoteCard";
import KnowledgeExplainCard from "./../cards/KnowledgeExplainCard";
import { useExplainStore, getCardsForMessage } from "@/store/explain/explain-store";
import type { ExplainCardData } from "@/store/explain/explain-store";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { useConversationStore, useMessageStore } from "@/store/conversation/conversation-store";
import type { MessageNode, ResponseBlock, SubBranchInfo } from "@/types";

// ── Feynman evaluation type ──
interface FeynmanEval {
  highlights: string[];
  weaknesses: string[];
  mastery_level: "high" | "medium" | "low";
  summary: string;
}

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
  isLoading?: boolean;
  statusMessage?: string;
  replyingToId?: string | null;
  conversationId?: string | null;  // for explain cards loading
  isFeynmanMode?: boolean;  // 费曼模式视觉区分
  onDeleteMessage?: (messageId: string) => void;
  onEditMessage?: (messageId: string, newText: string) => Promise<number>;
  onSend?: (text: string) => void;
  onFeynmanTeach?: (messageId: string, messageText: string, conversationId: string) => void;
  breadcrumb?: React.ReactNode;
}

type EditedMap = Record<string, string>;

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
  breadcrumb,
}: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const breadcrumbRef = useRef<HTMLDivElement>(null);
  const [breadcrumbHeight, setBreadcrumbHeight] = useState(0);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingText, setEditingText] = useState("");
  const [showScrollButton, setShowScrollButton] = useState(false);
  const scrollDirRef = useRef<"up" | "down">("up");
  const [scrollDir, setScrollDir] = useState<"up" | "down">("up");
  const lastScrollTopRef = useRef(0);
  const scrollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 兼容旧字段：标记用户是否已离开底部足够远
  const userAwayFromBottom = useRef(false);
  const hoverOnButtonRef = useRef(false);
  const initialLoadDoneRef = useRef(false);
  const isAutoScrollingRef = useRef(false);
  const scrollEndTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastMsgsLengthRef = useRef(0);
  // ── 自动跟随状态机 ──
  // autoFollow = 是否"跟随底部"。true 时新消息/流式 token 自动滚动到底部。
  // 进入条件：scrollTop 距离底部 ≤ AUTO_FOLLOW_THRESHOLD（50px）
  // 退出条件：用户主动向上滚动（滚轮向上 / scrollTop 减小）且已离开底部
  // 重新进入：滚回底部 / 点击"滚到底部"按钮 / 发送新消息
  const AUTO_FOLLOW_THRESHOLD = 50;
  const autoFollowRef = useRef(true);
  // 用于在自动滚动动画期间忽略 scroll 事件对 autoFollow 的反向更新
  const autoScrollOriginRef = useRef<"user" | "program" | null>(null);
  const lastWheelDeltaYRef = useRef(0);
  const lastWheelTsRef = useRef(0);
  const streamingId = useMessageStore((s) => s.streamingId);
  const [editedTexts, setEditedTexts] = useState<EditedMap>({});
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

  const handleCopyMessage = async (text: string) => {
    try { await navigator.clipboard.writeText(text); }
    catch {
      const ta = document.createElement("textarea");
      ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select(); document.execCommand("copy"); document.body.removeChild(ta);
    }
  };

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

  // Memo: find the latest evaluation from the last assistant message
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

  // ── 版本切换：纯前端 tip 指针 ──
  const handleVersionNav = useCallback((messageId: string, direction: "prev" | "next") => {
    useMessageStore.getState().navigateVersion(messageId, direction);
  }, []);

  const handleDeleteMessage = (messageId: string) => onDeleteMessage?.(messageId);
  const handleStartEdit = (msgId: string, currentText: string) => { setEditingId(msgId); setEditingText(currentText); };

  const handleSaveEdit = async () => {
    const msgId = editingId; const newText = editingText.trim();
    if (!msgId || !newText) { setEditingId(null); return; }
    if (onEditMessage) {
      try {
        await onEditMessage(msgId, newText);
        setEditedTexts(prev => ({ ...prev, [msgId]: newText }));
      } catch {}
    }
    setEditingId(null);
  };

  const handleCancelEdit = () => setEditingId(null);

  // ── 懒加载：IntersectionObserver + 冷却 ──
  const loadedContent = useMessageStore((s) => s.loadedContent);
  const loadingContents = useMessageStore((s) => s.loadingContents);
  const lazyLoadBatch = useMessageStore((s) => s.lazyLoadBatch);

  // 判断消息正文是否已加载（骨架 vs 完整）
  const isContentLoaded = useCallback((msgId: string) => {
    const state = useMessageStore.getState();
    // Pipeline 写入的消息（不在 outlines 中）不需要懒加载
    if (!state.outlines.some(o => o.id === msgId)) return true;
    // 流式消息在 messages 中已有内容（optimistic write 写入），不需要等懒加载
    if (state.streamingId === msgId) return true;
    return !!state.loadedContent[msgId];
  }, []);

  const ioRef = useRef<IntersectionObserver | null>(null);
  const ioQueueRef = useRef<string[]>([]);
  const ioTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [preloadTrigger, setPreloadTrigger] = useState(0); // 触发预加载检测

  // 观察可见消息元素，遇则触发懒加载（带 throttle 300ms 冷却）
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    ioRef.current?.disconnect();
    ioRef.current = new IntersectionObserver((entries) => {
      if (isAutoScrollingRef.current) return; // 自动滚动期间不触发懒加载
      let hasNew = false;
      for (const entry of entries) {
        if (entry.isIntersecting) {
          const msgId = entry.target.getAttribute('data-lazy-id');
          if (!msgId) continue;
          // 用 getState() 实时读取，不从闭包取 (避免 loadedContent 变化导致 observer 重建)
          const st = useMessageStore.getState();
          if (!st.loadedContent[msgId] && !st.loadingContents.includes(msgId)) {
            ioQueueRef.current.push(msgId);
            hasNew = true;
          }
        }
      }
      if (!hasNew) return;
      // 冷却：300ms 内批量发送
      if (ioTimerRef.current) clearTimeout(ioTimerRef.current);
      ioTimerRef.current = setTimeout(() => {
        const batch = Array.from(new Set(ioQueueRef.current));
        ioQueueRef.current = [];
        if (batch.length > 0) {
          useMessageStore.getState().lazyLoadBatch(batch);
        }
        // 触发预加载检测
        setPreloadTrigger(t => t + 1);
      }, 300);
    }, {
      root: container,
      rootMargin: '200px 0px',  // 提前 200px 预加载
      threshold: 0,
    });

    // 观察所有带 data-lazy-id 的消息元素
    const msgEls = container.querySelectorAll('[data-lazy-id]');
    msgEls.forEach(el => ioRef.current?.observe(el));

    return () => {
      ioRef.current?.disconnect();
      if (ioTimerRef.current) clearTimeout(ioTimerRef.current);
    };
  }, [messages.map(m => m.id).join(',')]);

  // 预加载：视口上下 N 条未加载消息提前加载
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const st = useMessageStore.getState();
    const visibleEls: { msgId: string; top: number }[] = [];
    const els = Array.from(container.querySelectorAll('[data-lazy-id]'));
    const scrollTop = container.scrollTop;
    const clientH = container.clientHeight;
    for (const el of els) {
      const msgId = el.getAttribute('data-lazy-id');
      if (!msgId || st.loadedContent[msgId] || st.loadingContents.includes(msgId)) continue;
      const rect = el.getBoundingClientRect();
      const containerRect = container.getBoundingClientRect();
      const top = rect.top - containerRect.top + scrollTop;
      visibleEls.push({ msgId, top });
    }
    // 按位置排序
    visibleEls.sort((a, b) => a.top - b.top);
    // 找出视口范围 (±300px) 内的消息
    const viewTop = scrollTop - 300;
    const viewBottom = scrollTop + clientH + 300;
    const toPreload = visibleEls
      .filter(v => v.top >= viewTop && v.top <= viewBottom)
      .slice(0, 6)  // 最多预加载 6 条
      .map(v => v.msgId);
    if (toPreload.length > 0) {
      st.lazyLoadBatch(toPreload);
    }
  }, [preloadTrigger, loadedContent, lazyLoadBatch]);

  // ── 骨架屏组件 ──
  function MessageSkeleton({ isUser }: { isUser: boolean }) {
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

  // ── 动态测量面包屑实际高度（移动端按钮高度 > 固定 h-12） ──
  useEffect(() => {
    if (!breadcrumbRef.current) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const h = entry.contentRect.height;
        if (h > 0) setBreadcrumbHeight(h);
      }
    });
    ro.observe(breadcrumbRef.current);
    return () => ro.disconnect();
  }, [breadcrumb]);

  // Auto-scroll on load（尊重用户设置）+ 后续由 autoFollow 状态机接管
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

  useEffect(() => {
    if (!bottomRef.current || !containerRef.current) return;

    // 首次加载：等消息真正加载完成后再决策
    if (!initialLoadDoneRef.current) {
      if (messages.length === 0) return;
      initialLoadDoneRef.current = true;
      if (!autoScrollOnLoad) {
        containerRef.current.scrollTo({ top: 0 });
        autoFollowRef.current = false;
        return;
      }
      // 用户开启了"加载时滚动到底部"→ 执行原逻辑 + 启用 autoFollow
      autoScrollOriginRef.current = "program";
      isAutoScrollingRef.current = true;
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
      autoFollowRef.current = true;
      return;
    }

    // 后续：仅在新消息或流式输出时触发自动滚动
    // 懒加载（text_summary 变但长度不变）不触发
    const isNewMessage = messages.length > lastMsgsLengthRef.current;
    const isStreaming = !!streamingId;
    if (!isNewMessage && !isStreaming) return;
    lastMsgsLengthRef.current = messages.length;

    // autoFollow 为 false → 尊重用户已上滑的意图，不自动滚动
    if (!autoFollowRef.current) return;

    autoScrollOriginRef.current = "program";
    isAutoScrollingRef.current = true;
    bottomRef.current.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, streamingId, autoScrollOnLoad]);

  // 组件卸载时清理定时器
  useEffect(() => {
    return () => {
      if (scrollTimerRef.current) clearTimeout(scrollTimerRef.current);
      if (scrollEndTimerRef.current) clearTimeout(scrollEndTimerRef.current);
    };
  }, []);

  const clearScrollTimer = useCallback(() => {
    if (scrollTimerRef.current) {
      clearTimeout(scrollTimerRef.current);
      scrollTimerRef.current = null;
    }
  }, []);

  const startHideTimer = useCallback(() => {
    clearScrollTimer();
    if (hoverOnButtonRef.current) return;
    scrollTimerRef.current = setTimeout(() => {
      setShowScrollButton(false);
    }, 1500);
  }, [clearScrollTimer]);

  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    const isAtBottom = distanceFromBottom <= AUTO_FOLLOW_THRESHOLD;

    // ── autoFollow 状态机更新 ──
    // 由程序触发的滚动不修改 autoFollow（避免动画过程中的反弹取消）
    const isProgramScroll = autoScrollOriginRef.current === "program";
    if (isProgramScroll) {
      // 程序滚动：保持 autoFollow 状态，只在到达底部时确保为 true
      if (isAtBottom) autoFollowRef.current = true;
    } else {
      // 用户滚动：根据位置切换 autoFollow
      if (isAtBottom) {
        // 滚到或接近底部 → 进入跟随模式
        autoFollowRef.current = true;
      } else if (scrollTop < lastScrollTopRef.current) {
        // 真正向上滚（scrollTop 减小）且已离开底部 → 退出跟随
        autoFollowRef.current = false;
      }
      // scrollTop 增大但在中间 → 保持当前状态（可能是用户手动下滚查看历史）
    }
    lastScrollTopRef.current = scrollTop;

    // 兼容旧字段
    userAwayFromBottom.current = distanceFromBottom > 300;

    // 检测自动滚动是否结束（200ms 无新 scroll 事件视为结束）
    if (isAutoScrollingRef.current) {
      if (scrollEndTimerRef.current) clearTimeout(scrollEndTimerRef.current);
      scrollEndTimerRef.current = setTimeout(() => {
        isAutoScrollingRef.current = false;
        autoScrollOriginRef.current = null;
      }, 200);
    }

    // 在两端尽头时不显示按钮
    const atTop = scrollTop <= 50;
    if (atTop || isAtBottom) {
      setShowScrollButton(false);
      return;
    }

    // 判断实际滚动方向
    const scrollingDown = scrollTop > lastScrollTopRef.current;
    scrollDirRef.current = scrollingDown ? "down" : "up";
    setScrollDir(scrollingDown ? "down" : "up");
    setShowScrollButton(true);

    // 滚动时重置自动隐藏计时器
    startHideTimer();
  }, [startHideTimer]);

  // ── 滚轮事件：单独追踪以识别"用户主动向上滑"意图 ──
  // scroll 事件在程序触发的 smooth scroll 期间也会触发，
  // 单独监听 wheel 可以更精准地标记用户意图
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      // 滚轮向上（deltaY < 0）→ 标记为用户主动上滑
      if (e.deltaY < -1) {
        autoScrollOriginRef.current = "user";
        const distanceFromBottom =
          el.scrollHeight - el.scrollTop - el.clientHeight;
        if (distanceFromBottom > AUTO_FOLLOW_THRESHOLD) {
          autoFollowRef.current = false;
        }
      }
    };
    el.addEventListener("wheel", onWheel, { passive: true });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  // ── 触摸滑动：移动端上下拖动也应退出 autoFollow ──
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let lastTouchY = 0;
    const onTouchStart = (e: TouchEvent) => {
      lastTouchY = e.touches[0]?.clientY ?? 0;
    };
    const onTouchMove = (e: TouchEvent) => {
      const y = e.touches[0]?.clientY ?? 0;
      const dy = y - lastTouchY;
      lastTouchY = y;
      // 向下拖（手指向上滑 → 视图向下滑）→ dy > 0 实际是向上滚内容
      // 这里 dy > 0 表示手指从下往上 → 视图内容向上滚 → 用户在看历史
      if (dy > 1) {
        autoScrollOriginRef.current = "user";
        const distanceFromBottom =
          el.scrollHeight - el.scrollTop - el.clientHeight;
        if (distanceFromBottom > AUTO_FOLLOW_THRESHOLD) {
          autoFollowRef.current = false;
        }
      }
    };
    el.addEventListener("touchstart", onTouchStart, { passive: true });
    el.addEventListener("touchmove", onTouchMove, { passive: true });
    return () => {
      el.removeEventListener("touchstart", onTouchStart);
      el.removeEventListener("touchmove", onTouchMove);
    };
  }, []);

  // ── 版本感知显示 ──
  // 版本组信息从 outlines 推导（outlines 包含全版本，messages 已被 tip 过滤）
  const outlines = useMessageStore((s) => s.outlines);
  const { versionGroups, versionGroupByMessage } = useMemo(() => {
    type GroupKey = string;
    const messageGroupKey = new Map<string, GroupKey>();
    for (const m of outlines) {
      if (m.is_deleted) continue;
      messageGroupKey.set(m.id, `${m.parent_id}::${m.role}`);
    }
    const groupIds = new Map<GroupKey, string[]>();
    for (const m of outlines) {
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
  }, [outlines]);

  // 可见消息直接从 store.messages 取（已由 tip 过滤）
  const visibleMessages = messages;



  // Get display text from a message
  const getDisplayText = (msg: MessageNode) => {
    if (editedTexts[msg.id]) return editedTexts[msg.id];
    const fromBlocks = msg.content_blocks?.filter(b => b.type === "text").map(b => b.text || "").join("\n\n") || "";
    if (fromBlocks) return fromBlocks;
    // Fallback to msg.content for backward compatibility (old data without content_blocks)
    return msg.content || "";
  };

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
    <div className="flex-1 flex flex-col overflow-hidden relative">
      <ErrorBoundary>
      <div ref={containerRef} className="flex-1 overflow-y-auto px-4 pb-2 space-y-6" onScroll={handleScroll}>
        {/* Spacer to prevent content hidden under overlay breadcrumb */}
        {breadcrumb && <div style={{ height: breadcrumbHeight || 48 }} />}
        {visibleMessages.map((message) => {
          const isUser = message.role === "user";
          const isEditing = editingId === message.id;
          const loaded = isContentLoaded(message.id);
          const displayText = loaded ? getDisplayText(message) : "";
          const groupKey = versionGroupByMessage[message.id];
          const group = groupKey ? versionGroups[groupKey] : undefined;
          const hasVersions = !!group && group.total > 1;
          const vInfo = hasVersions
            ? { index: group.activeIndex + 1, total: group.total }
            : { index: 1, total: 1 };
          const cardsForMsg = getCardsForMessage(message.id, explainCards);

          return (
            <div key={message.id} data-lazy-id={message.id}>
            {!loaded && !isEditing ? (
              <MessageSkeleton isUser={isUser} />
            ) : (
            <Fragment>
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
                        sourceConversationId={b.source_conv_id} sourceMessageId={b.source_message_id} />
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
                          <div data-message-id={message.id} data-conv-id={message.conv_id} data-full-text={displayText}
                            className="text-base leading-[1.65] text-[var(--color-text)] whitespace-pre-wrap break-words select-text"
                          >
                            <ExplainMarkers text={displayText} cards={cardsForMsg} messageId={message.id} onBadgeClick={(id) => {
                              const c = useExplainStore.getState().cards.find(c => c.id === id);
                              if (c) useExplainStore.getState().toggleCollapse(id, !c.collapsed);
                            }} />
                          </div>
                        </>
                      ) : (
                        <>
                          {/* ── 按 content_blocks 原始顺序交织渲染（text ↔ tool ↔ reasoning 等）── */}
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
                                  <ExplainMarkers text={blockText} cards={cardsForMsg} messageId={message.id} onBadgeClick={(id) => {
                                    const c = useExplainStore.getState().cards.find(c => c.id === id);
                                    if (c) useExplainStore.getState().toggleCollapse(id, !c.collapsed);
                                  }} />
                                </div>
                              );
                            }
                            const Renderer = BLOCK_RENDERERS[b.type];
                            return Renderer ? <Renderer key={`block-${bi}`} block={b} /> : null;
                          })}
                          {/* 无 text 块且流式未完成 → 加载动画 */}
                          {!(message.content_blocks || []).some(b => b.type === "text") && isLoading && (
                            <div className="flex gap-1.5 items-center py-1 px-1">
                              <span className="w-2 h-2 bg-[var(--color-text-muted)] rounded-full animate-pulse" style={{ animationDelay: "0ms" }} />
                              <span className="w-2 h-2 bg-[var(--color-text-muted)] rounded-full animate-pulse" style={{ animationDelay: "200ms" }} />
                              <span className="w-2 h-2 bg-[var(--color-text-muted)] rounded-full animate-pulse" style={{ animationDelay: "400ms" }} />
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
                      {/* Self-explain card (P0-R03) — assistant messages with cognitive nodes */}
                      {!isUser && message.cognitive_node_ids && message.cognitive_node_ids.length > 0 && (
                        <SelfExplainCard
                          knowledgeNodeId={message.cognitive_node_ids[0]}
                          messageId={message.id}
                        />
                      )}
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
                        onFeynmanTeach={(!isUser && !isFeynmanMode && onFeynmanTeach)
                          ? () => onFeynmanTeach(message.id, displayText, message.conv_id || "")
                          : undefined}
                      />
                    )}
                  </div>
                </div>
              </div>
              {/* Loading indicator below the message being edited */}
              {replyingToId === message.id && loadingIndicator}
            </div>
          </Fragment>
          )}
            </div>
          );
        })}

        {/* Bottom loading indicator — only when no assistant message exists yet */}
        {isLoading && !replyingToId && !messages.some(m => m.role === "assistant") && loadingIndicator}

        {/* ── Feynman 评估展示 ── */}
        {latestEval && (
          <div className="mx-4 my-4 p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/5">
            <div className="flex items-center gap-2 mb-3">
              <BookOpen size={16} className="text-emerald-500" />
              <span className="text-sm font-semibold text-emerald-600">费曼评估报告</span>
              <span className={`ml-auto text-xs px-2 py-0.5 rounded-full font-medium ${
                latestEval.mastery_level === "high" ? "bg-emerald-100 text-emerald-700" :
                latestEval.mastery_level === "medium" ? "bg-amber-100 text-amber-700" :
                "bg-red-100 text-red-700"
              }`}>
                掌握度: {latestEval.mastery_level === "high" ? "高" : latestEval.mastery_level === "medium" ? "中" : "低"}
              </span>
            </div>
            {latestEval.highlights.length > 0 && (
              <div className="mb-2">
                <span className="text-[10px] font-medium text-emerald-500">✨ 亮点</span>
                <ul className="mt-1 space-y-0.5">
                  {latestEval.highlights.map((h, i) => (
                    <li key={i} className="text-xs text-[var(--color-text-secondary)] flex items-start gap-1">
                      <span className="text-emerald-400 mt-0.5">•</span>
                      {h}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {latestEval.weaknesses.length > 0 && (
              <div className="mb-2">
                <span className="text-[10px] font-medium text-amber-500">⚠️ 不足</span>
                <ul className="mt-1 space-y-0.5">
                  {latestEval.weaknesses.map((w, i) => (
                    <li key={i} className="text-xs text-[var(--color-text-secondary)] flex items-start gap-1">
                      <span className="text-amber-400 mt-0.5">•</span>
                      {w}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {latestEval.summary && (
              <p className="text-xs text-[var(--color-text-secondary)] italic border-t border-emerald-500/10 pt-2 mt-2">
                {latestEval.summary}
              </p>
            )}
          </div>
        )}

        <div ref={bottomRef} />
      </div>
      {breadcrumb && (
        <div
          ref={breadcrumbRef}
          className="absolute top-0 inset-x-0"
          style={{ zIndex: 10 }}
        >
          {/* Layer 3: 渐变背景 */}
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              zIndex: 1,
              background: 'linear-gradient(to top, transparent 0%, var(--color-bg) 60%)',
            }}
          />
          {/* Layer 2: 渐变毛玻璃（blur 与背景渐变同步增强） */}
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              zIndex: 2,
              backdropFilter: 'blur(6px) saturate(140%)',
              WebkitBackdropFilter: 'blur(6px) saturate(140%)',
              maskImage: 'linear-gradient(to top, transparent 0%, black 60%)',
              WebkitMaskImage: 'linear-gradient(to top, transparent 0%, black 60%)',
            }}
          />
          {/* Layer 1: 按钮文字，透明背景 */}
          <div className="relative" style={{ zIndex: 3, background: 'transparent' }}>
            {breadcrumb}
          </div>
        </div>
      )}
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

      {/* Scroll navigation button */}
      <button
        onMouseEnter={() => { hoverOnButtonRef.current = true; clearScrollTimer(); }}
        onMouseLeave={() => {
          hoverOnButtonRef.current = false;
          startHideTimer();
        }}
        onClick={() => {
          if (scrollDirRef.current === "up") {
            // 向上滚到顶部 → 退出 autoFollow
            autoScrollOriginRef.current = "program";
            isAutoScrollingRef.current = true;
            autoFollowRef.current = false;
            containerRef.current?.scrollTo({ top: 0, behavior: "smooth" });
          } else {
            // 向下滚到底部 → 启用 autoFollow
            autoScrollOriginRef.current = "program";
            isAutoScrollingRef.current = true;
            autoFollowRef.current = true;
            bottomRef.current?.scrollIntoView({ behavior: "smooth" });
            userAwayFromBottom.current = false;
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
      >
        {scrollDir === "up" ? (
          <ChevronUp size={20} className="text-[var(--color-text-secondary)]" />
        ) : (
          <ChevronDown size={20} className="text-[var(--color-text-secondary)]" />
        )}
      </button>
    </div>
  );
}
