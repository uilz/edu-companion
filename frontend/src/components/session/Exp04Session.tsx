// ============================================================
// EXP-04 Session 容器 — Stage + Mode 双轴模型
//
// Stage（进度）：enter → chat → reflect → finish
// Mode（体验）：normal / deep_chat / stuck / silent / breakthrough
//
// 5 屏：ENTER → CHAT（含内联练习） → REFLECTION → END
// ============================================================

"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { authedFetch } from "@/lib/api/api";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { useExp04StateMachine } from "@/lib/exp04/state-machine";
import { createConversationEngine } from "@/lib/exp04/conversation-engine";
import type { Exp04State, SessionMode, StateEvent } from "@/lib/exp04/types";
import { BACKEND_STAGE_TO_EXP04, EXP04_TO_BACKEND_STAGE } from "@/lib/exp04/types";
import Exp04EnterScreen from "./exp04/Exp04EnterScreen";
import ChatScreen from "./exp04/ChatScreen";
import Exp04ReflectionScreen from "./exp04/Exp04ReflectionScreen";
import Exp04EndScreen from "./exp04/Exp04EndScreen";
import StageDots from "./exp04/StageDots";
import ProgressBar from "./exp04/ProgressBar";
import ResourcesSidebar from "./exp04/ResourcesSidebar";
import StudioCompanion from "./exp04/StudioCompanion";
import BottomDock from "./exp04/BottomDock";
import type { ToolKey } from "./exp04/BottomDock";
import ActivePrompt from "./exp04/ActivePrompt";
import FlashcardCreatePanel from "./exp04/FlashcardCreatePanel";
import PomodoroPanel from "./exp04/PomodoroPanel";
import CanvasPanel from "./exp04/CanvasPanel";
import VoicePanel from "./exp04/VoicePanel";
import HandwritingPanel from "./exp04/HandwritingPanel";
import FileListPanel from "./exp04/FileListPanel";
import { getToolState, updateToolState } from "@/lib/api/session-tool-api";
import { toast } from "@/components/ui/Toast";

// ── API helpers ───────────────────────────────────────────

async function apiFetch(path: string, options?: RequestInit): Promise<Response> {
  return authedFetch(path, options);
}

// ── 类型 ──────────────────────────────────────────────────

interface ToolState {
  activeTool?: ToolKey | null;
  cardCreated?: boolean;
  practiceDone?: boolean;
  [key: string]: unknown;
}

interface SessionData {
  id: string;
  title: string;
  stage: string;
  status: string;
  estimated_minutes: number;
  started_at: number;
  finished_at: number | null;
  conversation_id: string | null;
  mission: { title: string; estimated_minutes: number } | null;
  reflection: { content: string; key_takeaways: string[]; next_steps: string[] } | null;
}

// ── 主容器 ────────────────────────────────────────────────

export default function Exp04Session() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const sessionId = params.id;

  // ── State Machine（默认 enter/normal） ──
  const sm = useExp04StateMachine();

  // ── Conversation Engine ──
  const engine = useMemo(() => createConversationEngine(), []);

  // ── Session Data ──
  const [session, setSession] = useState<SessionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [transitioning, setTransitioning] = useState(false);
  const [reflectionContent, setReflectionContent] = useState<string | null>(null);

  // ── 工具状态 ──
  const [toolState, setToolState] = useState<ToolState>({});
  const [activeTool, setActiveTool] = useState<ToolKey | null>(null);
  const [flashcardOpen, setFlashcardOpen] = useState(false);
  const [flashcardDefaultFront, setFlashcardDefaultFront] = useState("");
  const [pomodoroOpen, setPomodoroOpen] = useState(false);
  const [canvasOpen, setCanvasOpen] = useState(false);
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [handwritingOpen, setHandwritingOpen] = useState(false);
  const [filesOpen, setFilesOpen] = useState(false);
  const [prompts, setPrompts] = useState<string[]>([]);
  const [messageCount, setMessageCount] = useState(0);

  // ── Fetch Session ──
  const fetchSession = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/session/${sessionId}`);
      if (res.ok) {
        const data = await res.json();
        setSession(data);
      } else {
        setError("找不到这个学习 Session");
      }
    } catch {
      setError("加载 Session 失败");
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  const fetchToolState = useCallback(async () => {
    if (!sessionId) return;
    try {
      const state = await getToolState(sessionId);
      setToolState((state || {}) as ToolState);
    } catch (e) {
      console.debug("[EXP04] tool-state 加载失败", e);
    }
  }, [sessionId]);

  useEffect(() => { fetchSession(); fetchToolState(); }, [fetchSession, fetchToolState]);

  // ── Stage 转换（同步后端） ──
  const transitionStage = async (targetStage: string) => {
    setTransitioning(true);
    try {
      await apiFetch(`/api/session/${sessionId}/stage`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_stage: targetStage }),
      });
      await fetchSession();
    } catch (e) {
      console.error("Stage transition failed:", e);
    } finally {
      setTransitioning(false);
    }
  };

  const cancelSession = async () => {
    if (!window.confirm("确定取消这次学习吗？")) return;
    setTransitioning(true);
    try {
      await apiFetch(`/api/session/${sessionId}/cancel`, { method: "POST" });
      sm.transition({ type: "SESSION_CANCELLED" });
      router.push("/");
    } catch (e) {
      console.error("Cancel session error:", e);
    } finally {
      setTransitioning(false);
    }
  };

  // ── 事件处理器 ──
  const handleEnterStart = useCallback(async () => {
    sm.transition({ type: "START_CLICKED" });
    await transitionStage(EXP04_TO_BACKEND_STAGE.chat);
  }, [sm]);

  // ChatScreen 的 transition 包装：SM 转换 + 后端同步
  const handleChatTransition = useCallback(async (event: any) => {
    sm.transition(event);
    setMessageCount((c) => c + 1);
    // REFLECTION_REQUESTED 需要同步后端到 reflect 阶段
    if (event.type === "REFLECTION_REQUESTED") {
      await transitionStage(EXP04_TO_BACKEND_STAGE.reflect);
    }
  }, [sm]);

  const handleReflectionSubmit = async (content: string) => {
    setTransitioning(true);
    try {
      await apiFetch(`/api/session/${sessionId}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reflection: { content, key_takeaways: [], next_steps: [] } }),
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

  // ── 工具逻辑 ──
  const patchToolState = useCallback(async (patch: Partial<ToolState>) => {
    if (!sessionId) return;
    const next = { ...toolState, ...patch };
    setToolState(next);
    try { await updateToolState(sessionId, next); } catch { /* ignore */ }
  }, [sessionId, toolState]);

  const handleOpenTool = useCallback((tool: ToolKey) => {
    setActiveTool(tool);
    patchToolState({ activeTool: tool });

    if (tool === "flashcard") {
      setFlashcardDefaultFront(""); setFlashcardOpen(true);
    } else if (tool === "pomodoro") { setPomodoroOpen(true); }
    else if (tool === "canvas") { setCanvasOpen(true); }
    else if (tool === "voice") { setVoiceOpen(true); }
    else if (tool === "handwriting") { setHandwritingOpen(true); }
    else if (tool === "files") { setFilesOpen(true); }
    else {
      sm.transition({ type: "TOOL_OPENED", tool });
      toast.info(`即将开放`, "先专注当前学习吧");
    }
  }, [patchToolState, sm]);

  const handleFlashcardCreated = useCallback((card: { front_text?: string }) => {
    setFlashcardOpen(false);
    sm.transition({ type: "FLASHCARD_CREATED" });
    patchToolState({ cardCreated: true });
    toast.success("已保存闪卡", card.front_text || "以后复习会再见到");
  }, [patchToolState, sm]);

  const handlePromptClick = useCallback((prompt: string) => {
    if (prompt.includes("闪卡") || prompt.includes("记下")) {
      setFlashcardDefaultFront(""); setFlashcardOpen(true);
    } else if (prompt.includes("画布")) {
      handleOpenTool("canvas");
    } else {
      toast.info("苹果果听到了", prompt);
    }
  }, [handleOpenTool]);

  // ── Mode 感知提示 ──
  useEffect(() => {
    const next: string[] = [];
    if (sm.stage === "chat" && sm.mode !== "deep_chat") {
      if (!toolState.practiceDone) next.push("来检验一下理解吧～");
      if (!toolState.cardCreated) next.push("这个点值得记下来");
    }
    setPrompts(next);
  }, [sm.stage, sm.mode, toolState.practiceDone, toolState.cardCreated]);

  // ── Loading ──
  if (loading) return <SessionSkeleton />;

  // ── Error ──
  if (error || !session) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <p className="text-ink-muted">{error || "Session 不存在"}</p>
        <Button variant="ghost" onClick={() => router.push("/")}>返回首页</Button>
      </div>
    );
  }

  const isFinish = sm.stage === "finish";
  const isEnter = sm.stage === "enter";

  return (
    <div className="studio-root">
      {/* ═══ HEADER ZONE ═══ */}
      <header className="studio-header">
        <div className="sh-root">
          <button onClick={() => router.push("/")} className="sh-back">
            <ArrowLeft size={20} />
          </button>
          <h1 className="sh-title">{session.title || "学习 Session"}</h1>
          {!isFinish && !isEnter && (
            <>
              <StageDots currentState={sm.stage} />
              <span className="sh-progress">42%</span>
            </>
          )}
          <div className="sh-ai-status">
            <span className="sh-ai-dot"></span>
            <span>观察中</span>
          </div>
          <div className="sh-actions">
            <button
              onClick={cancelSession}
              disabled={transitioning}
              className="text-xs text-ink-muted hover:text-red-500 disabled:opacity-50 px-2 py-1"
            >
              取消
            </button>
          </div>
        </div>
        {!isFinish && <ProgressBar currentState={sm.stage} />}
      </header>

      {/* ═══ SIDEBAR ZONE ═══ */}
      <nav className="studio-sidebar">
        <ResourcesSidebar />
      </nav>

      {/* ═══ CANVAS ZONE ═══ */}
      <main className="studio-canvas">
        <div className="sc-canvas">
          {!isEnter && !isFinish && sm.stage === "chat" && sm.mode !== "deep_chat" && (
            <ActivePrompt prompts={prompts} onPromptClick={handlePromptClick} />
          )}
          <div className="flex-1 overflow-y-auto">
            {isFinish ? (
              <Exp04EndScreen sessionTitle={session.mission?.title} />
            ) : isEnter ? (
              <Exp04EnterScreen
                engine={engine}
                currentState={sm.currentState}
                mission={session.mission}
                lastTitle={null}
                onStart={handleEnterStart}
                transitioning={transitioning}
              />
            ) : sm.stage === "chat" ? (
              <ChatScreen
                engine={engine}
                currentState={sm.currentState}
                mission={session.mission}
                lastTitle={null}
                onTransition={handleChatTransition}
                onSetMode={sm.setMode}
                onOpenTool={handleOpenTool}
                sessionId={session.id}
              />
            ) : (
              <Exp04ReflectionScreen
                engine={engine}
                currentState={sm.currentState}
                onSkip={handleReflectionSkip}
                onSubmit={handleReflectionSubmit}
                transitioning={transitioning}
                missionTitle={session.title || session.mission?.title}
              />
            )}
          </div>
        </div>
      </main>

      {/* ═══ COMPANION ZONE ═══ */}
      <aside className="studio-companion">
        <StudioCompanion
          stage={sm.stage}
          mode={sm.mode}
          toolState={toolState}
          messageCount={messageCount}
          sessionTitle={session.mission?.title}
          onOpenCanvas={() => handleOpenTool("canvas")}
          onOpenFlashcard={() => handleOpenTool("flashcard")}
          onOpenPractice={() => handleOpenTool("canvas")} /* 练习 → 画布暂代 */
        />
      </aside>

      {/* ═══ DOCK ZONE ═══ */}
      <footer className="studio-dock">
        <BottomDock activeTool={activeTool} onOpenTool={handleOpenTool} />
      </footer>

      {/* ── Tool Panels（浮层） ── */}
      {flashcardOpen && (
        <FlashcardCreatePanel
          sessionId={sessionId}
          defaultFront={flashcardDefaultFront}
          onCreated={handleFlashcardCreated}
          onClose={() => setFlashcardOpen(false)}
        />
      )}
      <PomodoroPanel sessionTitle={session?.mission?.title} open={pomodoroOpen} onClose={() => setPomodoroOpen(false)} />
      <CanvasPanel sessionTitle={session?.mission?.title} open={canvasOpen} onClose={() => setCanvasOpen(false)} />
      <VoicePanel convId={session?.conversation_id} sessionId={session?.id} open={voiceOpen} onClose={() => setVoiceOpen(false)} />
      <HandwritingPanel open={handwritingOpen} onClose={() => setHandwritingOpen(false)} />
      <FileListPanel sessionTitle={session?.mission?.title} open={filesOpen} onClose={() => setFilesOpen(false)} />
    </div>
  );
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
