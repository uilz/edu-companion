"use client";

import { useState } from "react";
import { Check, X, Clock, ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import type { DashboardPendingItem } from "@/lib/api/secretary-dashboard-api";

interface PendingItemCardProps {
  item: DashboardPendingItem;
  onAccept?: (item: DashboardPendingItem) => void;
  onDismiss?: (item: DashboardPendingItem) => void;
}

const KIND_LABELS: Record<string, string> = {
  proposal: "建议",
  confirmation: "计划确认",
  notification: "通知",
};

export default function PendingItemCard({
  item,
  onAccept,
  onDismiss,
}: PendingItemCardProps) {
  const [expanded, setExpanded] = useState(false);

  const borderColor =
    item.priority >= 4
      ? "border-l-red-500"
      : item.priority >= 3
        ? "border-l-yellow-400"
        : "border-l-blue-400";

  return (
    <div
      className={`rounded-lg border border-divider border-l-4 ${borderColor} bg-surface p-3 transition-shadow hover:shadow-sm`}
    >
      <div className="flex items-start gap-3">
        <span className="text-base leading-none mt-0.5">{item.emoji || "💡"}</span>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-sm font-medium text-ink-primary hover:text-accent transition-colors text-left"
            >
              {item.title}
            </button>
            <Badge variant={item.kind === "proposal" ? "accent" : item.kind === "confirmation" ? "success" : "default"}>
              {KIND_LABELS[item.kind] || item.kind}
            </Badge>
            {item.priority >= 4 && (
              <Badge variant="danger">高优</Badge>
            )}
          </div>

          {!expanded ? (
            <p className="text-xs text-ink-secondary mt-1 line-clamp-2">
              {item.description}
            </p>
          ) : (
            <div className="mt-2 space-y-2 text-xs text-ink-secondary">
              <p>{item.description}</p>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-ink-muted">
                <span>来源: {item.source}</span>
                <span>类型: {item.action_type}</span>
                <span>优先级: {item.priority}</span>
              </div>
            </div>
          )}

          <div className="flex gap-2 mt-2">
            <Button variant="primary" size="xs" onClick={() => onAccept?.(item)}>
              <Check size={10} />
              {item.kind === "confirmation" ? "加入计划" : "采纳"}
            </Button>
            {item.kind !== "notification" && (
              <Button variant="ghost" size="xs" onClick={() => onDismiss?.(item)}>
                <X size={10} />
                忽略
              </Button>
            )}
          </div>
        </div>

        <button
          onClick={() => setExpanded(!expanded)}
          className="flex-shrink-0 mt-0.5 text-ink-muted hover:text-ink-primary"
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
      </div>
    </div>
  );
}
