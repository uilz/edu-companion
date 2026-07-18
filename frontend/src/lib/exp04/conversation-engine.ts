// ============================================================
// EXP-04 Conversation Engine
//
// 苹果果的说话规则引擎。
// 决定"能不能说话"和"说什么"——不决定"怎么说"（那是 AI 的事）。
//
// 规则来自 Implementation Model Layer C。
// ============================================================

import type {
  Exp04State,
  ConversationTrigger,
  EngineOutput,
  MessageSpec,
} from "./types";
import { DEFAULT_MESSAGE_SPEC } from "./types";

// ── 沉默规则 ──────────────────────────────────────────────

/**
 * 返回 true = 不能说话（沉默）。
 */
function isSilenced(state: Exp04State, trigger: ConversationTrigger): boolean {
  // 终态永远不说话
  if (state === "END") return true;

  switch (state) {
    case "LEARN":
      // LEARN 中：用户消息、能量下降、工具/练习/闪卡主动提示可说话
      return ![
        "USER_MESSAGE",
        "ENERGY_DECLINING",
        "TOOL_NUDGE",
        "PRACTICE_PROMPT",
        "PRACTICE_FEEDBACK",
        "FLASHCARD_SUGGESTION",
      ].includes(trigger);

    case "COGNITIVE_SEARCH":
      // COGNITIVE_SEARCH 只在 SEARCH_DETECTED（第二阶段）时说话
      return trigger !== "SEARCH_DETECTED";

    case "SELF_VALIDATION":
      // SELF_VALIDATION：进入验证、练习、工具/闪卡提示可说话；用户写的过程中其他触发静默
      return !["VALIDATION_REQUESTED", "TOOL_NUDGE", "PRACTICE_PROMPT", "PRACTICE_FEEDBACK", "FLASHCARD_SUGGESTION"].includes(
        trigger
      );

    case "REFLECTION":
      // REFLECTION 只在进入时说一句提取问题；闪卡建议可轻声提示
      // 用户写的过程中完全沉默
      return !["REFLECTION_ENTERED", "FLASHCARD_SUGGESTION"].includes(trigger);

    case "ENTER":
      // ENTER 只在 SESSION_ENTER 时说话
      return trigger !== "SESSION_ENTER";

    default:
      return true;
  }
}

// ── 消息格式化 ────────────────────────────────────────────

/**
 * 检查消息是否符合规格。
 */
function validateMessage(text: string, spec: MessageSpec): string | null {
  const len = text.length;

  // 字数检查
  if (len > spec.maxChars) {
    return `消息过长 (${len} > ${spec.maxChars})`;
  }
  if (len < spec.minChars) {
    return `消息过短 (${len} < ${spec.minChars})`;
  }

  // 禁用词检查
  for (const word of spec.forbiddenWords) {
    if (text.includes(word)) {
      return `包含禁用词: "${word}"`;
    }
  }

  return null; // 通过
}

// ── 硬编码文案 ────────────────────────────────────────────

export interface HardcodedContext {
  last_title?: string | null;
  /** PRACTICE_FEEDBACK / TOOL_NUDGE 等场景使用 */
  correct?: boolean;
  tool?: string;
  prompt?: string;
}

/**
 * 非 AI 内容——问候、确认、结束语等固定文案。
 * 这些内容不由 LLM 生成，直接硬编码。
 */
const HARDCODED_MESSAGES: Partial<
  Record<ConversationTrigger, (ctx: HardcodedContext) => string>
> = {
  SESSION_ENTER: (ctx) =>
    ctx.last_title
      ? `上次我们就停在这里。你当时在想什么？`
      : "今天，我们从一个问题开始。准备好了吗？",

  SEARCH_DETECTED: () => "这里可以多想一会儿。不着急，慢慢来。",

  REFLECTION_ENTERED: () =>
    "今天的这些内容，如果只能记住一件事，你希望是什么？",

  SESSION_ENDING: () => "今天就到这里。我会记住今天的这些。",

  ENERGY_DECLINING: () => "今天就到这里吧。你已经想了很久了。",

  TOOL_NUDGE: (ctx) => {
    if (ctx.tool === "voice") return "要不用语音说出来？";
    if (ctx.tool === "canvas") return "需要用画布梳理思路吗？";
    if (ctx.tool === "handwriting") return "动手写一写，也许会更清楚。";
    return "需要换个工具试试吗？";
  },

  PRACTICE_PROMPT: () => "来检验一下理解吧～",

  PRACTICE_FEEDBACK: (ctx) =>
    ctx.correct ? "这个思路很清晰。" : "我们再看看这里。",

  FLASHCARD_SUGGESTION: () => "这个点值得记下来，以后复习。",
};

// ── 公共 API ──────────────────────────────────────────────

export interface ConversationEngineOptions {
  spec?: MessageSpec;
}

export function createConversationEngine(options?: ConversationEngineOptions) {
  const spec = options?.spec || DEFAULT_MESSAGE_SPEC;

  return {
    /**
     * 判断苹果果在当前状态下是否允许说话。
     */
    canSpeak(state: Exp04State, trigger: ConversationTrigger): boolean {
      return !isSilenced(state, trigger);
    },

    /**
     * 获取应该说的话。
     * - 硬编码文案 → 直接返回
     * - USER_MESSAGE / VALIDATION_REQUESTED → 返回 null（需要调用 AI）
     * - 不允许说话 → 返回 null
     */
    getHardcodedMessage(
      state: Exp04State,
      trigger: ConversationTrigger,
      ctx: HardcodedContext = {}
    ): string | null {
      if (!this.canSpeak(state, trigger)) return null;

      const factory = HARDCODED_MESSAGES[trigger];
      if (!factory) return null;

      return factory(ctx);
    },

    /**
     * 检查一条消息是否符合规范。
     * 返回 null = 通过，返回 string = 违规原因。
     */
    validate(text: string): string | null {
      return validateMessage(text, spec);
    },

    /**
     * 处理触发事件，返回引擎输出。
     *
     * @param state 当前 Session 状态
     * @param trigger 触发事件
     * @param aiMessage 如果是 AI 生成的消息（USER_MESSAGE 场景），传入以供校验
     * @param ctx 上下文（last_title 等）
     */
    process(
      state: Exp04State,
      trigger: ConversationTrigger,
      aiMessage?: string,
      ctx: HardcodedContext = {}
    ): EngineOutput {
      // 1. 检查是否允许说话
      if (!this.canSpeak(state, trigger)) {
        return {
          shouldSpeak: false,
          message: null,
          reason: `状态 ${state} 不允许触发 ${trigger}`,
        };
      }

      // 2. 硬编码文案优先
      const hardcoded = this.getHardcodedMessage(state, trigger, ctx);
      if (hardcoded !== null) {
        const err = this.validate(hardcoded);
        if (err) {
          console.warn(`[EXP04 CE] 硬编码文案违规: ${err}`);
          return { shouldSpeak: false, message: null, reason: err };
        }
        return { shouldSpeak: true, message: hardcoded };
      }

      // 3. AI 消息校验
      if (aiMessage) {
        const err = this.validate(aiMessage);
        if (err) {
          console.warn(`[EXP04 CE] AI 消息违规: ${err}`);
          return { shouldSpeak: false, message: null, reason: err };
        }
        return { shouldSpeak: true, message: aiMessage };
      }

      // 4. 需要 AI 但未提供
      return {
        shouldSpeak: true,
        message: null,
        reason: "需要 AI 生成内容",
      };
    },

    /** 消息规格 */
    spec,
  };
}

export type ConversationEngine = ReturnType<typeof createConversationEngine>;
