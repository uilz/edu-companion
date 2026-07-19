// ============================================================
// EXP-04 类型定义
//
// Stage(进度) + Mode(体验) 双轴状态模型。
// Session State Machine + Conversation Engine 的类型系统。
// 所有 EXP-04 组件共享的类型定义。
// ============================================================

// ── 状态 ──────────────────────────────────────────────────

/** Session 进度阶段（3 段 + finish，对应顶部 4 个圆点） */
export type SessionStage = "enter" | "chat" | "reflect" | "finish";

/** 体验模式：AI 根据用户行为动态选择 */
export type SessionMode =
  | "normal"         // 默认对话
  | "deep_chat"      // 用户追问轮次多 → 深度对话
  | "stuck"          // 停留检测 → 卡住状态
  | "silent"         // 用户很少回复 → 安静讲解
  | "breakthrough";  // 卡住后答对 → 顿悟庆祝

/** 情绪基调（影响视觉风格和文案语气） */
export type SessionMood = "warm" | "neutral" | "cautious";

/** 新状态类型：进度 + 体验双轴 */
export interface Exp04State {
  stage: SessionStage;
  mode: SessionMode;
}

// ── 状态辅助函数 ──────────────────────────────────────────

export function getStageIndex(stage: SessionStage): number {
  return ["enter", "chat", "reflect", "finish"].indexOf(stage);
}

export function getStageCount(): number {
  return 4;
}

export function getMood(mode: SessionMode): SessionMood {
  switch (mode) {
    case "deep_chat":
    case "breakthrough":
      return "warm";
    case "stuck":
    case "silent":
      return "cautious";
    default:
      return "neutral";
  }
}

/**
 * Old backend stage → Exp04 state mapping.
 *
 * Studio 设计理念：practice 是 chat 阶段的内联活动（通过 ActivePrompt
 * + BottomDock 工具触发），不独立为一个阶段。因此 learn 和 practice
 * 都映射到 chat。后端仅跟踪 session 整体进度，细粒度活动由前端状态机管理。
 */
export const BACKEND_STAGE_TO_EXP04: Record<string, Partial<{ stage: SessionStage; mode: SessionMode }>> = {
  intro: { stage: "enter", mode: "normal" },
  learn: { stage: "chat", mode: "normal" },
  practice: { stage: "chat", mode: "normal" },
  reflect: { stage: "reflect", mode: "normal" },
  finish: { stage: "finish", mode: "normal" },
};

export const EXP04_TO_BACKEND_STAGE: Record<SessionStage, string> = {
  enter: "intro",
  chat: "learn",
  reflect: "reflect",
  finish: "completed",
};

// ── 状态事件 ──────────────────────────────────────────────

export type StateEvent =
  // 进度转换事件
  | { type: "START_CLICKED" }
  | { type: "ENTER_TIMEOUT" }
  | { type: "REFLECTION_REQUESTED" }
  | { type: "REFLECTION_DONE" }
  | { type: "SESSION_CANCELLED" }
  // 体验模式检测事件
  | { type: "INACTIVITY_DETECTED" }
  | { type: "INTERACTION_RESUMED" }
  | { type: "STUCK_RESOLVED" }       // 卡住后答对
  | { type: "SILENT_MODE" }
  | { type: "DEEP_CHAT_MODE" }
  | { type: "MODE_RESET" }
  // 练习事件（在对话流中内联）
  | { type: "PRACTICE_STARTED" }
  | { type: "PRACTICE_DONE"; correct: boolean }
  // 工具 / 闪卡自环
  | { type: "TOOL_OPENED"; tool: string }
  | { type: "TOOL_CLOSED"; tool: string }
  | { type: "FLASHCARD_CREATED"; cardId?: string };

// ── 对话触发 ──────────────────────────────────────────────

export type ConversationTrigger =
  // 现有 trigger
  | "SESSION_ENTER"
  | "USER_MESSAGE"
  | "REFLECTION_ENTERED"
  | "ENERGY_DECLINING"
  | "SESSION_ENDING"
  // 工具 / 练习 / 闪卡
  | "TOOL_NUDGE"
  | "PRACTICE_PROMPT"
  | "PRACTICE_FEEDBACK"
  | "FLASHCARD_SUGGESTION"
  // 模式感知 trigger（新增）
  | "STUCK_DETECTED"
  | "BREAKTHROUGH_DETECTED"
  | "SILENT_MODE_ACTIVE"
  | "DEEP_CHAT_ACTIVE";

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
