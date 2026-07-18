// ============================================================
// EXP-04 Conversation Engine — Stage + Mode 感知说话规则
//
// 决定"能不能说话"和"说什么"——不决定"怎么说"（那是 AI 的事）。
//
// 模式感知：
//   - normal: 默认对话规则
//   - stuck: 卡住状态，AI 主动提供帮助
//   - silent: 安静模式，AI 继续讲解
//   - deep_chat: 深度对话，AI 跟随提问
//   - breakthrough: 顿悟庆祝
// ============================================================

import type {
  SessionStage,
  SessionMode,
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
  if (state.stage === "finish") return true;

  switch (state.stage) {
    case "enter":
      // enter 只在 SESSION_ENTER 时说话
      return trigger !== "SESSION_ENTER";

    case "chat":
      // chat 阶段：默认所有 trigger 都可说话
      // 但模式会决定 AI 是否主动说（由 Exp04Session 控制调用频率）
      return false;

    case "reflect":
      // reflect 只在进入时说一句；闪卡建议可轻声提示
      return !["REFLECTION_ENTERED", "FLASHCARD_SUGGESTION"].includes(trigger);

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
  correct?: boolean;
  tool?: string;
  mode?: SessionMode;
}

/**
 * 非 AI 内容——问候、确认、结束语等固定文案。
 */
const HARDCODED_MESSAGES: Partial<
  Record<ConversationTrigger, (ctx: HardcodedContext) => string>
> = {
  // ── 进入问候 ──
  SESSION_ENTER: (ctx) =>
    ctx.last_title
      ? "今天聊聊这个。我还是从上次你停顿的地方开始。"
      : "今天，我们从一个问题开始。准备好了吗？",

  // ── 模式感知文案 ──
  STUCK_DETECTED: () =>
    "等等，我看你在这里想了很久。要不要换个角度看看？",

  BREAKTHROUGH_DETECTED: () =>
    "你理解了！这个感觉很棒。趁热来一道，巩固一下？",

  SILENT_MODE_ACTIVE: () =>
    "没关系，我接着说。你随时可以打断我。",

  DEEP_CHAT_ACTIVE: (ctx) =>
    `你问得很好。我们往深走一步。`,

  // ── 反思 ──
  REFLECTION_ENTERED: () =>
    "学到什么了？写不写都行。苹果果已经记住了。",

  SESSION_ENDING: () =>
    "今天就到这里。我会记住今天的这些。",

  ENERGY_DECLINING: () =>
    "今天就到这里吧。你已经想了很久了。",

  // ── 工具建议 ──
  TOOL_NUDGE: (ctx) => {
    if (ctx.tool === "voice") return "要不用语音说出来？";
    if (ctx.tool === "canvas") return "需要用画布梳理思路吗？";
    if (ctx.tool === "handwriting") return "动手写一写，也许会更清楚。";
    return "需要换个工具试试吗？";
  },

  PRACTICE_PROMPT: () =>
    "来，想不想试试看？",

  PRACTICE_FEEDBACK: (ctx) =>
    ctx.correct ? "这个思路很清晰。" : "我们再看看这里。",

  FLASHCARD_SUGGESTION: () =>
    "这个点值得记下来，以后复习。",
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
     * - USER_MESSAGE 等 → 返回 null（需要调用 AI）
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
     */
    validate(text: string): string | null {
      return validateMessage(text, spec);
    },

    /**
     * 处理触发事件，返回引擎输出。
     *
     * @param state 当前 Session 状态（含 stage + mode）
     * @param trigger 触发事件
     * @param aiMessage 如果是 AI 生成的消息，传入以供校验
     * @param ctx 上下文
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
          reason: `状态 ${state.stage}/${state.mode} 不允许触发 ${trigger}`,
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
