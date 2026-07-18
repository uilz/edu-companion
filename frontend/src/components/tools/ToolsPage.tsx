"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Brain,
  BookOpen,
  Mic,
  Puzzle,
  PenTool,
  FileText,
  Timer,
  Settings,
} from "lucide-react";
import PomodoroPanel from "@/components/session/exp04/PomodoroPanel";
import HandwritingPanel from "@/components/session/exp04/HandwritingPanel";
import CanvasPanel from "@/components/session/exp04/CanvasPanel";
import FileListPanel from "@/components/session/exp04/FileListPanel";
import VoicePanel from "@/components/session/exp04/VoicePanel";
import ToolsReader from "./ToolsReader";
import ToolsPreferences from "./ToolsPreferences";

// ── Tool card definitions ──────────────────────────────────

interface ToolCard {
  key: string;
  icon: React.ReactNode;
  bg: string;
  title: string;
  desc: string;
}

const TOOLS: ToolCard[] = [
  {
    key: "reader",
    icon: <BookOpen size={22} />,
    bg: "bg-teal-500/10 text-teal-600",
    title: "阅读",
    desc: "划线就能做卡片",
  },
  {
    key: "voice",
    icon: <Mic size={22} />,
    bg: "bg-pink-500/10 text-pink-600",
    title: "语音房间",
    desc: "和 AI 练口语",
  },
  {
    key: "flashcard",
    icon: <Brain size={22} />,
    bg: "bg-purple-500/10 text-purple-600",
    title: "卡片",
    desc: "记忆调度复习",
  },
  {
    key: "canvas",
    icon: <Puzzle size={22} />,
    bg: "bg-blue-500/10 text-blue-600",
    title: "画布",
    desc: "把概念连起来",
  },
  {
    key: "handwriting",
    icon: <PenTool size={22} />,
    bg: "bg-amber-500/10 text-amber-600",
    title: "手写",
    desc: "随手演算笔记",
  },
  {
    key: "files",
    icon: <FileText size={22} />,
    bg: "bg-teal-500/10 text-teal-600",
    title: "文件",
    desc: "知识文件管理",
  },
  {
    key: "pomodoro",
    icon: <Timer size={22} />,
    bg: "bg-red-500/10 text-red-600",
    title: "番茄钟",
    desc: "规划与追踪",
  },
  {
    key: "preferences",
    icon: <Settings size={22} />,
    bg: "bg-gray-500/10 text-gray-600",
    title: "偏好",
    desc: "一言、信息源设置",
  },
];

// ── Component ──────────────────────────────────────────────

export default function ToolsPage() {
  const router = useRouter();

  // Active tool panel state
  const [activeTool, setActiveTool] = useState<string | null>(null);

  const openTool = useCallback(
    (key: string) => {
      switch (key) {
        // Standalone overlays — reuse existing panels
        case "pomodoro":
        case "handwriting":
        case "canvas":
        case "files":
        case "voice":
        case "reader":
        case "preferences":
          setActiveTool(key);
          break;
        // Session-dependent — navigate to Today to start a session
        case "flashcard":
          router.push("/");
          break;
        default:
          break;
      }
    },
    [router],
  );

  const closeTool = useCallback(() => setActiveTool(null), []);

  return (
    <div className="animate-in fade-in">
      <h1 className="text-[28px] font-bold tracking-tight mb-6">
        我的学习工具箱
      </h1>

      {/* ── Tool grid ── */}
      <div className="grid grid-cols-2 gap-3">
        {TOOLS.map((tool) => (
          <button
            key={tool.key}
            onClick={() => openTool(tool.key)}
            className="flex flex-col gap-2.5 p-5 rounded-[18px] bg-surface border border-divider-soft text-left transition-all duration-200 hover:shadow-[0_4px_16px_rgba(0,0,0,0.06)] hover:border-divider-hover hover:-translate-y-0.5 active:scale-[0.98]"
          >
            <div
              className={`w-11 h-11 rounded-xl flex items-center justify-center ${tool.bg}`}
            >
              {tool.icon}
            </div>
            <div>
              <div className="text-[15px] font-semibold">{tool.title}</div>
              <div className="text-[12.5px] text-ink-muted leading-relaxed">
                {tool.desc}
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* ── Tool overlays ── */}
      <ToolOverlay
        open={activeTool === "pomodoro"}
        onClose={closeTool}
        label="番茄钟 · 今日规划"
      >
        <PomodoroPanel open={true} onClose={closeTool} />
      </ToolOverlay>

      <ToolOverlay
        open={activeTool === "handwriting"}
        onClose={closeTool}
        label="手写演算"
      >
        <HandwritingPanel open={true} onClose={closeTool} />
      </ToolOverlay>

      <ToolOverlay
        open={activeTool === "canvas"}
        onClose={closeTool}
        label="概念画布"
      >
        <CanvasPanel open={true} onClose={closeTool} />
      </ToolOverlay>

      <ToolOverlay
        open={activeTool === "files"}
        onClose={closeTool}
        label="知识文件"
      >
        <FileListPanel open={true} onClose={closeTool} />
      </ToolOverlay>

      <ToolOverlay
        open={activeTool === "voice"}
        onClose={closeTool}
        label="口语练习房间"
      >
        <VoicePanel open={true} onClose={closeTool} />
      </ToolOverlay>

      <ToolOverlay
        open={activeTool === "reader"}
        onClose={closeTool}
        label="阅读"
      >
        <ToolsReader onClose={closeTool} />
      </ToolOverlay>

      <ToolOverlay
        open={activeTool === "preferences"}
        onClose={closeTool}
        label="偏好"
      >
        <ToolsPreferences onClose={closeTool} />
      </ToolOverlay>
    </div>
  );
}

// ── Tool overlay wrapper ───────────────────────────────────

function ToolOverlay({
  open,
  onClose,
  label,
  children,
}: {
  open: boolean;
  onClose: () => void;
  label: string;
  children: React.ReactNode;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-page animate-in slide-in-from-bottom-4 duration-300">
      {/* Top bar */}
      <div className="flex items-center gap-3 px-4 py-3.5 bg-surface/88 backdrop-blur-xl border-b border-divider">
        <button
          onClick={onClose}
          className="w-9 h-9 rounded-full grid place-items-center text-ink-secondary hover:bg-surface-hover transition-colors"
          aria-label="返回"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            width="22"
            height="22"
          >
            <path
              d="M15 18l-6-6 6-6"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
        <div className="flex-1 text-[15px] font-semibold truncate">
          {label}
        </div>
        <div style={{ width: 36 }} />
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto">{children}</div>
    </div>
  );
}
