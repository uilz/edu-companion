"use client";

import React, { useCallback, useEffect, useState, useRef } from "react";
import { Tag, Plus, Loader2, Check } from "lucide-react";
import { v2 } from "@/lib/api/api";

interface CandidateNode {
  id: string;
  label: string;
  score: number;
}

interface CognitiveTagProps {
  messageId: string;
  messageText: string;
  initialNodeIds?: string[];
}

export default function CognitiveTag({ messageId, messageText, initialNodeIds }: CognitiveTagProps) {
  const [confirmedIds, setConfirmedIds] = useState<string[]>(initialNodeIds || []);
  const [candidates, setCandidates] = useState<CandidateNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [showPanel, setShowPanel] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  // 外部 initialNodeIds 更新时同步
  useEffect(() => {
    setConfirmedIds(initialNodeIds || []);
  }, [initialNodeIds]);

  // 点击外部关闭面板
  useEffect(() => {
    if (!showPanel) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setShowPanel(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showPanel]);

  const handleClassify = useCallback(async () => {
    setLoading(true);
    try {
      const result = await v2<{ candidates: CandidateNode[] }>("/classify", {
        method: "POST",
        body: JSON.stringify({ conversation_id: "", message: messageText }),
      });
      setCandidates(result.candidates || []);
      setShowPanel(true);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [messageText]);

  const handleConfirm = useCallback(async (nodeId: string) => {
    const newIds = confirmedIds.includes(nodeId)
      ? confirmedIds.filter((id) => id !== nodeId)
      : [...confirmedIds, nodeId];

    try {
      await v2(`/messages/${messageId}/cognitive-confirm`, {
        method: "POST",
        body: JSON.stringify({ cognitive_node_ids: newIds }),
      });
      setConfirmedIds(newIds);
      // 关闭候选面板
      setShowPanel(false);
    } catch {
      // silent
    }
  }, [messageId, confirmedIds]);

  // 获取已确认节点的 label
  const [nodeLabels, setNodeLabels] = useState<Record<string, string>>({});
  useEffect(() => {
    if (confirmedIds.length === 0) return;
    // 从 candidates 中查找 label
    const labels: Record<string, string> = {};
    for (const c of candidates) {
      if (confirmedIds.includes(c.id)) {
        labels[c.id] = c.label;
      }
    }
    // 暂未取到的留空
    setNodeLabels(labels);
  }, [confirmedIds, candidates]);

  if (confirmedIds.length === 0 && !showPanel) {
    return (
      <div className="mt-1.5 flex items-center gap-1">
        <button
          onClick={handleClassify}
          disabled={loading}
          className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] rounded
            text-[var(--color-text-muted)] hover:text-[var(--color-info)]
            border border-[var(--color-border)] hover:border-[var(--color-info)]
            transition-colors disabled:opacity-50"
          title="认知分类"
        >
          {loading ? <Loader2 size={10} className="animate-spin" /> : <Plus size={10} />}
          分类
        </button>
      </div>
    );
  }

  return (
    <div ref={panelRef} className="mt-1.5">
      {/* 已确认的标签 */}
      {confirmedIds.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-1">
          {confirmedIds.map((id) => (
            <span
              key={id}
              className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px]
                bg-[var(--color-accent)]/10 text-[var(--color-accent)]
                border border-[var(--color-accent)]/20"
            >
              <Tag size={9} />
              {nodeLabels[id] || id.slice(0, 8)}
              <button
                onClick={() => handleConfirm(id)}
                className="ml-0.5 hover:text-[var(--color-error)]"
                title="移除"
              >
                ×
              </button>
            </span>
          ))}
          <button
            onClick={handleClassify}
            disabled={loading}
            className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px]
              text-[var(--color-text-muted)] hover:text-[var(--color-info)]
              border border-dashed border-[var(--color-border)] hover:border-[var(--color-info)]
              transition-colors disabled:opacity-50"
            title="添加分类"
          >
            {loading ? <Loader2 size={9} className="animate-spin" /> : <Plus size={9} />}
          </button>
        </div>
      )}

      {/* 候选面板 */}
      {showPanel && candidates.length > 0 && (
        <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-2 shadow-lg">
          <div className="text-[10px] text-[var(--color-text-muted)] mb-1">推荐分类：</div>
          <div className="flex flex-wrap gap-1">
            {candidates.map((c) => {
              const isConfirmed = confirmedIds.includes(c.id);
              return (
                <button
                  key={c.id}
                  onClick={() => handleConfirm(c.id)}
                  className={`inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] transition-colors ${
                    isConfirmed
                      ? "bg-[var(--color-accent)] text-white"
                      : "bg-[var(--color-surface-hover)] text-[var(--color-text)] hover:bg-[var(--color-accent)]/10 hover:text-[var(--color-accent)]"
                  }`}
                >
                  {c.label}
                  <span className="text-[9px] opacity-60">{Math.round(c.score * 100)}%</span>
                  {isConfirmed && <Check size={10} />}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* 无候选 */}
      {showPanel && candidates.length === 0 && !loading && (
        <div className="text-[10px] text-[var(--color-text-muted)]">暂无推荐分类</div>
      )}
    </div>
  );
}
