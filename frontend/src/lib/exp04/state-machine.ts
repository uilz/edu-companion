// ============================================================
// EXP-04 State Machine — Stage + Mode 双轴模型
//
// Stage（进度）：enter → chat → reflect → finish（不可逆，对应 4 个圆点）
// Mode（体验）：normal / deep_chat / stuck / silent / breakthrough（在 chat 阶段可切换）
//
// Mode 转换由 Exp04Session 中的行为检测驱动（非自动）。
// ============================================================

import { useReducer, useCallback } from "react";
import type {
  SessionStage,
  SessionMode,
  Exp04State,
  StateEvent,
} from "./types";
import { getStageIndex } from "./types";

// ── Stage 转换表 ──────────────────────────────────────────

/** 合法的 stage 转换事件 */
const STAGE_TRANSITIONS: Record<SessionStage, Set<StateEvent["type"]>> = {
  enter: new Set<StateEvent["type"]>(["START_CLICKED", "ENTER_TIMEOUT", "SESSION_CANCELLED"]),
  chat: new Set<StateEvent["type"]>(["REFLECTION_REQUESTED", "SESSION_CANCELLED",
    "TOOL_OPENED", "TOOL_CLOSED", "FLASHCARD_CREATED", "PRACTICE_STARTED", "PRACTICE_DONE",
  ]),
  reflect: new Set<StateEvent["type"]>(["REFLECTION_DONE", "SESSION_CANCELLED",
    "TOOL_OPENED", "TOOL_CLOSED", "FLASHCARD_CREATED",
  ]),
  finish: new Set<StateEvent["type"]>(), // 终态
};

/** 事件 → 目标 stage 的映射 */
const NEXT_STAGE: Record<string, Record<string, SessionStage>> = {
  enter: {
    START_CLICKED: "chat",
    ENTER_TIMEOUT: "chat",
    SESSION_CANCELLED: "finish",
  },
  chat: {
    REFLECTION_REQUESTED: "reflect",
    SESSION_CANCELLED: "finish",
    // 自环事件
    TOOL_OPENED: "chat",
    TOOL_CLOSED: "chat",
    FLASHCARD_CREATED: "chat",
    PRACTICE_STARTED: "chat",
    PRACTICE_DONE: "chat",
  },
  reflect: {
    REFLECTION_DONE: "finish",
    SESSION_CANCELLED: "finish",
    TOOL_OPENED: "reflect",
    TOOL_CLOSED: "reflect",
    FLASHCARD_CREATED: "reflect",
  },
  finish: {},
};

// ── Mode 管理 ────────────────────────────────────────────

/** Mode 的合法转换映射（当前 mode → 可切换到的 mode 集合） */
const MODE_TRANSITIONS: Record<SessionMode, Set<SessionMode>> = {
  normal: new Set<SessionMode>(["deep_chat", "stuck", "silent"]),
  deep_chat: new Set<SessionMode>(["normal"]),
  stuck: new Set<SessionMode>(["breakthrough", "normal"]),
  silent: new Set<SessionMode>(["normal", "deep_chat"]),
  breakthrough: new Set<SessionMode>(["normal"]),
};

export function canTransitionMode(from: SessionMode, to: SessionMode): boolean {
  const allowed = MODE_TRANSITIONS[from];
  return allowed ? allowed.has(to) : false;
}

// ── State ──────────────────────────────────────────────────

interface StateMachineState {
  stage: SessionStage;
  mode: SessionMode;
  transitionCount: number;
}

type Action =
  | { type: "TRANSITION"; event: StateEvent }
  | { type: "SET_MODE"; mode: SessionMode }
  | { type: "INIT"; state: Partial<{ stage: SessionStage; mode: SessionMode }> };

function reducer(state: StateMachineState, action: Action): StateMachineState {
  switch (action.type) {
    case "INIT":
      return {
        stage: action.state.stage || "enter",
        mode: action.state.mode || "normal",
        transitionCount: 0,
      };

    case "TRANSITION": {
      const currentStage = state.stage;

      // 检查 stage 转换是否合法
      const allowed = STAGE_TRANSITIONS[currentStage];
      if (!allowed || !allowed.has(action.event.type)) {
        console.debug(
          `[EXP04 SM] 非法 stage 转换: ${currentStage} → ${action.event.type}`
        );
        return state;
      }

      const nextStageMap = NEXT_STAGE[currentStage];
      if (!nextStageMap) return state;

      const nextStage = nextStageMap[action.event.type];
      if (!nextStage) return state;

      const isStageChange = nextStage !== currentStage;

      return {
        stage: nextStage,
        mode: isStageChange ? state.mode : state.mode, // mode 在 stage 转换时不重置
        transitionCount: state.transitionCount + 1,
      };
    }

    case "SET_MODE": {
      if (!canTransitionMode(state.mode, action.mode)) {
        console.debug(
          `[EXP04 SM] 非法 mode 转换: ${state.mode} → ${action.mode}`
        );
        return state;
      }
      return {
        ...state,
        mode: action.mode,
        transitionCount: state.transitionCount + 1,
      };
    }

    default:
      return state;
  }
}

const initialState: StateMachineState = {
  stage: "enter",
  mode: "normal",
  transitionCount: 0,
};

// ── Hook ───────────────────────────────────────────────────

export function useExp04StateMachine(
  initial?: Partial<{ stage: SessionStage; mode: SessionMode }>
) {
  const [state, dispatch] = useReducer(reducer, {
    ...initialState,
    ...(initial || {}),
  });

  const transition = useCallback((event: StateEvent) => {
    dispatch({ type: "TRANSITION", event });
  }, []);

  const setMode = useCallback((mode: SessionMode) => {
    dispatch({ type: "SET_MODE", mode });
  }, []);

  const canTransition = useCallback(
    (eventType: StateEvent["type"]): boolean => {
      const allowed = STAGE_TRANSITIONS[state.stage];
      return allowed ? allowed.has(eventType) : false;
    },
    [state.stage]
  );

  return {
    currentState: { stage: state.stage, mode: state.mode } as Exp04State,
    stage: state.stage,
    mode: state.mode,
    stageIndex: getStageIndex(state.stage),
    transitionCount: state.transitionCount,
    transition,
    setMode,
    canTransition,
  } as const;
}

export type Exp04StateMachine = ReturnType<typeof useExp04StateMachine>;
