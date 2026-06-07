"use client";

import React, { useState } from "react";
import { X } from "lucide-react";
import type { GraphNode } from "@/lib/types/graph-types";
import TreeChatPanel from "@/components/graph/panels/TreeChatPanel";
import type { DialogState } from "./KnowledgeTreePage";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface DialogContainerProps {
  dialogState: DialogState | null;
  onDialogStateChange: (s: DialogState | null) => void;
  partitionId: string;
  selectedNode: GraphNode | null;
  onNodeUpdated: () => void;
  width: number;
  onWidthChange: (width: number) => void;
}

export default function DialogContainer({
  dialogState, onDialogStateChange, partitionId, selectedNode, onNodeUpdated, width, onWidthChange,
}: DialogContainerProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [globalInput, setGlobalInput] = useState("");

  if (collapsed) {
    return (
      <div className="flex-shrink-0 w-[40px] bg-[var(--color-surface)] border-r border-[var(--color-border)] flex flex-col items-center pt-3 gap-2">
        <button onClick={() => setCollapsed(false)}
          className="p-2 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
          title="展开对话面板">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/>
          </svg>
        </button>
        <div className="w-4 h-px bg-[var(--color-border)] rotate-90" />
        <span className="text-[9px] text-[var(--color-text-muted)] writing-mode-vertical" style={{ writingMode: "vertical-rl" }}>对话</span>
      </div>
    );
  }

  const isNodeMode = dialogState?.type === "tree_exploration" && dialogState.boundNode;
  const isTemporary = dialogState?.type === "temporary";
  const isGlobal = dialogState && !isNodeMode && !isTemporary;

  const toggleMode = () => {
    if (isNodeMode) {
      // 切换到全局
      onDialogStateChange({
        type: "tree_exploration",
        conversationId: "",
        parentId: partitionId,
        parentType: "partition",
        boundNode: null,
      });
    } else if (selectedNode) {
      // 切换到节点探索
      onDialogStateChange({
        type: "tree_exploration",
        conversationId: "",
        parentId: partitionId,
        parentType: "partition",
        boundNode: selectedNode,
      });
    } else if (isTemporary) {
      onDialogStateChange(null);
    } else {
      onDialogStateChange(null);
    }
  };

  const handleGlobalSend = async () => {
    if (!globalInput.trim() || !dialogState) return;
    // 对全局/临时对话发送消息（实验性：先存消息到后端）
    try {
      await fetch(`${API_BASE}/api/conversations/tree/conversation/${dialogState.conversationId}/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: globalInput.trim(),
          partition_id: partitionId,
        }),
      });
    } catch {
      // fallback 静默
    }
    setGlobalInput("");
  };

  return (
    <div className="flex-shrink-0 bg-[var(--color-surface)] border-r border-[var(--color-border)] flex flex-col overflow-hidden"
      style={{ width: `${width}px` }}>
      {/* 头部 */}
      <div className="flex items-center gap-2 px-3 py-2.5 border-b border-[var(--color-border)] flex-shrink-0">
        <div className="w-7 h-7 rounded-full bg-[var(--color-accent)]/10 flex items-center justify-center">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-[var(--color-accent)]">
            <rect x="6" y="6" width="14" height="14" rx="3"/><circle cx="14" cy="10" r="1.5"/><path d="M10 14c0-1.5 2-2.5 4-2.5s4 1 4 2.5"/>
          </svg>
        </div>
        <span className="text-xs font-medium text-[var(--color-text)] flex-1">
          {isTemporary ? "临时对话" : isNodeMode ? "节点探索" : "知识树对话"}
        </span>

        {/* 模式切换 */}
        <button onClick={toggleMode}
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold transition-all ${
            isNodeMode
              ? "bg-[var(--color-warning)]/10 text-[var(--color-warning)]"
              : isTemporary
                ? "bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                : "bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
          }`}>
          {isNodeMode ? "📍 节点" : isTemporary ? "💬 临时" : "🌐 全局"}
        </button>

        <button onClick={() => setCollapsed(true)}
          className="p-1 rounded text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors">
          <X size={13} />
        </button>
      </div>

      {/* 作用域提示 */}
      {isNodeMode && dialogState?.boundNode && (
        <div className="px-3 py-2 text-[10px] text-[var(--color-text-muted)] border-b border-[var(--color-border)] bg-[var(--color-page-secondary)] truncate flex items-center gap-1.5">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/></svg>
          探索: {dialogState.boundNode.label}
        </div>
      )}

      {/* 临时对话迁移提示 */}
      {isTemporary && (
        <div className="px-3 py-2 text-[10px] text-[var(--color-accent)] border-b border-[var(--color-border)] bg-[var(--color-accent)]/5 flex items-center gap-1.5">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/></svg>
          临时对话 — 对话内容可以在稍后迁移到正式分区
        </div>
      )}

      {/* 内容 */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {isNodeMode && dialogState?.boundNode ? (
          <TreeChatPanel
            node={dialogState.boundNode}
            partitionId={partitionId}
            onNodeUpdated={onNodeUpdated}
          />
        ) : (
          <>
            {/* 消息占位 — 统一提示 */}
            <div className="flex-1 overflow-y-auto p-3 space-y-3">
              <div className="flex gap-2" style={{ maxWidth: "92%" }}>
                <div className="w-6 h-6 rounded-full bg-[var(--color-page-secondary)] flex items-center justify-center text-xs flex-shrink-0">🤖</div>
                <div className="px-3 py-2 text-[11px] leading-relaxed whitespace-pre-wrap bg-[var(--color-page-secondary)] border border-[var(--color-border)] rounded-xl rounded-bl-md text-[var(--color-text)]">
                  {isTemporary
                    ? "你好！这是临时对话。你可以直接和我聊天，稍后可以把内容迁移到正式分区。"
                    : "你好！我是知识树助手。我可以帮你总结知识树、推荐学习路径、管理节点。"}
                </div>
              </div>
            </div>

            {/* 输入区 */}
            <div className="p-3 border-t border-[var(--color-border)] flex gap-2 bg-[var(--color-surface)]">
              <input value={globalInput} onChange={e => setGlobalInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleGlobalSend()}
                placeholder={isNodeMode ? "询问此节点相关…" : isTemporary ? "临时对话…" : "向知识树提问…"}
                className="flex-1 px-3 py-2 text-[11px] border border-[var(--color-border)] rounded-lg bg-[var(--color-page-secondary)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] transition-colors" />
              <button onClick={handleGlobalSend}
                className="px-3 py-2 bg-[var(--color-accent)] text-white rounded-lg hover:opacity-90 transition-opacity">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M22 2L11 13"/><path d="M22 2L15 22l-4-9-9-4z"/>
                </svg>
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
