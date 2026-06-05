"use client";

import React, { useState } from "react";
import { StickyNote, X, Plus, Trash2 } from "lucide-react";

interface Note {
  id: string;
  text: string;
  sourceText: string;
  nodeId?: string;
  createdAt: string;
}

interface NoteSidebarProps {
  open: boolean;
  onClose: () => void;
  sourceText?: string;
  nodeId?: string;
  nodeLabel?: string;
}

export default function NoteSidebar({
  open,
  sourceText,
  nodeId,
  nodeLabel,
  onClose,
}: NoteSidebarProps) {
  const [notes, setNotes] = useState<Note[]>([]);
  const [newNote, setNewNote] = useState("");
  const [showInput, setShowInput] = useState(false);

  const handleAddNote = () => {
    if (!newNote.trim()) return;
    const note: Note = {
      id: `note_${Date.now()}`,
      text: newNote.trim(),
      sourceText: sourceText || "",
      nodeId,
      createdAt: new Date().toLocaleString("zh-CN"),
    };
    setNotes([note, ...notes]);
    setNewNote("");
    setShowInput(false);
  };

  const handleDeleteNote = (id: string) => {
    setNotes(notes.filter((n) => n.id !== id));
  };

  if (!open) return null;

  return (
    <div className="fixed right-0 top-0 h-full w-80 z-40 bg-[var(--color-surface)] border-l border-[var(--color-border)] shadow-xl flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-2">
          <StickyNote size={16} className="text-[var(--color-success)]" />
          <span className="text-sm font-medium">笔记</span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]"
        >
          <X size={14} />
        </button>
      </div>

      {/* Context */}
      {nodeLabel && (
        <div className="px-4 py-2 bg-[var(--color-surface-hover)]/50 border-b border-[var(--color-border)]/50">
          <span className="text-[10px] text-[var(--color-text-muted)]">当前知识节点</span>
          <p className="text-xs font-medium mt-0.5">{nodeLabel}</p>
        </div>
      )}

      {/* Add note button / input */}
      <div className="px-3 py-2 border-b border-[var(--color-border)]/50">
        {showInput ? (
          <div className="space-y-2">
            {sourceText && (
              <p className="text-[10px] text-[var(--color-text-muted)] italic line-clamp-2">
                &ldquo;{sourceText}&rdquo;
              </p>
            )}
            <textarea
              value={newNote}
              onChange={(e) => setNewNote(e.target.value)}
              placeholder="输入笔记内容..."
              className="w-full h-20 px-2 py-1.5 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)] resize-none focus:outline-none focus:border-[var(--color-accent)]"
              autoFocus
            />
            <div className="flex gap-1.5 justify-end">
              <button
                onClick={() => { setShowInput(false); setNewNote(""); }}
                className="px-2 py-1 text-[10px] rounded text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
              >
                取消
              </button>
              <button
                onClick={handleAddNote}
                disabled={!newNote.trim()}
                className="px-2 py-1 text-[10px] rounded bg-[var(--color-success)] text-white hover:opacity-90 disabled:opacity-40"
              >
                保存
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowInput(true)}
            className="flex items-center gap-1.5 w-full px-2 py-1.5 rounded text-xs text-[var(--color-text-muted)] hover:text-[var(--color-success)] hover:bg-[var(--color-success)]/5 border border-dashed border-[var(--color-border)] transition-colors"
          >
            <Plus size={12} />
            添加笔记
          </button>
        )}
      </div>

      {/* Notes list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {notes.length === 0 ? (
          <p className="text-xs text-[var(--color-text-muted)] text-center py-8">
            暂无笔记
          </p>
        ) : (
          notes.map((note) => (
            <div
              key={note.id}
              className="p-2.5 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] group"
            >
              <p className="text-xs text-[var(--color-text)] leading-relaxed">
                {note.text}
              </p>
              {note.sourceText && (
                <p className="text-[10px] text-[var(--color-text-muted)] mt-1 italic line-clamp-1">
                  &ldquo;{note.sourceText}&rdquo;
                </p>
              )}
              <div className="flex items-center justify-between mt-1.5">
                <span className="text-[9px] text-[var(--color-text-muted)]">
                  {note.createdAt}
                </span>
                <button
                  onClick={() => handleDeleteNote(note.id)}
                  className="p-0.5 rounded opacity-0 group-hover:opacity-100 text-[var(--color-text-muted)] hover:text-[var(--color-error)] transition-all"
                >
                  <Trash2 size={10} />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
