// ============================================================
// EXP-04 State Machine — 单元测试
//
// 覆盖：
//   1. 所有合法转换路径
//   2. 所有非法转换被静默忽略
//   3. ENTER → LEARN → COGNITIVE_SEARCH → LEARN 循环
//   4. END 终态不可转换
//   5. SESSION_CANCELLED 全线可达
// ============================================================

import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useExp04StateMachine } from "@/lib/exp04/state-machine";

function setup(initial?: Parameters<typeof useExp04StateMachine>[0]) {
  return renderHook(() => useExp04StateMachine(initial));
}

describe("EXP-04 State Machine — 合法转换", () => {
  // ── ENTER ──

  it("ENTER → LEARN (START_CLICKED)", () => {
    const { result } = setup("ENTER");
    act(() => result.current.transition({ type: "START_CLICKED" }));
    expect(result.current.currentState).toBe("LEARN");
    expect(result.current.previousState).toBe("ENTER");
    expect(result.current.transitionCount).toBe(1);
  });

  it("ENTER → LEARN (ENTER_TIMEOUT)", () => {
    const { result } = setup("ENTER");
    act(() => result.current.transition({ type: "ENTER_TIMEOUT" }));
    expect(result.current.currentState).toBe("LEARN");
  });

  it("ENTER → END (SESSION_CANCELLED)", () => {
    const { result } = setup("ENTER");
    act(() => result.current.transition({ type: "SESSION_CANCELLED" }));
    expect(result.current.currentState).toBe("END");
  });

  // ── LEARN ──

  it("LEARN → COGNITIVE_SEARCH (INACTIVITY_DETECTED)", () => {
    const { result } = setup("LEARN");
    act(() => result.current.transition({ type: "INACTIVITY_DETECTED" }));
    expect(result.current.currentState).toBe("COGNITIVE_SEARCH");
  });

  it("LEARN → SELF_VALIDATION (VALIDATION_REQUESTED)", () => {
    const { result } = setup("LEARN");
    act(() => result.current.transition({ type: "VALIDATION_REQUESTED" }));
    expect(result.current.currentState).toBe("SELF_VALIDATION");
  });

  it("LEARN → END (SESSION_CANCELLED)", () => {
    const { result } = setup("LEARN");
    act(() => result.current.transition({ type: "SESSION_CANCELLED" }));
    expect(result.current.currentState).toBe("END");
  });

  // ── COGNITIVE_SEARCH ──

  it("COGNITIVE_SEARCH → LEARN (INTERACTION_RESUMED)", () => {
    const { result } = setup("COGNITIVE_SEARCH");
    act(() => result.current.transition({ type: "INTERACTION_RESUMED" }));
    expect(result.current.currentState).toBe("LEARN");
  });

  it("COGNITIVE_SEARCH → END (SESSION_CANCELLED)", () => {
    const { result } = setup("COGNITIVE_SEARCH");
    act(() => result.current.transition({ type: "SESSION_CANCELLED" }));
    expect(result.current.currentState).toBe("END");
  });

  // ── SELF_VALIDATION ──

  it("SELF_VALIDATION → LEARN (BACK_TO_LEARN)", () => {
    const { result } = setup("SELF_VALIDATION");
    act(() => result.current.transition({ type: "BACK_TO_LEARN" }));
    expect(result.current.currentState).toBe("LEARN");
  });

  it("SELF_VALIDATION → OBSERVATION (VALIDATION_DONE)", () => {
    const { result } = setup("SELF_VALIDATION");
    act(() => result.current.transition({ type: "VALIDATION_DONE" }));
    expect(result.current.currentState).toBe("OBSERVATION");
  });

  it("SELF_VALIDATION → END (SESSION_CANCELLED)", () => {
    const { result } = setup("SELF_VALIDATION");
    act(() => result.current.transition({ type: "SESSION_CANCELLED" }));
    expect(result.current.currentState).toBe("END");
  });

  // ── OBSERVATION ──

  it("OBSERVATION → REFLECTION (OBSERVATION_DONE)", () => {
    const { result } = setup("OBSERVATION");
    act(() => result.current.transition({ type: "OBSERVATION_DONE" }));
    expect(result.current.currentState).toBe("REFLECTION");
  });

  it("OBSERVATION → END (SESSION_CANCELLED)", () => {
    const { result } = setup("OBSERVATION");
    act(() => result.current.transition({ type: "SESSION_CANCELLED" }));
    expect(result.current.currentState).toBe("END");
  });

  // ── REFLECTION ──

  it("REFLECTION → END (REFLECTION_DONE)", () => {
    const { result } = setup("REFLECTION");
    act(() => result.current.transition({ type: "REFLECTION_DONE" }));
    expect(result.current.currentState).toBe("END");
  });

  it("REFLECTION → END (SESSION_CANCELLED)", () => {
    const { result } = setup("REFLECTION");
    act(() => result.current.transition({ type: "SESSION_CANCELLED" }));
    expect(result.current.currentState).toBe("END");
  });

  // ── END 终态 ──

  it("END 不接受任何转换", () => {
    const { result } = setup("END");
    const events = [
      "START_CLICKED", "INACTIVITY_DETECTED", "INTERACTION_RESUMED",
      "VALIDATION_REQUESTED", "BACK_TO_LEARN", "VALIDATION_DONE",
      "OBSERVATION_DONE", "REFLECTION_DONE", "SESSION_CANCELLED",
    ] as const;
    for (const event of events) {
      act(() => result.current.transition({ type: event }));
      expect(result.current.currentState).toBe("END");
      expect(result.current.transitionCount).toBe(0);
    }
  });
});

describe("EXP-04 State Machine — 非法转换被忽略", () => {
  it("ENTER 不接受 INACTIVITY_DETECTED", () => {
    const { result } = setup("ENTER");
    act(() => result.current.transition({ type: "INACTIVITY_DETECTED" }));
    expect(result.current.currentState).toBe("ENTER");
    expect(result.current.transitionCount).toBe(0);
  });

  it("LEARN 不接受 REFLECTION_DONE", () => {
    const { result } = setup("LEARN");
    act(() => result.current.transition({ type: "REFLECTION_DONE" }));
    expect(result.current.currentState).toBe("LEARN");
  });

  it("COGNITIVE_SEARCH 不接受 START_CLICKED", () => {
    const { result } = setup("COGNITIVE_SEARCH");
    act(() => result.current.transition({ type: "START_CLICKED" }));
    expect(result.current.currentState).toBe("COGNITIVE_SEARCH");
  });

  it("SELF_VALIDATION 不接受 INACTIVITY_DETECTED", () => {
    const { result } = setup("SELF_VALIDATION");
    act(() => result.current.transition({ type: "INACTIVITY_DETECTED" }));
    expect(result.current.currentState).toBe("SELF_VALIDATION");
  });

  it("REFLECTION 不接受 START_CLICKED", () => {
    const { result } = setup("REFLECTION");
    act(() => result.current.transition({ type: "START_CLICKED" }));
    expect(result.current.currentState).toBe("REFLECTION");
  });

  it("OBSERVATION 不接受 START_CLICKED", () => {
    const { result } = setup("OBSERVATION");
    act(() => result.current.transition({ type: "START_CLICKED" }));
    expect(result.current.currentState).toBe("OBSERVATION");
  });
});

describe("EXP-04 State Machine — 完整流程", () => {
  it("ENTER → LEARN → COGNITIVE_SEARCH → LEARN → SELF_VALIDATION → OBSERVATION → REFLECTION → END", () => {
    const { result } = setup("ENTER");

    act(() => result.current.transition({ type: "START_CLICKED" }));
    expect(result.current.currentState).toBe("LEARN");

    act(() => result.current.transition({ type: "INACTIVITY_DETECTED" }));
    expect(result.current.currentState).toBe("COGNITIVE_SEARCH");

    act(() => result.current.transition({ type: "INTERACTION_RESUMED" }));
    expect(result.current.currentState).toBe("LEARN");

    act(() => result.current.transition({ type: "VALIDATION_REQUESTED" }));
    expect(result.current.currentState).toBe("SELF_VALIDATION");

    act(() => result.current.transition({ type: "VALIDATION_DONE" }));
    expect(result.current.currentState).toBe("OBSERVATION");

    act(() => result.current.transition({ type: "OBSERVATION_DONE" }));
    expect(result.current.currentState).toBe("REFLECTION");

    act(() => result.current.transition({ type: "REFLECTION_DONE" }));
    expect(result.current.currentState).toBe("END");

    expect(result.current.transitionCount).toBe(7);
  });

  it("ENTER → 取消 (中途取消全流程)", () => {
    const { result } = setup("ENTER");
    act(() => result.current.transition({ type: "START_CLICKED" }));
    expect(result.current.currentState).toBe("LEARN");

    act(() => result.current.transition({ type: "SESSION_CANCELLED" }));
    expect(result.current.currentState).toBe("END");
  });
});

describe("EXP-04 State Machine — canTransition", () => {
  it("ENTER 可以 START_CLICKED，不可以 VALIDATION_DONE", () => {
    const { result } = setup("ENTER");
    expect(result.current.canTransition("START_CLICKED")).toBe(true);
    expect(result.current.canTransition("VALIDATION_DONE")).toBe(false);
  });

  it("LEARN 可以 INACTIVITY_DETECTED，不可以 REFLECTION_DONE", () => {
    const { result } = setup("LEARN");
    expect(result.current.canTransition("INACTIVITY_DETECTED")).toBe(true);
    expect(result.current.canTransition("REFLECTION_DONE")).toBe(false);
    expect(result.current.canTransition("VALIDATION_REQUESTED")).toBe(true);
    expect(result.current.canTransition("SESSION_CANCELLED")).toBe(true);
  });
});
