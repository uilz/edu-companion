"use client";

import React from "react";
import { Pencil, Trash2, Copy, ChevronLeft, ChevronRight, MessageSquare } from "lucide-react";
import SpeakButton from "./../media/SpeakButton";

export interface VersionInfo {
  index: number;
  total: number;
}

interface MessageActionsProps {
  role: "user" | "assistant";
  vInfo: VersionInfo;
  hasVersions: boolean;
  text: string;  // displayText for SpeakButton
  onEdit?: () => void;
  onDelete?: () => void;
  onCopy?: () => void;
  onVersionNav?: (direction: "prev" | "next") => void;
  onFeynmanTeach?: () => void;
}

/**
 * MessageActions — 消息气泡下方的操作按钮组
 *
 * 用户消息: 版本切换 | 编辑 | 删除 | 复制
 * 助手消息: 删除 | 复制 | 语音 | 我来给你讲讲
 */
export default function MessageActions({
  role,
  vInfo,
  hasVersions,
  onEdit,
  text,
  onDelete,
  onCopy,
  onVersionNav,
  onFeynmanTeach,
}: MessageActionsProps) {
  if (role === "user") {
    return (
      <div className="absolute bottom-0 right-0 flex items-center gap-1 px-1 py-0.5 opacity-0 group-hover:opacity-100 max-lg:opacity-100 transition-opacity">
        {vInfo.total > 1 && onVersionNav && (
          <div className="flex items-center gap-0.5 text-xs text-[var(--color-text-muted)] mr-1 border-r border-[var(--color-border)] pr-1">
            <button onClick={() => onVersionNav("prev")} className="p-0.5 hover:text-[var(--color-text)]" title="上一版本">
              <ChevronLeft size={12} />
            </button>
            <span className="min-w-[2em] text-center font-mono">{vInfo.index}/{vInfo.total}</span>
            <button onClick={() => onVersionNav("next")} className="p-0.5 hover:text-[var(--color-text)]" title="下一版本">
              <ChevronRight size={12} />
            </button>
          </div>
        )}
        {onEdit && (
          <button onClick={onEdit} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]" title="编辑">
            <Pencil size={12} />
          </button>
        )}
        {onDelete && (
          <button onClick={onDelete} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-error)]" title="删除">
            <Trash2 size={12} />
          </button>
        )}
        {onCopy && (
          <button onClick={onCopy} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]" title="复制">
            <Copy size={12} />
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="absolute bottom-0 left-0 flex items-center gap-1 px-1 py-0.5 opacity-0 group-hover:opacity-100 max-lg:opacity-100 transition-opacity">
      {onDelete && (
        <button onClick={onDelete} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-error)]" title="删除">
          <Trash2 size={12} />
        </button>
      )}
      {onCopy && (
        <button onClick={onCopy} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]" title="复制">
          <Copy size={12} />
        </button>
      )}
      {onFeynmanTeach && (
        <button onClick={onFeynmanTeach}
          className="flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[11px] text-[var(--color-accent)] hover:bg-[var(--color-accent)]/10 transition-colors"
          title="费曼学习法——讲给AI听">
          <MessageSquare size={11} />
          <span>我来给你讲讲</span>
        </button>
      )}
          <SpeakButton text={text} />
    </div>
  );
}
