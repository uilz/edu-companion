// ============================================================
// EXP-04 类型定义
//
// Session State Machine + Conversation Engine 的类型系统。
// 所有 EXP-04 组件共享的类型定义。
// ============================================================

// ── 状态 ──────────────────────────────────────────────────

/** EXP-04 的 5 个 Session 状态（+ 结束态）。对齐 Vision: intro → learn → practice → reflect → finish */
export type Exp04State =
  | "ENTER"
  | "LEARN"
  | "COGNITIVE_SEARCH"
  | "SELF_VALIDATION"
  | "REFLECTION"
  | "END";

/** 旧 Session 的 stage 字符串 → EXP-04 状态映射（用于兼容） */
export const BACKEND_STAGE_TO_EXP04: Record<string, Exp04State> = {
  intro: "ENTER",
  learn: "LEARN",
  practice: "SELF_VALIDATION",
  reflect: "REFLECTION",
  finish: "END",
};

export const EXP04_TO_BACKEND_STAGE: Partial<Record<Exp04State, string>> = {
  ENTER: "intro",
  LEARN: "learn",
  SELF_VALIDATION: "practice",
  REFLECTION: "reflect",
  END: "completed",
};

// ── 状态事件 ──────────────────────────────────────────────

export type StateEvent =
  | { type: "SESSION_ENTERED" }
  | { type: "START_CLICKED" }
  | { type: "ENTER_TIMEOUT" }
  | { type: "INACTIVITY_DETECTED" }
  | { type: "INTERACTION_RESUMED" }
  | { type: "VALIDATION_REQUESTED" }
  | { type: "BACK_TO_LEARN" }
  | { type: "VALIDATION_DONE" }
  | { type: "REFLECTION_DONE" }
  | { type: "SESSION_CANCELLED" }
  // 工具 / 练习 / 主动提示 / 闪卡事件（自环，用于追踪交互）
  | { type: "TOOL_OPENED"; tool: string }
  | { type: "TOOL_CLOSED"; tool: string }
  | { type: "PRACTICE_STARTED" }
  | { type: "PRACTICE_DONE"; correct: boolean }
  | { type: "FLASHCARD_CREATED"; cardId?: string }
  | { type: "PROMPT_CLICKED"; prompt: string };

// ── 对话触发 ──────────────────────────────────────────────

export type ConversationTrigger =
  | "SESSION_ENTER"
  | "USER_MESSAGE"
  | "SEARCH_DETECTED"
  | "VALIDATION_REQUESTED"
  | "REFLECTION_ENTERED"
  | "ENERGY_DECLINING"
  | "SESSION_ENDING"
  // 工具 / 练习 / 主动提示 / 闪卡触发
  | "TOOL_NUDGE"
  | "PRACTICE_PROMPT"
  | "PRACTICE_FEEDBACK"
  | "FLASHCARD_SUGGESTION";

// ── 消息规格 ──────────────────────────────────────────────

export interface MessageSpec {
  maxChars: number;
  minChars: number;
  forbiddenWords: string[];
}

export const DEFAULT_MESSAGE_SPEC: MessageSpec = {
  maxChars: 60,
  minChars: 15,
  forbiddenWords: [
    "正确", "错误", "对", "加油", "太棒了", "快", "还需要", "你应该",
  ],
};

/** Conversation Engine 的输出 */
export interface EngineOutput {
  shouldSpeak: boolean;
  message: string | null;
  reason?: string; // 为什么不说话（调试用）
}

// ── 停留检测 ──────────────────────────────────────────────

export interface DwellState {
  isActive: boolean;
  phase: "OBSERVING" | "CONFIRMED" | "SPOKEN";
  startedAt: number | null;
  confirmedAt: number | null;
}

export const DWELL_PHASE1_MS = 90_000; // 90s 第一阶段：观察
export const DWELL_PHASE2_MS = 180_000; // 180s 第二阶段：确认说话
// 第二阶段触发 = 从 startedAt 起累计 180s

// ── Session 上下文 ─────────────────────────────────────────

export interface Exp04Context {
  user_id: string;
  session_id: string;
  has_history: boolean; // 是否有上次学习记录
  last_title: string | null; // 上次学习标题
  days_ago: number | null; // 间隔天数（welcome_back 场景）
}
