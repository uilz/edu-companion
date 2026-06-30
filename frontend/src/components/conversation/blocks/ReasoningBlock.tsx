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

  return (
    <div className="mb-2 rounded-lg bg-amber-500/5 border border-amber-500/20 overflow-hidden">
      <button
        className="flex items-center gap-2 w-full py-1.5 px-3 text-left"
        onClick={() => setCollapsed(!collapsed)}
      >
        <span className="text-xs text-amber-600 dark:text-amber-400">
          {block.status === "streaming" ? "🤔 思考中..." : "💡 思考过程"}
        </span>
        <svg
          className={`w-3 h-3 text-amber-500 transition-transform ${collapsed ? "" : "rotate-180"}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
        {block.status === "streaming" && (
          <div className="w-3 h-3 rounded-full border-2 border-amber-500 border-t-transparent animate-spin ml-auto" />
        )}
      </button>
      {!collapsed && block.text && (
        <div className="px-3 pb-2 text-xs text-[var(--color-text-secondary)] whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto">
          {block.text}
          {block.status === "streaming" && <span className="inline-block w-1.5 h-3.5 bg-amber-500 animate-pulse ml-0.5 align-middle" />}
        </div>
      )}
    </div>
  );
}
