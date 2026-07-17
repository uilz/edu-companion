// ============================================================
// EXP-04 Session 容器（EPIC-05 完成）
//
// State Machine + Conversation Engine 驱动的全流程 Session。
// 5 屏全部就位：ENTER → LEARN → SELF_VALIDATION → REFLECTION → END
//
// EPIC-01: State Machine + Conversation Engine + Feature Flag
// EPIC-02: ENTER + LEARN
// EPIC-03: Cognitive Search + Conversation Engine 接驳
// EPIC-04: Self-Validation
// EPIC-05: Reflection + End
// ============================================================

"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Loader2 } from "lucide-react";
import { authedFetch } from "@/lib/api/api";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { useExp04StateMachine } from "@/lib/exp04/state-machine";
import { createConversationEngine } from "@/lib/exp04/conversation-engine";
import type { Exp04State, StateEvent } from "@/lib/exp04/types";
import { BACKEND_STAGE_TO_EXP04 } from "@/lib/exp04/types";
import Exp04EnterScreen from "./exp04/Exp04EnterScreen";
import Exp04LearnScreen from "./exp04/Exp04LearnScreen";
import Exp04SelfValidationScreen from "./exp04/Exp04SelfValidationScreen";
import Exp04ObservationScreen from "./exp04/Exp04ObservationScreen";
import Exp04ReflectionScreen from "./exp04/Exp04ReflectionScreen";
import Exp04EndScreen from "./exp04/Exp04EndScreen";
import StageDots from "./exp04/StageDots";
import ProgressBar from "./exp04/ProgressBar";
import ToolTray, { type ToolKey } from "./exp04/ToolTray";
import ActivePrompt from "./exp04/ActivePrompt";
import PracticeCard from "./exp04/PracticeCard";
import FlashcardCreatePanel from "./exp04/FlashcardCreatePanel";
import PomodoroPanel from "./exp04/PomodoroPanel";
import CanvasPanel from "./exp04/CanvasPanel";
import { getToolState, updateToolState } from "@/lib/api/session-tool-api";
import { generateQuestions } from "@/lib/api/practice-api";
import type { V7Question } from "@/lib/api/practice-api";
import { toast, useToastStore } from "@/components/ui/Toast";
import { initMechanismLogger, logMechanismEvent, flushEvents } from "@/lib/exp04/mechanism-logger";

// ── API helpers ───────────────────────────────────────────

async function apiFetch(path: string, options?: RequestInit): Promise<Response> {
  return authedFetch(path, options);
}

// ── EXP-04 工具 / 练习 / 闪卡 fallback ──────────────────

const FALLBACK_PRACTICE_QUESTION: V7Question = {
  id: "fallback_session_q1",
  bank_id: "fallback",
  question_type: "single",
  stem: "TCP 三次握手中，第三次握手的核心作用是什么？",
  options: [
    { letter: "A", text: "确认客户端到服务器的双向通路都已建立", is_correct: true },
    { letter: "B", text: "服务器通知客户端可以开始发送数据", is_correct: false },
    { letter: "C", text: "客户端第一次携带实际数据", is_correct: false },
    { letter: "D", text: "关闭旧的连接状态", is_correct: false },
  ],
  difficulty: 1,
  cognitive_node_ids: [],
  metadata: {},
};

interface ToolState {
  nudges?: string[];
  activeTool?: ToolKey | null;
  cardCreated?: boolean;
  practiceDone?: boolean;
  [key: string]: unknown;
}

// ── 类型（与 SessionPage 同源，后续 Epic 统一迁移） ──────

interface SessionData {
  id: string;
  title: string;
  stage: string;
  status: string;
  estimated_minutes: number;
  started_at: number;
  finished_at: number | null;
  conversation_id: string | null;
  mission: { title: string; estimated_minutes: number; steps: MissionStep[] } | null;
  reflection: { content: string; key_takeaways: string[]; next_steps: string[] } | null;
}

interface MissionStep {
  order: number;
  description: string;
  type: "explain" | "practice" | "review";
  status: "pending" | "active" | "completed";
}

// ── 主容器 ────────────────────────────────────────────────

export default function Exp04Session() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const sessionId = params.id;

  // ── State Machine ──
  const sm = useExp04StateMachine("ENTER");

  // ── Conversation Engine ──
  const engine = useMemo(() => createConversationEngine(), []);

  // ── Session Data (same API as old SessionPage) ──
  const [session, setSession] = useState<SessionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [transitioning, setTransitioning] = useState(false);
  const [reflectionContent, setReflectionContent] = useState<string | null>(null);

  // ── EXP-04 工具托盘 / 主动提示 / 练习 / 闪卡 ──
  const [toolState, setToolState] = useState<ToolState>({});
  const [activeTool, setActiveTool] = useState<ToolKey | null>(null);
  const [practiceOpen, setPracticeOpen] = useState(false);
  const [practiceQuestion, setPracticeQuestion] = useState<V7Question | null>(null);
  const [practiceLoading, setPracticeLoading] = useState(false);
  const [flashcardOpen, setFlashcardOpen] = useState(false);
  const [flashcardDefaultFront, setFlashcardDefaultFront] = useState("");
  const [pomodoroOpen, setPomodoroOpen] = useState(false);
  const [canvasOpen, setCanvasOpen] = useState(false);
  const [prompts, setPrompts] = useState<string[]>([]);

  const fetchSession = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/session/${sessionId}`);
      if (res.ok) {
        const data = await res.json();
        setSession(data);

        // Sync backend stage → state machine（仅首次加载）
        const mappedState = BACKEND_STAGE_TO_EXP04[data.stage];
        if (mappedState && mappedState !== sm.currentState) {
          // 不做强制同步，State Machine 是权威来源
          console.debug(
            `[EXP04] Backend stage=${data.stage}, SM state=${sm.currentState}`
          );
        }
      } else {
        setError("找不到这个学习 Session");
      }
    } catch {
      setError("加载 Session 失败");
    } finally {
      setLoading(false);
    }
  }, [sessionId, sm.currentState]);

  // ── 加载工具托盘状态 ──
  const fetchToolState = useCallback(async () => {
    if (!sessionId) return;
    try {
      const state = await getToolState(sessionId);
      setToolState((state || {}) as ToolState);
    } catch (e) {
      console.debug("[EXP04] tool-state 加载失败，使用本地状态", e);
    }
  }, [sessionId]);

  useEffect(() => { fetchSession(); fetchToolState(); }, [fetchSession, fetchToolState]);

  // ── Mechanism Logger 初始化 ──
  useEffect(() => {
    if (session) {
      initMechanismLogger(session.id);
      logMechanismEvent("session.entered", {
        from: document.referrer ? "direct" : "today",
        is_returning: !!session.mission?.title,
        has_mission: !!session.mission?.steps?.length,
      });
    }
    return () => { flushEvents(); };
  }, [session?.id]);

  // ── 旧 API → State Machine 事件映射 ──

  const transitionStage = async (targetBackendStage: string) => {
    // 先通过后端 API 更新 stage
    setTransitioning(true);
    try {
      const res = await apiFetch(`/api/session/${sessionId}/stage`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_stage: targetBackendStage }),
      });
      if (res.ok) {
        await fetchSession();
        // 后触发状态机事件
        const event = mapBackendStageToEvent(targetBackendStage);
        if (event) sm.transition(event);
      }
    } catch (e) {
      console.error("Stage transition failed:", e);
    } finally {
      setTransitioning(false);
    }
  };

  const cancelSession = async () => {
    if (!window.confirm("确定取消这次学习吗？你可以随时从 Today 继续。")) return;
    setTransitioning(true);
    try {
      const res = await apiFetch(`/api/session/${sessionId}/cancel`, {
        method: "POST",
      });
      sm.transition({ type: "SESSION_CANCELLED" });
      if (res.ok) {
        router.push("/");
      } else {
        console.error("Cancel session failed:", await res.text().catch(() => ""));
      }
    } catch (e) {
      console.error("Cancel session error:", e);
    } finally {
      setTransitioning(false);
    }
  };

  // ── Reflection 处理器（EPIC-05） ──

  const handleReflectionSubmit = async (content: string) => {
    setTransitioning(true);
    try {
      await apiFetch(`/api/session/${sessionId}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reflection: { content, key_takeaways: [], next_steps: [] },
        }),
      });
      setReflectionContent(content);
      sm.transition({ type: "REFLECTION_DONE" });
      await fetchSession();
    } catch (e) {
      console.error("Reflection submit failed:", e);
    } finally {
      setTransitioning(false);
    }
  };

  const handleReflectionSkip = async () => {
    setTransitioning(true);
    try {
      await apiFetch(`/api/session/${sessionId}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reflection: null }),
      });
      setReflectionContent(null);
      sm.transition({ type: "REFLECTION_DONE" });
      await fetchSession();
    } catch (e) {
      console.error("Reflection skip failed:", e);
    } finally {
      setTransitioning(false);
    }
  };

  // ── Self-Validation 专用导航 ──

  const handleBackToLearn = async () => {
    setTransitioning(true);
    try {
      await apiFetch(`/api/session/${sessionId}/stage`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_stage: "learn" }),
      });
      sm.transition({ type: "BACK_TO_LEARN" });
      await fetchSession();
    } catch (e) {
      console.error("Back to learn failed:", e);
    } finally {
      setTransitioning(false);
    }
  };

  const handleValidationDone = async () => {
    setTransitioning(true);
    try {
      await apiFetch(`/api/session/${sessionId}/stage`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_stage: "reflect" }),
      });
      sm.transition({ type: "VALIDATION_DONE" });
      await fetchSession();
    } catch (e) {
      console.error("Validation done failed:", e);
    } finally {
      setTransitioning(false);
    }
  };

  // ── EXP-04 工具托盘 / 主动提示 / 练习 / 闪卡逻辑 ──

  const patchToolState = useCallback(async (patch: Partial<ToolState>) => {
    if (!sessionId) return;
    const next = { ...toolState, ...patch };
    setToolState(next);
    try {
      await updateToolState(sessionId, next);
    } catch (e) {
      console.warn("[EXP04] 工具状态同步失败", e);
    }
  }, [sessionId, toolState]);

  const handleOpenTool = useCallback((tool: ToolKey) => {
    setActiveTool(tool);
    patchToolState({ activeTool: tool });

    if (tool === "flashcard") {
      setFlashcardDefaultFront("");
      setFlashcardOpen(true);
      return;
    }

    if (tool === "pomodoro") {
      setPomodoroOpen(true);
      return;
    }

    if (tool === "canvas") {
      setCanvasOpen(true);
      return;
    }

    // 其余工具当前为占位：记录 nudge 并给出轻反馈
    const nudges = [...(toolState.nudges || [])];
    if (!nudges.includes(tool)) nudges.push(tool);
    patchToolState({ nudges });

    const labels: Record<ToolKey, string> = {
      voice: "语音",
      canvas: "画布",
      handwriting: "手写",
      files: "文件",
      pomodoro: "番茄钟",
      flashcard: "闪卡",
    };
    toast.info(`${labels[tool]}工具`, "即将开放，先专注当前学习吧");
  }, [patchToolState, toolState.nudges]);

  const handleStartPractice = useCallback(async () => {
    if (practiceLoading || practiceOpen) return;
    setPracticeLoading(true);
    try {
      const topic = session?.title || session?.mission?.title || "当前学习内容";
      const result = await generateQuestions(topic);
      const question = result.questions?.[0] || FALLBACK_PRACTICE_QUESTION;
      setPracticeQuestion(question);
      setPracticeOpen(true);
      sm.transition({ type: "PRACTICE_STARTED" });
    } catch (e) {
      console.warn("[EXP04] 出题失败，使用 fallback", e);
      setPracticeQuestion(FALLBACK_PRACTICE_QUESTION);
      setPracticeOpen(true);
      sm.transition({ type: "PRACTICE_STARTED" });
    } finally {
      setPracticeLoading(false);
    }
  }, [practiceLoading, practiceOpen, session?.title, session?.mission?.title, sm]);

  const handlePracticeDone = useCallback((correct: boolean) => {
    setPracticeOpen(false);
    sm.transition({ type: "PRACTICE_DONE", correct });
    patchToolState({ practiceDone: true });
    useToastStore.getState().push({
      type: "info",
      title: correct ? "这个思路很清晰。" : "我们再看看这里。",
      duration: 2500,
    });
  }, [patchToolState, sm]);

  const handleFlashcardCreated = useCallback((card: { front_text?: string }) => {
    setFlashcardOpen(false);
    sm.transition({ type: "FLASHCARD_CREATED" });
    patchToolState({ cardCreated: true });
    toast.success("已保存闪卡", card.front_text || "以后复习会再见到");
  }, [patchToolState, sm]);

  const handlePromptClick = useCallback((prompt: string) => {
    sm.transition({ type: "PROMPT_CLICKED", prompt });
    if (prompt.includes("练习") || prompt.includes("检验") || prompt.includes("练一练")) {
      handleStartPractice();
      return;
    }
    if (prompt.includes("闪卡") || prompt.includes("记下")) {
      setFlashcardDefaultFront("");
      setFlashcardOpen(true);
      return;
    }
    if (prompt.includes("画布")) {
      handleOpenTool("canvas");
      return;
    }
    if (prompt.includes("手写")) {
      handleOpenTool("handwriting");
      return;
    }
    // 默认：当作与苹果果的对话输入（仅 toast 反馈）
    toast.info("苹果果听到了", prompt);
  }, [handleOpenTool, handleStartPractice, sm]);

  // 根据当前状态维护主动提示
  useEffect(() => {
    const next: string[] = [];
    if (sm.currentState === "LEARN") {
      if (!toolState.practiceDone) next.push("来检验一下理解吧～");
      if (!toolState.cardCreated) next.push("这个点值得记下来");
    } else if (sm.currentState === "OBSERVATION") {
      if (!toolState.practiceDone) next.push("再练一道");
      if (!toolState.cardCreated) next.push("做成一张卡记住它");
    }
    setPrompts(next);
  }, [sm.currentState, toolState.practiceDone, toolState.cardCreated]);

  // 一段时间后轻轻提示工具托盘（仅在 LEARN 且未主动展开过工具）
  useEffect(() => {
    if (sm.currentState !== "LEARN") return;
    if (toolState.nudges?.length || activeTool) return;
    const timer = setTimeout(() => {
      patchToolState({ nudges: ["tool"] });
    }, 8000);
    return () => clearTimeout(timer);
  }, [sm.currentState, toolState.nudges, activeTool, patchToolState]);

  // ── 原文参考（EPIC-04: 后端生成前，从 mission 提取 fallback） ──

  const referenceText = useMemo(() => {
    if (!session?.mission?.steps) return null;
    const explainSteps = session.mission.steps
      .filter((s) => s.type === "explain" && s.description)
      .map((s) => s.description);
    return explainSteps.length > 0 ? explainSteps.join("；") : null;
  }, [session?.mission?.steps]);

  // ── Loading ──
  if (loading) return <SessionSkeleton />;

  // ── Error ──
  if (error || !session) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <p className="text-ink-muted">{error || "Session 不存在"}</p>
        <Button variant="ghost" onClick={() => router.push("/")}>
          返回首页
        </Button>
      </div>
    );
  }

  const isEnd = sm.currentState === "END";
  const isEnter = sm.currentState === "ENTER";
  const showHeader = !isEnd;

  return (
    <div className="flex flex-col min-h-screen bg-page">
      {/* ── Header ── */}
      {showHeader && (
        <header
          className={`flex items-center gap-3 px-4 py-3 border-b border-border bg-page/80 backdrop-blur sticky top-0 z-10 ${
            isEnter ? "justify-between" : ""
          }`}
        >
          <button
            onClick={() => router.push("/")}
            className="p-1.5 rounded-lg hover:bg-surface-hover transition-colors"
          >
            <ArrowLeft size={20} className="text-ink-muted" />
          </button>

          {!isEnter && (
            <>
              <h1 className="text-base font-semibold text-ink-primary flex-1 truncate">
                {session.title || "学习 Session"}
              </h1>
              <StageDots currentState={sm.currentState} />
              <div className="w-2" />
              <ToolTray
                nudge={toolState.nudges?.[0] ?? null}
                activeTool={activeTool}
                onOpenTool={handleOpenTool}
              />
            </>
          )}

          <button
            onClick={cancelSession}
            disabled={transitioning}
            className="text-xs text-ink-muted hover:text-red-500 disabled:opacity-50 px-2 py-1"
          >
            取消
          </button>
        </header>
      )}

      {/* ── Progress Bar ── */}
      {showHeader && <ProgressBar currentState={sm.currentState} />}

      {/* ── Active Prompts ── */}
      {!isEnter && !isEnd && (
        <ActivePrompt prompts={prompts} onPromptClick={handlePromptClick} />
      )}

      {/* ── Stage Content ── */}
      <div className="flex-1 overflow-y-auto">
        {isEnd ? (
          <Exp04EndScreen
            engine={engine}
            reflectionContent={reflectionContent}
          />
        ) : (
          <StageContent
            session={session}
            currentState={sm.currentState}
            onTransition={transitionStage}
            transitioning={transitioning}
            engine={engine}
            onStateTransition={sm.transition}
            referenceText={referenceText}
            onBackToLearn={handleBackToLearn}
            onValidationDone={handleValidationDone}
            onReflectionSubmit={handleReflectionSubmit}
            onReflectionSkip={handleReflectionSkip}
            onObservationDone={() => sm.transition({ type: "OBSERVATION_DONE" })}
          />
        )}
      </div>

      {/* ── Practice Card Overlay ── */}
      {practiceOpen && practiceQuestion && (
        <PracticeCard
          question={practiceQuestion}
          onDone={handlePracticeDone}
          onClose={() => setPracticeOpen(false)}
        />
      )}

      {/* ── Flashcard Create Panel Overlay ── */}
      {flashcardOpen && (
        <FlashcardCreatePanel
          sessionId={sessionId}
          defaultFront={flashcardDefaultFront}
          onCreated={handleFlashcardCreated}
          onClose={() => setFlashcardOpen(false)}
        />
      )}

      {/* ── Pomodoro Panel Overlay ── */}
      <PomodoroPanel
        sessionTitle={session?.title || session?.mission?.title}
        open={pomodoroOpen}
        onClose={() => setPomodoroOpen(false)}
      />

      {/* ── Canvas Panel Overlay ── */}
      <CanvasPanel
        sessionTitle={session?.title || session?.mission?.title}
        open={canvasOpen}
        onClose={() => setCanvasOpen(false)}
      />
    </div>
  );
}

// ── 工具函数 ──────────────────────────────────────────────

function mapBackendStageToEvent(stage: string): StateEvent | null {
  switch (stage) {
    case "learn":   return { type: "START_CLICKED" };
    case "practice":return { type: "VALIDATION_REQUESTED" };
    case "reflect": return { type: "VALIDATION_DONE" };
    default:        return null;
  }
}

// ── Stage Content ──────────────────────────────────────────

function StageContent({
  session,
  currentState,
  onTransition,
  transitioning,
  engine,
  onStateTransition,
  referenceText,
  onBackToLearn,
  onValidationDone,
  onReflectionSubmit,
  onReflectionSkip,
  onObservationDone,
}: {
  session: SessionData;
  currentState: Exp04State;
  onTransition: (stage: string) => Promise<void>;
  transitioning: boolean;
  engine: ReturnType<typeof createConversationEngine>;
  onStateTransition: (event: StateEvent) => void;
  referenceText: string | null;
  onBackToLearn: () => Promise<void>;
  onValidationDone: () => Promise<void>;
  onReflectionSubmit: (content: string) => Promise<void>;
  onReflectionSkip: () => Promise<void>;
  onObservationDone: () => void;
}) {
  switch (currentState) {
    case "ENTER":
      return (
        <Exp04EnterScreen
          engine={engine}
          currentState={currentState}
          mission={session.mission}
          lastTitle={null}
          onStart={() => onTransition("learn")}
          transitioning={transitioning}
        />
      );
    case "LEARN":
    case "COGNITIVE_SEARCH":
      return (
        <Exp04LearnScreen
          engine={engine}
          currentState={currentState}
          mission={session.mission}
          onValidate={() => onTransition("practice")}
          onStateTransition={onStateTransition}
          transitioning={transitioning}
          sessionId={session.id}
          convId={session.conversation_id}
        />
      );
    case "SELF_VALIDATION":
      return (
        <Exp04SelfValidationScreen
          engine={engine}
          currentState={currentState}
          mission={session.mission}
          referenceText={referenceText}
          onBackToLearn={onBackToLearn}
          onContinue={onValidationDone}
          transitioning={transitioning}
          sessionId={session.id}
          missionTitle={session.title || session.mission?.title}
        />
      );
    case "OBSERVATION":
      return (
        <Exp04ObservationScreen
          mission={session.mission}
          referenceText={referenceText}
          onContinue={onObservationDone}
          transitioning={transitioning}
          sessionId={session.id}
          missionTitle={session.title || session.mission?.title}
        />
      );
    case "REFLECTION":
      return (
        <Exp04ReflectionScreen
          engine={engine}
          currentState={currentState}
          onSkip={onReflectionSkip}
          onSubmit={onReflectionSubmit}
          transitioning={transitioning}
        />
      );
    default:
      return <p className="p-8 text-ink-muted text-center">未知阶段</p>;
  }
}

// ── Skeleton ───────────────────────────────────────────────

function SessionSkeleton() {
  return (
    <div className="flex flex-col min-h-screen bg-bg-primary">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
        <Skeleton className="w-8 h-8 rounded-lg" />
        <Skeleton className="h-6 w-48" />
      </div>
      <div className="px-4 py-4 space-y-4">
        <Skeleton className="h-4 w-64" />
        <Skeleton className="h-20 w-full rounded-xl" />
        <Skeleton className="h-20 w-full rounded-xl" />
        <Skeleton className="h-12 w-40 mx-auto rounded-full" />
      </div>
    </div>
  );
}
