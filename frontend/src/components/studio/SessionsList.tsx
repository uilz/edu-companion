"use client";

import React from "react";

// ─── Types ──────────────────────────────────────────────────────
export type SessionStatus = "active" | "done" | "new";

export interface SessionItem {
  id: string;
  name: string;
  desc: string;
  progress: number; // 0-100
  status: SessionStatus;
  timeLabel: string;
}

export interface SessionsListProps {
  sessions: SessionItem[];
  onNewSession: () => void;
  onOpenSession: (sessionId: string) => void;
}

// ─── Component ──────────────────────────────────────────────────

const STATUS_DOT_CLASS: Record<SessionStatus, string> = {
  active: "active",
  done: "done",
  new: "new",
};

export default function SessionsList({
  sessions,
  onNewSession,
  onOpenSession,
}: SessionsListProps) {
  return (
    <div className="flex-1 max-w-[700px] mx-auto w-full py-8 px-8">
      {/* ── Title Row ── */}
      <div
        className="text-[11px] font-semibold tracking-[0.02em] mb-4 flex items-center justify-between"
        style={{ color: "#a69c8f" }}
      >
        <span>所有会话</span>
        <button
          onClick={onNewSession}
          className="px-4 py-[7px] rounded-full text-[13px] font-medium transition-colors duration-100 cursor-pointer"
          style={{
            border: "1.5px solid #dcd0c2",
            background: "#fff",
            color: "#2a2420",
          }}
        >
          ＋ 新建
        </button>
      </div>

      {/* ── Session Cards ── */}
      <div>
        {sessions.map((s) => (
          <div
            key={s.id}
            onClick={() => onOpenSession(s.id)}
            className="flex items-center gap-3 p-5 mb-2 rounded-2xl cursor-pointer transition-all duration-150 hover:-translate-y-px"
            style={{
              background: "#fff",
              boxShadow:
                "0 1px 2px rgba(0,0,0,0.04), 0 0 0 1px #e6dcd0",
            }}
          >
            {/* Status Dot */}
            <span
              className="w-[6px] h-[6px] rounded-full flex-shrink-0 mt-1"
              style={{
                background:
                  s.status === "active"
                    ? "#8f7a62"
                    : s.status === "done"
                      ? "#5a8f6b"
                      : "#a69c8f",
              }}
            />

            {/* Info */}
            <div className="flex-1 min-w-0">
              <div className="text-[15px] font-semibold" style={{ color: "#2a2420" }}>
                {s.name}
              </div>
              <div
                className="text-[13px] mt-[2px] whitespace-nowrap overflow-hidden text-ellipsis"
                style={{ color: "#7a7068" }}
              >
                {s.desc}
              </div>
              <div
                className="flex items-center gap-[10px] mt-1 text-[11px]"
                style={{ color: "#a69c8f" }}
              >
                {s.status === "done" ? (
                  <span>完成</span>
                ) : s.status === "new" ? (
                  <span>未开始</span>
                ) : (
                  <span>{s.progress}%</span>
                )}
                <span>{s.timeLabel}</span>
              </div>
            </div>

            {/* Progress Bar */}
            <div
              className="w-[52px] h-1 rounded-sm overflow-hidden flex-shrink-0"
              style={{ background: "#dcd0c2" }}
            >
              <div
                className="h-full rounded-sm"
                style={{
                  width: `${s.progress}%`,
                  background:
                    s.progress >= 100 ? "#5a8f6b" : "#8f7a62",
                }}
              />
            </div>

            {/* Arrow */}
            <span
              className="text-[12px] flex-shrink-0 opacity-50 transition-opacity duration-100 group-hover:opacity-100"
              style={{ color: "#a69c8f" }}
            >
              &rarr;
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
