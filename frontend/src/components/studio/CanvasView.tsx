"use client";

import React from "react";
import LearningFlow, {
  type LearningFlowProps,
} from "./LearningFlow";
import SessionsList, {
  type SessionsListProps,
} from "./SessionsList";
import PlanRoadmap, {
  type PlanRoadmapProps,
} from "./PlanRoadmap";

// ─── Types ──────────────────────────────────────────────────────
export type CanvasViewType = "flow" | "sessions" | "plan" | "session" | "rag";

export interface CanvasViewProps {
  currentView: CanvasViewType;
  /** Props for LearningFlow */
  learningFlow?: LearningFlowProps;
  /** Props for SessionsList */
  sessionsList?: SessionsListProps;
  /** Props for PlanRoadmap */
  planRoadmap?: PlanRoadmapProps;
  /** RAG search or session content — rendered as React child */
  children?: React.ReactNode;
}

// ─── Component ──────────────────────────────────────────────────
export default function CanvasView({
  currentView,
  learningFlow,
  sessionsList,
  planRoadmap,
  children,
}: CanvasViewProps) {
  return (
    <div
      className="flex flex-col overflow-y-auto"
      style={{ background: "#faf9f6" }}
    >
      {currentView === "flow" && learningFlow && (
        <LearningFlow {...learningFlow} />
      )}
      {currentView === "sessions" && sessionsList && (
        <SessionsList {...sessionsList} />
      )}
      {currentView === "plan" && planRoadmap && (
        <PlanRoadmap {...planRoadmap} />
      )}
      {currentView === "session" && (
        <div className="flex flex-col flex-1">{children}</div>
      )}
      {currentView === "rag" && (
        <div className="flex flex-col flex-1">{children}</div>
      )}
    </div>
  );
}
