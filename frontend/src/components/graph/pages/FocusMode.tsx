"use client";

import React, { useState, useCallback } from "react";
import { Focus, X, Volume2, ChevronDown, Brain } from "lucide-react";

interface FocusModeProps {
  /** 当前知识节点标签 */
  currentTopic?: string;
  /** 认知负荷 0-1 */
  cognitiveLoad?: number;
  /** 打开/关闭 */
  open: boolean;
  /** 当前目标 */
  currentGoal?: string;
  /** 关闭专注模式 */
  onExit: () => void;
  /** 子元素：对话区域 */
  children?: React.ReactNode;
}

/**
 * 专注模式（10.1）
 * 基于认知负荷的自适应极简学习界面。
 * 全屏覆盖，仅保留核心对话流 + 认知负荷指示器 + 当前目标。
 */
export default function FocusMode({
  currentTopic,
  cognitiveLoad = 0.3,
  open,
  currentGoal,
  onExit,
  children,
}: FocusModeProps) {
  const [showGoal, setShowGoal] = useState(true);

  // Cognitive load level
  const loadLevel =
    cognitiveLoad < 0.3
      ? "低"
      : cognitiveLoad < 0.6
        ? "中"
        : cognitiveLoad < 0.8
          ? "高"
          : "极高";

  const loadColor =
    cognitiveLoad < 0.3
      ? "var(--color-success)"
      : cognitiveLoad < 0.6
        ? "var(--color-accent)"
        : cognitiveLoad < 0.8
          ? "var(--color-warning)"
          : "var(--color-error)";

  const loadDotCount =
    cognitiveLoad < 0.3 ? 1 : cognitiveLoad < 0.6 ? 2 : cognitiveLoad < 0.8 ? 3 : 4;

  if (!open) return <>{children}</>;

  return (
    <>
      {/* Backdrop dim + focus wrapper */}
      <div className="fixed inset-0 z-40 flex flex-col bg-page/95 backdrop-blur-sm">
        {/* Top bar: minimal controls */}
        <div className="flex items-center justify-between px-6 py-3 border-b border/20">
          {/* Left: topic indicator */}
          <div className="flex items-center gap-3">
            {currentTopic && (
              <div className="flex items-center gap-2">
                <Brain size={16} className="text-accent" />
                <span className="text-sm font-medium text">
                  {currentTopic}
                </span>
              </div>
            )}

            {/* Mini cognitive load indicator */}
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-surface-hover/50">
              <div className="flex gap-0.5">
                {[1, 2, 3, 4].map((i) => (
                  <div
                    key={i}
                    className={`w-1.5 h-3 rounded-full transition-all duration-500 ${
                      i <= loadDotCount
                        ? "opacity-100"
                        : "opacity-20"
                    }`}
                    style={{ backgroundColor: i <= loadDotCount ? loadColor : "var(--color-text-muted)" }}
                  />
                ))}
              </div>
              <span className="text-[10px] text-muted ml-1">
                负荷{loadLevel}
              </span>
            </div>
          </div>

          {/* Right: goal + exit */}
          <div className="flex items-center gap-2">
            {currentGoal && (
              <button
                onClick={() => setShowGoal(!showGoal)}
                className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] text-muted hover:text hover:bg-surface-hover/50 transition-colors"
              >
                <span className="max-w-[160px] truncate">{currentGoal}</span>
                <ChevronDown
                  size={10}
                  className={`transition-transform ${showGoal ? "rotate-180" : ""}`}
                />
              </button>
            )}

            <button
              onClick={onExit}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs text-muted hover:text hover:bg-surface-hover/60 border border/30 hover:border/60 transition-all opacity-60 hover:opacity-100"
            >
              <X size={12} />
              退出专注
            </button>
          </div>
        </div>

        {/* Goal bar (expandable) */}
        {currentGoal && showGoal && (
          <div className="flex items-center justify-center px-6 py-2 bg-accent/5 border-b border/10">
            <div className="flex items-center gap-2 text-xs text-muted">
              <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
              <span>当前目标：</span>
              <span className="font-medium text">{currentGoal}</span>
            </div>
          </div>
        )}

        {/* Main content: focused conversation */}
        <div className="flex-1 overflow-y-auto px-6 py-4 max-w-3xl mx-auto w-full">
          {/* Socratic emphasis indicator */}
          <div className="flex items-center gap-2 mb-4 text-[11px] text-accent/70">
            <Focus size={12} />
            <span>苏格拉底模式 · 试着先自己思考，再与AI对话</span>
          </div>

          {children || (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 rounded-full bg-accent/10 flex items-center justify-center mb-4">
                <Focus size={28} className="text-accent" />
              </div>
              <p className="text-sm text-muted">
                选择一个知识点，开始专注学习
              </p>
              <p className="text-xs text-muted mt-1 opacity-60">
                在专注模式下，系统会引导你通过提问和思考来深入理解
              </p>
            </div>
          )}
        </div>

        {/* Bottom: minimal input area hint */}
        <div className="px-6 py-3 border-t border/20">
          <div className="max-w-3xl mx-auto flex items-center gap-3">
            <div className="flex-1 h-9 rounded-lg border border/40 bg-surface/50 flex items-center px-3 text-xs text-muted opacity-60">
              在此输入你的问题或思考...
            </div>
            <button className="p-2 rounded-lg bg-accent/10 text-accent hover:bg-accent/20 transition-colors">
              <Volume2 size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* Original content hidden behind */}
      <div className="hidden">{children}</div>
    </>
  );
}
