"use client";

import React, { useEffect, useRef } from "react";
import {
  Edit3, PlusCircle, Sparkles, PenLine, Link, HelpCircle, Trash2,
} from "lucide-react";

export interface ContextMenuItem {
  id: string;
  label: string;
  icon?: React.ReactNode;
  danger?: boolean;
  divider?: boolean;
  onClick: () => void;
}

interface ContextMenuProps {
  x: number;
  y: number;
  items: ContextMenuItem[];
  onClose: () => void;
}

export default function ContextMenu({ x, y, items, onClose }: ContextMenuProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const escHandler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", handler);
    document.addEventListener("keydown", escHandler);
    return () => {
      document.removeEventListener("mousedown", handler);
      document.removeEventListener("keydown", escHandler);
    };
  }, [onClose]);

  // 确保菜单不超出视口
  const adjustedX = Math.min(x, window.innerWidth - 200);
  const adjustedY = Math.min(y, window.innerHeight - items.length * 36 - 16);

  return (
    <div
      ref={ref}
      className="fixed z-[300] min-w-[180px] bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-xl shadow-lg py-1.5 animate-in fade-in duration-100"
      style={{ left: adjustedX, top: adjustedY }}
    >
      {items.map((item, i) => {
        if (item.divider) {
          return <div key={i} className="h-px bg-[var(--color-border)] my-1 mx-2" />;
        }
        return (
          <button
            key={item.id}
            onClick={() => { item.onClick(); onClose(); }}
            className={`w-full flex items-center gap-2.5 px-3 py-2 text-[12px] transition-colors hover:bg-[var(--color-accent)]/10 ${
              item.danger ? "text-[var(--color-danger)] hover:bg-red-500/10" : "text-[var(--color-text)] hover:text-[var(--color-accent)]"
            }`}
          >
            <span className="w-4 h-4 flex items-center justify-center flex-shrink-0">
              {item.icon}
            </span>
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

// ── 默认知识树右键菜单项 ──
export function getDefaultContextMenuItems(
  nodeLabel: string,
  nodeId: string,
  handlers: {
    onEdit: () => void;
    onAddChild: () => void;
    onAiExpand: () => void;
    onAiEdit: () => void;
    onLinkConversation: () => void;
    onExplain: () => void;
    onDelete: () => void;
  },
): ContextMenuItem[] {
  return [
    { id: "edit", label: "编辑节点", icon: <Edit3 size={12} />, onClick: handlers.onEdit },
    { id: "add-child", label: "添加子节点", icon: <PlusCircle size={12} />, onClick: handlers.onAddChild },
    { id: "ai-expand", label: "AI 扩充子节点", icon: <Sparkles size={12} />, onClick: handlers.onAiExpand },
    { id: "ai-edit", label: "AI 编辑内容", icon: <PenLine size={12} />, onClick: handlers.onAiEdit },
    { id: "link", label: "关联会话", icon: <Link size={12} />, onClick: handlers.onLinkConversation },
    { id: "divider", label: "", divider: true, onClick: () => {} },
    { id: "explain", label: "请求讲解", icon: <HelpCircle size={12} />, onClick: handlers.onExplain },
    { id: "divider2", label: "", divider: true, onClick: () => {} },
    { id: "delete", label: "删除节点", icon: <Trash2 size={12} />, danger: true, onClick: handlers.onDelete },
  ];
}
