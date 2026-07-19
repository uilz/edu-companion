"use client";

import React from "react";

// ─── Types ──────────────────────────────────────────────────────
export type StageStatus = "done" | "active" | "next" | "future";

export interface RoadmapStage {
  name: string;
  status: StageStatus;
  desc: string;
  stats: string;
  badge: string;
}

export interface PlanRoadmapProps {
  title: string;
  overallProgress: number;
  stages: RoadmapStage[];
}

// ─── Component ──────────────────────────────────────────────────

const STATUS_CSS: Record<
  StageStatus,
  { dot: string; dotBg: string; dotShadow: string; badge: string; badgeBg: string; isLast: boolean }
> = {
  done: {
    dot: "#5a8f6b",
    dotBg: "rgba(90,143,107,0.1)",
    dotShadow: "none",
    badge: "#5a8f6b",
    badgeBg: "rgba(90,143,107,0.1)",
    isLast: false,
  },
  active: {
    dot: "#8f7a62",
    dotBg: "rgba(143,122,98,0.1)",
    dotShadow: "0 0 0 4px rgba(143,122,98,0.1)",
    badge: "#8f7a62",
    badgeBg: "rgba(143,122,98,0.1)",
    isLast: false,
  },
  next: {
    dot: "#cec1b1",
    dotBg: "#f3eee7",
    dotShadow: "none",
    badge: "#a69c8f",
    badgeBg: "#e6dcd0",
    isLast: false,
  },
  future: {
    dot: "#cec1b1",
    dotBg: "#f3eee7",
    dotShadow: "none",
    badge: "#a69c8f",
    badgeBg: "#e6dcd0",
    isLast: true,
  },
};

const BADGE_LABELS: Record<StageStatus, string> = {
  done: "已掌握",
  active: "进行中",
  next: "下一个",
  future: "之后",
};

export default function PlanRoadmap({
  title,
  overallProgress,
  stages,
}: PlanRoadmapProps) {
  return (
    <div className="flex flex-col flex-1 py-4 px-8 max-w-[700px] mx-auto w-full">
      {/* ── Header ── */}
      <div className="flex items-center justify-between mb-5">
        <div className="text-[14px] font-semibold" style={{ color: "#2a2420" }}>
          {title}
        </div>
        <div className="text-[11px]" style={{ color: "#a69c8f" }}>
          总体进度{" "}
          <strong style={{ color: "#8f7a62", fontWeight: 600 }}>
            {overallProgress}%
          </strong>
        </div>
      </div>

      {/* ── Timeline ── */}
      <div className="relative pl-8 flex-1">
        {/* Vertical timeline line */}
        <div
          className="absolute left-[9px] top-2 bottom-2 w-[2px] rounded-[1px]"
          style={{ background: "#e6dcd0" }}
        />

        {stages.map((stage, i) => {
          const isLast = i === stages.length - 1;
          const s = STATUS_CSS[stage.status];

          return (
            <div key={stage.name} className="relative pb-5">
              {/* ── Marker (dot + connecting line) ── */}
              <div className="absolute left-[-32px] top-[2px] flex flex-col items-center">
                <div
                  className="w-5 h-5 rounded-full grid place-items-center text-[9px] border-2 flex-shrink-0 z-[1] transition-all duration-300"
                  style={{
                    borderColor: s.dot,
                    background: s.dotBg,
                    boxShadow: s.dotShadow,
                  }}
                >
                  {stage.status === "done" ? (
                    <span style={{ color: "#5a8f6b" }}>&#10003;</span>
                  ) : stage.status === "active" ? (
                    <span style={{ color: "#8f7a62" }}>&#9679;</span>
                  ) : null}
                </div>
                {!isLast && (
                  <div
                    className="w-[2px] flex-1 min-h-[20px] mt-1"
                    style={{ background: "#e6dcd0" }}
                  />
                )}
              </div>

              {/* ── Body ── */}
              <div className="pt-0">
                <span
                  className="inline-flex text-[9px] font-semibold tracking-[0.02em] px-2 py-[2px] rounded mb-1"
                  style={{
                    color: s.badge,
                    background: s.badgeBg,
                  }}
                >
                  {stage.badge || BADGE_LABELS[stage.status]}
                </span>
                <div className="text-[14px] font-semibold mb-[2px]" style={{ color: "#2a2420" }}>
                  {stage.name}
                </div>
                <div className="text-[13px] leading-[1.5]" style={{ color: "#7a7068" }}>
                  {stage.desc}
                </div>
                <div className="text-[11px] mt-1" style={{ color: "#a69c8f" }}>
                  {stage.stats}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
