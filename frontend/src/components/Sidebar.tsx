"use client";

import React from "react";
import { Plus, MessageSquare, Settings, X, Trash2 } from "lucide-react";
import { Conversation } from "@/types";

interface SidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onSettings: () => void;
  open: boolean;
  onClose: () => void;
}

export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onSettings,
  open,
  onClose,
}: SidebarProps) {
  const sorted = [...conversations].sort((a, b) => b.updatedAt - a.updatedAt);

  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div
          className="sidebar-overlay fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar panel */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-72 bg-[var(--color-bg-secondary)] border-r border-[var(--color-border-default)] flex flex-col transform transition-transform duration-300 lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-4 border-b border-[var(--color-border-default)]">
          <h1 className="text-base font-semibold text-[var(--color-text-primary)]">
            📚 智能学习助手
          </h1>
          <button
            onClick={onClose}
            className="lg:hidden p-1 rounded-md text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-hover)]"
            aria-label="关闭菜单"
          >
            <X size={18} />
          </button>
        </div>

        {/* New chat button */}
        <div className="px-3 pt-3">
          <button
            onClick={() => {
              onNew();
              onClose();
            }}
            className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm text-[var(--color-text-primary)] border border-[var(--color-border-default)] hover:bg-[var(--color-bg-hover)] transition-colors"
          >
            <Plus size={16} />
            新建对话
          </button>
        </div>

        {/* Conversation list */}
        <nav className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
          {sorted.length === 0 && (
            <p className="text-xs text-[var(--color-text-muted)] text-center py-8">
              还没有对话记录
            </p>
          )}
          {sorted.map((conv) => (
            <div
              key={conv.id}
              className={`group flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm cursor-pointer transition-colors ${
                activeId === conv.id
                  ? "bg-[var(--color-bg-hover)] text-[var(--color-text-primary)]"
                  : "text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-hover)] hover:text-[var(--color-text-primary)]"
              }`}
              onClick={() => {
                onSelect(conv.id);
                onClose();
              }}
            >
              <MessageSquare size={14} className="flex-shrink-0" />
              <span className="truncate flex-1">{conv.title}</span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(conv.id);
                }}
                className="opacity-0 group-hover:opacity-100 p-1 rounded hover:text-red-400 transition-opacity"
                aria-label="删除对话"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </nav>

        {/* Settings */}
        <div className="border-t border-[var(--color-border-default)] px-3 py-3">
          <button
            onClick={() => {
              onSettings();
              onClose();
            }}
            className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-hover)] hover:text-[var(--color-text-primary)] transition-colors"
          >
            <Settings size={16} />
            模型设置
          </button>
        </div>
      </aside>
    </>
  );
}
