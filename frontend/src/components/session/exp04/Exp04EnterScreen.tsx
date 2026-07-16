// ============================================================
// EXP-04 V2 · ENTER Screen
//
// "一本书正在陪你学习"
//
// 视觉语言（来自 preview.html）：
//   - 暖米色背景 + 白色卡片
//   - 大字标题 34px
//   - 金色点缀（tag / dot / 按钮）
//   - 大圆角（22px / 38px）
//   - SF Pro Display 字体家族
//
// 内容：
//   ① Today's Mission tag
//   ② 大标题
//   ③ 温柔副标题
//   ④ Mission 卡片（3 个目标点）
//   ⑤ "开始" 按钮
// ============================================================

"use client";

import { useState, useMemo, useRef, useEffect, useCallback } from "react";
import type { Exp04State } from "@/lib/exp04/types";

// ── Props ──

interface MissionStep {
  order: number;
  description: string;
  type: "explain" | "practice" | "review";
}

interface EnterScreenProps {
  engine: any;
  currentState: Exp04State;
  mission: { title: string; steps: MissionStep[] } | null;
  lastTitle: string | null;
  onStart: () => void;
  transitioning: boolean;
}

// ── 组件 ──

export default function Exp04EnterScreen({
  engine,
  currentState,
  mission,
  lastTitle,
  onStart,
  transitioning,
}: EnterScreenProps) {
  // 问候文案（兼容旧 engine）
  const greeting = useMemo(() => {
    if (engine?.process) {
      const output = engine.process(currentState, "SESSION_ENTER", undefined, {
        last_title: lastTitle,
      });
      return output.message;
    }
    return null;
  }, [engine, currentState, lastTitle]);

  // Mission 步骤
  const missionSteps = useMemo(() => {
    if (!mission?.steps?.length) return null;
    return mission.steps
      .sort((a, b) => a.order - b.order)
      .map((s) => s.description)
      .filter(Boolean);
  }, [mission]);

  // ── 自动过渡 ──
  const enterStartRef = useRef(Date.now());
  useEffect(() => {
    enterStartRef.current = Date.now();
  }, []);

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
  const [showFooter, setShowFooter] = useState(false);
  useEffect(() => {
    const t1 = setTimeout(() => setShowMain(true), 300);
    const t2 = setTimeout(() => setShowFooter(true), 800);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, []);

  const title = mission?.title || "开始今天的学习";

  return (
    <div className="min-h-screen bg-page flex flex-col">
      {/* ── 主内容 ── */}
      <div className="flex-1 overflow-auto">
        <div className="max-w-lg mx-auto px-5 pt-10 sm:pt-14">
          {/* 渐进浮现容器 */}
          <div
            className={`transition-all duration-600 ease-out ${
              showMain ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
            }`}
          >
            {/* Tag */}
            <span className="inline-block px-3.5 py-1.5 bg-[#FFF6E8] text-[#A96F00] text-xs font-medium rounded-full tracking-wide mb-5">
              Today's Mission
            </span>

            {/* 标题 */}
            <h1 className="text-[34px] font-bold text-ink-primary leading-[1.2] mb-3 tracking-tight">
              {title}
            </h1>

            {/* 副标题 */}
            <p className="text-base text-ink-muted leading-relaxed mb-10">
              {greeting || "今天我们不用着急学会。先理解它为什么存在。"}
            </p>

            {/* Mission 卡片 */}
            <div className="mb-6">
              <p className="text-xs text-ink-muted tracking-[2px] uppercase mb-4 font-medium">
                Mission
              </p>

              <div className="bg-surface rounded-2xl border border-border/50 p-5 sm:p-6">
                <h3 className="text-xl font-semibold text-ink-primary mb-4">
                  今天会经历什么？
                </h3>
                {missionSteps && missionSteps.length > 0 ? (
                  <div className="space-y-4">
                    {missionSteps.map((step, i) => (
                      <div key={i} className="flex items-start gap-3">
                        <span className="w-2.5 h-2.5 rounded-full bg-[#ffb84d] mt-[6px] shrink-0" />
                        <p className="text-sm text-ink-secondary leading-relaxed flex-1">
                          {step}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="space-y-4">
                    {["理解建立连接真正发生了什么", "尝试用自己的话解释整个过程", "思考为什么一定要三次"].map(
                      (tip, i) => (
                        <div key={i} className="flex items-start gap-3">
                          <span className="w-2.5 h-2.5 rounded-full bg-[#ffb84d] mt-[6px] shrink-0" />
                          <p className="text-sm text-ink-secondary leading-relaxed flex-1">{tip}</p>
                        </div>
                      ),
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* ── AppleGo Observation 预览（可选，移到了 OBSERVATION 屏） ── */}
        </div>
      </div>

      {/* ── 底部按钮 ── */}
      <div
        className={`border-t border-border/50 px-5 py-4 transition-all duration-500 ease-out ${
          showFooter ? "opacity-100" : "opacity-0"
        }`}
      >
        <div className="max-w-lg mx-auto flex gap-3">
          <button
            className="flex-1 h-14 rounded-xl bg-white border border-border/60 text-ink-primary text-base font-medium hover:bg-surface transition-colors"
            disabled={transitioning}
          >
            💬 问苹果果
          </button>
          <button
            onClick={handleStart}
            disabled={transitioning}
            className="flex-1 h-14 rounded-xl bg-[#F4B400] text-white text-base font-semibold hover:bg-[#e5a800] transition-colors disabled:opacity-50"
          >
            {transitioning ? "准备中…" : "继续"}
          </button>
        </div>
      </div>
    </div>
  );
}
