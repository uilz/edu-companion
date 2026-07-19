"use client";

import React, { useState, useRef, useEffect } from "react";
import { Search } from "lucide-react";
import type { WorkspaceItem } from "./Landing";
import type { LayoutMode } from "./StudioLayout";

// ─── Types ──────────────────────────────────────────────────────
export interface StudioHeaderProps {
  /** Available workspaces */
  workspaces: WorkspaceItem[];
  /** Currently selected workspace */
  currentWorkspace: WorkspaceItem | null;
  /** Mission area label (e.g. "学习流" / "会话列表" / "学习中") */
  missionLabel: string;
  /** Mission area title */
  missionTitle: string;
  /** Whether user is in an active session */
  inSession: boolean;
  /** Progress percentage (0-100), used in session indicators */
  progress: number;
  /** Current layout mode */
  layoutMode: LayoutMode;
  /** Layout mode change handler */
  onModeChange: (mode: LayoutMode) => void;
  /** Search button click handler */
  onSearch: () => void;
  /** Back button click handler (navigate to landing) */
  onBack: () => void;
  /** Workspace change handler */
  onWorkspaceChange: (workspaceId: string) => void;
}

// ─── Component ──────────────────────────────────────────────────

const MODE_LABELS: Record<LayoutMode, string> = {
  explore: "浏览",
  dialogue: "对话",
  focus: "专注",
};

export default function StudioHeader({
  workspaces,
  currentWorkspace,
  missionLabel,
  missionTitle,
  inSession,
  progress,
  layoutMode,
  onModeChange,
  onSearch,
  onBack,
  onWorkspaceChange,
}: StudioHeaderProps) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const selectorRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (
        selectorRef.current &&
        !selectorRef.current.contains(e.target as Node)
      ) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("click", handleClick);
    return () => document.removeEventListener("click", handleClick);
  }, []);

  const wsIcon = currentWorkspace?.icon || "?";
  const wsName = currentWorkspace?.name || "选择工作区";

  // Stage dots: 4 dots, active stage = 1 if progress < 100, else 3
  const activeStage = progress >= 100 ? 3 : 1;

  return (
    <div
      className="sh-root"
      style={{ background: "#faf9f6" }}
    >
      {/* ── Back Button ── */}
      <button
        className="sh-back"
        onClick={onBack}
        title="返回启动页"
        style={{ fontSize: "18px" }}
      >
        &larr;
      </button>

      {/* ── Workspace Selector ── */}
      <div
        ref={selectorRef}
        className={`sh-ws-selector relative flex-shrink-0 ${dropdownOpen ? "open" : ""}`}
      >
        <button
          onClick={() => setDropdownOpen((v) => !v)}
          className="flex items-center gap-[6px] px-[14px] py-[7px] rounded-md text-[14px] font-semibold transition-colors duration-100"
          style={{ background: "#f3eee7" }}
        >
          <span className="text-[10px] font-bold" style={{ color: "#7a7068" }}>
            {wsIcon}
          </span>
          <span style={{ color: "#2a2420" }}>{wsName}</span>
          <span className="text-[8px]" style={{ color: "#a69c8f" }}>
            &#9662;
          </span>
        </button>

        {/* ── Dropdown ── */}
        {dropdownOpen && (
          <div
            className="absolute top-full left-0 mt-[6px] rounded-xl overflow-hidden z-20 w-[190px]"
            style={{
              background: "#fff",
              boxShadow: "0 8px 32px rgba(0,0,0,0.08)",
              animation: "fadeInUp 0.15s cubic-bezier(0.4,0,0.2,1)",
            }}
          >
            {workspaces.map((ws) => (
              <button
                key={ws.id}
                onClick={() => {
                  onWorkspaceChange(ws.id);
                  setDropdownOpen(false);
                }}
                className={`flex items-center gap-[10px] px-4 py-[11px] w-full text-left text-[13px] transition-colors duration-100 ${
                  currentWorkspace?.id === ws.id
                    ? "font-semibold"
                    : ""
                }`}
                style={{
                  background:
                    currentWorkspace?.id === ws.id
                      ? "rgba(143,122,98,0.1)"
                      : "transparent",
                  color:
                    currentWorkspace?.id === ws.id
                      ? "#8f7a62"
                      : "#2a2420",
                }}
              >
                <span className="text-[18px]">{ws.icon}</span>
                {ws.name}
              </button>
            ))}
            <div
              className="mx-0 my-1"
              style={{ borderTop: "1px solid #e6dcd0" }}
            />
            <button
              onClick={() => {
                setDropdownOpen(false);
                // reserved for new workspace
              }}
              className="flex items-center gap-[10px] px-4 py-[11px] w-full text-left text-[13px] transition-colors duration-100"
              style={{ color: "#7a7068" }}
            >
              <span className="text-[18px]">+</span>
              新建工作区
            </button>
          </div>
        )}
      </div>

      {/* ── Mission Area ── */}
      <div className="sh-mission flex-1 min-w-0">
        <div className="sh-m-label">{missionLabel}</div>
        <div className="sh-m-title">{missionTitle}</div>
      </div>

      {/* ── Controls Group ── */}
      <div className="flex items-center gap-[6px] flex-shrink-0">
        {/* Session Indicators (only visible in session) */}
        <div
          className="sh-session-indicators"
          style={{ display: inSession ? "flex" : "none" }}
        >
          {/* Stage Dots */}
          <div className="sh-stage-dots">
            {[0, 1, 2, 3].map((i) => (
              <span
                key={i}
                className={`stage-dot${
                  i === activeStage
                    ? " active"
                    : i < activeStage
                      ? " done"
                      : ""
                }`}
              />
            ))}
          </div>
          {/* Progress Bar */}
          <div className="sh-progress-bar">
            <div
              className="sh-progress-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* ── Mode Toggle ── */}
        <div className="sh-mode-toggle">
          {(Object.keys(MODE_LABELS) as LayoutMode[]).map((mode) => (
            <button
              key={mode}
              className={`sh-mode-btn${layoutMode === mode ? " active" : ""}`}
              onClick={() => onModeChange(mode)}
            >
              {MODE_LABELS[mode]}
            </button>
          ))}
        </div>

        {/* ── Search Button ── */}
        <button
          className="sh-search-btn"
          onClick={onSearch}
          title="全局搜索"
        >
          <Search size={15} />
        </button>
      </div>
    </div>
  );
}
