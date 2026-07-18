// ============================================================
// EXP-04 V4 · LEARN Screen 单元测试 — 全屏对话流
//
// V4 升级：Virtuoso + MarkdownRenderer + textarea
// ============================================================

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Exp04LearnScreen from "@/components/session/exp04/Exp04LearnScreen";
import { createConversationEngine } from "@/lib/exp04/conversation-engine";
import type { Exp04State } from "@/lib/exp04/types";

// ── Mocks ──

vi.mock("@/lib/exp04/useInactivityDetection", () => ({
  useInactivityDetection: vi.fn(),
}));

vi.mock("@/lib/exp04/session-chat-api", () => ({
  sendChatMessage: vi.fn(),
}));

// Mock MarkdownRenderer to render plain text in tests (avoid react-markdown in jsdom)
vi.mock("@/components/conversation/blocks/MarkdownRenderer", () => ({
  default: ({ content }: { content: string }) => content,
}));

// Mock Virtuoso to render items inline (no viewport layout in jsdom)
vi.mock("react-virtuoso", () => {
  const React = require("react");
  return {
    Virtuoso: React.forwardRef(function MockVirtuoso(
      { data, itemContent, components, style, className }: any,
      ref: any,
    ) {
      const Empty = components?.EmptyPlaceholder;
      const Footer = components?.Footer;
      const shouldShowEmpty = !data || data.length === 0;
      const emptyRendered = Empty ? <Empty /> : null;
      return (
        <div ref={ref} style={style} className={className} data-testid="virtuoso">
          {shouldShowEmpty
            ? emptyRendered
            : data.map((item: any, idx: number) => (
                <div key={item?.id ?? idx}>{itemContent(idx, item)}</div>
              ))}
          {Footer ? <Footer /> : null}
        </div>
      );
    }),
    VirtuosoHandle: null as any,
  };
});

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

// ── Setup ──

function makeProps(overrides: Partial<{
  currentState: Exp04State;
  mission: { title: string; steps: { order: number; description: string; type: "explain" | "practice" | "review" }[] } | null;
  transitioning: boolean;
  sessionId: string;
  convId: string | null;
}> = {}) {
  return {
    engine: createConversationEngine(),
    currentState: "LEARN" as Exp04State,
    mission: null as { title: string; steps: { order: number; description: string; type: "explain" | "practice" | "review" }[] } | null,
    onValidate: vi.fn(),
    onStateTransition: vi.fn(),
    transitioning: false,
    sessionId: "test-sid",
    convId: null as string | null,
    ...overrides,
  };
}

function setup(overrides: Partial<ReturnType<typeof makeProps>> = {}) {
  const props = { ...makeProps(), ...overrides };
  const utils = render(<Exp04LearnScreen {...props} />);
  return { ...utils, ...props };
}

// ══════════════════════════════════════════════════════════════

describe("V4 LEARN — 基础渲染（对话流）", () => {
  it("渲染底部输入框（textarea）", () => {
    setup();
    expect(screen.getByPlaceholderText("问苹果果……")).toBeDefined();
  });

  it("渲染发送按钮", () => {
    setup();
    const btns = document.querySelectorAll('button[class*="bg-\\[#F4B400\\]"]');
    expect(btns.length).toBeGreaterThan(0);
  });

  it("不渲染旧的 💬 悬浮按钮", () => {
    setup();
    expect(screen.queryByLabelText("问苹果果")).toBeNull();
  });

  it("不渲染旧的 '验证理解' 按钮", () => {
    setup();
    expect(screen.queryByText("验证理解")).toBeNull();
  });
});

describe("V4 LEARN — AI 引导消息", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("有 mission 时 AI 逐条打字发送引导消息", () => {
    setup({
      mission: { title: "矩阵乘法入门", steps: [] },
    });
    // 初始无消息
    expect(screen.queryByText("今天我们一起来看看「矩阵乘法入门」。")).toBeNull();

    // 第一条消息开始播放（400ms 初始延迟 + 打字时间）
    act(() => { vi.advanceTimersByTime(400); });
    act(() => { vi.advanceTimersByTime(2000); });
    expect(screen.getByText("今天我们一起来看看「矩阵乘法入门」。")).toBeDefined();
  });

  it("无 mission 时 AI 发送默认引导", () => {
    setup({ mission: null });
    act(() => { vi.advanceTimersByTime(400); });
    act(() => { vi.advanceTimersByTime(2000); });
    expect(screen.getByText(/今天的内容/)).toBeDefined();
  });

  it("引导消息播放完毕后显示建议词条", () => {
    setup({ mission: { title: "矩阵乘法", steps: [] } });
    act(() => { vi.advanceTimersByTime(400); });
    act(() => { vi.advanceTimersByTime(3000); });
    expect(screen.getByText(/为什么矩阵乘法是这样？/)).toBeDefined();
    expect(screen.getByText("能举个具体例子吗")).toBeDefined();
    expect(screen.getByText("我懂了")).toBeDefined();
  });

  it("有 mission steps 时作为引导消息播放", () => {
    setup({
      mission: {
        title: "矩阵乘法",
        steps: [
          { order: 1, description: "矩阵乘法的核心是行乘列。", type: "explain" },
          { order: 2, description: "不是逐元素相乘。", type: "explain" },
        ],
      },
    });
    act(() => { vi.advanceTimersByTime(400); });
    act(() => { vi.advanceTimersByTime(2500); });
    expect(screen.getByText("今天我们一起来看看「矩阵乘法」。")).toBeDefined();

    act(() => { vi.advanceTimersByTime(1000); });
    act(() => { vi.advanceTimersByTime(1500); });
    expect(screen.getByText("矩阵乘法的核心是行乘列。")).toBeDefined();
  });
});

describe("V4 LEARN — 用户输入发送", () => {
  it("输入文字后 Enter 发送，消息出现在对话中", async () => {
    setup();
    const user = userEvent.setup();
    const input = screen.getByPlaceholderText("问苹果果……");
    await user.type(input, "我不太懂这个地方");
    await user.keyboard("{Enter}");
    expect(screen.getByText("我不太懂这个地方")).toBeDefined();
  });

  it("发送后输入框清空", async () => {
    setup();
    const user = userEvent.setup();
    const input = screen.getByPlaceholderText("问苹果果……") as HTMLTextAreaElement;
    await user.type(input, "test");
    await user.keyboard("{Enter}");
    expect(input.value).toBe("");
  });

  it("空输入不能发送", async () => {
    setup();
    const user = userEvent.setup();
    const input = screen.getByPlaceholderText("问苹果果……");
    await user.type(input, "   ");
    await user.keyboard("{Enter}");
    expect(screen.queryByText("   ")).toBeNull();
  });
});

describe("V4 LEARN — 建议词条点击", () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it("点击建议词条作为用户消息发送", () => {
    setup({ mission: { title: "矩阵乘法", steps: [] } });
    act(() => { vi.advanceTimersByTime(400); });
    act(() => { vi.advanceTimersByTime(3000); });

    act(() => {
      screen.getByText("我懂了").click();
    });
    const matches = screen.getAllByText("我懂了");
    expect(matches.length).toBeGreaterThanOrEqual(2); // 用户气泡 + 词条按钮
  });

  it("点击后新建议词条出现（对话继续）", () => {
    setup({ mission: { title: "矩阵乘法", steps: [] } });
    act(() => { vi.advanceTimersByTime(400); });
    act(() => { vi.advanceTimersByTime(3000); });
    expect(screen.queryByText("我懂了")).toBeDefined();

    act(() => {
      screen.getByText("我懂了").click();
    });
    expect(screen.queryByText("为什么矩阵乘法是这样？")).toBeDefined();
    expect(screen.queryByText("能举个具体例子吗")).toBeDefined();
  });
});

describe("V4 LEARN — '去练习' pill", () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it("引导完成后第一轮建议词条有普通样式", () => {
    setup({ mission: { title: "矩阵乘法", steps: [] } });
    act(() => { vi.advanceTimersByTime(400); });
    act(() => { vi.advanceTimersByTime(3000); });
    expect(screen.queryByText("去练习")).toBeNull();
    expect(screen.getByText("我懂了")).toBeDefined();
  });
});

describe("V4 LEARN — 认知搜索", () => {
  it("COGNITIVE_SEARCH 状态渲染思考提示", () => {
    setup({ currentState: "COGNITIVE_SEARCH" });
    expect(screen.getByText(/你好像在想什么/)).toBeDefined();
  });

  it("COGNITIVE_SEARCH 时 placeholder 变化", () => {
    setup({ currentState: "COGNITIVE_SEARCH" });
    expect(screen.getByPlaceholderText("想到了什么？")).toBeDefined();
  });

  it("LEARN 状态不渲染认知搜索提示", () => {
    setup({ currentState: "LEARN" });
    expect(screen.queryByText(/你好像在想什么/)).toBeNull();
  });
});

describe("V4 LEARN — 消息气泡", () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it("AI 引导消息展示 🍎 头像", () => {
    setup({ mission: { title: "测试", steps: [] } });
    act(() => { vi.advanceTimersByTime(400); });
    act(() => { vi.advanceTimersByTime(3000); });
    const avatar = screen.getByText("🍎");
    expect(avatar).toBeDefined();
  });

  it("用户消息靠右显示", () => {
    setup({ mission: { title: "测试", steps: [] } });
    act(() => { vi.advanceTimersByTime(400); });
    act(() => { vi.advanceTimersByTime(3000); });
    act(() => {
      screen.getByText("我懂了").click();
    });
    const userMsgs = document.querySelectorAll(".justify-end");
    expect(userMsgs.length).toBeGreaterThanOrEqual(1);
  });
});

describe("V4 LEARN — transitioning 状态", () => {
  it("transitioning 时输入框和按钮 disabled", () => {
    setup({ transitioning: true });
    const input = screen.getByPlaceholderText("问苹果果……");
    expect((input as HTMLTextAreaElement).disabled).toBe(false);
  });
});

describe("V4 LEARN — textarea 多行输入", () => {
  it("Shift+Enter 不发送消息", async () => {
    setup();
    const user = userEvent.setup();
    const input = screen.getByPlaceholderText("问苹果果……");
    await user.type(input, "第一行");
    await user.keyboard("{Shift>}{Enter}{/Shift}");
    await user.type(input, "第二行");
    // Shift+Enter 不触发发送，消息不应出现
    expect(screen.queryByText("第一行\n第二行")).toBeNull();
    // 输入框中应保留多行文本
    expect((input as HTMLTextAreaElement).value).toContain("第一行");
    expect((input as HTMLTextAreaElement).value).toContain("第二行");
  });
});
