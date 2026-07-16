// ============================================================
// EXP-04 组件统一导出
// ============================================================

export { useExp04StateMachine } from "./state-machine";
export type { Exp04StateMachine } from "./state-machine";

export { createConversationEngine } from "./conversation-engine";
export type { ConversationEngine } from "./conversation-engine";

export { isExp04Enabled, useExp04Enabled } from "./feature-flag";

export { initMechanismLogger, logMechanismEvent, flushEvents } from "./mechanism-logger";
export type { MechanismEventName, MechanismEvent } from "./mechanism-logger";

export * from "./types";
