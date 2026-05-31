"use client";

import React, { useState } from "react";
import { ChevronRight, MessageCircle } from "lucide-react";
import type { SubBranchInfo } from "@/types";

interface Props {
  messageId: string;
  subBranches: SubBranchInfo[];
  onEnter: (conversationId: string) => void;
}

export default function SubBranchInline({ messageId, subBranches, onEnter }: Props) {
  const [expanded, setExpanded] = useState(false);

  if (!subBranches || subBranches.length === 0) return null;

  return (
    <div className="mt-2 pt-2 border-t border-[var(--color-border)]">
      {/* Toggle header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-xs text-[var(--color-text-muted)]
                   hover:text-[var(--color-text-secondary)] transition-colors select-none"
      >
        <ChevronRight
          size={12}
          className={`transition-transform duration-200 ${expanded ? "rotate-90" : ""}`}
        />
        <span>{subBranches.length}个子支</span>
      </button>

      {/* Expanded list */}
      {expanded && (
        <div className="mt-1.5 space-y-1">
          {subBranches.map((sb) => (
            <button
              key={sb.conversation_id}
              onClick={() => onEnter(sb.conversation_id)}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-xs
                         text-left text-[var(--color-text-secondary)]
                         hover:bg-[var(--color-surface-hover)]
                         active:scale-[0.98] transition-all"
            >
              <MessageCircle size={12} className="shrink-0 text-[var(--color-text-muted)]" />
              <span className="flex-1 truncate">{sb.name || sb.quoted_text.slice(0, 30)}</span>
              <span className="shrink-0 text-[10px] text-[var(--color-text-muted)]">
                {sb.message_count}条
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
