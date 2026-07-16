// ============================================================
// EXP-04 V2 · REFLECTION Screen 单元测试
//
// V2 变化：
//   - "今天最大的变化是什么？" 引导语
//   - "记下来" 按钮
//   - "跳过" 按钮
//   - 大输入框
// ============================================================

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Exp04ReflectionScreen from "@/components/session/exp04/Exp04ReflectionScreen";

function setup(overrides: Partial<Parameters<typeof Exp04ReflectionScreen>[0]> = {}) {
  const onSkip = vi.fn();
  const onSubmit = vi.fn();
  const engine = {} as any;
  const props = {
    engine,
    currentState: "REFLECTION",
    onSkip,
    onSubmit,
    transitioning: false,
    ...overrides,
  };
  const utils = render(<Exp04ReflectionScreen {...props} />);
  return { ...utils, onSkip, onSubmit };
}

describe("V2 REFLECTION — 基础渲染", () => {
  it("渲染引导标题", () => {
    setup();
    expect(screen.getByText("今天最大的变化是什么？")).toBeDefined();
  });

  it("渲染 textarea", () => {
    setup();
    const textarea = screen.getByPlaceholderText(/我以前以为/);
    expect(textarea).toBeDefined();
  });

  it("渲染 '记下来' 按钮", () => {
    setup();
    expect(screen.getByText("记下来")).toBeDefined();
  });

  it("渲染 '跳过' 按钮", () => {
    setup();
    expect(screen.getByText("跳过")).toBeDefined();
  });

  it("渲染 section-title", () => {
    setup();
    expect(screen.getByText("Reflection")).toBeDefined();
  });
});

describe("V2 REFLECTION — 按钮交互", () => {
  it("点击 '记下来' 触发 onSubmit", async () => {
    const { onSubmit } = setup();
    const user = userEvent.setup();
    const textarea = screen.getByPlaceholderText(/我以前以为/);
    await user.type(textarea, "今天理解了 SYN 的作用");
    await user.click(screen.getByText("记下来"));
    expect(onSubmit).toHaveBeenCalledWith("今天理解了 SYN 的作用");
  });

  it("点击 '跳过' 触发 onSkip", async () => {
    const { onSkip } = setup();
    const user = userEvent.setup();
    await user.click(screen.getByText("跳过"));
    expect(onSkip).toHaveBeenCalledTimes(1);
  });

  it("transitioning 时按钮 disabled", () => {
    setup({ transitioning: true });
    const btn = screen.getByRole("button", { name: /保存/ });
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });
});
