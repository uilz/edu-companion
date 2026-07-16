// ============================================================
// EXP-04 · Inactivity Detection 单元测试
//
// 覆盖：
//   1. 180s 后触发 onCognitiveSearch
//   2. 用户交互重置计时器
//   3. COGNITIVE_SEARCH 中交互触发 onResume
//   4. disabled 时不触发
// ============================================================

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useInactivityDetection } from "@/lib/exp04/useInactivityDetection";

const PHASE_2_MS = 180_000;

describe("useInactivityDetection — 基本行为", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  function setup(initialProps?: Partial<Parameters<typeof useInactivityDetection>[0]>) {
    const onCognitiveSearch = vi.fn();
    const onResume = vi.fn();
    const props = {
      onCognitiveSearch,
      onResume,
      enabled: true,
      isInCognitiveSearch: false,
      ...initialProps,
    };
    const { result, rerender } = renderHook(
      (p) => useInactivityDetection(p),
      { initialProps: props }
    );
    return { result, rerender, onCognitiveSearch, onResume, props };
  }

  it("180s 内不触发 onCognitiveSearch", () => {
    const { onCognitiveSearch } = setup();

    act(() => vi.advanceTimersByTime(PHASE_2_MS - 1));
    expect(onCognitiveSearch).not.toHaveBeenCalled();
  });

  it("180s 后触发 onCognitiveSearch", () => {
    const { onCognitiveSearch } = setup();

    act(() => vi.advanceTimersByTime(PHASE_2_MS));
    expect(onCognitiveSearch).toHaveBeenCalledTimes(1);
  });

  it("只触发一次", () => {
    const { onCognitiveSearch } = setup();

    act(() => vi.advanceTimersByTime(PHASE_2_MS));
    expect(onCognitiveSearch).toHaveBeenCalledTimes(1);

    act(() => vi.advanceTimersByTime(PHASE_2_MS));
    expect(onCognitiveSearch).toHaveBeenCalledTimes(1);
  });

  it("用户交互重置计时器", () => {
    const { onCognitiveSearch } = setup();

    // 模拟用户交互（触发 keydown 事件）
    act(() => {
      vi.advanceTimersByTime(90_000);
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "a" }));
    });

    // 此时距离初始已 90s，但计时器已重置
    // 再推进 179s → 不应触发（总共 90+179=269s 但交互时重置了）
    act(() => vi.advanceTimersByTime(PHASE_2_MS - 1));
    expect(onCognitiveSearch).not.toHaveBeenCalled();

    // 再推 1s → 应触发（因为交互发生在 90s，重置后 180s 是 270s）
    act(() => vi.advanceTimersByTime(1));
    expect(onCognitiveSearch).toHaveBeenCalledTimes(1);
  });

  it("disabled 时不触发", () => {
    const { onCognitiveSearch } = setup({ enabled: false });

    act(() => vi.advanceTimersByTime(PHASE_2_MS));
    expect(onCognitiveSearch).not.toHaveBeenCalled();
  });

  it("已触发后用户交互触发 onResume", () => {
    const { onCognitiveSearch, onResume, rerender } = setup();

    // 首先触发 COGNITIVE_SEARCH
    act(() => vi.advanceTimersByTime(PHASE_2_MS));
    expect(onCognitiveSearch).toHaveBeenCalledTimes(1);

    // re-render 以更新 isInCognitiveSearch = true
    rerender({
      onCognitiveSearch,
      onResume,
      enabled: true,
      isInCognitiveSearch: true,
    });

    // 用户交互
    act(() => {
      document.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(onResume).toHaveBeenCalledTimes(1);
  });
});
