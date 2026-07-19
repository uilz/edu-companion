"use client";

import React from "react";

// ─── Types ──────────────────────────────────────────────────────
export type LayoutMode = "explore" | "dialogue" | "focus";

export interface StudioLayoutProps {
  /** Content for the header zone (grid-area: header) */
  header: React.ReactNode;
  /** Content for the sidebar zone (grid-area: sidebar) */
  sidebar: React.ReactNode;
  /** Content for the canvas zone (grid-area: canvas) */
  canvas: React.ReactNode;
  /** Content for the companion zone (grid-area: companion) */
  companion: React.ReactNode;
  /** Content for the dock zone (grid-area: dock) */
  dock: React.ReactNode;
  /** Current layout mode */
  layoutMode: LayoutMode;
  /** Mode change handler */
  setLayoutMode: (mode: LayoutMode) => void;
}

// ─── Component ──────────────────────────────────────────────────
export default function StudioLayout({
  header,
  sidebar,
  canvas,
  companion,
  dock,
  layoutMode,
}: StudioLayoutProps) {
  const isVisible = true; // always visible when rendered

  const modeClass =
    layoutMode === "explore"
      ? ""
      : layoutMode === "dialogue"
        ? "mode-dialogue"
        : "mode-focus";

  return (
    <div
      className={`studio-root ${modeClass}${isVisible ? " visible" : ""}`}
      style={{
        display: "grid",
      }}
    >
      {/* ── Header (grid-area: header) ── */}
      <div className="studio-header">{header}</div>

      {/* ── Sidebar (grid-area: sidebar) ── */}
      <div className="studio-sidebar">{sidebar}</div>

      {/* ── Canvas (grid-area: canvas) ── */}
      <div className="studio-canvas">{canvas}</div>

      {/* ── Companion (grid-area: companion) ── */}
      <div className="studio-companion">{companion}</div>

      {/* ── Dock (grid-area: dock) ── */}
      <div className="studio-dock">{dock}</div>

      {/* ── Focus Mode: Floating AI Button ── */}
      {layoutMode === "focus" && (
        <button
          className="sh-focus-ai"
          title="打开 AI 对话"
          onClick={() => {
            /* reserved for future AI toggle in focus mode */
          }}
        >
          <span role="img" aria-label="AI">
            果
          </span>
        </button>
      )}
    </div>
  );
}
