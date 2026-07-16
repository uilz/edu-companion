// ============================================================
// EXP-04 V2 · END Screen 单元测试
//
// V2 变化：
//   - 成长叙事风格
//   - "今天就到这里"
//   - 显示 Reflection 内容
//   - "返回 Today" 按钮
// ============================================================

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import Exp04EndScreen from "@/components/session/exp04/Exp04EndScreen";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

function setup(overrides: Partial<Parameters<typeof Exp04EndScreen>[0]> = {}) {
  const engine = { process: vi.fn(() => ({ shouldSpeak: true, message: null })) } as any;
  const props = {
    engine,
    reflectionContent: null as string | null,
    missionTitle: undefined as string | undefined,
    ...overrides,
  };
  const utils = render(<Exp04EndScreen {...props} />);
  return { ...utils };
}

describe("V2 END — 基础渲染", () => {
  it("渲染 '今天就到这里' 标题", () => {
    setup();
    expect(screen.getByText("今天就到这里")).toBeDefined();
  });

  it("渲染 '返回 Today' 按钮", () => {
    setup();
    expect(screen.getByText("返回 Today")).toBeDefined();
  });

  it("无 reflectionContent 时显示默认成长叙事", () => {
    setup();
    expect(screen.getByText(/每一次你试着用自己的话讲出来/)).toBeDefined();
  });

  it("有 reflectionContent 时显示内容", () => {
    setup({ reflectionContent: "今天理解了三次握手" });
    expect(screen.getByText(/今天理解了三次握手/)).toBeDefined();
    expect(screen.getByText("你今天收获了什么？")).toBeDefined();
  });
});
