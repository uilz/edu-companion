// ============================================================
// EXP-04 V2 · OBSERVATION Screen 单元测试
//
// "苹果果注意到"
//   - 展示 AI 观察结果
//   - "你已经理解了" + "还有一个值得思考的地方" + "想一想"
//   - fallback 内容
// ============================================================

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Exp04ObservationScreen from "@/components/session/exp04/Exp04ObservationScreen";

function setup(overrides: Partial<Parameters<typeof Exp04ObservationScreen>[0]> = {}) {
  const onContinue = vi.fn();
  const props = {
    mission: null as any,
    referenceText: null as string | null,
    onContinue,
    transitioning: false,
    sessionId: undefined as string | undefined,
    missionTitle: undefined as string | undefined,
    ...overrides,
  };
  const utils = render(<Exp04ObservationScreen {...props} />);
  return { ...utils, onContinue };
}

describe("V2 OBSERVATION — 基础渲染", () => {
  it("渲染标题", () => {
    setup();
    expect(screen.getByText("苹果果注意到")).toBeDefined();
  });

  it("渲染 section-title", () => {
    setup();
    expect(screen.getByText("AppleGo Observation")).toBeDefined();
  });

  it("渲染 '你已经理解了' 区域", () => {
    setup();
    expect(screen.getByText("你已经理解了")).toBeDefined();
  });

  it("渲染 '还有一个值得思考的地方' 区域", () => {
    setup();
    expect(screen.getByText("还有一个值得思考的地方")).toBeDefined();
  });

  it("渲染 '想一想' 区域", () => {
    setup();
    expect(screen.getByText("想一想")).toBeDefined();
  });

  it("渲染 '继续' 按钮", () => {
    setup();
    expect(screen.getByText("继续")).toBeDefined();
  });
});

describe("V2 OBSERVATION — Fallback 内容", () => {
  it("无 sessionId 时显示 fallback 内容", () => {
    setup({ sessionId: undefined });
    expect(screen.getByText(/你已经提到了建立连接/)).toBeDefined();
  });
});

describe("V2 OBSERVATION — 按钮交互", () => {
  it("点击 '继续' 触发 onContinue", async () => {
    const { onContinue } = setup();
    const user = userEvent.setup();
    await user.click(screen.getByText("继续"));
    expect(onContinue).toHaveBeenCalledTimes(1);
  });

  it("transitioning 时按钮 disabled", () => {
    setup({ transitioning: true });
    const btn = screen.getByText("继续");
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });
});
