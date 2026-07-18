// ============================================================
// EXP-04 V2 · ENTER Screen
//
// 对齐 Vision (preview.html) 的 intro 屏：
//   - 一句 AI 引语
//   - "继续" 按钮
//   - "今天想学点别的" 文字链接
//   - 10 秒自动过渡
// ============================================================

"use client";

import { useState, useMemo, useEffect, useCallback } from "react";
import type { Exp04State } from "@/lib/exp04/types";

interface EnterScreenProps {
  engine: any;
  currentState: Exp04State;
  mission: { title: string } | null;
  lastTitle: string | null;
  onStart: () => void;
  transitioning: boolean;
}

export default function Exp04EnterScreen({
  engine,
  currentState,
  mission,
  lastTitle,
  onStart,
  transitioning,
}: EnterScreenProps) {
  // 问候文案
  const greeting = useMemo(() => {
    if (engine?.process) {
      const output = engine.process(currentState, "SESSION_ENTER", undefined, {
        last_title: lastTitle,
      });
      return output.message;
    }
    return null;
  }, [engine, currentState, lastTitle]);

  const title = mission?.title || "开始今天的学习";

  // ── 10 秒自动过渡 ──
  useEffect(() => {
    if (transitioning) return;
    const timer = setTimeout(() => {
      onStart();
    }, 10_000);
    return () => clearTimeout(timer);
  }, [onStart, transitioning]);

  const handleStart = useCallback(() => {
    onStart();
  }, [onStart]);

  // ── 渐进浮现 ──
  const [showMain, setShowMain] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setShowMain(true), 300);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="min-h-screen bg-page flex flex-col">
      {/* ── 主内容 ── */}
      <div className="flex-1 overflow-auto flex items-center justify-center">
        <div
          className={`max-w-lg mx-auto px-5 text-center transition-all duration-600 ease-out ${
            showMain ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
          }`}
        >
          {/* 标题 */}
          <h1 className="text-[28px] font-bold text-ink-primary leading-[1.2] mb-4 tracking-tight">
            {title}
          </h1>

          {/* AI 引语 */}
          <p className="text-[19px] text-ink-secondary leading-[1.6] font-medium mb-10">
            {greeting || "今天我们不用着急学会。先理解它为什么存在。"}
          </p>

          {/* 按钮 */}
          <div className="flex flex-col items-center gap-3">
            <button
              onClick={handleStart}
              disabled={transitioning}
              className="inline-flex items-center justify-center gap-2 h-14 px-10 rounded-full bg-[#0a84ff] text-white text-base font-semibold hover:bg-[#0070e0] transition-colors disabled:opacity-50"
            >
              {transitioning ? "准备中…" : "继续"}
            </button>
            <button
              onClick={handleStart}
              disabled={transitioning}
              className="text-sm text-ink-muted hover:text-ink-secondary transition-colors"
            >
              今天想学点别的
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
