"use client";

import { StickyNote, Mic, Palette, PenTool, FileText, Clock } from "lucide-react";

export type ToolKey = "flashcard" | "voice" | "canvas" | "handwriting" | "files" | "pomodoro";

interface ToolItem {
  key: ToolKey;
  label: string;
  icon: React.ReactNode;
}

const TOOLS: ToolItem[] = [
  { key: "flashcard", label: "闪卡", icon: <StickyNote size={15} /> },
  { key: "canvas", label: "画布", icon: <Palette size={15} /> },
  { key: "voice", label: "语音", icon: <Mic size={15} /> },
  { key: "handwriting", label: "手写", icon: <PenTool size={15} /> },
  { key: "files", label: "文件", icon: <FileText size={15} /> },
  { key: "pomodoro", label: "番茄钟", icon: <Clock size={15} /> },
];

interface Props {
  activeTool?: ToolKey | null;
  onOpenTool?: (tool: ToolKey) => void;
}

export default function BottomDock({ activeTool, onOpenTool }: Props) {
  return (
    <div className="bd-root">
      {TOOLS.map((t) => (
        <button
          key={t.key}
          className={`bd-item ${activeTool === t.key ? "active" : ""}`}
          onClick={() => onOpenTool?.(t.key as ToolKey)}
          title={t.label}
        >
          {t.icon}
          <span className="bd-label">{t.label}</span>
        </button>
      ))}
    </div>
  );
}
