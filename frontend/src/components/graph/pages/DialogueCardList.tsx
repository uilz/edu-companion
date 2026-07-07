"use client";

import React from "react";
import type { GraphNode } from "@/lib/types/graph-types";
import { getMasteryColor, getTrendIcon } from "@/lib/types/graph-types";
import { MessageSquare, BookOpen, Lightbulb, Pencil } from "lucide-react";

interface DialogueCard {
  id: string;
  question: string;
  summary: string;
  knowledgeNodes: string[];
  timestamp: string;
}

interface DialogueCardListProps {
  cards: DialogueCard[];
  selectedNode?: GraphNode | null;
  onCardClick?: (card: DialogueCard) => void;
}

export default function DialogueCardList({
  cards,
  selectedNode,
  onCardClick,
}: DialogueCardListProps) {
  if (cards.length === 0) {
    return (
      <div className="p-6 text-center">
        {selectedNode ? (
          <div className="space-y-3">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-accent/10">
              <BookOpen size={20} className="text-accent" />
            </div>
            <p className="text-sm text-muted">
              开始学习 <span className="font-medium text">{selectedNode.label}</span>
            </p>
            <p className="text-xs text-muted">
              在下方输入你的问题，AI 会围绕这个知识点进行讲解
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-surface-hover">
              <MessageSquare size={20} className="text-muted" />
            </div>
            <p className="text-sm text-muted">
              选择右侧图谱中的知识点开始学习
            </p>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-2 p-2">
      {cards.map((card) => (
        <div
          key={card.id}
          onClick={() => onCardClick?.(card)}
          className="p-3 rounded-lg bg-surface border border hover:border-accent/30 hover:shadow-sm transition-all cursor-pointer"
        >
          {/* Question */}
          <div className="flex items-start gap-2">
            <span className="text-xs px-1.5 py-0.5 rounded bg-accent/10 text-accent font-medium flex-shrink-0 mt-0.5">
              Q
            </span>
            <p className="text-sm font-medium text line-clamp-2">
              {card.question}
            </p>
          </div>

          {/* Summary */}
          <p className="text-xs text-muted mt-1.5 ml-7 line-clamp-2">
            {card.summary}
          </p>

          {/* Knowledge tags */}
          {card.knowledgeNodes.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2 ml-7">
              {card.knowledgeNodes.map((node, i) => (
                <span
                  key={i}
                  className="text-[10px] px-1.5 py-0.5 rounded bg-surface-hover text-muted"
                >
                  {node}
                </span>
              ))}
            </div>
          )}

          {/* Timestamp */}
          <div className="text-[10px] text-muted mt-1.5 ml-7">
            {card.timestamp}
          </div>
        </div>
      ))}
    </div>
  );
}
