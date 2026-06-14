"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { Loader2, Send, Bot, User, AlertCircle, Sparkles, ArrowRight } from "lucide-react";
import type { GraphNode } from "@/lib/types/graph-types";
import { authedFetch } from "@/lib/api/api";

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  id: string;
}

interface TreeChatPanelProps {
  node: GraphNode;
  partitionId: string;
  onNodeUpdated: () => void;
}

export default function TreeChatPanel({
  node, partitionId, onNodeUpdated,
}: TreeChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [convId, setConvId] = useState("");
  const [error, setError] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  // 滚动到底部
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  // 发送消息
  const handleSend = useCallback(async () => {
    if (!input.trim() || loading) return;
    const userText = input.trim();
    const userMsg: ChatMessage = { role: "user", text: userText, id: "u-" + Date.now() };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    setError("");

    try {
      const res = await authedFetch(`/api/knowledge/graph/${partitionId}/ai-chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          node_id: node.id,
          message: userText,
          conversation_id: convId || undefined,
        }),
      });
      const data = await res.json();

      if (data.error === "scope_mismatch") {
        const asstMsg: ChatMessage = {
          role: "assistant",
          text: `⚠️ ${data.message}\n\n👉 请点击「${data.bound_node_label}」节点，在它的详情面板中启动探索会话。`,
          id: "a-" + Date.now(),
        };
        setMessages(prev => [...prev, asstMsg]);
        return;
      }

      if (data.conversation_id) setConvId(data.conversation_id);

      // 如果有对话推荐，附加在回复下方
      let replyText = data.response || "";
      if (data.conversation_recommendation) {
        const rec = data.conversation_recommendation;
        if (rec.type === "exploration_complete") {
          replyText += `\n\n---\n💡 **探索完成！** 建议到[对话系统](/)深入学习具体知识点。`;
        } else if (rec.type === "deep_dive") {
          replyText += `\n\n---\n💡 对「${rec.node_label}」很感兴趣？去[对话系统](/)深入探讨。`;
        } else if (rec.type === "parent_reference") {
          replyText += `\n\n---\n💡 这个知识属于「${rec.node_label}」，建议切换到该节点的探索会话。`;
        }
      }

      const asstMsg: ChatMessage = {
        role: "assistant",
        text: replyText || "（收到空回复）",
        id: "a-" + Date.now(),
      };
      setMessages(prev => [...prev, asstMsg]);
      onNodeUpdated();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [input, loading, node.id, partitionId, convId, onNodeUpdated]);

  // 快捷键：Enter 发送
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* 节点上下文提示 */}
      <div className="flex-shrink-0 px-4 py-2.5 border-b border-[var(--color-border)] bg-[var(--color-accent)]/5">
        <div className="flex items-center gap-2 text-xs">
          <Sparkles size={12} className="text-[var(--color-accent)]" />
          <span className="text-[var(--color-text-muted)]">
            正在探索 <strong className="text-[var(--color-text)]">{node.label}</strong>
          </span>
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] ml-auto">
            {node.level}
          </span>
        </div>
        {node.description && (
          <p className="text-[10px] text-[var(--color-text-muted)] mt-1 leading-relaxed line-clamp-2">
            {node.description}
          </p>
        )}
      </div>

      {/* 消息列表 */}
      <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center h-full text-center gap-2">
            <Bot size={28} className="text-[var(--color-accent)] opacity-40" />
            <p className="text-xs text-[var(--color-text-muted)] max-w-[240px] leading-relaxed">
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
                  onClick={() => {
                    setInput(hint);
                  }}
                  className="px-2 py-1 text-[10px] rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] transition-colors"
                >
                  {hint}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} className={`flex gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            {msg.role === "assistant" && (
              <div className="flex-shrink-0 w-6 h-6 rounded-full bg-[var(--color-accent)]/10 flex items-center justify-center mt-0.5">
                <Bot size={12} className="text-[var(--color-accent)]" />
              </div>
            )}
            <div className={`max-w-[85%] px-3 py-2 rounded-xl text-xs leading-relaxed ${
              msg.role === "user"
                ? "bg-[var(--color-accent)] text-white rounded-br-sm"
                : "bg-[var(--color-surface)] border border-[var(--color-border)] rounded-bl-sm"
            }`}>
              <div className="whitespace-pre-wrap">{msg.text}</div>
            </div>
            {msg.role === "user" && (
              <div className="flex-shrink-0 w-6 h-6 rounded-full bg-[var(--color-accent)] flex items-center justify-center mt-0.5">
                <User size={12} className="text-white" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-2 justify-start">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-[var(--color-accent)]/10 flex items-center justify-center">
              <Bot size={12} className="text-[var(--color-accent)]" />
            </div>
            <div className="px-3 py-2 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] rounded-bl-sm">
              <Loader2 size={12} className="animate-spin text-[var(--color-text-muted)]" />
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-red-500/10 text-red-500 text-[11px]">
            <AlertCircle size={12} /> {error}
          </div>
        )}
      </div>

      {/* 输入区 */}
      <div className="flex-shrink-0 border-t border-[var(--color-border)] bg-[var(--color-bg)]">
        <div className="flex items-end gap-2 px-4 py-2">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="告诉 AI 你想怎么编辑..."
            rows={1}
            className="flex-1 px-3 py-2 text-xs rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] resize-none transition-colors"
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="flex-shrink-0 p-2 rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-40 transition-all active:scale-[0.97]"
          >
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
          </button>
        </div>
      </div>
    </div>
  );
}
