// ============================================================
// EXP-04 State Machine
//
// Session 状态机。管理 ENTER → LEARN → COGNITIVE_SEARCH →
// SELF_VALIDATION → REFLECTION → END 的状态转换。
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
  ENTER: new Set(["START_CLICKED", "ENTER_TIMEOUT", "SESSION_CANCELLED"]),
  LEARN: new Set([
    "INACTIVITY_DETECTED",
    "VALIDATION_REQUESTED",
    "SESSION_CANCELLED",
  ]),
  COGNITIVE_SEARCH: new Set([
    "INTERACTION_RESUMED",
    "SESSION_CANCELLED",
  ]),
  SELF_VALIDATION: new Set([
    "BACK_TO_LEARN",
    "VALIDATION_DONE",
    "SESSION_CANCELLED",
  ]),
  OBSERVATION: new Set(["OBSERVATION_DONE", "SESSION_CANCELLED"]),
  REFLECTION: new Set(["REFLECTION_DONE", "SESSION_CANCELLED"]),
  END: new Set([]), // 终态，不可转换
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
  },
  COGNITIVE_SEARCH: {
    INTERACTION_RESUMED: "LEARN",
    SESSION_CANCELLED: "END",
  },
  SELF_VALIDATION: {
    BACK_TO_LEARN: "LEARN",
    VALIDATION_DONE: "OBSERVATION",
    SESSION_CANCELLED: "END",
  },
  OBSERVATION: {
    OBSERVATION_DONE: "REFLECTION",
    SESSION_CANCELLED: "END",
  },
  REFLECTION: {
    REFLECTION_DONE: "END",
    SESSION_CANCELLED: "END",
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
