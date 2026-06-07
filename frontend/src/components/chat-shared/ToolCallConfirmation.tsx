"use client";

import type { ToolCallEvent } from "@/components/chat-shared/useChatStream";

interface ToolCallConfirmationProps {
  toolCall: ToolCallEvent;
  onAccept: () => void;
  onReject: () => void;
}

export default function ToolCallConfirmation({
  toolCall,
  onAccept,
  onReject,
}: ToolCallConfirmationProps) {
  return (
    <div className="p-3 rounded-lg border border-[var(--color-accent)]/30 bg-[var(--color-accent)]/5">
      <p className="text-xs text-[var(--color-text)] mb-2">
        {toolCall.confirmation_text || "确认执行此操作？"}
      </p>
      <div className="flex gap-2">
        <button
          onClick={onReject}
          className="flex-1 px-2 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
        >
          取消
        </button>
        <button
          onClick={onAccept}
          className="flex-1 px-2 py-1 text-xs rounded bg-[var(--color-accent)] text-white hover:opacity-90"
        >
          确认
        </button>
      </div>
    </div>
  );
}