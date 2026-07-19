"use client";

import React from "react";

// ─── Types ──────────────────────────────────────────────────────
export interface ChatMessage {
  id: string;
  role: "ai" | "user";
  content: string;
}

export interface LearningSurfaceProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  messages: ChatMessage[];
}

const TABS = [
  { key: "chat", label: "对话" },
  { key: "canvas", label: "画布" },
  { key: "pdf", label: "教材" },
  { key: "video", label: "视频" },
];

// ─── Component ──────────────────────────────────────────────────
export default function LearningSurface({
  activeTab,
  onTabChange,
  messages,
}: LearningSurfaceProps) {
  return (
    <div className="flex flex-col flex-1 px-8 py-4 pb-8 max-w-[700px] mx-auto w-full">
      {/* ── Tab Bar ── */}
      <div className="flex gap-[2px] mb-3">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => onTabChange(tab.key)}
            className="px-[14px] py-[7px] rounded-t-md text-[12px] font-medium transition-colors duration-100 cursor-pointer border-b-2"
            style={{
              color: activeTab === tab.key ? "#8f7a62" : "#a69c8f",
              background:
                activeTab === tab.key
                  ? "rgba(143,122,98,0.1)"
                  : "transparent",
              borderBottomColor:
                activeTab === tab.key ? "#8f7a62" : "transparent",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Panel Content ── */}
      <div
        className="rounded-b-xl rounded-r-xl p-5 flex-1 min-h-[200px] overflow-y-auto"
        style={{
          background: "#fff",
          boxShadow:
            "0 1px 2px rgba(0,0,0,0.04), 0 0 0 1px #e6dcd0",
        }}
      >
        {/* Chat Panel */}
        {activeTab === "chat" && (
          <div className="flex flex-col gap-3">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-[10px] items-end ${
                  msg.role === "user" ? "flex-row-reverse" : ""
                }`}
              >
                {/* Avatar */}
                {msg.role === "ai" ? (
                  <div
                    className="w-7 h-7 rounded-full grid place-items-center text-[13px] font-semibold flex-shrink-0"
                    style={{ background: "#8f7a62", color: "#fff" }}
                  >
                    果
                  </div>
                ) : (
                  <div
                    className="w-7 h-7 rounded-md grid place-items-center text-[11px] font-semibold flex-shrink-0"
                    style={{ background: "#8f7a62", color: "#fff" }}
                  >
                    小
                  </div>
                )}
                {/* Bubble */}
                <div
                  className="max-w-[85%] py-[10px] px-[14px] text-[13px] leading-[1.6]"
                  style={{
                    background:
                      msg.role === "ai" ? "#f3eee7" : "#efe9e1",
                    borderRadius:
                      msg.role === "ai"
                        ? "4px 12px 12px 12px"
                        : "12px 12px 4px 12px",
                    color: "#2a2420",
                  }}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {messages.length === 0 && (
              <div
                className="text-[13px] py-6 text-center"
                style={{ color: "#a69c8f" }}
              >
                暂无对话
              </div>
            )}
          </div>
        )}

        {/* Canvas Panel */}
        {activeTab === "canvas" && (
          <div
            className="h-[160px] rounded-lg flex flex-col items-center justify-center text-[13px] gap-[6px]"
            style={{ background: "#efe9e1", color: "#a69c8f" }}
          >
            Canvas 画布区域
            <span className="text-[10px]" style={{ color: "#a69c8f" }}>
              点击恢复编辑
            </span>
          </div>
        )}

        {/* PDF / Textbook Panel */}
        {activeTab === "pdf" && (
          <div className="flex flex-col gap-[6px]">
            <div
              className="text-[12px] font-semibold"
              style={{ color: "#7a7068" }}
            >
              教材内容
            </div>
            <div
              className="h-[140px] rounded flex items-center justify-center text-[12px]"
              style={{ background: "#efe9e1", color: "#a69c8f" }}
            >
              PDF 阅读器区域
            </div>
            <div className="text-[11px]" style={{ color: "#a69c8f" }}>
              自动滚动到上次位置
            </div>
          </div>
        )}

        {/* Video Panel */}
        {activeTab === "video" && (
          <div className="flex flex-col gap-[6px]">
            <div
              className="text-[12px] font-semibold"
              style={{ color: "#7a7068" }}
            >
              视频播放器
            </div>
            <div
              className="h-[140px] rounded flex items-center justify-center text-[12px]"
              style={{ background: "#222", color: "#999" }}
            >
              视频播放区域
            </div>
            <div className="text-[11px]" style={{ color: "#a69c8f" }}>
              上次播放到 0:00
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
