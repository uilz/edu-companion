"use client";

import React, { useState, useEffect } from "react";
import type { ReasoningBlock } from "@/types";

interface ReasoningBlockProps {
  block: ReasoningBlock;
}

export default function ReasoningBlock({ block }: ReasoningBlockProps) {
  const [collapsed, setCollapsed] = useState(block.status === "done");

  // 思考完成时自动收起
  useEffect(() => {
    if (block.status === "done") {
      setCollapsed(true);
    }
  }, [block.status]);

  const isStreaming = block.status === "streaming";

  return (
    <div className="ai-tool-block">
      <button
        className="flex items-center gap-2 w-full text-left"
        onClick={() => setCollapsed(!collapsed)}
      >
        <span
          className={`inline-block w-1.5 h-1.5 rounded-full ${
            isStreaming
              ? "bg-[var(--color-accent)] animate-pulse"
              : "bg-[var(--color-ink-muted)]"
          }`}
        />
        <span className="text-xs text-[var(--color-ink-secondary)] font-medium">
          {isStreaming ? "思考中..." : "思考过程"}
        </span>
        <svg
          className={`w-3 h-3 text-[var(--color-ink-muted)] transition-transform ml-auto ${collapsed ? "" : "rotate-180"}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {!collapsed && block.text && (
        <div className="ai-tool-block-inner mt-1.5 text-[var(--color-ink-secondary)] whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto">
          {block.text}
          {isStreaming && (
            <span className="inline-block w-1.5 h-3.5 bg-[var(--color-accent)] animate-pulse ml-0.5 align-middle" />
          )}
        </div>
      )}
    </div>
  );
}
