// ============================================================
// EXP-04 V2 · ENTER Screen 单元测试
//
// 对齐 Vision: 极简 intro — AI 引语 + "继续" + "今天想学点别的"
// ============================================================

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import Exp04EnterScreen from "@/components/session/exp04/Exp04EnterScreen";
import { createConversationEngine } from "@/lib/exp04/conversation-engine";

function setup(overrides: Partial<Parameters<typeof Exp04EnterScreen>[0]> = {}) {
  const engine = createConversationEngine();
  const onStart = vi.fn();
  const props = {
    engine,
    currentState: "ENTER" as const,
    mission: null as { title: string } | null,
    lastTitle: null as string | null,
    onStart,
    transitioning: false,
    ...overrides,
  };
  const utils = render(<Exp04EnterScreen {...props} />);
  return { ...utils, engine, onStart };
}

describe("ENTER — 基础渲染", () => {
  it("渲染标题（Mission title 或默认）", () => {
    setup({ mission: { title: "矩阵乘法" } });
    expect(screen.getByText("矩阵乘法")).toBeDefined();
  });

  it("无 mission 时渲染默认标题", () => {
    setup();
    expect(screen.getByText("开始今天的学习")).toBeDefined();
  });

  it("渲染 '继续' 按钮", () => {
    setup();
    expect(screen.getByText("继续")).toBeDefined();
  });

  it("渲染 '今天想学点别的' 链接", () => {
    setup();
    expect(screen.getByText("今天想学点别的")).toBeDefined();
  });

  it("渲染 AI 引语", () => {
    setup();
    expect(screen.getByText("今天，我们从一个问题开始。准备好了吗？")).toBeDefined();
  });
});

describe("ENTER — 自动过渡", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("10 秒后自动调用 onStart", () => {
    const { onStart } = setup();
    expect(onStart).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(10_000);
    });

    expect(onStart).toHaveBeenCalledTimes(1);
  });

  it("5 秒时尚未调用 onStart", () => {
    const { onStart } = setup();

    act(() => {
      vi.advanceTimersByTime(5_000);
    });

    expect(onStart).not.toHaveBeenCalled();
  });

  it("transitioning 时不触发自动过渡", () => {
    const { onStart } = setup({ transitioning: true });

    act(() => {
      vi.advanceTimersByTime(10_000);
    });

    expect(onStart).not.toHaveBeenCalled();
  });

  it("手动点击 '继续' 触发 onStart", () => {
    const { onStart } = setup();
    fireEvent.click(screen.getByText("继续"));
    expect(onStart).toHaveBeenCalledTimes(1);
  });

  it("'今天想学点别的' 也触发 onStart", () => {
    const { onStart } = setup();
    fireEvent.click(screen.getByText("今天想学点别的"));
    expect(onStart).toHaveBeenCalledTimes(1);
  });

  it("transitioning 时按钮 disabled", () => {
    setup({ transitioning: true });
    const btn = screen.getByText("准备中…");
    expect(btn).toBeDefined();
  });
});

describe("ENTER — fade-in 序列", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("初始时主内容 opacity-0", () => {
    const { container } = setup();
    const mainContent = container.querySelector(".opacity-0");
    expect(mainContent).not.toBeNull();
  });

  it("300ms 后主内容可见", () => {
    const { container } = setup();
    act(() => { vi.advanceTimersByTime(300); });
    const mainContent = container.querySelector(".opacity-100");
    expect(mainContent).not.toBeNull();
  });
});
