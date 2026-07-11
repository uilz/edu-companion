"use client";

import { useState } from "react";
import { Check, X, Clock, ChevronDown, ChevronRight, AlertCircle } from "lucide-react";
import type { PlanItemConfirmation } from "@/hooks/planning/usePlanning";

interface Props {
  confirmations: PlanItemConfirmation[];
  busyId: string | null;
  onAccept: (id: string) => void;
  onDismiss: (id: string) => void;
}

const SOURCE_LABELS: Record<string, string> = {
  secretary: "秘书引擎",
  practice: "练习系统",
  planning: "规划系统",
  flashcard: "卡片系统",
  reading: "阅读系统",
};

export default function PlanItemConfirmationPool({
  confirmations,
  busyId,
  onAccept,
  onDismiss,
}: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (confirmations.length === 0) return null;

  return (
    <div className="rounded-xl border border bg-surface p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text flex items-center gap-2">
          <AlertCircle size={14} className="text-warning" />
          待确认计划项
          <span className="text-xs font-normal text-muted">({confirmations.length})</span>
        </h2>
      </div>

      <div className="space-y-2">
        {confirmations.map((c) => (
          <ConfirmationCard
            key={c.id}
            item={c}
            expanded={expandedId === c.id}
            busy={busyId === c.id}
            onToggle={() => setExpandedId(expandedId === c.id ? null : c.id)}
            onAccept={() => onAccept(c.id)}
            onDismiss={() => onDismiss(c.id)}
          />
        ))}
      </div>
    </div>
  );
}

interface ConfirmationCardProps {
  item: PlanItemConfirmation;
  expanded: boolean;
  busy: boolean;
  onToggle: () => void;
  onAccept: () => void;
  onDismiss: () => void;
}

function ConfirmationCard({ item, expanded, busy, onToggle, onAccept, onDismiss }: ConfirmationCardProps) {
  const borderColor =
    item.priority >= 4 ? "border-l-red-500" : item.priority >= 3 ? "border-l-yellow-400" : "border-l-blue-400";

  return (
    <div className={`rounded-lg border border-l-4 ${borderColor} bg-page p-3`}>
      <div className="flex items-start gap-2">
        <span className="text-base leading-none mt-0.5">{(item.metadata?.emoji as string) || "⏳"}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <button
              onClick={onToggle}
              className="text-sm font-medium text hover:text-accent transition-colors text-left"
            >
              {item.title}
            </button>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-hover text-muted">
              {SOURCE_LABELS[item.source_module] || item.source_module}
            </span>
            {item.priority >= 4 && (
              <span className="text-[10px] px-1 rounded bg-danger/10 text-danger">高优</span>
            )}
          </div>

          {!expanded && item.description && (
            <div className="text-xs text-muted mt-0.5 line-clamp-1">{item.description}</div>
          )}

          {expanded && (
            <div className="mt-2 space-y-1.5 text-xs">
              {item.description && <p className="text-secondary">{item.description}</p>}
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-muted">
                <span className="flex items-center gap-1"><Clock size={10} /> {item.estimated_minutes} min</span>
                <span>优先级: {item.priority}</span>
                {item.proposed_scheduled_for && (
                  <span>建议时间: {new Date(item.proposed_scheduled_for).toLocaleString("zh-CN")}</span>
                )}
              </div>
            </div>
          )}

          <div className="flex gap-1.5 mt-2 flex-wrap">
            <button
              onClick={onAccept}
              disabled={busy}
              className="inline-flex items-center gap-1 px-2 py-1 text-[10px] font-medium bg-success text-white rounded hover:opacity-90 active:scale-[0.97] transition-all disabled:opacity-50"
            >
              <Check size={10} />{busy ? "处理中…" : "加入计划"}
            </button>
            <button
              onClick={onDismiss}
              disabled={busy}
              className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-muted hover:text bg-surface rounded border border hover:border-text-muted transition-colors disabled:opacity-50"
            >
              <X size={10} />忽略
            </button>
          </div>
        </div>

        <button
          onClick={onToggle}
          className="flex-shrink-0 mt-0.5 text-muted hover:text-muted transition-colors"
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
      </div>
    </div>
  );
}
