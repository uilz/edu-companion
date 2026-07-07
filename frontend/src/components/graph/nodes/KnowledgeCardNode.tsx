"use client";

import React, { useState, useEffect } from "react";
import type { GraphNode, DialogueCardInfo } from "@/lib/types/graph-types";
import { getMasteryColor, getTrendIcon } from "@/lib/types/graph-types";
import {
  ChevronDown, ChevronUp, BookOpen, MessageSquare, Play,
  HelpCircle, CheckCircle, AlertCircle, StickyNote, Lightbulb,
  ExternalLink, Youtube, BarChart3, ListTree, X, Brain,
} from "lucide-react";
import { authedFetch } from "@/lib/api/api";
import CardResources from "./../panels/CardResources";

interface Props {
  node: GraphNode;
  relatedCards?: DialogueCardInfo[];
  relatedNotes?: { id: string; text: string; type: string }[];
  onClose?: () => void;
  onJumpToCard?: (cardId: string) => void;
  onStartPractice?: (nodeId: string) => void;
  onRequestExplain?: (nodeId: string) => void;
  onMarkMastered?: (nodeId: string) => void;
  onMarkQuestion?: (nodeId: string, question: string) => void;
  childNodes?: GraphNode[];
}

type CardSection = "overview" | "conversations" | "practice" | "resources";

export default function KnowledgeCardNode({
  node, relatedCards = [], relatedNotes = [], onClose, onJumpToCard,
  onStartPractice, onRequestExplain, onMarkMastered, onMarkQuestion, childNodes = [],
}: Props) {
  const [section, setSection] = useState<CardSection>("overview");
  const [showAllCards, setShowAllCards] = useState(false);
  const [showQuestionInput, setShowQuestionInput] = useState(false);
  const [question, setQuestion] = useState("");
  const [bbResults, setBbResults] = useState<any[]>([]);
  const [bbLoading, setBbLoading] = useState(false);
  const [bbError, setBbError] = useState<string | null>(null);

  const masteryPct = Math.round(node.mastery * 100);
  const masteryColor = getMasteryColor(node.mastery);
  const visibleCards = showAllCards ? relatedCards : relatedCards.slice(0, 3);
  const isTopicLevel = node.level === "topic";
  const isDomainLevel = node.level === "domain";
  const isPartitionLevel = node.level === "partition";

  const searchBilibili = async () => {
    if (!node.label) return;
    setBbLoading(true);
    setBbError(null);
    try {
      const res = await authedFetch(`/api/search/bilibili?q=${encodeURIComponent(node.label + " 讲解")}`, { signal: AbortSignal.timeout(8000) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setBbResults(data.results || data.data || []);
    } catch (e: any) {
      if (e.name !== "AbortError") setBbError("搜索失败");
      setBbResults([]);
    } finally {
      setBbLoading(false);
    }
  };

  useEffect(() => {
    if (section === "resources" && bbResults.length === 0 && !bbLoading) searchBilibili();
  }, [section]);

  const practiceStats = { total: 24, correct: 16, accuracy: Math.round(16 / 24 * 100), streak: 3 };

  return (
    <div className="h-full overflow-y-auto border-l border bg-surface">
      {/* ── Header ── */}
      <div className="sticky top-0 z-10 bg-surface border-b border">
        <div className="p-4 pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-lg flex-shrink-0">{node.emoji || "📘"}</span>
              <span className="text-sm font-semibold text truncate">{node.label}</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-hover text-muted uppercase tracking-wider flex-shrink-0">{node.level}</span>
            </div>
            {onClose && (
              <button onClick={onClose} className="p-1 rounded hover:bg-surface-hover text-muted hover:text transition-colors flex-shrink-0">
                <X size={14} />
              </button>
            )}
          </div>

          <div className="mt-3 flex items-center gap-3">
            <div className="flex-1">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-muted">掌握度</span>
                <span className="text-[10px] font-medium" style={{ color: masteryColor }}>{masteryPct}%</span>
              </div>
              <div className="w-full h-1.5 rounded-full bg-surface-hover overflow-hidden">
                <div className="h-full rounded-full transition-all duration-700 ease-out" style={{ width: `${masteryPct}%`, backgroundColor: masteryColor }} />
              </div>
            </div>
            <span className="text-[11px] text-muted flex-shrink-0">趋势 {getTrendIcon(node.trend)}</span>
          </div>

          {isPartitionLevel && <p className="mt-2 text-[10px] text-muted">分区 · {childNodes.length} 个领域 · 整体掌握度概览</p>}
          {isDomainLevel && <p className="mt-2 text-[10px] text-muted">领域 · {childNodes.length} 个专题</p>}
          {isTopicLevel && childNodes.length > 0 && <p className="mt-2 text-[10px] text-muted">专题 · {childNodes.length} 个知识点</p>}
        </div>

        <div className="px-3 pb-3 flex flex-wrap gap-1.5">
          <button onClick={() => onStartPractice?.(node.id)}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[11px] font-medium bg-accent/10 text-accent hover:bg-accent/20 transition-colors">
            <Play size={12} />练习</button>
          <button onClick={() => onRequestExplain?.(node.id)}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[11px] font-medium bg-info/10 text-info hover:bg-info/20 transition-colors">
            <HelpCircle size={12} />AI讲解</button>
          <button onClick={() => onMarkMastered?.(node.id)}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[11px] font-medium bg-success/10 text-success hover:bg-success/20 transition-colors">
            <CheckCircle size={12} />已掌握</button>
          <button onClick={() => setShowQuestionInput(!showQuestionInput)}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[11px] font-medium bg-warning/10 text-warning hover:bg-warning/20 transition-colors">
            <AlertCircle size={12} />有疑问</button>
        </div>

        {showQuestionInput && (
          <div className="px-3 pb-3 bg-warning/5 border-t border/30 pt-2">
            <div className="flex gap-2">
              <input value={question} onChange={(e) => setQuestion(e.target.value)}
                placeholder="描述你的疑问..."
                className="flex-1 px-2.5 py-1.5 text-xs rounded-md border border bg-page focus:outline-none focus:border-warning" autoFocus />
              <button onClick={() => { if (question.trim()) { onMarkQuestion?.(node.id, question.trim()); setQuestion(""); setShowQuestionInput(false); } }}
                disabled={!question.trim()}
                className="px-2.5 py-1.5 text-xs rounded-md bg-warning text-white hover:opacity-90 disabled:opacity-40">提交</button>
            </div>
          </div>
        )}
      </div>

      {/* ── Section tabs ── */}
      <div className="flex border-b border px-2">
        {[
          { key: "overview", label: "概览", icon: <BarChart3 size={12} /> },
          { key: "conversations", label: "对话", icon: <MessageSquare size={12} />, badge: relatedCards.length },
          { key: "practice", label: "练习", icon: <Play size={12} />, badge: practiceStats.total },
          { key: "resources", label: "资源", icon: <Youtube size={12} /> },
        ].map((tab) => (
          <button key={tab.key} onClick={() => setSection(tab.key as CardSection)}
            className={`flex items-center gap-1 px-3 py-2 text-[11px] font-medium border-b-2 transition-colors ${
              section === tab.key ? "text-accent border-accent" : "text-muted border-transparent hover:text"
            }`}>
            {tab.icon}{tab.label}
            {tab.badge != null && tab.badge > 0 && <span className="text-[9px] px-1 py-0.5 rounded-full bg-surface-hover">{tab.badge}</span>}
          </button>
        ))}
      </div>

      {/* ── Section content ── */}
      <div className="p-3 space-y-4">
        {/* 概览 */}
        {section === "overview" && (
          <>
            {childNodes.length > 0 && (
              <div>
                <div className="flex items-center gap-1.5 mb-2">
                  <ListTree size={12} className="text-muted" />
                  <span className="text-[11px] font-medium text-muted">{isTopicLevel ? "知识点" : isDomainLevel ? "专题" : "领域"}</span>
                  <span className="text-[10px] text-muted opacity-60">{childNodes.length}</span>
                </div>
                <div className="space-y-1">
                  {childNodes.map((child) => (
                    <div key={child.id} className="flex items-center gap-2 p-1.5 rounded-md hover:bg-surface-hover cursor-pointer transition-colors">
                      <span>{child.emoji || "•"}</span>
                      <span className="text-[11px] text flex-1 truncate">{child.label}</span>
                      <div className="w-12 h-1 rounded-full bg-surface-hover overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${Math.round(child.mastery * 100)}%`, backgroundColor: getMasteryColor(child.mastery) }} />
                      </div>
                      <span className="text-[9px] text-muted w-7 text-right">{Math.round(child.mastery * 100)}%</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <BarChart3 size={12} className="text-muted" />
                <span className="text-[11px] font-medium text-muted">练习统计</span>
              </div>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { label: "总题数", value: practiceStats.total, color: "text" },
                  { label: "正确率", value: `${practiceStats.accuracy}%`, color: "text-success" },
                  { label: "连续正确", value: practiceStats.streak, color: "text-accent" },
                ].map((s) => (
                  <div key={s.label} className="p-2 rounded-lg bg-page border border/50 text-center">
                    <span className={`text-base font-semibold ${s.color}`}>{s.value}</span>
                    <p className="text-[9px] text-muted mt-0.5">{s.label}</p>
                  </div>
                ))}
              </div>
            </div>

            {relatedNotes.length > 0 && (
              <div>
                <div className="flex items-center gap-1.5 mb-2">
                  <StickyNote size={12} className="text-success" />
                  <span className="text-[11px] font-medium text-muted">最近笔记</span>
                  <span className="text-[10px] text-muted opacity-60">{relatedNotes.length}</span>
                </div>
                <div className="space-y-1.5">
                  {relatedNotes.slice(0, 2).map((note) => (
                    <div key={note.id} className="p-2 rounded-lg bg-page border border/50">
                      <div className="flex items-center gap-1 mb-0.5">
                        {note.type === "explain" ? <Lightbulb size={10} className="text-accent" />
                          : note.type === "reflect" ? <Brain size={10} className="text-accent" />
                          : <StickyNote size={10} className="text-success" />}
                        <span className="text-[9px] text-muted">{note.type === "explain" ? "自我解释" : note.type === "reflect" ? "反思" : "笔记"}</span>
                      </div>
                      <p className="text-[10px] text leading-relaxed line-clamp-2">{note.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {childNodes.length === 0 && relatedNotes.length === 0 && (
              <p className="text-[10px] text-muted text-center py-6">暂无详细数据，开始学习来填充内容</p>
            )}
          </>
        )}

        {/* 关联对话 */}
        {section === "conversations" && (
          <div>
            {visibleCards.length === 0 ? (
              <p className="text-[10px] text-muted text-center py-6">暂无关联对话</p>
            ) : (
              <div className="space-y-1.5">
                {visibleCards.map((card) => (
                  <button key={card.id} onClick={() => onJumpToCard?.(card.id)}
                    className="w-full text-left p-2 rounded-lg bg-page border border/50 hover:border-accent/30 hover:bg-accent/5 transition-all group">
                    <div className="flex items-start gap-1.5">
                      <span className="text-[9px] px-1 py-0.5 rounded bg-accent/10 text-accent flex-shrink-0 mt-0.5">Q</span>
                      <p className="text-[11px] text line-clamp-1 group-hover:text-accent">{card.question}</p>
                    </div>
                    <p className="text-[9px] text-muted mt-0.5 ml-5 line-clamp-1">{card.summary}</p>
                  </button>
                ))}
              </div>
            )}
            {relatedCards.length > 3 && (
              <button onClick={() => setShowAllCards(!showAllCards)} className="flex items-center gap-1 mt-2 text-[10px] text-accent hover:underline mx-auto">
                {showAllCards ? "收起" : `全部 ${relatedCards.length} 条`}{showAllCards ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
              </button>
            )}
          </div>
        )}

        {/* 练习 */}
        {section === "practice" && (
          <div>
            <div className="grid grid-cols-3 gap-2 mb-3">
              {[
                { label: "总题数", value: practiceStats.total, color: "text" },
                { label: "正确率", value: `${practiceStats.accuracy}%`, color: "text-success" },
                { label: "连续正确", value: practiceStats.streak, color: "text" },
              ].map((s) => (
                <div key={s.label} className="p-2 rounded-lg bg-page border border/50 text-center">
                  <span className={`text-base font-semibold ${s.color}`}>{s.value}</span>
                  <p className="text-[9px] text-muted mt-0.5">{s.label}</p>
                </div>
              ))}
            </div>
            <div className="p-3 rounded-lg bg-page border border/50">
              <p className="text-[10px] text-muted text-center">练习记录正在对接中，后续将展示详细错题集</p>
            </div>
            <button onClick={() => onStartPractice?.(node.id)}
              className="w-full mt-3 flex items-center justify-center gap-1 px-3 py-2 rounded-lg bg-accent text-white text-xs font-medium hover:opacity-90 transition-opacity">
              <Play size={12} />开始新练习
            </button>
          </div>
        )}

        {/* B站资源 */}
        {section === "resources" && (
          <CardResources nodeLabel={node.label} results={bbResults} loading={bbLoading} error={bbError} onSearch={searchBilibili} />
        )}
      </div>

      {/* ── Footer ── */}
      <div className="p-3 border-t border/50">
        <button className="flex items-center gap-1 text-[10px] text-accent hover:underline">
          <ExternalLink size={10} />查看完整知识详情
        </button>
      </div>
    </div>
  );
}
