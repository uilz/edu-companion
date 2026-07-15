"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, Target, BookOpen, Dumbbell, CheckCircle2,
  Send, Loader2, Clock, ChevronRight,
} from "lucide-react";
import { authedFetch } from "@/lib/api/api";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";

// ── API helpers ───────────────────────────────────────────

async function apiFetch(path: string, options?: RequestInit): Promise<Response> {
  return authedFetch(path, options);
}

// ── 类型 ──────────────────────────────────────────────────

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

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
}

const STAGES = [
  { key: "learn", label: "学习", icon: BookOpen, desc: "AI 引导讲解" },
  { key: "practice", label: "练习", icon: Dumbbell, desc: "巩固理解" },
  { key: "reflect", label: "反思", icon: CheckCircle2, desc: "总结成长" },
] as const;

const stageIndex: Record<string, number> = {
  intro: -1, learn: 0, practice: 1, reflect: 2,
};

// ── 组件 ──────────────────────────────────────────────────

export default function SessionPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const sessionId = params.id;

  const [session, setSession] = useState<SessionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [transitioning, setTransitioning] = useState(false);

  const fetchSession = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/session/${sessionId}`);
      if (res.ok) {
        setSession(await res.json());
      } else {
        setError("找不到这个学习 Session");
      }
    } catch {
      setError("加载 Session 失败");
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => { fetchSession(); }, [fetchSession]);

  const transitionStage = async (newStage: string) => {
    setTransitioning(true);
    try {
      const res = await apiFetch(`/api/session/${sessionId}/stage`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_stage: newStage }),
      });
      if (res.ok) {
        await fetchSession();
      }
    } catch (e) {
      console.error("Stage transition failed:", e);
    } finally {
      setTransitioning(false);
    }
  };

  const completeSession = async (reflection?: {
    content: string;
    key_takeaways: string[];
    next_steps: string[];
  }) => {
    setTransitioning(true);
    try {
      const res = await apiFetch(`/api/session/${sessionId}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reflection }),
      });
      if (res.ok) {
        await fetchSession();
      }
    } catch (e) {
      console.error("Complete session failed:", e);
    } finally {
      setTransitioning(false);
    }
  };

  // ── S1.10：取消 Session ──
  const cancelSession = async () => {
    if (!window.confirm("确定取消这次学习吗？你可以随时从 Today 继续。")) return;
    setTransitioning(true);
    try {
      const res = await apiFetch(`/api/session/${sessionId}/cancel`, {
        method: "POST",
      });
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

  const currentIdx = stageIndex[session.stage] ?? 0;
  const isCompleted = session.status === "completed";
  const isArrival = session.stage === "intro";

  return (
    <div className="flex flex-col min-h-screen bg-bg-primary">
      {/* ── Arrival 阶段：无标题栏，无 MissionBar ── */}
      {isArrival ? (
        /* 仅保留返回按钮，不展示标题/计时 */
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
      ) : (
        <>
          {/* ── Header ── */}
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
            <span className="text-xs text-ink-muted">
              {Math.round((Date.now() / 1000 - session.started_at) / 60)}min
            </span>
            <button
              onClick={cancelSession}
              disabled={transitioning}
              className="text-xs text-ink-muted hover:text-red-500 disabled:opacity-50 px-2 py-1"
            >
              取消
            </button>
          </header>

          {/* ── MissionBar（Arrival 阶段不显示）── */}
          <MissionBar session={session} currentIdx={currentIdx} />
        </>
      )}

      {/* ── Stage Content ── */}
      <div className="flex-1 overflow-y-auto">
        {isCompleted ? (
          <SessionCompleteView session={session} />
        ) : (
          <StageContent
            session={session}
            onTransition={transitionStage}
            onComplete={completeSession}
            transitioning={transitioning}
            onRefresh={fetchSession}
          />
        )}
      </div>
    </div>
  );
}

// ── MissionBar ─────────────────────────────────────────────

function MissionBar({ session, currentIdx }: { session: SessionData; currentIdx: number }) {
  return (
    <div className="px-4 py-3 border-b border-border bg-bg-secondary/50">
      {/* Stage dots */}
      <div className="flex items-center gap-1 mb-2">
        {STAGES.map((s, i) => {
          const Icon = s.icon;
          const active = i === currentIdx;
          const done = i < currentIdx;
          return (
            <div key={s.key} className="flex items-center gap-1">
              <div
                className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs transition-colors ${
                  active
                    ? "bg-brand text-white"
                    : done
                    ? "bg-brand/10 text-brand"
                    : "bg-bg-tertiary text-ink-muted"
                }`}
              >
                <Icon size={12} />
                <span className="hidden sm:inline">{s.label}</span>
              </div>
              {i < STAGES.length - 1 && (
                <ChevronRight size={10} className="text-ink-muted" />
              )}
            </div>
          );
        })}
      </div>

      {/* Mission details */}
      {session.mission && (
        <div className="flex items-center gap-2">
          <Target size={14} className="text-brand" />
          <p className="text-sm font-medium text-ink-primary">{session.mission.title}</p>
          {session.mission.estimated_minutes > 0 && (
            <span className="text-xs text-ink-muted flex items-center gap-1">
              <Clock size={10} />
              {session.mission.estimated_minutes}min
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// ── Stage Content ──────────────────────────────────────────

function StageContent({
  session,
  onTransition,
  onComplete,
  transitioning,
  onRefresh,
}: {
  session: SessionData;
  onTransition: (stage: string) => Promise<void>;
  onComplete: (reflection?: {
    content: string;
    key_takeaways: string[];
    next_steps: string[];
  }) => Promise<void>;
  transitioning: boolean;
  onRefresh: () => void;
}) {
  switch (session.stage) {
    case "intro":
      return (
        <IntroStage
          session={session}
          onConfirm={() => onTransition("learn")}
          transitioning={transitioning}
        />
      );
    case "learn":
      return (
        <LearnStage
          session={session}
          onNext={() => onTransition("practice")}
          transitioning={transitioning}
        />
      );
    case "practice":
      return (
        <PracticeStage
          onNext={() => onTransition("reflect")}
          transitioning={transitioning}
        />
      );
    case "reflect":
      return (
        <ReflectStage
          session={session}
          onCompleteWithReflection={(reflection) => onComplete(reflection)}
          transitioning={transitioning}
        />
      );
    default:
      return <p className="p-8 text-ink-muted text-center">未知阶段</p>;
  }
}

// ── Arrival Stage ───────────────────────────────────────────
//
// Arrival 的唯一目标：帮助用户进入学习状态。
// 不收集信息，不建立全部信任，不承担产品介绍。
// 只有一个按钮。

function IntroStage({
  onConfirm,
  transitioning,
}: {
  session: SessionData;
  onConfirm: () => void;
  transitioning: boolean;
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-6 gap-8">
      {/* 🍎 */}
      <div className="text-7xl select-none">🍎</div>

      <Button
        variant="primary"
        size="lg"
        onClick={onConfirm}
        disabled={transitioning}
        className="px-10 py-3 rounded-full text-base shadow-md"
      >
        {transitioning ? (
          <>
            <Loader2 size={18} className="animate-spin" />
            正在准备……
          </>
        ) : (
          "开始今天的学习"
        )}
      </Button>
    </div>
  );
}

// ── Learn Stage ───────────────────────────────────────────
//
// Sprint 1：简化 Learn 阶段，不依赖真实 LLM 调用。
// 目标：让全链路 Today → Arrival → Learn → Practice → Reflect → Complete 跑通。
// 后续 Sprint 接入真实对话能力。

function LearnStage({
  session,
  onNext,
  transitioning,
}: {
  session: SessionData;
  onNext: () => void;
  transitioning: boolean;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "ai-intro",
      role: "assistant",
      content: "我们今天第一次一起学习。",
    },
  ]);
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed) return;

    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, role: "user", content: trimmed },
      {
        id: `ai-${Date.now()}`,
        role: "assistant",
        content: "好，我记下了。我们继续。",
      },
    ]);
    setInput("");
  };

  return (
    <div className="flex flex-col h-[calc(100vh-180px)]">
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-brand text-white"
                  : "bg-bg-secondary text-ink-primary"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Actions */}
      <div className="px-4 py-3 border-t border-border flex items-center gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }}}
          placeholder="输入你的问题..."
          className="flex-1 px-4 py-2 bg-bg-secondary border border-border rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-brand/30"
        />
        <button
          onClick={handleSend}
          disabled={!input.trim()}
          className="p-2.5 rounded-full bg-brand text-white disabled:opacity-50"
        >
          <Send size={16} />
        </button>
        <Button
          variant="outline"
          size="sm"
          onClick={onNext}
          disabled={transitioning}
        >
          {transitioning ? <Loader2 size={14} className="animate-spin" /> : "进入练习"}
        </Button>
      </div>
    </div>
  );
}

// ── Practice Stage ─────────────────────────────────────────
//
// Practice 是用户验证自己理解的环节。
// V1 Sprint 1：一道通用练习题 + 用户提交 + 苹果果反馈。
// 不调用题库，不显示正确率，不评分。

function PracticeStage({
  onNext,
  transitioning,
}: {
  onNext: () => void;
  transitioning: boolean;
}) {
  const [answer, setAnswer] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = () => {
    if (!answer.trim()) return;
    setSubmitted(true);
  };

  return (
    <div className="flex flex-col min-h-[50vh] px-6 py-8 gap-6 max-w-lg mx-auto">
      {/* AppleGo 提示 */}
      <div className="flex gap-3">
        <div className="text-2xl">🍎</div>
        <div className="bg-bg-secondary rounded-2xl rounded-tl-md px-4 py-2.5 text-sm text-ink-primary leading-relaxed">
          我们来检验一下你刚才学的。
        </div>
      </div>

      {/* 题目卡片 */}
      <div className="p-5 rounded-xl bg-surface border border-border/60">
        <p className="text-xs text-ink-muted mb-2">问题</p>
        <p className="text-sm text-ink-primary leading-relaxed">
          用你自己的话，描述一下刚才学习的内容最关键的一个点。
          不需要完整，说一个你真正理解的就行。
        </p>
      </div>

      {!submitted ? (
        <>
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="我理解为……"
            rows={4}
            className="w-full px-4 py-3 bg-bg-secondary border border-border rounded-xl text-sm text-ink-primary placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand/30 resize-none"
          />
          <Button
            variant="primary"
            size="lg"
            onClick={handleSubmit}
            disabled={!answer.trim()}
            className="w-full rounded-full"
          >
            提交
          </Button>
        </>
      ) : (
        <>
          {/* 用户答案 */}
          <div className="bg-brand/10 rounded-2xl rounded-tr-md px-4 py-2.5 text-sm text-ink-primary leading-relaxed self-end max-w-[85%]">
            {answer}
          </div>

          {/* 苹果果反馈 */}
          <div className="flex gap-3">
            <div className="text-2xl">🍎</div>
            <div className="bg-bg-secondary rounded-2xl rounded-tl-md px-4 py-2.5 text-sm text-ink-primary leading-relaxed">
              收到。能用自己的话说出来，说明这个点已经开始变成你自己的理解了。
            </div>
          </div>

          <Button
            variant="primary"
            size="lg"
            onClick={onNext}
            disabled={transitioning}
            className="w-full rounded-full"
          >
            {transitioning ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                正在准备……
              </>
            ) : (
              "进入反思"
            )}
          </Button>
        </>
      )}
    </div>
  );
}

// ── Reflect Stage ──────────────────────────────────────────
//
// Reflect 是用户自己总结今天学到了什么的环节。
// 反思区默认空白，由用户填写。苹果果不评价反思质量。

function ReflectStage({
  onCompleteWithReflection,
  transitioning,
}: {
  session: SessionData;
  onCompleteWithReflection: (reflection: {
    content: string;
    key_takeaways: string[];
    next_steps: string[];
  }) => void;
  transitioning: boolean;
}) {
  const [reflection, setReflection] = useState("");

  const handleComplete = () => {
    if (!reflection.trim()) {
      // 允许空反思，但提示用户写一点
      onCompleteWithReflection({
        content: "",
        key_takeaways: [],
        next_steps: [],
      });
      return;
    }
    onCompleteWithReflection({
      content: reflection.trim(),
      key_takeaways: [],
      next_steps: [],
    });
  };

  return (
    <div className="flex flex-col min-h-[50vh] px-6 py-8 gap-6 max-w-lg mx-auto">
      {/* AppleGo 提示 */}
      <div className="flex gap-3">
        <div className="text-2xl">🍎</div>
        <div className="bg-bg-secondary rounded-2xl rounded-tl-md px-4 py-2.5 text-sm text-ink-primary leading-relaxed">
          今天结束了。
          <br />
          你感觉自己学到了什么？
        </div>
      </div>

      <textarea
        value={reflection}
        onChange={(e) => setReflection(e.target.value)}
        placeholder="我今天理解了……"
        rows={6}
        className="w-full px-4 py-3 bg-bg-secondary border border-border rounded-xl text-sm text-ink-primary placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand/30 resize-none"
      />

      <Button
        variant="primary"
        size="lg"
        onClick={handleComplete}
        disabled={transitioning}
        className="w-full rounded-full"
      >
        {transitioning ? (
          <>
            <Loader2 size={18} className="animate-spin" />
            正在保存……
          </>
        ) : (
          "完成今天"
        )}
      </Button>
    </div>
  );
}

// ── Session Complete View ──────────────────────────────────

function SessionCompleteView({ session }: { session: SessionData }) {
  const router = useRouter();
  const duration = session.finished_at
    ? Math.round((session.finished_at - session.started_at) / 60)
    : 0;

  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] px-6 gap-6 py-12">
      <div className="text-6xl">🍎</div>

      <div className="text-center max-w-md">
        <h2 className="text-2xl font-bold text-ink-primary mb-2">
          今天完成了
        </h2>
        <p className="text-ink-secondary text-sm">
          你总共学习了 {duration} 分钟
        </p>

        {session.reflection?.content && (
          <div className="mt-6 p-4 bg-bg-secondary rounded-xl text-left">
            <p className="text-xs font-medium text-ink-muted mb-2">今天学到的</p>
            <p className="text-sm text-ink-primary leading-relaxed whitespace-pre-line">
              {session.reflection.content}
            </p>
          </div>
        )}

        <div className="mt-8 flex gap-3 justify-center">
          <Button
            variant="primary"
            size="lg"
            onClick={() => router.push("/")}
            className="rounded-full px-8"
          >
            返回首页
          </Button>
        </div>
      </div>
    </div>
  );
}

// ── Skeleton ─────────────────────────────────────────────

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
