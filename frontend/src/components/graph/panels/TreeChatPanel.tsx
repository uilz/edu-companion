"use client";

import React, { useEffect, useRef, useCallback } from "react";
import { Loader2, Send, Bot, User, AlertCircle, Sparkles } from "lucide-react";
import type { GraphNode } from "@/lib/types/graph-types";
import { useTreeChatStream } from "@/hooks/graph/useTreeChatStream";

interface TreeChatPanelProps {
  node: GraphNode;
  partitionId: string;
  onNodeUpdated: () => void;
}

export default function TreeChatPanel({
  node, partitionId, onNodeUpdated,
}: TreeChatPanelProps) {
  const chat = useTreeChatStream();
  const [input, setInput] = React.useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const initRef = useRef(false);

  // 节点变化时重新初始化会话
  useEffect(() => {
    initRef.current = false;
    chat.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [node.id]);

  useEffect(() => {
    if (!chat.conversationId && !initRef.current) {
      initRef.current = true;
      chat.initChat(node.id).catch((e) => {
        console.error("initChat failed:", e);
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [node.id, chat.conversationId]);

  // 滚动到底部
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [chat.messages, chat.streamText]);

  // 发送消息
  const handleSend = useCallback(async () => {
    if (!input.trim() || chat.streaming) return;
    const text = input.trim();
    setInput("");
    await chat.sendMessage(text, partitionId);
    onNodeUpdated();
  }, [input, chat, partitionId, onNodeUpdated]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // 合并历史消息 + 正在流式的内容
  const allMessages = [
    ...chat.messages,
    ...(chat.streamText ? [{ role: "assistant" as const, text: chat.streamText, id: "streaming" }] : []),
  ];

  return (
    <div className="flex flex-col h-full">
      {/* 节点上下文提示 */}
      <div className="flex-shrink-0 px-4 py-2.5 border-b border bg-accent/5">
        <div className="flex items-center gap-2 text-xs">
          <Sparkles size={12} className="text-accent" />
          <span className="text-muted">
            正在探索 <strong className="text">{node.label}</strong>
          </span>
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-surface-hover text-muted ml-auto">
            {node.level}
          </span>
        </div>
        {node.description && (
          <p className="text-[10px] text-muted mt-1 leading-relaxed line-clamp-2">
            {node.description}
          </p>
        )}
      </div>

      {/* 消息列表 */}
      <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {allMessages.length === 0 && !chat.streaming && (
          <div className="flex flex-col items-center justify-center h-full text-center gap-2">
            <Bot size={28} className="text-accent opacity-40" />
            <p className="text-xs text-muted max-w-[240px] leading-relaxed">
              在知识树中探索 <strong>{node.label}</strong>
              <br />你可以要求 AI 添加子节点、编辑描述、或梳理知识关系
            </p>
            <div className="flex flex-wrap gap-1.5 mt-1 justify-center">
              {[
                `为「${node.label}」添加子节点`,
                "编辑这个节点的描述",
                "梳理相关知识的关系",
              ].map((hint, i) => (
                <button
                  key={i}
                  onClick={() => setInput(hint)}
                  className="px-2 py-1 text-[10px] rounded-lg border border text-muted hover:border-accent hover:text-accent transition-colors"
                >
                  {hint}
                </button>
              ))}
            </div>
          </div>
        )}

        {allMessages.map((msg) => (
          <div key={msg.id} className={`flex gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            {msg.role === "assistant" && (
              <div className="flex-shrink-0 w-6 h-6 rounded-full bg-accent/10 flex items-center justify-center mt-0.5">
                <Bot size={12} className="text-accent" />
              </div>
            )}
            <div className={`max-w-[85%] px-3 py-2 rounded-xl text-xs leading-relaxed ${
              msg.role === "user"
                ? "bg-accent text-white rounded-br-sm"
                : "bg-surface border border rounded-bl-sm"
            }`}>
              <div className="whitespace-pre-wrap">{msg.text}</div>
            </div>
            {msg.role === "user" && (
              <div className="flex-shrink-0 w-6 h-6 rounded-full bg-accent flex items-center justify-center mt-0.5">
                <User size={12} className="text-white" />
              </div>
            )}
          </div>
        ))}

        {chat.streaming && !chat.streamText && (
          <div className="flex gap-2 justify-start">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-accent/10 flex items-center justify-center">
              <Bot size={12} className="text-accent" />
            </div>
            <div className="px-3 py-2 rounded-xl bg-surface border border rounded-bl-sm">
              <Loader2 size={12} className="animate-spin text-muted" />
            </div>
          </div>
        )}

        {chat.error && (
          <div className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-danger/10 text-danger text-[11px]">
            <AlertCircle size={12} /> {chat.error}
          </div>
        )}
      </div>

      {/* 输入区 */}
      <div className="flex-shrink-0 border-t border bg-page">
        <div className="flex items-end gap-2 px-4 py-2">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="告诉 AI 你想怎么编辑..."
            rows={1}
            disabled={chat.streaming}
            className="flex-1 px-3 py-2 text-xs rounded-lg bg-surface border border text placeholder:text-muted focus:outline-none focus:border-accent resize-none transition-colors disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={chat.streaming || !input.trim()}
            className="flex-shrink-0 p-2 rounded-lg bg-accent text-white hover:opacity-90 disabled:opacity-40 transition-all active:scale-[0.97]"
          >
            {chat.streaming ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
          </button>
        </div>
      </div>
    </div>
  );
}