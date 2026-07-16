// ============================================================
// EXP-04 V2 · ENTER Screen 单元测试
//
// V2 设计变化：
//   - 按钮文本 "开始" → "继续"
//   - 问候语从 Conversation Engine → 融合到副标题
//   - 渐进浮现：2 阶段（主内容 300ms → 底部按钮 800ms）
//   - Mission 空步骤回退到 3 个默认目标点
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
    mission: null as { title: string; steps: { order: number; description: string; type: "explain" | "practice" | "review" }[] } | null,
    lastTitle: null as string | null,
    onStart,
    transitioning: false,
    ...overrides,
  };
  const utils = render(<Exp04EnterScreen {...props} />);
  return { ...utils, engine, onStart };
}

describe("V2 ENTER — 基础渲染", () => {
  it("渲染 Today's Mission tag", () => {
    setup();
    expect(screen.getByText("Today's Mission")).toBeDefined();
  });

  it("渲染标题（Mission title 或默认）", () => {
    setup({ mission: { title: "TCP 三次握手", steps: [] } });
    expect(screen.getByText("TCP 三次握手")).toBeDefined();
  });

  it("无 mission 时渲染默认标题", () => {
    setup();
    expect(screen.getByText("开始今天的学习")).toBeDefined();
  });

  it("渲染 '继续' 按钮", () => {
    setup();
    expect(screen.getByText("继续")).toBeDefined();
  });
});

describe("V2 ENTER — Mission 目标点", () => {
  const sampleMission = {
    title: "矩阵乘法入门",
    steps: [
      { order: 0, description: "理解矩阵乘法的定义", type: "explain" as const },
      { order: 1, description: "练习矩阵计算", type: "practice" as const },
    ],
  };

  it("渲染 Mission 卡片标题", () => {
    setup();
    expect(screen.getByText("今天会经历什么？")).toBeDefined();
  });

  it("渲染 Mission 步骤文本", () => {
    setup({ mission: sampleMission });
    expect(screen.getByText("理解矩阵乘法的定义")).toBeDefined();
    expect(screen.getByText("练习矩阵计算")).toBeDefined();
  });

  it("mission 为 null 时渲染 3 个默认目标点", () => {
    setup({ mission: null });
    expect(screen.getByText("理解建立连接真正发生了什么")).toBeDefined();
    expect(screen.getByText("尝试用自己的话解释整个过程")).toBeDefined();
    expect(screen.getByText("思考为什么一定要三次")).toBeDefined();
  });

  it("mission 步骤为空时渲染 3 个默认目标点", () => {
    setup({ mission: { title: "测试", steps: [] } });
    expect(screen.getByText("理解建立连接真正发生了什么")).toBeDefined();
    expect(screen.getByText("尝试用自己的话解释整个过程")).toBeDefined();
    expect(screen.getByText("思考为什么一定要三次")).toBeDefined();
  });
});

describe("V2 ENTER — 自动过渡", () => {
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

  it("transitioning 时按钮 disabled", () => {
    setup({ transitioning: true });
    const btn = screen.getByRole("button", { name: /准备/ });
    expect(btn).toBeDefined();
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });
});

describe("V2 ENTER — fade-in 序列", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("初始时主内容 opacity-0", () => {
    const { container } = setup();
    // 主内容容器初始状态 opacity-0
    const mainContent = container.querySelector(".opacity-0");
    expect(mainContent).not.toBeNull();
  });

  it("300ms 后主内容可见", () => {
    const { container } = setup();
    act(() => { vi.advanceTimersByTime(300); });
    const mainContent = container.querySelector(".opacity-100");
    expect(mainContent).not.toBeNull();
  });

  it("800ms 后底部按钮可见", () => {
    const { container } = setup();
    act(() => { vi.advanceTimersByTime(800); });
    // 底部 footer 区域可见
    const footer = container.querySelector(".border-t");
    expect(footer).not.toBeNull();
    expect(footer?.className).toContain("opacity-100");
  });
});
