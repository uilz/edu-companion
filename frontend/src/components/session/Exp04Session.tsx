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
import { initMechanismLogger, logMechanismEvent, flushEvents } from "@/lib/exp04/mechanism-logger";

// ── API helpers ───────────────────────────────────────────

async function apiFetch(path: string, options?: RequestInit): Promise<Response> {
  return authedFetch(path, options);
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

  useEffect(() => { fetchSession(); }, [fetchSession]);

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

  return (
    <div className="flex flex-col min-h-screen bg-bg-primary">
      {/* ── Header ── */}
      {isEnter ? (
        /* ENTER: 极简头 — 仅返回 + 取消 */
        <header className="flex items-center justify-between px-4 py-3 border-b border-border">
          <button
            onClick={() => router.push("/")}
            className="p-1.5 rounded-lg hover:bg-bg-secondary transition-colors"
          >
            <ArrowLeft size={20} className="text-ink-muted" />
          </button>
          <button
            onClick={cancelSession}
            disabled={transitioning}
            className="text-xs text-ink-muted hover:text-red-500 disabled:opacity-50 px-2 py-1"
          >
            取消
          </button>
        </header>
      ) : isEnd ? null : (
        /* LEARN+：简化头 — 无计时器；END 屏无 Header */
        <header className="flex items-center gap-3 px-4 py-3 border-b border-border bg-bg-primary/80 backdrop-blur sticky top-0 z-10">
          <button
            onClick={() => router.push("/")}
            className="p-1.5 rounded-lg hover:bg-bg-secondary transition-colors"
          >
            <ArrowLeft size={20} className="text-ink-muted" />
          </button>
          <h1 className="text-lg font-semibold text-ink-primary flex-1 truncate">
            {session.title || "学习 Session"}
          </h1>
          <button
            onClick={cancelSession}
            disabled={transitioning}
            className="text-xs text-ink-muted hover:text-red-500 disabled:opacity-50 px-2 py-1"
          >
            取消
          </button>
        </header>
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
