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

export default function ToolCallBlock({ block }: ToolCallBlockProps) {
  // ask_question 工具默认展开
  const [expanded, setExpanded] = useState(block.tool_name === "ask_question");
  const label = displayName(block);
  const ico = icon(block);
  const hasResult = block.status === "done" && block.result_content && block.result_block_type;

  const shellCls =
    "my-2 rounded-xl border bg-white/60 dark:bg-zinc-800/60 backdrop-blur-sm transition-all duration-200";

  switch (block.status) {
    // ── Pending ──
    case "pending":
      return (
        <div className={`${shellCls} border-zinc-200/60 dark:border-zinc-700/60 px-4 py-3`}>
          <div className="flex items-center gap-3">
            <div className="w-5 h-5 rounded-full border-2 border-blue-400 border-t-transparent animate-spin shrink-0" />
            <span className="text-sm text-zinc-500 dark:text-zinc-400">
              正在准备 <span className="font-medium text-zinc-700 dark:text-zinc-200">{ico} {label}</span>
            </span>
          </div>
        </div>
      );

    // ── Running ──
    case "running":
      return (
        <div className={`${shellCls} border-blue-300/40 dark:border-blue-700/40 bg-blue-50/40 dark:bg-blue-950/30 px-4 py-3`}>
          <div className="flex items-center gap-3">
            <div className="w-5 h-5 rounded-full border-2 border-blue-500 border-t-transparent animate-spin shrink-0" />
            <span className="text-sm text-blue-700 dark:text-blue-300 font-medium">
              {ico} {label} 执行中...
            </span>
          </div>
        </div>
      );

    // ── Done ──
    case "done":
      return (
        <div className={`${shellCls} border-emerald-200/60 dark:border-emerald-800/60 overflow-hidden`}>
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-emerald-50/50 dark:hover:bg-emerald-950/20 transition-colors"
          >
            <span
              className={`text-xs transition-transform duration-200 ${expanded ? "rotate-90" : ""}`}
            >
              ▶
            </span>
            <span className="w-5 h-5 rounded-full bg-emerald-100 dark:bg-emerald-900/50 flex items-center justify-center shrink-0">
              <span className="text-[11px] text-emerald-600 dark:text-emerald-400">✓</span>
            </span>
            <span className="text-sm text-emerald-700 dark:text-emerald-300 font-medium">
              {ico} {label}{" "}
              <span className="text-xs text-emerald-500 dark:text-emerald-500 font-normal ml-1">
                完成
              </span>
            </span>
          </button>
          {hasResult && expanded && (
            <div className="border-t border-emerald-200/40 dark:border-emerald-800/40">
              <ResponseBlockRenderer
                block={{
                  id: block.tool_call_id,
                  message_id: "",
                  dir_id: block.dir_id || "",
                  conv_id: block.conv_id || "",
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

    // ── Error ──
    case "error":
      return (
        <div className={`${shellCls} border-red-200/60 dark:border-red-800/60 bg-red-50/40 dark:bg-red-950/20 px-4 py-3`}>
          <div className="flex items-center gap-3">
            <span className="w-5 h-5 rounded-full bg-red-100 dark:bg-red-900/50 flex items-center justify-center shrink-0">
              <span className="text-[11px] text-red-500">✕</span>
            </span>
            <div className="min-w-0">
              <span className="text-sm text-red-700 dark:text-red-300 font-medium">
                {ico} {label} 执行失败
              </span>
              {block.error && (
                <p className="text-xs text-red-500 dark:text-red-400 mt-0.5 truncate">
                  {block.error}
                </p>
              )}
            </div>
          </div>
        </div>
      );

    default:
      return null;
  }
}
