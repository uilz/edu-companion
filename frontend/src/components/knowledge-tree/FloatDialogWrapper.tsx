"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { MessageCircle, X, Send, Bot, Loader2 } from "lucide-react";
import type { GraphNode } from "@/lib/types/graph-types";
import type { DialogState } from "./KnowledgeTreePage";
import { useTreeChatStream } from "@/hooks/graph/useTreeChatStream";

const SNAP_THRESHOLD = 30;
const POS_KEY = "kt-float-pos";

export default function FloatDialogWrapper({
  dialogState, onDialogStateChange, partitionId, selectedNode, onNodeUpdated,
}: {
  dialogState: DialogState | null;
  onDialogStateChange: (s: DialogState | null) => void;
  partitionId: string;
  selectedNode: GraphNode | null;
  onNodeUpdated: () => void;
}) {
  const [open, setOpen] = useState(false);
  const chat = useTreeChatStream();
  const [input, setInput] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [chat.messages, chat.streamText]);

  // 绑定 conversationId
  useEffect(() => {
    if (dialogState?.conversationId && !chat.conversationId) {
      chat.bindConversation(dialogState.conversationId);
    }
  }, [dialogState?.conversationId, chat.conversationId, chat]);

  const btnRef = useRef<HTMLButtonElement>(null);
  const dragRef = useRef({ dragging: false, moved: false, startX: 0, startY: 0, startLeft: 0, startTop: 0 });
  const [pos, setPos] = useState<{ x: number; y: number }>(() => {
    try { const s = localStorage.getItem(POS_KEY); if (s) return JSON.parse(s); } catch {}
    return { x: typeof window !== "undefined" ? window.innerWidth - 72 : 0, y: typeof window !== "undefined" ? window.innerHeight - 80 : 0 };
  });

  const [snapped, setSnapped] = useState<"none" | "left" | "right">(() => {
    try { const s = localStorage.getItem(POS_KEY); if (s) { const p = JSON.parse(s); if (p.x <= SNAP_THRESHOLD) return "left"; if (p.x >= window.innerWidth - 52 - SNAP_THRESHOLD) return "right"; } } catch {}
    return "right";
  });

  const _startDrag = useCallback((clientX: number, clientY: number) => {
    let adjustedX = pos.x;
    if (snapped === "left") adjustedX = 8;
    else if (snapped === "right") adjustedX = window.innerWidth - 60;
    if (adjustedX !== pos.x) setPos({ x: adjustedX, y: pos.y });
    setSnapped("none");
    dragRef.current = { dragging: true, moved: false, startX: clientX, startY: clientY, startLeft: adjustedX, startTop: pos.y };
  }, [pos, snapped]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    _startDrag(e.clientX, e.clientY);
  }, [_startDrag]);

  // 用原生 addEventListener 注册 touchstart（passive: false），因为 React touch 事件默认 passive
  useEffect(() => {
    const el = btnRef.current;
    if (!el) return;
    const onTouchStart = (e: TouchEvent) => {
      e.preventDefault();
      _startDrag(e.touches[0].clientX, e.touches[0].clientY);
    };
    el.addEventListener("touchstart", onTouchStart, { passive: false });
    return () => el.removeEventListener("touchstart", onTouchStart);
  }, [_startDrag]);

  useEffect(() => {
    const onMove = (e: MouseEvent | TouchEvent) => {
      if (!dragRef.current.dragging) return;
      e.preventDefault();
      const cx = "touches" in e ? e.touches[0].clientX : e.clientX;
      const cy = "touches" in e ? e.touches[0].clientY : e.clientY;
      const dx = cx - dragRef.current.startX;
      const dy = cy - dragRef.current.startY;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) dragRef.current.moved = true;
      setPos({
        x: Math.max(0, Math.min(window.innerWidth - 52, dragRef.current.startLeft + dx)),
        y: Math.max(0, Math.min(window.innerHeight - 52, dragRef.current.startTop + dy)),
      });
    };
    const onUp = () => {
      if (!dragRef.current.dragging) return;
      dragRef.current.dragging = false;
      if (dragRef.current.moved) {
        setPos(prev => {
          const vw = window.innerWidth;
          let newX = prev.x;
          let newSnap: "none" | "left" | "right" = "none";
          if (prev.x < 60) { newX = -26; newSnap = "left"; }
          else if (prev.x > vw - 52 - 60) { newX = vw - 26; newSnap = "right"; }
          setSnapped(newSnap);
          const s = { x: newX, y: prev.y };
          try { localStorage.setItem(POS_KEY, JSON.stringify(s)); } catch {}
          return s;
        });
      }
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    window.addEventListener("touchmove", onMove, { passive: false });
    window.addEventListener("touchend", onUp);
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); window.removeEventListener("touchmove", onMove); window.removeEventListener("touchend", onUp); };
  }, []);

  const handleClick = () => {
    if (dragRef.current.moved) { dragRef.current.moved = false; return; }
    setOpen(!open);
  };

  const isNodeMode = dialogState?.type === "tree_exploration" && !!dialogState.boundNode;

  // 合并消息流
  const displayMessages = [
    ...chat.messages,
    ...(chat.streamText ? [{ role: "assistant" as const, text: chat.streamText, id: "streaming" }] : []),
  ];

  const send = async () => {
    if (!input.trim() || chat.streaming || !dialogState?.conversationId) return;
    const text = input.trim();
    setInput("");
    if (!chat.conversationId) {
      chat.bindConversation(dialogState.conversationId);
    }
    await chat.sendMessage(text, partitionId);
  };

  const [hovering, setHovering] = useState(false);
  const isSnapped = snapped !== "none";
  const showFull = !isSnapped || hovering || open;

  void onDialogStateChange; void selectedNode; void onNodeUpdated;

  return (
    <>
      <button ref={btnRef}
        onMouseDown={handleMouseDown}
        onClick={handleClick}
        onMouseEnter={() => setHovering(true)}
        onMouseLeave={() => setHovering(false)}
        className="fixed w-[52px] h-[52px] rounded-full bg-[var(--color-accent)] text-white border-none cursor-pointer flex items-center justify-center shadow-lg z-50 hover:scale-105 transition-all duration-300 overflow-hidden"
        style={{
          left: isSnapped ? (showFull ? (snapped === "left" ? 8 : pos.x - 18) : pos.x) : pos.x,
          top: `${pos.y}px`,
        }}>
        {open ? <X size={20} /> : <MessageCircle size={22} />}
      </button>

      {open && (
        <div className="fixed w-[380px] max-h-[560px] bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl shadow-2xl z-50 flex flex-col overflow-hidden animate-in slide-in-from-bottom-4 duration-200"
          style={{
            left: `${Math.min(snapped === "left" ? 12 : pos.x, window.innerWidth - 400)}px`,
            bottom: `${window.innerHeight - pos.y + 8}px`,
          }}>
          <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--color-border)] flex-shrink-0">
            <MessageCircle size={15} className="text-[var(--color-accent)]" />
            <span className="text-xs font-medium text-[var(--color-text)]">
              {isNodeMode ? "节点探索" : "知识树助手"}
            </span>
            {isNodeMode && dialogState?.boundNode && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--color-accent)]/10 text-[var(--color-accent)] truncate max-w-[100px]">
                {dialogState.boundNode.label}
              </span>
            )}
          </div>

          <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0">
            {displayMessages.length === 0 && !chat.streaming && (
              <div className="flex flex-col items-center justify-center h-full text-center gap-2 py-6">
                <Bot size={24} className="text-[var(--color-accent)] opacity-40" />
                <p className="text-xs text-[var(--color-text-muted)]">
                  {isNodeMode ? "选中节点后会自动进入探索模式" : "点击节点选择具体知识点"}
                </p>
              </div>
            )}
            {displayMessages.map((msg, i) => (
              <div key={msg.id || i} className={`flex gap-2 ${msg.role === "user" ? "flex-row-reverse" : ""}`} style={{ maxWidth: "92%" }}>
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs shrink-0 ${
                  msg.role === "user" ? "bg-[var(--color-accent)]/10" : "bg-[var(--color-page-secondary)]"
                }`}>
                  {msg.role === "user" ? "👤" : "🤖"}
                </div>
                <div className={`px-3 py-2 text-[11px] leading-relaxed whitespace-pre-wrap rounded-xl ${
                  msg.role === "user"
                    ? "bg-[var(--color-accent)] text-white rounded-tr-md"
                    : "bg-[var(--color-page-secondary)] border border-[var(--color-border)] text-[var(--color-text)] rounded-tl-md"
                }`}>
                  {msg.text}
                </div>
              </div>
            ))}
            {chat.streaming && !chat.streamText && (
              <div className="flex gap-2" style={{ maxWidth: "92%" }}>
                <div className="w-6 h-6 rounded-full bg-[var(--color-page-secondary)] flex items-center justify-center text-xs shrink-0">🤖</div>
                <div className="px-3 py-2 rounded-xl rounded-tl-md border border-[var(--color-border)] bg-[var(--color-page-secondary)]">
                  <Loader2 size={12} className="animate-spin text-[var(--color-text-muted)]" />
                </div>
              </div>
            )}
            {chat.error && (
              <div className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-red-500/10 text-red-500 text-[11px]">
                <span>{chat.error}</span>
              </div>
            )}
          </div>

          <div className="flex-shrink-0 px-4 py-3 border-t border-[var(--color-border)] bg-[var(--color-surface)]">
            <div className="flex items-center gap-2">
              <input value={input} onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && !chat.streaming && send()}
                placeholder="输入消息…"
                disabled={chat.streaming}
                className="flex-1 px-3 py-2 text-[12px] border border-[var(--color-border)] rounded-lg bg-[var(--color-page-secondary)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] transition-colors disabled:opacity-50" />
              <button onClick={send} disabled={chat.streaming || !input.trim()}
                className="p-2 rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-40 transition-opacity">
                {chat.streaming ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}