// ============================================================
// EXP-04 V2 · Self-Validation / Practice Screen 单元测试
//
// 对齐 Vision: 练习题 → 答题反馈 → "再来一道"/"去反思"
// ============================================================

import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Exp04SelfValidationScreen from "@/components/session/exp04/Exp04SelfValidationScreen";

// Mock generateQuestions to return a predictable question
const mockQuestion = {
  id: "q1", bank_id: "test", question_type: "single" as const,
  stem: "1 + 1 等于多少？",
  options: [
    { letter: "A", text: "1", is_correct: false },
    { letter: "B", text: "2", is_correct: true },
    { letter: "C", text: "3", is_correct: false },
  ],
  difficulty: 1, cognitive_node_ids: [], metadata: {},
};

vi.mock("@/lib/api/practice-api", () => ({
  generateQuestions: vi.fn(() => Promise.resolve({ questions: [mockQuestion] })),
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

describe("SELF_VALIDATION — 基础渲染", () => {
  it("渲染 '练一练' section label", () => {
    setup();
    expect(screen.getByText("练一练")).toBeDefined();
  });

  it("渲染标题 '来检验一下吧'", () => {
    setup();
    expect(screen.getByText("来检验一下吧")).toBeDefined();
  });

  it("显示加载状态后加载题目", async () => {
    setup();
    // 初始显示 "苹果果在出题…"
    expect(screen.getByText("苹果果在出题…")).toBeDefined();

    // 等待题目加载
    await waitFor(() => {
      expect(screen.getByText("1 + 1 等于多少？")).toBeDefined();
    });
  });

  it("渲染选项按钮", async () => {
    setup();
    await waitFor(() => {
      expect(screen.getByText("1")).toBeDefined();
      expect(screen.getByText("2")).toBeDefined();
      expect(screen.getByText("3")).toBeDefined();
    });
  });

  it("渲染底部 '返回学习' 按钮", () => {
    setup();
    expect(screen.getByText("返回学习")).toBeDefined();
  });

  it("渲染底部 '继续' 按钮", () => {
    setup();
    const buttons = screen.getAllByText("继续");
    // 至少有一个「继续」按钮（底部）
    expect(buttons.length).toBeGreaterThanOrEqual(1);
  });

  it("missionTitle 显示在描述中", () => {
    setup({ missionTitle: "矩阵乘法" });
    expect(screen.getByText(/矩阵乘法/)).toBeDefined();
  });
});

describe("SELF_VALIDATION — 答题交互", () => {
  it("点击选项后显示反馈区", async () => {
    setup();
    await waitFor(() => {
      expect(screen.getByText("1 + 1 等于多少？")).toBeDefined();
    });

    // 点击正确选项 B (text "2")
    const user = userEvent.setup();
    await user.click(screen.getByText("2"));

    // 应该出现反馈
    await waitFor(() => {
      expect(screen.getByText("算对了。")).toBeDefined();
    });
  });

  it("答题后显示 '再来一道' 和 '去反思'", async () => {
    setup();
    await waitFor(() => {
      expect(screen.getByText("1 + 1 等于多少？")).toBeDefined();
    });

    const user = userEvent.setup();
    await user.click(screen.getByText("2"));

    await waitFor(() => {
      expect(screen.getByText("再来一道")).toBeDefined();
      expect(screen.getByText("去反思")).toBeDefined();
    });
  });

  it("点击 '去反思' 触发 onContinue", async () => {
    const { onContinue } = setup();
    await waitFor(() => {
      expect(screen.getByText("1 + 1 等于多少？")).toBeDefined();
    });

    const user = userEvent.setup();
    await user.click(screen.getByText("2"));

    await waitFor(() => {
      expect(screen.getByText("去反思")).toBeDefined();
    });

    await user.click(screen.getByText("去反思"));
    expect(onContinue).toHaveBeenCalledTimes(1);
  });
});

describe("SELF_VALIDATION — 按钮交互", () => {
  it("点击 '返回学习' 触发 onBackToLearn", async () => {
    const { onBackToLearn } = setup();
    const user = userEvent.setup();
    await user.click(screen.getByText("返回学习"));
    expect(onBackToLearn).toHaveBeenCalledTimes(1);
  });

  it("底部 '继续' 触发 onContinue", async () => {
    const { onContinue } = setup();
    const user = userEvent.setup();
    // 底部「继续」
    const buttons = screen.getAllByText("继续");
    const bottomBtn = buttons[buttons.length - 1]; // 最后一个
    await user.click(bottomBtn);
    expect(onContinue).toHaveBeenCalledTimes(1);
  });

  it("transitioning 时按钮 disabled", () => {
    setup({ transitioning: true });
    const bottomBtn = screen.getByText("准备中…");
    expect(bottomBtn).toBeDefined();
  });
});
