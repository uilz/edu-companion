"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Lightbulb, Sparkles, ChevronDown, ChevronUp, Loader2,
  Video, Search, Star, BookOpen, Target,
  BookMarked, X, ExternalLink, Copy, Send, Bot, User, Trash2,
} from "lucide-react";
import { API_BASE } from "@/lib/api";
import MarkdownRenderer from "./MarkdownRenderer";
import { useExplainStore, type ExplainCardData, type CardMessage } from "@/store/explain-store";

export type { ExplainCardData } from "@/store/explain-store";

// 层级对应的主题配色数组
const DEPTH_COLORS = [
  { badge: "from-indigo-500 to-purple-500", border: "border-l-indigo-400", accent: "text-indigo-500", bg: "bg-indigo-50 dark:bg-indigo-950/80" },
  { badge: "from-emerald-500 to-teal-500", border: "border-l-emerald-400", accent: "text-emerald-500", bg: "bg-emerald-50 dark:bg-emerald-950/80" },
  { badge: "from-amber-500 to-orange-500", border: "border-l-amber-400", accent: "text-amber-500", bg: "bg-amber-50 dark:bg-amber-950/80" },
  { badge: "from-rose-500 to-pink-500", border: "border-l-rose-400", accent: "text-rose-500", bg: "bg-rose-50 dark:bg-rose-950/80" },
  { badge: "from-cyan-500 to-blue-500", border: "border-l-cyan-400", accent: "text-cyan-500", bg: "bg-cyan-50 dark:bg-cyan-950/80" },
  { badge: "from-violet-500 to-fuchsia-500", border: "border-l-violet-400", accent: "text-violet-500", bg: "bg-violet-50 dark:bg-violet-950/80" },
];

// 根据层级获取配色配置
function getDc(depth: number) {
  return DEPTH_COLORS[Math.min(depth - 1, DEPTH_COLORS.length - 1)];
}

export default function KnowledgeExplainCard({ card }: { card: ExplainCardData }) {
  const {
    id, depth, selected_text, context_node_id, collapsed, explanation, mastery,
    conversation_id, message_id, pos_x, pos_y, conversation,
  } = card;
  const updateCard = useExplainStore((s) => s.updateCard);
  const deleteCard = useExplainStore((s) => s.deleteCard);
  const toggleCollapse = useExplainStore((s) => s.toggleCollapse);
  const createCard = useExplainStore((s) => s.createCard);

  const dc = getDc(depth);

  // AI解释内容状态
  const [exp, setExp] = useState(explanation || "");
  const [loading, setLoading] = useState(!explanation);
  const [videos, setVideos] = useState<{ title: string; url: string; source: string }[]>([]);
  const [loadingVideos, setLoadingVideos] = useState(false);

  // 卡片内部对话列表
  const [conv, setConv] = useState<CardMessage[]>(conversation || []);
  const initialConvLoaded = useRef(false);
  const [input, setInput] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const convEndRef = useRef<HTMLDivElement>(null);

  // 对话变更同步到全局仓库
  useEffect(() => {
    // 初次加载跳过，不触发保存
    if (!initialConvLoaded.current && conversation?.length === conv.length) {
      initialConvLoaded.current = true;
      return;
    }
    if (initialConvLoaded.current) {
      updateCard(id, { conversation: conv });
    } else {
      initialConvLoaded.current = true;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conv]);

  // 卡片缩放相关变量
  const cardRef = useRef<HTMLDivElement>(null);
  const explainRef = useRef<HTMLDivElement>(null);
  const [selectedInside, setSelectedInside] = useState("");
  const [toolbar, setToolbar] = useState<{ x: number; y: number } | null>(null);
  const [cardWidth, setCardWidth] = useState(card.width || 300);
  const [cardHeight, setCardHeight] = useState<number | null>(card.height || null);
  const resizeRef = useRef({ active: false, startX: 0, startY: 0, startW: 300, startH: 0, startPosX: 0 });

  // 卡片拖拽相关变量
  const dragRef = useRef({
    active: false,
    startX: 0,
    startY: 0,
    startBaseX: 0,
    startBaseY: 0,
  });
  // 拖拽临时偏移（仅组件局部state，不会触发全局所有卡片重渲染）
  const [dragOffset, setDragOffset] = useState({ dx: 0, dy: 0 });

  // 右下角缩放手柄事件
  const handleResizeDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const MIN_W = 200;
    const MIN_H = 200;
    const currentH = cardHeight ?? cardRef.current?.offsetHeight ?? 400;
    if (cardHeight === null) setCardHeight(currentH);
    const startPosX = card.pos_x || 0;
    resizeRef.current = {
      active: true,
      startX: e.clientX,
      startY: e.clientY,
      startW: cardWidth,
      startH: currentH,
      startPosX: startPosX,
    };

    const onMove = (ev: MouseEvent) => {
      if (!resizeRef.current.active) return;
      const dx = ev.clientX - resizeRef.current.startX;
      const dy = ev.clientY - resizeRef.current.startY;

      let newW = Math.round(resizeRef.current.startW - dx);
      if (newW < MIN_W) newW = MIN_W;
      const newPosX = Math.round(resizeRef.current.startPosX + (resizeRef.current.startW - newW));
      const newH = Math.max(MIN_H, Math.round(resizeRef.current.startH + dy));

      setCardWidth(newW);
      setCardHeight(newH);
      useExplainStore.setState((s) => ({
        cards: s.cards.map((c) => c.id === id ? { ...c, pos_x: newPosX } : c),
      }));
    };

    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      resizeRef.current.active = false;
      const finalW = cardRef.current?.offsetWidth || cardWidth;
      const finalH = cardRef.current?.offsetHeight || cardHeight || undefined;
      const finalPosX = Math.round(resizeRef.current.startPosX + (resizeRef.current.startW - finalW));
      updateCard(id, {
        width: finalW,
        height: finalH,
        pos_x: finalPosX,
      });
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [cardWidth, cardHeight, card.pos_x, id, updateCard]);

  // 头部拖动卡片事件
  const handleDragDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const baseX = pos_x ?? 0;
    const baseY = pos_y ?? 0;
    dragRef.current = {
      active: true,
      startX: e.clientX,
      startY: e.clientY,
      startBaseX: baseX,
      startBaseY: baseY,
    };
    document.body.style.userSelect = 'none';

    const onMove = (ev: MouseEvent) => {
      const dx = ev.clientX - dragRef.current.startX;
      const dy = ev.clientY - dragRef.current.startY;
      // 只更新局部state，仅当前卡片重渲染，全局store不动
      setDragOffset({ dx, dy });
    };

    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      document.body.style.userSelect = '';
      const { startBaseX, startBaseY } = dragRef.current;
      const finalX = startBaseX + dragOffset.dx;
      const finalY = startBaseY + dragOffset.dy;
      // 松手一次性落库
      updateCard(id, { pos_x: finalX, pos_y: finalY });
      // 清空偏移，卡片回归pos基准
      setDragOffset({ dx: 0, dy: 0 });
      dragRef.current.active = false;
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [id, pos_x, pos_y, updateCard, dragOffset]);

  // 卡片内选中文本，弹出工具栏定位
  const handleSel = useCallback(() => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !explainRef.current?.contains(sel.anchorNode)) {
      setToolbar(null); setSelectedInside(""); return;
    }
    const text = sel.toString().trim();
    if (text.length < 3) { setToolbar(null); setSelectedInside(""); return; }
    const r = sel.getRangeAt(0).getBoundingClientRect();
    const cr = cardRef.current?.getBoundingClientRect();
    if (!cr) { setToolbar(null); setSelectedInside(""); return; }
    let tx = Math.round(r.left + r.width / 2 - cr.left);
    let ty = Math.round(r.bottom + 4 - cr.top);
    const tw = 180;
    tx = Math.max(tw / 2 + 4, Math.min(tx, cardWidth - tw / 2 - 4));
    if (ty < 4) ty = 4;
    setSelectedInside(text);
    setToolbar({ x: tx, y: ty });
  }, [cardWidth]);

  // UI开关状态
  const [showFull, setShowFull] = useState(false);
  const [showVideos, setShowVideos] = useState(false);
  const [locMastery, setLocMastery] = useState<"unknown" | "learning" | "mastered">((mastery as any) || "unknown");

  // 页面初次加载拉取AI解释和相关视频
  useEffect(() => {
    if (!selected_text || exp) return;
    // 请求AI解释
    (async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/api/knowledge/explain`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: selected_text, node_id: context_node_id || undefined, style: "simple" }),
        });
        if (!res.ok) throw new Error();
        const d = await res.json();
        const e = d.explanation || d.content || "暂无解释";
        setExp(e);
        updateCard(id, { explanation: e });
      } catch { setExp("AI 解释暂不可用，可以在下方输入框提问。"); }
      finally { setLoading(false); }
    })();
    // 请求关联视频
    (async () => {
      setLoadingVideos(true);
      try {
        const res = await fetch(`${API_BASE}/api/search/media?q=${encodeURIComponent(selected_text.slice(0, 100))}&platforms=bilibili,youtube`);
        if (res.ok) { const d = await res.json(); if (d.results?.length) setVideos(d.results); }
      } catch { } finally { setLoadingVideos(false); }
    })();
  }, []);

  // 对话新增自动滚动到底部
  useEffect(() => { convEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [conv]);

  // 发送追问消息
  const sendInternal = useCallback(async (text: string) => {
    if (!text.trim() || aiLoading) return;
    const userMsg: CardMessage = { role: "user", content: text.trim() };
    setConv(prev => [...prev, userMsg]);
    setInput("");
    setAiLoading(true);

    try {
      const context = explanation ? exp : selected_text;
      const prompt = `上下文：${context}\n\n用户提问：${text}`;
      const res = await fetch(`${API_BASE}/api/knowledge/explain`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: prompt, node_id: context_node_id || undefined, style: "conversation" }),
      });
      if (!res.ok) throw new Error();
      const d = await res.json();
      const reply = d.explanation || d.content || "暂无法回答";
      setConv(prev => [...prev, { role: "assistant", content: reply }]);
    } catch {
      setConv(prev => [...prev, { role: "assistant", content: "AI 暂时无法回答，请稍后再试。" }]);
    } finally { setAiLoading(false); }
  }, [aiLoading, explanation, exp, selected_text, context_node_id]);

  // 快捷追问按钮配置
  const followUps = [
    { label: "再详细点", icon: <Sparkles size={10} />, prompt: "请详细解释一下" },
    { label: "换个角度", icon: <BookOpen size={10} />, prompt: "用另一个角度解释，比如类比" },
    { label: "举例说明", icon: <Lightbulb size={10} />, prompt: "请举一个具体例子" },
    { label: "做道题", icon: <Target size={10} />, prompt: "出一道关于这个的练习题" },
  ];

  // 选中文本新建子卡片，子卡片在父卡片右下偏移26px
  const mkChild = useCallback(() => {
    if (!selectedInside) return;
    createCard({
      conversation_id, message_id, depth: depth + 1, parent_card_id: id,
      selected_text: selectedInside,
      pos_x: (pos_x ?? 0) + 26,
      pos_y: (pos_y ?? 0) + 26,
      badge_x: 0, badge_y: 0,
    });
    setToolbar(null); setSelectedInside("");
    window.getSelection()?.removeAllRanges();
  }, [selectedInside, conversation_id, message_id, depth, id, createCard, pos_x, pos_y]);

  // 修改掌握状态
  const handleMastery = (m: "learning" | "mastered") => { setLocMastery(m); updateCard(id, { mastery: m }); };

  // 输入框回车发送
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendInternal(input); }
  };

  // 折叠状态直接不渲染卡片
  if (collapsed) {
    return null;
  }

  return (
    <div ref={cardRef} className={`rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] shadow-sm relative`}
      style={{
        width: cardWidth,
        height: cardHeight ?? undefined,
        overflow: cardHeight ? 'auto' : undefined,
        // 基准坐标 + 拖拽实时临时偏移
        transform: `translate(${(pos_x || 0) + dragOffset.dx}px,${(pos_y || 0) + dragOffset.dy}px)`,
        // 拖动时卡片置顶，防止被其他卡片挤压碰撞
        zIndex: dragRef.current.active ? 999 : 10 + depth
      }}>
      {/* 缩放手柄固定锚层，永久在卡片可视左下角 */}
      <div className="absolute inset-0 pointer-events-none">
        <div
          className="absolute bottom-0 left-0 w-5 h-5 flex items-end justify-start cursor-se-resize select-none text-[var(--color-text-muted)] hover:text-[var(--color-accent)] z-20 opacity-40 hover:opacity-100 transition-opacity pointer-events-auto"
          onMouseDown={handleResizeDown}
          title="拖动调整宽度和高度"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" className="pointer-events-none" fill="none">
            <path d="M1 2 L13 14" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
            <path d="M6 2 L12 8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
          </svg>
        </div>
      </div>

      {/* 顶部固定头部 */}
      <div className="sticky top-0 z-30 bg-[var(--color-surface)]">
        <div className={`h-1 bg-gradient-to-r ${dc.badge}`} />
        {/* 卡片拖动栏，绑定拖动事件 */}
        <div
          data-drag-handle="true"
          className="flex items-center gap-2 px-3 py-2 cursor-grab active:cursor-grabbing select-none border-b border-[var(--color-border)]/20"
          onMouseDown={handleDragDown}
        >
          <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold text-white bg-gradient-to-br ${dc.badge}`}>{depth}</span>
          <span className="text-xs font-medium text-[var(--color-text)] truncate flex-1">解释 &ldquo;{selected_text.slice(0, 28)}{selected_text.length > 28 ? "…" : ""}&rdquo;</span>
          <button onClick={() => toggleCollapse(id, true)}
            className="p-1 rounded hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] transition-colors"
            title="折叠">
            <X size={12} />
          </button>
        </div>
      </div>

      {/* AI解释内容区域 */}
      <div className="px-3 py-2.5 border-b border-[var(--color-border)]/20" ref={explainRef} onMouseUp={handleSel}>
        {loading ? (
          <div className="flex items-center gap-2 py-1"><Loader2 size={12} className="animate-spin text-indigo-500" /><span className="text-xs text-[var(--color-text-muted)]">解释中...</span></div>
        ) : (
          <div className="text-xs leading-relaxed text-[var(--color-text)] select-text">
            <div className={showFull ? "" : "max-h-24 overflow-hidden"}>
              <MarkdownRenderer content={exp} />
            </div>
            {!showFull && exp.length > 200 && <button onClick={() => setShowFull(true)} className="text-[10px] text-indigo-500 hover:underline mt-1">展开全部...</button>}
            {showFull && exp.length > 200 && <button onClick={() => setShowFull(false)} className="text-[10px] text-indigo-500 hover:underline mt-1">收起</button>}
          </div>
        )}
      </div>

      {/* 相关视频折叠面板 */}
      <div className="px-3 py-2 border-b border-[var(--color-border)]/20">
        <button onClick={() => setShowVideos(!showVideos)}
          className="flex items-center gap-1.5 text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors">
          {loadingVideos ? <Loader2 size={10} className="animate-spin" /> : <Video size={10} />}
          <span className="text-xs">{showVideos ? "收起视频" : "相关视频"}</span>
          {videos.length > 0 && !showVideos && <span className={`text-[8px] px-1.5 py-0.5 rounded-full bg-gradient-to-br ${dc.badge} text-white`}>{videos.length}</span>}
          {showVideos ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
        </button>
        {showVideos && (
          <div className="mt-1.5 space-y-1">
            {videos.length > 0 ? videos.map((v, i) => (
              <a key={i} href={v.url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-[var(--color-bg)]/50 hover:bg-[var(--color-bg)] transition-colors">
                <span className="text-[10px]">🎬</span>
                <span className="flex-1 text-[10px] text-[var(--color-text)] truncate">{v.title}</span>
                <ExternalLink size={8} className="text-[var(--color-text-muted)]" />
              </a>
            )) : <div className="text-[10px] text-[var(--color-text-muted)] py-1"><Search size={9} /> 搜索推荐中...</div>}
          </div>
        )}
      </div>

      {/* 历史对话列表 */}
      {(conv.length > 0) && (
        <div className="px-3 py-2 space-y-2 max-h-48 overflow-y-auto border-b border-[var(--color-border)]/20">
          {conv.map((m, i) => (
            <div key={i} className={`flex gap-2 ${m.role === "user" ? "" : ""}`}>
              <div className={`flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center ${m.role === "user" ? "bg-[var(--color-accent)]" : "bg-[var(--color-surface)] border border-[var(--color-border)]"}`}>
                {m.role === "user" ? <User size={8} className="text-white" /> : <Bot size={8} className={dc.accent} />}
              </div>
              <div className={`flex-1 text-[10px] leading-relaxed ${m.role === "user" ? "text-[var(--color-text)]" : "text-[var(--color-text-secondary)]"}`}>
                <MarkdownRenderer content={m.content} />
              </div>
            </div>
          ))}
          {aiLoading && (
            <div className="flex items-center gap-2 py-1">
              <Loader2 size={10} className="animate-spin text-indigo-500" />
              <span className="text-[10px] text-[var(--color-text-muted)]">思考中...</span>
            </div>
          )}
          <div ref={convEndRef} />
        </div>
      )}

      {/* 无对话时展示快捷提问按钮 */}
      {conv.length === 0 && (
        <div className="px-3 py-2 flex flex-wrap gap-1.5 border-b border-[var(--color-border)]/20">
          {followUps.map(f => (
            <button key={f.label} onClick={() => sendInternal(f.prompt)}
              className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[10px] font-medium bg-[var(--color-bg)] border border-[var(--color-border)]/60 text-[var(--color-text-secondary)] hover:bg-[var(--color-accent)]/8 hover:border-[var(--color-accent)]/25 hover:text-[var(--color-accent)] active:scale-[0.97] transition-all select-none">
              {f.icon}<span>{f.label}</span>
            </button>
          ))}
        </div>
      )}

      {/* 底部输入框区域 */}
      <div className="px-3 py-2 border-b border-[var(--color-border)]/20">
        <div className="flex items-center gap-1.5">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="追问..."
            disabled={aiLoading}
            className="flex-1 text-[11px] px-2.5 py-1.5 rounded-md bg-[var(--color-bg)] border border-[var(--color-border)] outline-none focus:border-[var(--color-accent)] placeholder:text-[var(--color-text-muted)] disabled:opacity-50"
          />
          <button onClick={() => sendInternal(input)} disabled={!input.trim() || aiLoading}
            className="p-1.5 rounded-md bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-40 transition-all flex-shrink-0">
            {aiLoading ? <Loader2 size={10} className="animate-spin" /> : <Send size={10} />}
          </button>
        </div>
        {conv.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-1.5">
            {followUps.map(f => (
              <button key={f.label} onClick={() => sendInternal(f.prompt)} disabled={aiLoading}
                className="flex items-center gap-1 px-2 py-1 rounded text-[9px] font-medium text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-accent)]/5 transition-colors disabled:opacity-40">
                {f.icon}<span>{f.label}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 掌握程度选择栏 */}
      <div className="flex items-center gap-2 px-3 py-2">
        <span className="text-[10px] text-[var(--color-text-muted)]">掌握</span>
        <button onClick={() => handleMastery("learning")}
          className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] transition-all ${locMastery === "learning" ? "bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400 font-medium" : "text-[var(--color-text-muted)] hover:text-amber-500"}`}>
          <BookMarked size={8} />学习中
        </button>
        <button onClick={() => handleMastery("mastered")}
          className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] transition-all ${locMastery === "mastered" ? "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400 font-medium" : "text-[var(--color-text-muted)] hover:text-emerald-500"}`}>
          <Star size={8} />已掌握
        </button>
        {conv.length > 0 && <span className="text-[9px] text-[var(--color-text-muted)] mr-2">{conv.length} 条对话</span>}
        <button onClick={() => deleteCard(id)}
          className="ml-auto p-1 rounded hover:bg-[var(--color-error)]/10 text-[var(--color-text-muted)] hover:text-[var(--color-error)] transition-colors"
          title="删除卡片">
          <Trash2 size={12} />
        </button>
      </div>

      {/* 选中文本弹出工具栏 */}
      {toolbar && selectedInside && (
        <div className="absolute z-50 flex items-center gap-1 px-2 py-1.5 rounded-lg bg-[var(--color-surface-elevated)] border border-[var(--color-border)] shadow-md"
          style={{ left: toolbar.x, top: toolbar.y, transform: "translateX(-50%)" }}>
          <span className="text-[10px] text-[var(--color-text-muted)] px-1">解释此段</span>
          <button onClick={mkChild}
            className="flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-semibold text-[var(--color-accent)] hover:bg-[var(--color-accent-soft)] active:scale-[0.97] transition-all">
            <Sparkles size={10} /><span>解释</span>
          </button>
          <button onClick={() => { navigator.clipboard.writeText(selectedInside); setToolbar(null); }}
            className="flex items-center gap-1 px-2 py-1 rounded-md text-[10px] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] active:scale-[0.97] transition-all">
            <Copy size={10} /><span>复制</span>
          </button>
        </div>
      )}
    </div>
  );
}