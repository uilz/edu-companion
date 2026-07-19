"use client";

import React from "react";

// ─── Types ──────────────────────────────────────────────────────
export type TimelineItemType = "会话" | "笔记" | "视频" | "教材";

export interface TimelineItem {
  type: TimelineItemType;
  title: string;
  meta: string;
  sessionId?: string;
  isActive?: boolean;
  isStatic?: boolean;
}

export interface TimelineSection {
  dateLabel: string;
  sections: TimelineItem[];
}

export interface TimelineSidebarProps {
  timeline: TimelineSection[];
  /** Called when a clickable session item is clicked */
  onOpenSession?: (sessionId: string) => void;
}

// ─── Component ──────────────────────────────────────────────────
export default function TimelineSidebar({
  timeline,
  onOpenSession,
}: TimelineSidebarProps) {
  const todaySection = timeline[0];
  const isToday = (idx: number) => idx === 0;

  return (
    <nav
      className="flex flex-col h-full overflow-y-auto"
      style={{ background: "#f3eee7", borderRight: "1px solid #e6dcd0" }}
    >
      <div className="relative flex-1 py-4 pl-4 pr-2">
        {/* Vertical timeline line — positioned absolute at left */}
        <div
          className="absolute left-[18px] top-0 bottom-0 w-px"
          style={{ background: "#dcd0c2" }}
        />

        {timeline.map((section, sIdx) => (
          <div key={section.dateLabel} className="mb-4">
            {/* ── Section Header ── */}
            <div className="flex items-center gap-2 mb-[6px] relative z-[1]">
              <span
                className="w-[7px] h-[7px] rounded-full flex-shrink-0 -ml-[2px]"
                style={{
                  background: isToday(sIdx) ? "#8f7a62" : "#cec1b1",
                  transition: "background 0.1s",
                }}
              />
              <span
                className="text-[9px] font-semibold tracking-[0.02em]"
                style={{ color: "#a69c8f" }}
              >
                {section.dateLabel}
              </span>
            </div>

            {/* ── Section Items ── */}
            <div className="pl-[15px]">
              {section.sections.map((item, iIdx) => {
                const isClickable = !item.isStatic && !!item.sessionId;

                if (isClickable) {
                  return (
                    <button
                      key={`${section.dateLabel}-${iIdx}`}
                      onClick={() =>
                        item.sessionId && onOpenSession?.(item.sessionId)
                      }
                      className={`flex items-start gap-2 py-[5px] px-2 my-px rounded-md w-full text-left transition-colors duration-100 ${
                        item.isActive ? "bg-[rgba(143,122,98,0.1)]" : ""
                      }`}
                    >
                      <span
                        className="w-[3px] h-[3px] rounded-full flex-shrink-0 mt-[7px] ml-[2px]"
                        style={{
                          background: item.isActive ? "#8f7a62" : "#a69c8f",
                        }}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-baseline gap-[5px]">
                          <span
                            className="text-[9px] font-medium tracking-[0.02em] whitespace-nowrap"
                            style={{ color: "#a69c8f" }}
                          >
                            {item.type}
                          </span>
                          <span
                            className="text-[13px] font-medium whitespace-nowrap overflow-hidden text-ellipsis"
                            style={{ color: "#2a2420" }}
                          >
                            {item.title}
                          </span>
                        </div>
                        <div
                          className="text-[10px] mt-[2px] whitespace-nowrap overflow-hidden text-ellipsis"
                          style={{ color: "#a69c8f" }}
                        >
                          {item.meta}
                        </div>
                      </div>
                    </button>
                  );
                }

                // Static item (non-clickable)
                return (
                  <div
                    key={`${section.dateLabel}-${iIdx}`}
                    className="flex items-start gap-2 py-[5px] px-2 my-px rounded-md"
                    style={{ cursor: "default" }}
                  >
                    <span
                      className="w-[3px] h-[3px] rounded-full flex-shrink-0 mt-[7px] ml-[2px]"
                      style={{ background: "#a69c8f" }}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-[5px]">
                        <span
                          className="text-[9px] font-medium tracking-[0.02em] whitespace-nowrap"
                          style={{ color: "#a69c8f" }}
                        >
                          {item.type}
                        </span>
                        <span
                          className="text-[13px] font-medium whitespace-nowrap overflow-hidden text-ellipsis"
                          style={{ color: "#2a2420" }}
                        >
                          {item.title}
                        </span>
                      </div>
                      <div
                        className="text-[10px] mt-[2px] whitespace-nowrap overflow-hidden text-ellipsis"
                        style={{ color: "#a69c8f" }}
                      >
                        {item.meta}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </nav>
  );
}
