"use client";

// ============================================================
//  ViewSwitcher — 5 视图切换器 (Task #89)
// ============================================================

import { FileText, ListTree, Trello, GitBranch, Activity } from "lucide-react";
import { ProjectViewName } from "../types";

export interface ViewSwitcherProps {
  current: ProjectViewName;
  onChange: (v: ProjectViewName) => void;
}

const TABS: { value: ProjectViewName; label: string; icon: React.ReactNode }[] = [
  { value: "document", label: "手稿", icon: <FileText size={14} /> },
  { value: "outline", label: "大纲", icon: <ListTree size={14} /> },
  { value: "kanban", label: "看板", icon: <Trello size={14} /> },
  { value: "knowledge", label: "知识图谱", icon: <GitBranch size={14} /> },
  { value: "activity", label: "活动流", icon: <Activity size={14} /> },
];

export function ViewSwitcher({ current, onChange }: ViewSwitcherProps) {
  return (
    <div className="flex items-center gap-1 mb-4 border-b border-divider overflow-x-auto">
      {TABS.map((t) => (
        <button
          key={t.value}
          onClick={() => onChange(t.value)}
          className={`px-4 py-2 text-sm flex items-center gap-1 whitespace-nowrap flex-shrink-0 ${
            current === t.value
              ? "border-b-2 border-accent text-accent"
              : "text-ink-secondary hover:text-ink-primary"
          }`}
        >
          {t.icon}
          {t.label}
        </button>
      ))}
    </div>
  );
}
