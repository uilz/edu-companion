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
    <div className="fixed right-0 top-0 h-full w-80 z-40 bg-surface border-l border shadow-xl flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border">
        <div className="flex items-center gap-2">
          <StickyNote size={16} className="text-success" />
          <span className="text-sm font-medium">笔记</span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-surface-hover text-muted"
        >
          <X size={14} />
        </button>
      </div>

      {/* Context */}
      {nodeLabel && (
        <div className="px-4 py-2 bg-surface-hover/50 border-b border/50">
          <span className="text-[10px] text-muted">当前知识节点</span>
          <p className="text-xs font-medium mt-0.5">{nodeLabel}</p>
        </div>
      )}

      {/* Add note button / input */}
      <div className="px-3 py-2 border-b border/50">
        {showInput ? (
          <div className="space-y-2">
            {sourceText && (
              <p className="text-[10px] text-muted italic line-clamp-2">
                &ldquo;{sourceText}&rdquo;
              </p>
            )}
            <textarea
              value={newNote}
              onChange={(e) => setNewNote(e.target.value)}
              placeholder="输入笔记内容..."
              className="w-full h-20 px-2 py-1.5 text-xs rounded border border bg-page resize-none focus:outline-none focus:border-accent"
              autoFocus
            />
            <div className="flex gap-1.5 justify-end">
              <button
                onClick={() => { setShowInput(false); setNewNote(""); }}
                className="px-2 py-1 text-[10px] rounded text-muted hover:bg-surface-hover"
              >
                取消
              </button>
              <button
                onClick={handleAddNote}
                disabled={!newNote.trim()}
                className="px-2 py-1 text-[10px] rounded bg-success text-white hover:opacity-90 disabled:opacity-40"
              >
                保存
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowInput(true)}
            className="flex items-center gap-1.5 w-full px-2 py-1.5 rounded text-xs text-muted hover:text-success hover:bg-success/5 border border-dashed border transition-colors"
          >
            <Plus size={12} />
            添加笔记
          </button>
        )}
      </div>

      {/* Notes list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {notes.length === 0 ? (
          <p className="text-xs text-muted text-center py-8">
            暂无笔记
          </p>
        ) : (
          notes.map((note) => (
            <div
              key={note.id}
              className="p-2.5 rounded-lg bg-page border border group"
            >
              <p className="text-xs text leading-relaxed">
                {note.text}
              </p>
              {note.sourceText && (
                <p className="text-[10px] text-muted mt-1 italic line-clamp-1">
                  &ldquo;{note.sourceText}&rdquo;
                </p>
              )}
              <div className="flex items-center justify-between mt-1.5">
                <span className="text-[9px] text-muted">
                  {note.createdAt}
                </span>
                <button
                  onClick={() => handleDeleteNote(note.id)}
                  className="p-0.5 rounded opacity-0 group-hover:opacity-100 text-muted hover:text-error transition-all"
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
