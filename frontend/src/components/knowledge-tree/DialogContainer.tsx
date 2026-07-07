"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { AlertCircle, Loader2, Send, Bot, MessageCircle } from "lucide-react";
import type { GraphNode } from "@/lib/types/graph-types";
import TreeChatPanel from "@/components/graph/panels/TreeChatPanel";
import type { DialogState } from "./KnowledgeTreePage";
import { useTreeChatStream } from "@/hooks/graph/useTreeChatStream";

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
  // 保留接口兼容性
  void onDialogStateChange; void selectedNode; void onWidthChange;

  const isNodeMode = dialogState?.type === "tree_exploration" && !!dialogState.boundNode;
  const isTemporary = dialogState?.type === "temporary";

  // ── 临时对话状态（独立流，用 hook 直接管理） ──
  const tempChat = useTreeChatStream();
  const [input, setInput] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  // 绑定已有 conversationId
  useEffect(() => {
    if (dialogState?.conversationId && !tempChat.conversationId) {
      tempChat.bindConversation(dialogState.conversationId);
    }
  }, [dialogState?.conversationId, tempChat.conversationId, tempChat]);

  // 自动滚动到底部
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [tempChat.messages, tempChat.streamText]);

  // ── 临时对话发送 ──
  const handleSend = useCallback(async () => {
    if (!input.trim() || tempChat.streaming || !dialogState) return;
    setInput("");
    if (dialogState.conversationId) {
      if (!tempChat.conversationId) {
        tempChat.bindConversation(dialogState.conversationId);
      }
      await tempChat.sendMessage(input.trim(), partitionId);
    }
  }, [input, tempChat, dialogState, partitionId]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (isNodeMode && dialogState?.boundNode) return;
      handleSend();
    }
  };

  // 合并消息流
  const displayMessages = dialogState?.conversationId
    ? [
        ...tempChat.messages,
        ...(tempChat.streamText ? [{ role: "assistant" as const, text: tempChat.streamText, id: "streaming" }] : []),
      ]
    : [];

  const isLoading = tempChat.streaming;

  const title = isTemporary ? "临时对话" : isNodeMode ? "节点探索" : "知识树助手";
  const boundLabel = isNodeMode ? dialogState?.boundNode?.label : "";

  return (
    <div className="flex flex-col h-full overflow-hidden bg-surface border-r border">
      {/* ══ 头部 ══ */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border flex-shrink-0">
        <MessageCircle size={15} className="text-accent shrink-0" />
        <span className="text-xs font-medium text truncate">{title}</span>
        {boundLabel && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent/10 text-accent truncate max-w-[120px] shrink-0">
            {boundLabel}
          </span>
        )}
        {isTemporary && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-warning/10 text-warning shrink-0">
            临时
          </span>
        )}
      </div>

      {/* ══ 内容 ══ */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {isNodeMode && dialogState?.boundNode ? (
          <TreeChatPanel
            node={dialogState.boundNode}
            partitionId={partitionId}
            onNodeUpdated={onNodeUpdated}
          />
        ) : (
          <>
            {/* 消息列表 */}
            <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
              {displayMessages.length === 0 && !isLoading && (
                <div className="flex flex-col items-center justify-center h-full text-center gap-3 px-4">
                  <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center">
                    <Bot size={22} className="text-accent" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text mb-1">
                      {isTemporary ? "临时对话" : "知识树助手"}
                    </p>
                    <p className="text-[11px] text-muted max-w-[220px] leading-relaxed">
                      {isTemporary
                        ? "你可以直接和我聊天，稍后可以把内容迁移到正式分区。"
                        : "我可以帮你总结知识树、推荐学习路径、管理节点。"}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-1.5 justify-center mt-1">
                    {[
                      "总结当前知识树",
                      "推荐学习路径",
                      "有哪些核心概念",
                    ].map((hint, i) => (
                      <button key={i} onClick={() => setInput(hint)}
                        className="px-2.5 py-1 text-[10px] rounded-lg border border text-muted hover:border-accent hover:text-accent transition-colors">
                        {hint}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {displayMessages.map((msg) => (
                <div key={msg.id} className={`flex gap-2 ${msg.role === "user" ? "flex-row-reverse" : ""}`} style={{ maxWidth: "92%" }}>
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs shrink-0
                    ${msg.role === "user" ? "bg-accent/10" : "bg-page-secondary"}`}>
                    {msg.role === "user" ? "👤" : "🤖"}
                  </div>
                  <div className={`px-3 py-2 text-[11px] leading-relaxed whitespace-pre-wrap rounded-xl ${
                    msg.role === "user"
                      ? "bg-accent text-white rounded-tr-md"
                      : "bg-page-secondary border border text rounded-tl-md"
                  }`}>
                    {msg.text}
                  </div>
                </div>
              ))}

              {isLoading && (
                <div className="flex gap-2" style={{ maxWidth: "92%" }}>
                  <div className="w-6 h-6 rounded-full bg-page-secondary flex items-center justify-center text-xs shrink-0">🤖</div>
                  <div className="px-3 py-2 rounded-xl rounded-tl-md border border bg-page-secondary">
                    <Loader2 size={12} className="animate-spin text-muted" />
                  </div>
                </div>
              )}

              {tempChat.error && (
                <div className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-danger/10 text-danger text-[11px]">
                  <AlertCircle size={12} />{tempChat.error}
                </div>
              )}
            </div>

            {/* 输入区 */}
            <div className="flex-shrink-0 px-4 py-3 border-t border bg-page-secondary">
              <div className="flex items-center gap-2">
                <input
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={isTemporary ? "输入消息…" : "向知识树提问…"}
                  className="flex-1 px-3 py-2 text-[12px] border border rounded-lg bg-page-secondary text placeholder:text-muted focus:outline-none focus:border-accent transition-colors"
                />
                <button onClick={handleSend} disabled={isLoading || !input.trim()}
                  className="p-2 rounded-lg bg-accent text-white hover:opacity-90 disabled:opacity-40 transition-opacity">
                  {isLoading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}