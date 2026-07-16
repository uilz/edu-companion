// ============================================================
// EXP-04 V2 · Self-Validation Screen 单元测试
//
// V2 变化：
//   - 仅有输入阶段（无 Compare phase，移到了 OBSERVATION）
//   - 提交时触发 LI-02 API 调用
//   - "写好了" → 触发 onContinue
//   - "再看看" → 返回 LEARN
// ============================================================

import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Exp04SelfValidationScreen from "@/components/session/exp04/Exp04SelfValidationScreen";

// Mock authedFetch to resolve quickly
vi.mock("@/lib/api/api", () => ({
  authedFetch: vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) })),
}));

function setup(overrides: Partial<Parameters<typeof Exp04SelfValidationScreen>[0]> = {}) {
  const onBackToLearn = vi.fn();
  const onContinue = vi.fn();
  const props = {
    engine: undefined as any,
    currentState: "SELF_VALIDATION" as const,
    mission: null as any,
    referenceText: null as string | null,
    onBackToLearn,
    onContinue,
    transitioning: false,
    sessionId: "test-session-id",
    missionTitle: undefined as string | undefined,
    ...overrides,
  };
  const utils = render(<Exp04SelfValidationScreen {...props} />);
  return { ...utils, onBackToLearn, onContinue };
}

describe("V2 SELF_VALIDATION — 基础渲染", () => {
  it("渲染引导标题", () => {
    setup();
    expect(screen.getByText("试着讲给苹果果听")).toBeDefined();
  });

  it("渲染 textarea", () => {
    setup();
    const textarea = screen.getByPlaceholderText(/把你对/);
    expect(textarea).toBeDefined();
  });

  it("渲染 '写好了' 按钮", () => {
    setup();
    expect(screen.getByText("写好了")).toBeDefined();
  });

  it("渲染 '再看看' 按钮", () => {
    setup();
    expect(screen.getByText("再看看")).toBeDefined();
  });

  it("空内容时 '写好了' 按钮 disabled", () => {
    setup();
    const btn = screen.getByText("写好了");
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });

  it("输入内容后 '写好了' 按钮可用", async () => {
    setup();
    const user = userEvent.setup();
    const textarea = screen.getByPlaceholderText(/把你对/);
    await user.type(textarea, "TCP 是可靠的传输协议");
    const btn = screen.getByText("写好了");
    expect((btn as HTMLButtonElement).disabled).toBe(false);
  });

  it("渲染 section-title", () => {
    setup();
    expect(screen.getByText("Self Validation")).toBeDefined();
  });
});

describe("V2 SELF_VALIDATION — 按钮交互", () => {
  it("点击 '再看看' 触发 onBackToLearn", async () => {
    const { onBackToLearn } = setup();
    const user = userEvent.setup();
    await user.click(screen.getByText("再看看"));
    expect(onBackToLearn).toHaveBeenCalledTimes(1);
  });

  it("点击 '写好了' 触发 onContinue", async () => {
    const { onContinue } = setup();
    const user = userEvent.setup();
    const textarea = screen.getByPlaceholderText(/把你对/);
    await user.type(textarea, "TCP 可靠传输");
    await user.click(screen.getByText("写好了"));
    expect(onContinue).toHaveBeenCalledTimes(1);
  });

  it("transitioning 时 '写好了' disabled", () => {
    setup({ transitioning: true });
    const btn = screen.getByText("写好了");
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });

  it("transitioning 时 '再看看' disabled", () => {
    setup({ transitioning: true });
    const btn = screen.getByText("再看看");
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });
});

describe("V2 SELF_VALIDATION — 加载状态", () => {
  it("提交后触发 onContinue", async () => {
    const { onContinue } = setup();
    const user = userEvent.setup();
    const textarea = screen.getByPlaceholderText(/把你对/);
    await user.type(textarea, "TCP 可靠传输");
    await user.click(screen.getByText("写好了"));
    // 由于 mock authedFetch 立即 resolve，analyze state 瞬间闪过
    // 验证最终 onContinue 被调用即可
    await waitFor(() => {
      expect(onContinue).toHaveBeenCalledTimes(1);
    });
  });
});

describe("V2 SELF_VALIDATION — Mission title", () => {
  it("渲染 mission title 在描述中", () => {
    setup({ missionTitle: "TCP 三次握手" });
    expect(screen.getByText(/TCP 三次握手/)).toBeDefined();
  });
});
