"use client";

import React, { useMemo } from "react";
import { Search } from "lucide-react";

// ─── Types ──────────────────────────────────────────────────────
export interface WorkspaceItem {
  id: string;
  icon: string;
  name: string;
  activeCount: number;
  completedCount: number;
}

export interface LandingMemory {
  workspaceName: string;
  topic: string;
}

export interface LandingProps {
  workspaces: WorkspaceItem[];
  memory: LandingMemory;
  onEnter: (workspaceId: string, sessionId?: string) => void;
  onSearch: (query: string) => void;
}

// ─── Helpers ────────────────────────────────────────────────────
function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 6) return "夜深了";
  if (hour < 9) return "早上好";
  if (hour < 12) return "上午好";
  if (hour < 14) return "中午好";
  if (hour < 18) return "下午好";
  return "晚上好";
}

function formatDate(): string {
  const now = new Date();
  const weekdays = ["日", "一", "二", "三", "四", "五", "六"];
  const y = now.getFullYear();
  const m = now.getMonth() + 1;
  const d = now.getDate();
  const w = weekdays[now.getDay()];
  return `${y}年${m}月${d}日 · 星期${w}`;
}

// ─── Component ──────────────────────────────────────────────────
export default function Landing({
  workspaces,
  memory,
  onEnter,
  onSearch,
}: LandingProps) {
  const greeting = useMemo(() => getGreeting(), []);
  const date = useMemo(() => formatDate(), []);

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      onSearch(e.currentTarget.value);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center min-h-screen px-6 py-10"
      style={{ background: "#f7f3ed" }}
    >
      <div className="max-w-[480px] w-full">
        {/* ── Greeting ── */}
        <div
          className="text-[34px] font-bold tracking-[-0.02em] mb-1"
          style={{
            color: "#2a2420",
            animation: "fadeIn 0.5s cubic-bezier(0.4,0,0.2,1)",
          }}
        >
          {greeting}，小新
        </div>

        {/* ── Date ── */}
        <div
          className="text-[13px] mb-8"
          style={{
            color: "#a69c8f",
            animation: "fadeIn 0.5s cubic-bezier(0.4,0,0.2,1) 0.1s both",
          }}
        >
          {date}
        </div>

        {/* ── Memory Narrative ── */}
        <div
          className="font-serif text-[15px] leading-[1.8] mb-8"
          style={{
            color: "#7a7068",
            animation: "fadeIn 0.5s cubic-bezier(0.4,0,0.2,1) 0.15s both",
          }}
        >
          上次在{" "}
          <strong style={{ color: "#8f7a62", fontWeight: 600 }}>
            {memory.workspaceName}
          </strong>{" "}
          里，你停在了 {memory.topic}。
          <br />
          今天要继续吗？
        </div>

        {/* ── CTA ── */}
        <div
          className="mb-8"
          style={{
            animation: "fadeIn 0.5s cubic-bezier(0.4,0,0.2,1) 0.2s both",
          }}
        >
          <button
            onClick={() => onEnter("math", "limits")}
            className="inline-flex items-center gap-2 px-8 py-[14px] text-[14px] font-semibold rounded-full transition-colors duration-150 active:scale-[0.97]"
            style={{ background: "#8f7a62", color: "#fff" }}
          >
            继续学习
            <span className="text-[15px]">&rarr;</span>
          </button>
          <div className="text-[11px] mt-2" style={{ color: "#a69c8f" }}>
            {memory.workspaceName} · {memory.topic}
          </div>
        </div>

        {/* ── Divider ── */}
        <div
          className="h-px mb-6"
          style={{
            background: "#e6dcd0",
            animation: "fadeIn 0.5s cubic-bezier(0.4,0,0.2,1) 0.25s both",
          }}
        />

        {/* ── Section Label ── */}
        <div
          className="text-[9px] font-semibold tracking-[0.02em] mb-3"
          style={{
            color: "#a69c8f",
            animation: "fadeIn 0.5s cubic-bezier(0.4,0,0.2,1) 0.28s both",
          }}
        >
          工作区
        </div>

        {/* ── Workspace List ── */}
        <div
          className="mb-6"
          style={{
            animation: "fadeIn 0.5s cubic-bezier(0.4,0,0.2,1) 0.3s both",
          }}
        >
          {workspaces.map((ws) => (
            <button
              key={ws.id}
              onClick={() => onEnter(ws.id)}
              className="flex items-center justify-between w-full py-3 text-left border-b transition-opacity duration-100 hover:opacity-70"
              style={{ borderColor: "#e6dcd0" }}
            >
              <span className="text-[14px] font-medium" style={{ color: "#2a2420" }}>
                {ws.name}
              </span>
              <span className="text-[11px]" style={{ color: "#a69c8f" }}>
                {ws.activeCount} 进行中 · {ws.completedCount} 已完成
              </span>
            </button>
          ))}
        </div>

        {/* ── Divider ── */}
        <div
          className="h-px mb-6"
          style={{
            background: "#e6dcd0",
            animation: "fadeIn 0.5s cubic-bezier(0.4,0,0.2,1) 0.25s both",
          }}
        />

        {/* ── Search ── */}
        <div
          style={{
            animation: "fadeIn 0.5s cubic-bezier(0.4,0,0.2,1) 0.33s both",
          }}
        >
          <div className="relative">
            <Search
              className="absolute left-3 top-1/2 -translate-y-1/2"
              size={14}
              style={{ color: "#a69c8f" }}
            />
            <input
              type="text"
              placeholder="搜索资源、对话、闪卡..."
              onKeyDown={handleSearchKeyDown}
              className="w-full py-3 pl-9 pr-4 text-[13px] rounded-full border-[1.5px] outline-none transition-colors duration-150"
              style={{
                borderColor: "#dcd0c2",
                background: "#fff",
                color: "#2a2420",
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = "#8f7a62";
                e.currentTarget.style.boxShadow =
                  "0 0 0 3px rgba(143,122,98,0.1)";
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = "#dcd0c2";
                e.currentTarget.style.boxShadow = "none";
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
