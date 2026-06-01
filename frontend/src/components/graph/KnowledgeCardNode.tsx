"use client";

import React, { useState } from "react";
import type { GraphNode, DialogueCardInfo } from "@/lib/graph-types";
import { getMasteryColor, getTrendIcon } from "@/lib/graph-types";
import {
  ChevronDown,
  ChevronUp,
  BookOpen,
  MessageSquare,
  Play,
  HelpCircle,
  CheckCircle,
  AlertCircle,
  StickyNote,
  Lightbulb,
  ExternalLink,
} from "lucide-react";

interface KnowledgeCardNodeProps {
  /** 选中的节点 */
  node: GraphNode;
  /** 关联对话卡片（模拟数据，待API对接） */
  relatedCards?: DialogueCardInfo[];
  /** 关联笔记 */
  relatedNotes?: { id: string; text: string; type: string }[];
  /** 关闭面板 */
  onClose?: () => void;
  /** 跳转到指定对话 */
  onJumpToCard?: (cardId: string) => void;
  /** 开始练习 */
  onStartPractice?: (nodeId: string) => void;
  /** 请求讲解 */
  onRequestExplain?: (nodeId: string) => void;
  /** 标记掌握 */
  onMarkMastered?: (nodeId: string) => void;
  /** 标记疑问 */
  onMarkQuestion?: (nodeId: string, question: string) => void;
}

/**
 * 右侧知识卡片详情面板（10.4）
 * 展开后显示节点详细信息、关联内容、操作入口。
 */
export default function KnowledgeCardNode({
  node,
  relatedCards = [],
  relatedNotes = [],
  onClose,
  onJumpToCard,
  onStartPractice,
  onRequestExplain,
  onMarkMastered,
  onMarkQuestion,
}: KnowledgeCardNodeProps) {
  const [showAllCards, setShowAllCards] = useState(false);
  const [showQuestionInput, setShowQuestionInput] = useState(false);
  const [question, setQuestion] = useState("");

  const masteryPct = Math.round(node.mastery * 100);
  const masteryColor = getMasteryColor(node.mastery);

  const visibleCards = showAllCards ? relatedCards : relatedCards.slice(0, 3);

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-sm overflow-hidden">
      {/* ----- Header: Node identity ----- */}
      <div className="p-4 pb-3 border-b border-[var(--color-border)]/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg">{node.emoji || "📘"}</span>
            <span className="text-base font-semibold text-[var(--color-text)]">
              {node.label}
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] uppercase tracking-wider">
              {node.level}
            </span>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
            >
              <ChevronDown size={14} />
            </button>
          )}
        </div>

        {/* Mastery bar */}
        <div className="mt-3 flex items-center gap-3">
          <div className="flex-1">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] text-[var(--color-text-muted)]">掌握度</span>
              <span className="text-[10px] font-medium" style={{ color: masteryColor }}>
                {masteryPct}%
              </span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-[var(--color-surface-hover)] overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700 ease-out"
                style={{
                  width: `${masteryPct}%`,
                  backgroundColor: masteryColor,
                }}
              />
            </div>
          </div>
          <span className="text-[11px] text-[var(--color-text-muted)]">
            趋势 {getTrendIcon(node.trend)}
          </span>
        </div>
      </div>

      {/* ----- Action buttons ----- */}
      <div className="px-3 py-2 border-b border-[var(--color-border)]/30 flex flex-wrap gap-1.5">
        <button
          onClick={() => onStartPractice?.(node.id)}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[11px] font-medium bg-[var(--color-accent)]/10 text-[var(--color-accent)] hover:bg-[var(--color-accent)]/20 transition-colors"
        >
          <Play size={12} />
          练习
        </button>
        <button
          onClick={() => onRequestExplain?.(node.id)}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[11px] font-medium bg-[var(--color-info)]/10 text-[var(--color-info)] hover:bg-[var(--color-info)]/20 transition-colors"
        >
          <HelpCircle size={12} />
          讲解
        </button>
        <button
          onClick={() => onMarkMastered?.(node.id)}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[11px] font-medium bg-[var(--color-success)]/10 text-[var(--color-success)] hover:bg-[var(--color-success)]/20 transition-colors"
        >
          <CheckCircle size={12} />
          已掌握
        </button>
        <button
          onClick={() => setShowQuestionInput(!showQuestionInput)}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[11px] font-medium bg-[var(--color-warning)]/10 text-[var(--color-warning)] hover:bg-[var(--color-warning)]/20 transition-colors"
        >
          <AlertCircle size={12} />
          有疑问
        </button>
      </div>

      {/* Question input (conditional) */}
      {showQuestionInput && (
        <div className="px-4 py-2 bg-[var(--color-warning)]/5 border-b border-[var(--color-border)]/30">
          <div className="flex gap-2">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="描述你的疑问..."
              className="flex-1 px-2.5 py-1.5 text-xs rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-warning)]"
              autoFocus
            />
            <button
              onClick={() => {
                if (question.trim()) {
                  onMarkQuestion?.(node.id, question.trim());
                  setQuestion("");
                  setShowQuestionInput(false);
                }
              }}
              disabled={!question.trim()}
              className="px-2.5 py-1.5 text-xs rounded-md bg-[var(--color-warning)] text-white hover:opacity-90 disabled:opacity-40"
            >
              提交
            </button>
          </div>
        </div>
      )}

      {/* ----- Related dialogue cards ----- */}
      <div className="px-4 py-3 border-b border-[var(--color-border)]/30">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5 text-[11px] font-medium text-[var(--color-text-muted)]">
            <MessageSquare size={12} />
            关联对话
            {relatedCards.length > 0 && (
              <span className="text-[10px] text-[var(--color-text-muted)] opacity-60">
                {relatedCards.length}
              </span>
            )}
          </div>
          {relatedCards.length > 3 && (
            <button
              onClick={() => setShowAllCards(!showAllCards)}
              className="flex items-center gap-0.5 text-[10px] text-[var(--color-accent)] hover:underline"
            >
              {showAllCards ? "收起" : "全部"}
              {showAllCards ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
            </button>
          )}
        </div>

        {visibleCards.length === 0 ? (
          <p className="text-[10px] text-[var(--color-text-muted)] py-2 text-center">
            暂无关联对话
          </p>
        ) : (
          <div className="space-y-1.5">
            {visibleCards.map((card) => (
              <button
                key={card.id}
                onClick={() => onJumpToCard?.(card.id)}
                className="w-full text-left p-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]/50 hover:border-[var(--color-accent)]/30 hover:bg-[var(--color-accent)]/5 transition-all group"
              >
                <div className="flex items-start gap-1.5">
                  <span className="text-[9px] px-1 py-0.5 rounded bg-[var(--color-accent)]/10 text-[var(--color-accent)] flex-shrink-0 mt-0.5">
                    Q
                  </span>
                  <p className="text-[11px] text-[var(--color-text)] line-clamp-1 group-hover:text-[var(--color-accent)] transition-colors">
                    {card.question}
                  </p>
                </div>
                <p className="text-[9px] text-[var(--color-text-muted)] mt-0.5 ml-5 line-clamp-1">
                  {card.summary}
                </p>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ----- Notes ----- */}
      <div className="px-4 py-3">
        <div className="flex items-center gap-1.5 mb-2">
          <StickyNote size={12} className="text-[var(--color-success)]" />
          <span className="text-[11px] font-medium text-[var(--color-text-muted)]">
            笔记与自我解释
          </span>
          {relatedNotes.length > 0 && (
            <span className="text-[10px] text-[var(--color-text-muted)] opacity-60">
              {relatedNotes.length}
            </span>
          )}
        </div>

        {relatedNotes.length === 0 ? (
          <p className="text-[10px] text-[var(--color-text-muted)] py-2 text-center">
            选中文本后点击「笔记」或「解释」添加
          </p>
        ) : (
          <div className="space-y-1.5">
            {relatedNotes.map((note) => (
              <div
                key={note.id}
                className="p-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]/50"
              >
                <div className="flex items-center gap-1 mb-0.5">
                  {note.type === "explain" ? (
                    <Lightbulb size={10} className="text-[var(--color-accent)]" />
                  ) : (
                    <StickyNote size={10} className="text-[var(--color-success)]" />
                  )}
                  <span className="text-[9px] text-[var(--color-text-muted)]">
                    {note.type === "explain" ? "自我解释" : "笔记"}
                  </span>
                </div>
                <p className="text-[10px] text-[var(--color-text)] leading-relaxed line-clamp-3">
                  {note.text}
                </p>
              </div>
            ))}
          </div>
        )}

        {/* External link */}
        <div className="mt-3 pt-2 border-t border-[var(--color-border)]/20">
          <button className="flex items-center gap-1 text-[10px] text-[var(--color-accent)] hover:underline">
            <ExternalLink size={10} />
            查看完整知识详情
          </button>
        </div>
      </div>
    </div>
  );
}
