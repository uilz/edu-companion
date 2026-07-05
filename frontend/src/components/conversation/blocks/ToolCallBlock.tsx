"use client";

import React, { useState } from "react";
import type { ToolBlock, ResponseBlock } from "@/types";
import ResponseBlockRenderer from "./ResponseBlockRenderer";
import { getToolDisplay } from "@/lib/tool-registry";

interface ToolCallBlockProps {
  block: ToolBlock;
}

function displayName(block: ToolBlock) {
  return block.display_name || getToolDisplay(block.tool_name).zh;
}
function icon(block: ToolBlock) {
  return block.icon || getToolDisplay(block.tool_name).icon;
}

// ── 状态色点（统一米色背景下的小色标）──
function StatusDot({ status }: { status: ToolBlock["status"] }) {
  if (status === "pending")
    return <span className="inline-block w-1.5 h-1.5 rounded-full bg-[var(--color-ink-muted)] animate-pulse" />;
  if (status === "running")
    return <span className="inline-block w-2 h-2 rounded-full border-2 border-[var(--color-accent)] border-t-transparent animate-spin" />;
  if (status === "done")
    return <span className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full bg-[var(--color-success)]/15 text-[var(--color-success)] text-[10px] font-bold">✓</span>;
  if (status === "error")
    return <span className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full bg-[var(--color-danger)]/15 text-[var(--color-danger)] text-[10px] font-bold">✕</span>;
  return null;
}

export default function ToolCallBlock({ block }: ToolCallBlockProps) {
  // ask_question 工具默认展开
  const [expanded, setExpanded] = useState(block.tool_name === "ask_question");
  const label = displayName(block);
  const ico = icon(block);
  const hasResult = block.status === "done" && block.result_content && block.result_block_type;

  // 错误态：保留红色提示背景，因为这是异常状态
  if (block.status === "error") {
    return (
      <div className="ai-tool-block" style={{ borderColor: 'var(--color-danger)', backgroundColor: 'var(--color-danger)/5' }}>
        <div className="flex items-center gap-2.5">
          <StatusDot status="error" />
          <span className="text-xs">{ico}</span>
          <span className="text-xs font-medium text-[var(--color-danger)]">
            {label} 执行失败
          </span>
        </div>
        {block.error && (
          <div className="ai-tool-block-inner mt-1.5 text-[var(--color-danger)] text-[11px]">
            {block.error}
          </div>
        )}
      </div>
    );
  }

  // running/pending 态：统一米色
  if (block.status === "pending" || block.status === "running") {
    return (
      <div className="ai-tool-block">
        <div className="flex items-center gap-2.5">
          <StatusDot status={block.status} />
          <span className="text-xs">{ico}</span>
          <span className="text-xs text-[var(--color-ink-secondary)]">
            <span className="font-medium text-[var(--color-ink-primary)]">{label}</span>{" "}
            {block.status === "running" ? "执行中..." : "准备中..."}
          </span>
        </div>
      </div>
    );
  }

  // done 态：可折叠
  return (
    <div className="ai-tool-block">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2.5 text-left hover:opacity-80 transition-opacity"
      >
        <StatusDot status="done" />
        <span className="text-xs">{ico}</span>
        <span className="text-xs font-medium text-[var(--color-ink-primary)] flex-1">
          {label}
        </span>
        <span className="text-[10px] text-[var(--color-ink-muted)]">完成</span>
        <svg
          className={`w-3 h-3 text-[var(--color-ink-muted)] transition-transform ${expanded ? "rotate-180" : ""}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {hasResult && expanded && (
        <div className="ai-tool-block-inner mt-1.5">
          <ResponseBlockRenderer
            block={{
              id: block.tool_call_id,
              message_id: "",
              dir_id: "",
              conv_id: "",
              type: block.result_block_type as ResponseBlock["type"],
              status: "ready",
              content: block.result_content || {},
              order: 0,
              created_at: 0,
              updated_at: 0,
            }}
          />
        </div>
      )}
    </div>
  );
}
