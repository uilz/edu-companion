"use client";

import React, { useEffect, useRef } from "react";
import { X, Pencil, Trash2, Loader2, Sparkles, Brain, MessageSquare, ChevronRight, BookOpen } from "lucide-react";
import type { GraphNode } from "@/lib/types/graph-types";
import { getMasteryColor, getTrendIcon } from "@/lib/types/graph-types";

interface FloatingNodeCardProps {
  node: GraphNode;
  partitionId: string;
  onClose: () => void;
  onNodeUpdated: () => void;
  onStartPractice?: (nodeId: string) => void;
  onRequestExplain?: (nodeId: string) => void;
  onFeynmanTeach?: (nodeId: string) => void;
  parentNode?: GraphNode | null;
  onNavigateToParent?: (node: GraphNode) => void;
}

export default function FloatingNodeCard({
  node, partitionId, onClose, onNodeUpdated,
  onStartPractice, onRequestExplain,
  onFeynmanTeach,
  parentNode, onNavigateToParent,
}: FloatingNodeCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const mColor = getMasteryColor(node.mastery);

  // 点击外部关闭
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const escHandler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    // 延迟添加，避免触发点击节点的冒泡
    const timer = setTimeout(() => {
      document.addEventListener("mousedown", handler);
      document.addEventListener("keydown", escHandler);
    }, 100);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("mousedown", handler);
      document.removeEventListener("keydown", escHandler);
    };
  }, [onClose]);

  return (
    <>
      {/* 半透明遮罩 */}
      <div className="fixed inset-0 z-40 bg-black/10" />

      {/* 浮动卡片 */}
      <div
        ref={ref}
        className="fixed z-50 top-1/2 right-8 -translate-y-1/2 w-72 max-h-[80vh] overflow-y-auto
          bg-surface-elevated border border rounded-xl shadow-2xl
          animate-in slide-in-from-right-4 fade-in duration-200"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border sticky top-0 bg-surface-elevated z-10">
          <div className="flex items-center gap-2 min-w-0">
            {parentNode && onNavigateToParent && (
              <button
                onClick={() => onNavigateToParent(parentNode)}
                className="flex items-center gap-0.5 text-[10px] text-muted hover:text-accent transition-colors shrink-0"
                title={`返回父节点: ${parentNode.label}`}
              >
                <ChevronRight size={12} className="rotate-180" />
              </button>
            )}
            <span className="text-xs font-medium text-muted truncate">节点详情</span>
          </div>
          <button onClick={onClose}
            className="p-1 rounded text-muted hover:text hover:bg-surface-hover shrink-0">
            <X size={14} />
          </button>
        </div>

        <div className="p-4 space-y-3">
          {/* 节点信息 */}
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: mColor }} />
              <h3 className="text-sm font-semibold text leading-tight">{node.label}</h3>
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-surface-hover text-muted ml-auto shrink-0">{node.level}</span>
            </div>
            {node.description && (
              <p className="text-[11px] text-secondary leading-relaxed line-clamp-3">{node.description}</p>
            )}
            <div className="flex items-center gap-3 mt-1.5 text-[10px] text-muted">
              <span>优先级: {"★".repeat(Math.min(node.priority, 5))}{"☆".repeat(Math.max(5 - node.priority, 0))}</span>
              <span>来源: {node.created_by === "user" ? "手动" : "AI"}</span>
            </div>
            {node.tags && node.tags.length > 0 && (
              <div className="flex items-center gap-1 mt-1.5 flex-wrap">
                {node.tags.map(tag => (
                  <span key={tag} className="text-[9px] px-1.5 py-0.5 rounded bg-accent/10 text-accent">{tag}</span>
                ))}
              </div>
            )}
          </div>

          {/* 掌握度 */}
          {node.mastery > 0 && (
            <div>
              <div className="flex items-center justify-between text-[10px] text-muted mb-1">
                <span>掌握度</span>
                <span style={{ color: mColor }}>{Math.round(node.mastery * 100)}% {getTrendIcon(node.trend)}</span>
              </div>
              <div className="h-1.5 rounded-full bg-surface-hover overflow-hidden">
                <div className="h-full rounded-full transition-all" style={{ width: `${node.mastery * 100}%`, backgroundColor: mColor }} />
              </div>
            </div>
          )}

          {/* 操作按钮 */}
          <div className="flex items-center gap-2 flex-wrap pt-1">
            {onRequestExplain && (
              <button onClick={() => onRequestExplain(node.id)}
                className="flex items-center gap-1 px-2.5 py-1.5 text-[10px] rounded-lg bg-accent/10 text-accent hover:bg-accent/20 transition-colors">
                <Brain size={10} />讲解
              </button>
            )}
            {onStartPractice && (
              <button onClick={() => onStartPractice(node.id)}
                className="flex items-center gap-1 px-2.5 py-1.5 text-[10px] rounded-lg bg-accent/10 text-accent hover:bg-accent/20 transition-colors">
                <MessageSquare size={10} />练习
              </button>
            )}
            {onFeynmanTeach && (
              <button onClick={() => onFeynmanTeach(node.id)}
                className="flex items-center gap-1 px-2.5 py-1.5 text-[10px] rounded-lg bg-success/10 text-success hover:bg-success/20 transition-colors"
                title="费曼学习法——我来给你讲讲">
                <BookOpen size={10} />讲给AI听
              </button>
            )}
            {onNavigateToParent && parentNode && (
              <button onClick={() => onNavigateToParent(parentNode)}
                className="flex items-center gap-1 px-2.5 py-1.5 text-[10px] rounded-lg border border text-secondary hover:border-accent hover:text-accent transition-colors">
                <ChevronRight size={10} className="rotate-180" />父节点
              </button>
            )}
          </div>

          {/* 关联会话 */}
          {node.conv_ids && node.conv_ids.length > 0 && (
            <div className="pt-2 border-t border">
              <span className="text-[10px] text-muted">关联 {node.conv_ids.length} 个会话</span>
            </div>
          )}
        </div>
      </div>
    </>
  );
}