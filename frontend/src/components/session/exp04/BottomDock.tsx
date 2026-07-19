"use client";

import { StickyNote, Mic, Palette, PenTool, FileText, Clock, Search, FolderKanban, CheckSquare, Map, Network } from "lucide-react";

export type ToolKey = "flashcard" | "canvas" | "voice" | "handwriting" | "files" | "pomodoro" | "mindmap" | "practice" | "project" | "plan" | "search";

interface ToolItem {
  key: ToolKey;
  label: string;
  icon: React.ReactNode;
  badge?: string;       // 角标（如 "新"）
  count?: number;       // 数字气泡（如闪卡 3 张）
}

// ── Demo §dock 对齐：4 组分隔（学习工具 / 输入工具 / 时间工具 / 检索） ──
const TOOL_GROUPS: ToolItem[][] = [
  // 学习工具组
  [
    { key: "flashcard", label: "闪卡", icon: <StickyNote size={17} />, count: 3 },
    { key: "mindmap",   label: "导图", icon: <Network size={17} /> },
    { key: "canvas",    label: "画布", icon: <Palette size={17} /> },
    { key: "practice",  label: "练习", icon: <CheckSquare size={17} /> },
  ],
  // 输入工具组
  [
    { key: "voice",       label: "语音", icon: <Mic size={17} /> },
    { key: "handwriting", label: "手写", icon: <PenTool size={17} /> },
    { key: "files",       label: "文件", icon: <FileText size={17} /> },
  ],
  // 时间工具组
  [
    { key: "pomodoro", label: "番茄钟", icon: <Clock size={17} /> },
    { key: "project",  label: "项目",  icon: <FolderKanban size={17} />, badge: "新" },
    { key: "plan",     label: "规划",  icon: <Map size={17} /> },
  ],
  // 检索组
  [
    { key: "search", label: "搜索", icon: <Search size={17} /> },
  ],
];

interface Props {
  activeTool?: ToolKey | null;
  onOpenTool?: (tool: ToolKey) => void;
}

export default function BottomDock({ activeTool, onOpenTool }: Props) {
  return (
    <div className="bd-root">
      {TOOL_GROUPS.map((group, gi) => (
        <div className="dock-group" key={`g-${gi}`}>
          {group.map((t) => (
            <button
              key={t.key}
              className={`dock-item ${activeTool === t.key ? "active" : ""}`}
              onClick={() => onOpenTool?.(t.key)}
              title={t.label}
            >
              <span className="di-icon">{t.icon}</span>
              <span className="di-label">{t.label}</span>
              {typeof t.count === "number" && (
                <span className="di-count">{t.count}</span>
              )}
              {t.badge && <span className="di-badge">{t.badge}</span>}
            </button>
          ))}
          {gi < TOOL_GROUPS.length - 1 && <div className="dock-divider" />}
        </div>
      ))}
    </div>
  );
}
