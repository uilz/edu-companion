// ============================================================
// EXP-04 · Inactivity Detection Hook（EPIC-03）
//
// 监听 LEARN 屏用户交互，检测长时间停留。
// 两阶段：
//   1. 90s — 内部检测（无视觉变化）
//   2. 180s — 触发 COGNITIVE_SEARCH（显示确认消息）
//
// 设计依据：docs/tmp/EXP-04-Engineering-Epics.md（EPIC-03）
// ============================================================

"use client";

import { useEffect, useRef, useState, useCallback } from "react";

// ── 常量 ──────────────────────────────────────────────────

/** 第一阶段：内部检测阈值 */
const PHASE_1_MS = 90_000; // 90 秒

/** 第二阶段：触发 Cognitive Search */
const PHASE_2_MS = 180_000; // 180 秒

// ── Hook ──────────────────────────────────────────────────

interface UseInactivityDetectionOptions {
  /** 当用户 180s 无操作时触发 */
  onCognitiveSearch: () => void;
  /** 当用户在 Cognitive Search 中恢复操作时触发 */
  onResume: () => void;
  /** 是否启用检测（仅 LEARN 状态启用） */
  enabled: boolean;
  /** 当前状态机状态（用于判断是否在 COGNITIVE_SEARCH 中） */
  isInCognitiveSearch: boolean;
}

interface UseInactivityDetectionReturn {
  /** 当前是否在 Cognitive Search 阶段 */
  isInCognitiveSearch: boolean;
  /** 重置计时器（用户操作时） */
  reset: () => void;
}

export function useInactivityDetection({
  onCognitiveSearch,
  onResume,
  enabled,
  isInCognitiveSearch = false,
}: UseInactivityDetectionOptions): UseInactivityDetectionReturn {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activatedRef = useRef(false);
  const onResumeRef = useRef(onResume);
  const onCognitiveSearchRef = useRef(onCognitiveSearch);
  onResumeRef.current = onResume;
  onCognitiveSearchRef.current = onCognitiveSearch;

  // 重置计时器（仅由事件触发）
  const reset = useCallback(() => {
    if (!enabled) return;

    // 如果当前在 COGNITIVE_SEARCH 中且用户交互 → 恢复
    if (isInCognitiveSearch) {
      onResumeRef.current();
      activatedRef.current = false;
      return; // 不复启计时器
    }

    // 清除旧计时器
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }

    activatedRef.current = false;

    // 启动新计时器
    timerRef.current = setTimeout(() => {
      if (!activatedRef.current) {
        activatedRef.current = true;
        onCognitiveSearchRef.current();
      }
    }, PHASE_2_MS);
  }, [enabled, isInCognitiveSearch]);

  // 监听交互事件
  useEffect(() => {
    if (!enabled) {
      if (timerRef.current) clearTimeout(timerRef.current);
      return;
    }

    // 启动初始计时器
    if (!isInCognitiveSearch) {
      if (timerRef.current) clearTimeout(timerRef.current);
      activatedRef.current = false;
      timerRef.current = setTimeout(() => {
        if (!activatedRef.current) {
          activatedRef.current = true;
          onCognitiveSearchRef.current();
        }
      }, PHASE_2_MS);
    }

    // 交互事件列表
    const events = ["click", "keydown", "scroll", "touchstart", "mousemove"];

    const handleActivity = () => reset();

    for (const event of events) {
      document.addEventListener(event, handleActivity, { passive: true });
    }

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      for (const event of events) {
        document.removeEventListener(event, handleActivity);
      }
    };
  }, [enabled, isInCognitiveSearch, reset]);

  return { isInCognitiveSearch, reset };
}
