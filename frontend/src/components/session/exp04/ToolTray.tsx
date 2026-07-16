"use client";

import { useState, useRef, useEffect } from "react";
import { LayoutGrid, StickyNote, Mic, Palette, PenTool, FileText, Clock } from "lucide-react";

export type ToolKey = "flashcard" | "voice" | "canvas" | "handwriting" | "files" | "pomodoro";

interface ToolItem {
  key: ToolKey;
  label: string;
  desc: string;
  icon: React.ReactNode;
}

const TOOLS: ToolItem[] = [
  { key: "flashcard", label: "闪卡", desc: "记一张卡", icon: <StickyNote size={16} /> },
  { key: "voice", label: "语音", desc: "说出来", icon: <Mic size={16} /> },
  { key: "canvas", label: "画布", desc: "画思路", icon: <Palette size={16} /> },
  { key: "handwriting", label: "手写", desc: "动笔写", icon: <PenTool size={16} /> },
  { key: "files", label: "文件", desc: "看资料", icon: <FileText size={16} /> },
  { key: "pomodoro", label: "番茄钟", desc: "专注一会儿", icon: <Clock size={16} /> },
];

interface Props {
  nudge?: string | null;
  activeTool?: ToolKey | null;
  onOpenTool: (tool: ToolKey) => void;
}

export default function ToolTray({ nudge, activeTool, onOpenTool }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className={`relative w-9 h-9 rounded-full grid place-items-center transition-colors ${
          open || activeTool ? "bg-accent/10 text-accent" : "text-ink-secondary hover:bg-surface-hover"
        }`}
        aria-label="工具托盘"
      >
        <LayoutGrid size={18} />
        {nudge && (
          <span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full bg-accent text-white text-[9px] font-bold grid place-items-center animate-pulse">
            {nudge.length > 2 ? "·" : nudge}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute top-11 right-0 w-52 bg-surface rounded-xl shadow-xl border border-border/50 p-1.5 z-50 animate-in fade-in slide-in-from-top-2 duration-200">
          {TOOLS.map((tool) => (
            <button
              key={tool.key}
              onClick={() => {
                onOpenTool(tool.key);
                setOpen(false);
              }}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors ${
                activeTool === tool.key ? "bg-accent/10" : "hover:bg-surface-hover"
              }`}
            >
              <span className="w-8 h-8 rounded-lg bg-page border border-border/50 grid place-items-center text-ink-secondary">
                {tool.icon}
              </span>
              <span className="flex-1">
                <span className="block text-sm font-medium text-ink-primary">{tool.label}</span>
                <span className="block text-[11px] text-ink-muted">{tool.desc}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
