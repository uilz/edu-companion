// ============================================================
// EXP-04 Conversation Engine — 单元测试
//
// 覆盖：
//   1. canSpeak: 每种状态的沉默规则
//   2. getHardcodedMessage: 硬编码文案返回
//   3. validate: 字数+禁用词校验
//   4. process: 完整输出流程
// ============================================================

import { describe, it, expect } from "vitest";
import { createConversationEngine } from "@/lib/exp04/conversation-engine";
import type { Exp04State, ConversationTrigger } from "@/lib/exp04/types";

function setup() {
  return createConversationEngine();
}

describe("EXP-04 Conversation Engine — canSpeak (沉默规则)", () => {
  const engine = setup();

  // ── ENTER ──
  it("ENTER: SESSION_ENTER 可以说话", () => {
    expect(engine.canSpeak("ENTER", "SESSION_ENTER")).toBe(true);
  });

  it("ENTER: USER_MESSAGE 不可以说话", () => {
    expect(engine.canSpeak("ENTER", "USER_MESSAGE")).toBe(false);
  });

  it("ENTER: ENERGY_DECLINING 不可以说话", () => {
    expect(engine.canSpeak("ENTER", "ENERGY_DECLINING")).toBe(false);
  });

  // ── LEARN ──
  it("LEARN: USER_MESSAGE 可以说话", () => {
    expect(engine.canSpeak("LEARN", "USER_MESSAGE")).toBe(true);
  });

  it("LEARN: ENERGY_DECLINING 可以说话", () => {
    expect(engine.canSpeak("LEARN", "ENERGY_DECLINING")).toBe(true);
  });

  it("LEARN: SESSION_ENTER 不可以说话", () => {
    expect(engine.canSpeak("LEARN", "SESSION_ENTER")).toBe(false);
  });

  it("LEARN: SEARCH_DETECTED 不可以说话", () => {
    expect(engine.canSpeak("LEARN", "SEARCH_DETECTED")).toBe(false);
  });

  // ── COGNITIVE_SEARCH ──
  it("COGNITIVE_SEARCH: SEARCH_DETECTED 可以说话", () => {
    expect(engine.canSpeak("COGNITIVE_SEARCH", "SEARCH_DETECTED")).toBe(true);
  });

  it("COGNITIVE_SEARCH: USER_MESSAGE 不可以说话", () => {
    expect(engine.canSpeak("COGNITIVE_SEARCH", "USER_MESSAGE")).toBe(false);
  });

  // ── SELF_VALIDATION ──
  it("SELF_VALIDATION: VALIDATION_REQUESTED 可以说话", () => {
    expect(engine.canSpeak("SELF_VALIDATION", "VALIDATION_REQUESTED")).toBe(true);
  });

  it("SELF_VALIDATION: PRACTICE_PROMPT 可以说话", () => {
    expect(engine.canSpeak("SELF_VALIDATION", "PRACTICE_PROMPT")).toBe(true);
  });

  it("SELF_VALIDATION: PRACTICE_FEEDBACK 可以说话", () => {
    expect(engine.canSpeak("SELF_VALIDATION", "PRACTICE_FEEDBACK")).toBe(true);
  });

  it("SELF_VALIDATION: USER_MESSAGE 不可以说话", () => {
    expect(engine.canSpeak("SELF_VALIDATION", "USER_MESSAGE")).toBe(false);
  });

  // ── REFLECTION ──
  it("REFLECTION: REFLECTION_ENTERED 可以说话", () => {
    expect(engine.canSpeak("REFLECTION", "REFLECTION_ENTERED")).toBe(true);
  });

  it("REFLECTION: USER_MESSAGE 不可以说话", () => {
    expect(engine.canSpeak("REFLECTION", "USER_MESSAGE")).toBe(false);
  });

  // ── END ──
  it("END: 任何触发都不说话", () => {
    const triggers: ConversationTrigger[] = [
      "SESSION_ENTER", "USER_MESSAGE", "SEARCH_DETECTED",
      "VALIDATION_REQUESTED", "REFLECTION_ENTERED",
      "ENERGY_DECLINING", "SESSION_ENDING",
    ];
    for (const trigger of triggers) {
      expect(engine.canSpeak("END", trigger)).toBe(false);
    }
  });
});

describe("EXP-04 Conversation Engine — getHardcodedMessage (硬编码文案)", () => {
  const engine = setup();

  it("SESSION_ENTER 无 last_title: 今天从一个问题开始", () => {
    const msg = engine.getHardcodedMessage("ENTER", "SESSION_ENTER", {});
    expect(msg).toBe("今天，我们从一个问题开始。准备好了吗？");
  });

  it("SESSION_ENTER 有 last_title: 上次我们停在这里", () => {
    const msg = engine.getHardcodedMessage("ENTER", "SESSION_ENTER", {
      last_title: "分数的意义",
    });
    expect(msg).toBe("上次我们就停在这里。你当时在想什么？");
  });

  it("SEARCH_DETECTED: 这里可以多想一会儿", () => {
    const msg = engine.getHardcodedMessage("COGNITIVE_SEARCH", "SEARCH_DETECTED");
    expect(msg).toBe("这里可以多想一会儿。不着急，慢慢来。");
  });

  it("REFLECTION_ENTERED: 如果只能记住一件事", () => {
    const msg = engine.getHardcodedMessage("REFLECTION", "REFLECTION_ENTERED");
    expect(msg).toBe("今天的这些内容，如果只能记住一件事，你希望是什么？");
  });

  it("SESSION_ENDING: 在 LEARN 状态被静默（LEARN 不接收 SESSION_ENDING）", () => {
    // SESSION_ENDING 在所有当前状态均被静默，EPIC-03/04 将激活
    expect(engine.canSpeak("LEARN", "SESSION_ENDING")).toBe(false);
    expect(engine.canSpeak("ENTER", "SESSION_ENDING")).toBe(false);
  });

  it("ENERGY_DECLINING: 今天就到这里吧", () => {
    const msg = engine.getHardcodedMessage("LEARN", "ENERGY_DECLINING");
    expect(msg).toBe("今天就到这里吧。你已经想了很久了。");
  });

  it("USER_MESSAGE 无硬编码文案（需要 AI）", () => {
    const msg = engine.getHardcodedMessage("LEARN", "USER_MESSAGE");
    expect(msg).toBeNull();
  });

  it("不允许说话的触发返回 null", () => {
    const msg = engine.getHardcodedMessage("ENTER", "USER_MESSAGE");
    expect(msg).toBeNull();
  });
});

describe("EXP-04 Conversation Engine — validate (消息校验)", () => {
  const engine = setup();

  it("合法消息通过", () => {
    expect(engine.validate("我们来看看这个问题，你之前是怎么想的？")).toBeNull();
    expect(engine.validate("今天学到了很多东西，可以再想一遍。")).toBeNull();
  });

  it("消息过长: 超过 maxChars (60)", () => {
    // 61 个中文字符，超过 maxChars=60
    const longMsg = Array(61).fill("学").join("");
    const err = engine.validate(longMsg);
    expect(err).not.toBeNull();
    expect(err).toContain("过长");
  });

  it("消息过短: 少于 minChars (15)", () => {
    const err = engine.validate("好。");
    expect(err).not.toBeNull();
    expect(err).toContain("过短");
  });

  it("包含禁用词", () => {
    expect(engine.validate("正确！你答对了")).not.toBeNull();
    expect(engine.validate("加油，你可以的")).not.toBeNull();
    expect(engine.validate("你还应该继续努力")).not.toBeNull();
    expect(engine.validate("太棒了")).not.toBeNull();
    expect(engine.validate("你这样是错的")).not.toBeNull();
    expect(engine.validate("快一点完成这个任务")).not.toBeNull();
  });
});

describe("EXP-04 Conversation Engine — process (完整输出)", () => {
  const engine = setup();

  it("ENTER + SESSION_ENTER → shouldSpeak=true, 硬编码消息", () => {
    const output = engine.process("ENTER", "SESSION_ENTER");
    expect(output.shouldSpeak).toBe(true);
    expect(output.message).toBe("今天，我们从一个问题开始。准备好了吗？");
  });

  it("ENTER + USER_MESSAGE → shouldSpeak=false (沉默)", () => {
    const output = engine.process("ENTER", "USER_MESSAGE");
    expect(output.shouldSpeak).toBe(false);
    expect(output.message).toBeNull();
    expect(output.reason).toContain("不允许");
  });

  it("LEARN + USER_MESSAGE + AI消息 → 校验通过后返回", () => {
    const output = engine.process("LEARN", "USER_MESSAGE", "这是一个很好的问题，让我帮你看看。");
    expect(output.shouldSpeak).toBe(true);
    expect(output.message).toBe("这是一个很好的问题，让我帮你看看。");
  });

  it("LEARN + USER_MESSAGE + AI消息含禁用词 → 拒绝", () => {
    const output = engine.process("LEARN", "USER_MESSAGE", "正确！太棒了，你的理解完全没问题。");
    expect(output.shouldSpeak).toBe(false);
    expect(output.message).toBeNull();
    expect(output.reason).toContain("禁用词");
  });

  it("COGNITIVE_SEARCH + SEARCH_DETECTED → 硬编码安慰消息", () => {
    const output = engine.process("COGNITIVE_SEARCH", "SEARCH_DETECTED");
    expect(output.shouldSpeak).toBe(true);
    expect(output.message).toBe("这里可以多想一会儿。不着急，慢慢来。");
  });

  it("END + SESSION_ENDING → shouldSpeak=false", () => {
    const output = engine.process("END", "SESSION_ENDING");
    expect(output.shouldSpeak).toBe(false);
    expect(output.message).toBeNull();
  });
});
