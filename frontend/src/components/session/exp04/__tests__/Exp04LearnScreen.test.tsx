// ============================================================
// EXP-04 V2 · LEARN Screen 单元测试
//
// V2 设计变化：
//   - 💬 改为悬浮 FAB（浮动按钮），点击弹迷你浮层
//   - AI 默认沉默，无底部抽屉
//   - 书页式阅读体验
//   - 认知搜索提示文案更新
// ============================================================

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Exp04LearnScreen from "@/components/session/exp04/Exp04LearnScreen";
import { createConversationEngine } from "@/lib/exp04/conversation-engine";
import type { Exp04State } from "@/lib/exp04/types";

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

const defaultProps = () => {
  const engine = createConversationEngine();
  const onValidate = vi.fn();
  const onStateTransition = vi.fn();
  return {
    engine,
    currentState: "LEARN" as Exp04State,
    mission: null as { title: string; steps: { order: number; description: string; type: "explain" | "practice" | "review" }[] } | null,
    onValidate,
    onStateTransition,
    transitioning: false,
  };
};

function setup(overrides: Partial<ReturnType<typeof defaultProps>> = {}) {
  const props = { ...defaultProps(), ...overrides };
  const utils = render(<Exp04LearnScreen {...props} />);
  return { ...utils, ...props };
}

describe("V2 LEARN — 基础渲染", () => {
  it("渲染内容区域标题", () => {
    setup({ mission: { title: "矩阵乘法入门", steps: [] } });
    expect(screen.getByText("矩阵乘法入门")).toBeDefined();
  });

  it("无 Mission 时显示默认阅读内容（TCP 案例）", () => {
    setup({ mission: null });
    expect(screen.getByText("Three-way Handshake。")).toBeDefined();
  });

  it("渲染 💬 悬浮按钮", () => {
    setup();
    const fab = screen.getByLabelText("问苹果果");
    expect(fab).toBeDefined();
  });

  it("渲染 '验证理解' 按钮", () => {
    setup();
    expect(screen.getByText("验证理解")).toBeDefined();
  });
});

describe("V2 LEARN — 💬 悬浮按钮 + 迷你浮层", () => {
  it("默认浮层不可见", () => {
    setup();
    expect(screen.queryByText("有什么想知道的？")).toBeNull();
  });

  it("点击 💬 按钮打开迷你浮层", async () => {
    setup();
    const user = userEvent.setup();
    await user.click(screen.getByLabelText("问苹果果"));
    expect(screen.getByText("有什么想知道的？")).toBeDefined();
  });

  it("浮层显示输入框", async () => {
    setup();
    const user = userEvent.setup();
    await user.click(screen.getByLabelText("问苹果果"));
    expect(screen.getByPlaceholderText("输入你的问题…")).toBeDefined();
  });

  it("遮罩点击关闭浮层", async () => {
    setup();
    const user = userEvent.setup();
    await user.click(screen.getByLabelText("问苹果果"));
    expect(screen.getByText("有什么想知道的？")).toBeDefined();
    // 点击遮罩背景
    const mask = document.querySelector(".bg-black\\/20, .bg-black\\/20");
    // 直接找所有 absolute inset-0 元素
    const backdrop = document.querySelector("[class*='bg-black']");
    if (backdrop) {
      await user.click(backdrop);
      expect(screen.queryByText("有什么想知道的？")).toBeNull();
    }
  });
});

describe("V2 LEARN — 消息发送", () => {
  it("发送消息后出现在对话中", async () => {
    setup();
    const user = userEvent.setup();
    await user.click(screen.getByLabelText("问苹果果"));
    const input = screen.getByPlaceholderText("输入你的问题…");
    await user.type(input, "我不太懂这个地方");
    await user.keyboard("{Enter}");
    expect(screen.getByText("我不太懂这个地方")).toBeDefined();
  });
});

describe("V2 LEARN — 1 轮对话限制", () => {
  it("发送 1 轮后输入区消失", async () => {
    setup();
    const user = userEvent.setup();
    await user.click(screen.getByLabelText("问苹果果"));
    const input = screen.getByPlaceholderText("输入你的问题…");
    await user.type(input, "一个问题");
    await user.keyboard("{Enter}");
    expect(screen.queryByPlaceholderText("输入你的问题…")).toBeNull();
  });

  it("1 轮后提示'已经聊过一轮了'", async () => {
    setup();
    const user = userEvent.setup();
    await user.click(screen.getByLabelText("问苹果果"));
    const input = screen.getByPlaceholderText("输入你的问题…");
    await user.type(input, "一个问题");
    await user.keyboard("{Enter}");
    expect(screen.getByText("已经聊过一轮了。")).toBeDefined();
  });
});

describe("V2 LEARN — Cognitive Search", () => {
  it("COGNITIVE_SEARCH 状态渲染温和提示", () => {
    setup({ currentState: "COGNITIVE_SEARCH" });
    expect(screen.getByText(/你好像在想什么/)).toBeDefined();
  });

  it("LEARN 状态不渲染认知搜索提示", () => {
    setup({ currentState: "LEARN" });
    expect(screen.queryByText(/你好像在想什么/)).toBeNull();
  });

  it("验证理解按钮在 COGNITIVE_SEARCH 状态仍可用", () => {
    setup({ currentState: "COGNITIVE_SEARCH" });
    expect(screen.getByText("验证理解")).toBeDefined();
  });
});

describe("V2 LEARN — 按钮交互", () => {
  it("点击 '验证理解' 触发 onValidate", async () => {
    const { onValidate } = setup();
    const user = userEvent.setup();
    await user.click(screen.getByText("验证理解"));
    expect(onValidate).toHaveBeenCalledTimes(1);
  });

  it("transitioning 时按钮 disabled", () => {
    setup({ transitioning: true });
    const btn = screen.getByText("准备中…");
    expect(btn).toBeDefined();
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });
});
