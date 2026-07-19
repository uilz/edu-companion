"use client";

import React from "react";
import LearningSurface from "./LearningSurface";

// ─── Types ──────────────────────────────────────────────────────
export interface TodayProgress {
  title: string;
  desc: string;
  pct: number;
  remainingMin: number;
}

export interface AiGreeting {
  message: string;
  autoActions: string[];
}

export interface ToolFlowItem {
  label: string;
  status: "done" | "active" | "pending";
}

export interface ChatMessage {
  id: string;
  role: "ai" | "user";
  content: string;
}

export interface LearningFlowProps {
  todayProgress: TodayProgress;
  aiGreeting: AiGreeting;
  toolFlow: ToolFlowItem[];
  messages: ChatMessage[];
  activeSurfaceTab: string;
  onSurfaceTabChange: (tab: string) => void;
  onViewSessions: () => void;
  onStartSession: () => void;
}

// ─── Component ──────────────────────────────────────────────────
export default function LearningFlow({
  todayProgress,
  aiGreeting,
  toolFlow,
  messages,
  activeSurfaceTab,
  onSurfaceTabChange,
  onViewSessions,
  onStartSession,
}: LearningFlowProps) {
  const statusColor = (status: ToolFlowItem["status"]) => {
    switch (status) {
      case "done":
        return { border: "#5a8f6b", color: "#5a8f6b", bg: "rgba(90,143,107,0.1)" };
      case "active":
        return { border: "#8f7a62", color: "#8f7a62", bg: "rgba(143,122,98,0.1)" };
      default:
        return { border: "#cec1b1", color: "#7a7068", bg: "#fff" };
    }
  };

  return (
    <div className="flex flex-col flex-1 overflow-y-auto">
      {/* ── Today Progress Card ── */}
      <div className="flex flex-col gap-3 py-5 px-8 max-w-[700px] mx-auto w-full">
        <div
          className="text-[11px] font-semibold tracking-[0.02em] flex items-center gap-[6px]"
          style={{ color: "#a69c8f" }}
        >
          今天正在进行
        </div>
        <div
          className="flex items-center gap-3 rounded-2xl p-5"
          style={{
            background: "#fff",
            boxShadow:
              "0 1px 2px rgba(0,0,0,0.04), 0 0 0 1px #e6dcd0",
            cursor: "pointer",
          }}
          onClick={onStartSession}
        >
          <div
            className="text-[28px] flex-shrink-0"
            style={{ color: "#8f7a62", fontWeight: 700 }}
          >
            &rarr;
          </div>
          <div className="flex-1">
            <div
              className="text-[15px] font-semibold"
              style={{ color: "#2a2420" }}
            >
              {todayProgress.title}
            </div>
            <div
              className="text-[13px] mt-[2px]"
              style={{ color: "#7a7068" }}
            >
              {todayProgress.desc}
            </div>
            <div className="flex items-center gap-2 mt-2">
              <div
                className="flex-1 h-1 rounded-sm overflow-hidden"
                style={{ background: "#dcd0c2" }}
              >
                <div
                  className="h-full rounded-sm transition-[width] duration-500"
                  style={{
                    width: `${todayProgress.pct}%`,
                    background: "#8f7a62",
                  }}
                />
              </div>
              <span
                className="text-[11px] font-medium"
                style={{ color: "#a69c8f" }}
              >
                剩余 ~{todayProgress.remainingMin}min
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ── AI Greeting Bubble ── */}
      <div className="flex gap-3 px-8 py-4 max-w-[700px] mx-auto w-full items-start">
        <div
          className="w-9 h-9 rounded-full grid place-items-center text-[16px] font-semibold flex-shrink-0 mt-[2px]"
          style={{ background: "#8f7a62", color: "#fff" }}
        >
          果
        </div>
        <div
          className="flex-1 rounded-2xl p-5 text-[14px] leading-[1.8]"
          style={{
            background: "#fff",
            color: "#7a7068",
            boxShadow:
              "0 1px 2px rgba(0,0,0,0.04), 0 0 0 1px #e6dcd0",
          }}
        >
          <strong style={{ color: "#2a2420", fontWeight: 600 }}>
            {aiGreeting.message}
          </strong>
          {aiGreeting.autoActions.length > 0 && (
            <div
              className="mt-3 p-3 rounded-md text-[13px]"
              style={{
                background: "rgba(90,143,107,0.1)",
                borderLeft: "2px solid #5a8f6b",
                color: "#2a2420",
              }}
            >
              {aiGreeting.autoActions.map((action, i) => (
                <span key={i} className="block py-[2px]">
                  {action}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Tool Flow Chain ── */}
      <div className="px-8 py-4 max-w-[700px] mx-auto w-full">
        <div
          className="text-[9px] font-semibold tracking-[0.03em] mb-3 flex items-center gap-[5px]"
          style={{ color: "#a69c8f" }}
        >
          工具之间的流动
        </div>
        <div className="flex items-center gap-[6px] flex-wrap">
          {toolFlow.map((item, i) => (
            <React.Fragment key={item.label}>
              <span
                className="inline-flex items-center gap-[5px] px-[14px] py-[6px] rounded-full text-[12px] font-medium cursor-pointer transition-colors duration-100"
                style={{
                  background: statusColor(item.status).bg,
                  color: statusColor(item.status).color,
                  border: `1.5px solid ${statusColor(item.status).border}`,
                }}
              >
                {item.label}
              </span>
              {i < toolFlow.length - 1 && (
                <span
                  className="text-[12px] flex-shrink-0"
                  style={{ color: "#a69c8f", opacity: 0.4 }}
                >
                  &rarr;
                </span>
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* ── Learning Surface (4 tabs) ── */}
      <LearningSurface
        activeTab={activeSurfaceTab}
        onTabChange={onSurfaceTabChange}
        messages={messages}
      />

      {/* ── View All Sessions Button ── */}
      <div className="text-center py-4 pb-8">
        <button
          onClick={onViewSessions}
          className="px-5 py-2 rounded-full text-[13px] font-medium transition-colors duration-100 cursor-pointer"
          style={{
            border: "1.5px solid #cec1b1",
            background: "#fff",
            color: "#7a7068",
          }}
        >
          查看所有会话 &rarr;
        </button>
      </div>
    </div>
  );
}
