// ============================================================
// EXP-04 State Machine
//
// Session 状态机。管理 ENTER → LEARN → COGNITIVE_SEARCH →
// SELF_VALIDATION → REFLECTION → END 的状态转换。
// 对齐 Vision 5 段：intro → learn → practice → reflect → finish
//
// 每条转换规则都对应 Implementation Model Layer B 的定义。
// ============================================================

import { useReducer, useCallback, useRef } from "react";
import type {
  Exp04State,
  StateEvent,
} from "./types";

// ── 转换表 ────────────────────────────────────────────────

/**
 * 合法的状态转换。
 * key = 当前状态，value = 允许的事件类型集合。
 */
const TRANSITIONS: Record<Exp04State, Set<StateEvent["type"]>> = {
  ENTER: new Set<StateEvent["type"]>([
    "START_CLICKED", "ENTER_TIMEOUT", "SESSION_CANCELLED",
  ]),
  LEARN: new Set<StateEvent["type"]>([
    "INACTIVITY_DETECTED",
    "VALIDATION_REQUESTED",
    "SESSION_CANCELLED",
    // 工具 / 练习 / 主动提示 / 闪卡
    "TOOL_OPENED",
    "TOOL_CLOSED",
    "PRACTICE_STARTED",
    "PRACTICE_DONE",
    "FLASHCARD_CREATED",
    "PROMPT_CLICKED",
  ]),
  COGNITIVE_SEARCH: new Set<StateEvent["type"]>([
    "INTERACTION_RESUMED", "SESSION_CANCELLED",
  ]),
  SELF_VALIDATION: new Set<StateEvent["type"]>([
    "BACK_TO_LEARN",
    "VALIDATION_DONE",
    "SESSION_CANCELLED",
    // 工具 / 练习 / 闪卡
    "TOOL_OPENED",
    "TOOL_CLOSED",
    "PRACTICE_STARTED",
    "PRACTICE_DONE",
    "FLASHCARD_CREATED",
    "PROMPT_CLICKED",
  ]),
  REFLECTION: new Set<StateEvent["type"]>([
    "REFLECTION_DONE",
    "SESSION_CANCELLED",
    // 工具 / 闪卡
    "TOOL_OPENED",
    "TOOL_CLOSED",
    "FLASHCARD_CREATED",
    "PROMPT_CLICKED",
  ]),
  END: new Set<StateEvent["type"]>([]), // 终态，不可转换
};

/**
 * 事件 → 目标状态的映射。
 */
const NEXT_STATE: Record<string, Record<string, Exp04State>> = {
  ENTER: {
    START_CLICKED: "LEARN",
    ENTER_TIMEOUT: "LEARN",
    SESSION_CANCELLED: "END",
  },
  LEARN: {
    INACTIVITY_DETECTED: "COGNITIVE_SEARCH",
    VALIDATION_REQUESTED: "SELF_VALIDATION",
    SESSION_CANCELLED: "END",
    // 工具 / 练习 / 主动提示 / 闪卡均为自环
    TOOL_OPENED: "LEARN",
    TOOL_CLOSED: "LEARN",
    PRACTICE_STARTED: "LEARN",
    PRACTICE_DONE: "LEARN",
    FLASHCARD_CREATED: "LEARN",
    PROMPT_CLICKED: "LEARN",
  },
  COGNITIVE_SEARCH: {
    INTERACTION_RESUMED: "LEARN",
    SESSION_CANCELLED: "END",
  },
  SELF_VALIDATION: {
    BACK_TO_LEARN: "LEARN",
    VALIDATION_DONE: "REFLECTION",
    SESSION_CANCELLED: "END",
    // 工具 / 闪卡 / 练习自环
    TOOL_OPENED: "SELF_VALIDATION",
    TOOL_CLOSED: "SELF_VALIDATION",
    PRACTICE_STARTED: "SELF_VALIDATION",
    PRACTICE_DONE: "SELF_VALIDATION",
    FLASHCARD_CREATED: "SELF_VALIDATION",
    PROMPT_CLICKED: "SELF_VALIDATION",
  },
  REFLECTION: {
    REFLECTION_DONE: "END",
    SESSION_CANCELLED: "END",
    // 工具 / 闪卡自环
    TOOL_OPENED: "REFLECTION",
    TOOL_CLOSED: "REFLECTION",
    FLASHCARD_CREATED: "REFLECTION",
    PROMPT_CLICKED: "REFLECTION",
  },
  END: {},
};

// ── State ──────────────────────────────────────────────────

interface StateMachineState {
  current: Exp04State;
  previous: Exp04State | null;
  transitionCount: number;
}

type Action =
  | { type: "TRANSITION"; event: StateEvent }
  | { type: "INIT"; state: Exp04State };

function reducer(
  state: StateMachineState,
  action: Action
): StateMachineState {
  switch (action.type) {
    case "INIT":
      return { current: action.state, previous: null, transitionCount: 0 };

    case "TRANSITION": {
      const allowed = TRANSITIONS[state.current];
      if (!allowed || !allowed.has(action.event.type)) {
        // 非法转换 → 静默忽略（不进 END，不抛错）
        console.debug(
          `[EXP04 SM] 非法转换: ${state.current} → ${action.event.type}`
        );
        return state;
      }

      const nextStateMap = NEXT_STATE[state.current];
      if (!nextStateMap) return state;

      const next = nextStateMap[action.event.type];
      if (!next) return state;

      return {
        current: next,
        previous: state.current,
        transitionCount: state.transitionCount + 1,
      };
    }

    default:
      return state;
  }
}

// ── Hook ───────────────────────────────────────────────────

const initialState: StateMachineState = {
  current: "ENTER",
  previous: null,
  transitionCount: 0,
};

export function useExp04StateMachine(initial?: Exp04State) {
  const [state, dispatch] = useReducer(reducer, {
    ...initialState,
    current: initial || "ENTER",
  });

  const transition = useCallback((event: StateEvent) => {
    dispatch({ type: "TRANSITION", event });
  }, []);

  const canTransition = useCallback(
    (eventType: StateEvent["type"]): boolean => {
      const allowed = TRANSITIONS[state.current];
      return allowed ? allowed.has(eventType) : false;
    },
    [state.current]
  );

  return {
    currentState: state.current,
    previousState: state.previous,
    transitionCount: state.transitionCount,
    transition,
    canTransition,
  } as const;
}

export type Exp04StateMachine = ReturnType<typeof useExp04StateMachine>;
