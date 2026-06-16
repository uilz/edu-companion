"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Play, Pause, BookOpen, Loader2,
} from "lucide-react";
import {
  getSession, submitAnswer, completeSession,
  startSession, pauseSession, resumeSession, cancelSession,
  type V7Session, type V7SubmitResult,
} from "@/lib/api/practice-api";
import QuestionCard from "@/components/practice/components/QuestionCard";
import ProgressBar from "@/components/practice/components/ProgressBar";
import SessionTimer from "@/components/practice/components/SessionTimer";
import SummaryPanel from "@/components/practice/components/SummaryPanel";

export default function PracticeSessionPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.id as string;

  const [session, setSession] = useState<V7Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [showFeedback, setShowFeedback] = useState(false);
  const [lastResult, setLastResult] = useState<V7SubmitResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [skipped, setSkipped] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const questionStartRef = useRef(Date.now());

  const loadSession = useCallback(async () => {
    try {
      const data = await getSession(sessionId);
      setSession(data);
      // 自动开始"created"状态的会话（跳过确认页）
      if (data.status === "created") {
        await startSession(sessionId);
        const started = await getSession(sessionId);
        setSession(started);
        const firstUn = started.questions?.findIndex((q: any) => !q.answered) ?? 0;
        setCurrentIdx(firstUn >= 0 ? firstUn : 0);
      } else {
        const firstUn = data.questions?.findIndex((q: any) => !q.answered) ?? 0;
        setCurrentIdx(firstUn >= 0 ? firstUn : 0);
      }
    } catch { router.push("/practice"); }
    finally { setLoading(false); }
  }, [sessionId, router]);
  useEffect(() => { loadSession(); }, [loadSession]);

  useEffect(() => {
    if (session?.status === "active") questionStartRef.current = Date.now();
  }, [session?.status]);

  const currentQuestion = session?.questions?.[currentIdx] ?? null;
  const isLastQuestion = currentIdx === (session?.questions?.length ?? 1) - 1;
  const answeredCount = session?.questions?.filter((q: any) => q.answered).length ?? 0;
  const correctCount = session?.questions?.filter((q: any) => q.correct).length ?? 0;
  const wrongCount = answeredCount - correctCount;
  const isExam = session?.session_type === "exam";
  const examDeadline = isExam && session?.config?.deadline ? new Date(session.config.deadline).getTime() : null;

  const resetQuestion = () => {
    setShowFeedback(false); setSelected([]); setLastResult(null); setSkipped(false);
    questionStartRef.current = Date.now();
  };

  const handleSelect = (label: string) => {
    if (showFeedback || submitting) return;
    const t = currentQuestion?.question_type;
    if (t === "single" || t === "judge" || t === "choice") setSelected([label]);
    else if (t === "multiple") setSelected(p => p.includes(label) ? p.filter(l => l !== label) : [...p, label]);
    else setSelected([label]); // fill/free_form/essay: 直接替换
  };

  const handleSubmit = async (answer?: string[]) => {
    const finalAnswer = answer || selected;
    if (!finalAnswer.length || submitting) return;
    setSubmitting(true);
    setSubmitError("");
    const ts = Math.floor((Date.now() - questionStartRef.current) / 1000);
    try {
      const r = await submitAnswer(sessionId, currentQuestion!.id, finalAnswer, ts);
      setLastResult(r); setShowFeedback(true);
      setSession(p => p ? { ...p, questions: p.questions?.map((q: any, i: number) =>
        i === currentIdx ? { ...q, answered: true } : q
      )} : p);
    } catch (e: any) {
      setSubmitError(e?.message || "提交失败");
    }
    setSubmitting(false);
  };

  const handleSkip = async () => {
    if (!currentQuestion || submitting) return;
    setSubmitting(true);
    const ts = Math.floor((Date.now() - questionStartRef.current) / 1000);
    try {
      const r = await submitAnswer(sessionId, currentQuestion.id, [], ts);
      setSkipped(true); setLastResult({ ...r, is_correct: false }); setShowFeedback(true);
    } catch {}
    setSubmitting(false);
  };

  const handleNext = async () => {
    if (isLastQuestion) { await completeSession(sessionId); loadSession(); }
    else { setCurrentIdx(i => i + 1); resetQuestion(); }
  };

  const handleStart = async () => { await startSession(sessionId); loadSession(); };
  const handleCancel = async () => {
    try { await cancelSession(sessionId); } catch {} finally { router.push("/practice"); }
  };
  const handlePause = async () => { await pauseSession(sessionId); loadSession(); };
  const handleResume = async () => { await resumeSession(sessionId); loadSession(); };

  // ── Loading ──
  if (loading) return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <Loader2 size={24} className="animate-spin text-[var(--color-accent)]" />
    </div>
  );
  if (!session) return null;

  // ── 空会话 ──
  if (!session.questions || session.questions.length === 0) {
    return (
      <div className="max-w-lg mx-auto px-4 py-20 text-center space-y-4">
        <BookOpen size={36} className="mx-auto text-[var(--color-text-muted)]" />
        <h2 className="text-base font-semibold text-[var(--color-text)]">此会话暂无题目</h2>
        <p className="text-xs text-[var(--color-text-muted)]">
          该题库没有可用题目，请先在对话中学习或创建题目。
        </p>
        <button onClick={() => router.push("/practice")}
          className="px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white text-xs font-medium">
          返回练习
        </button>
      </div>
    );
  }

  // ── 完成态 ──
  if (session.status === "completed" || session.status === "timeout" || session.status === "cancelled") {
    return (
      <SummaryPanel
        status={session.status}
        total={session.total_count}
        correct={session.correct_count}
        wrong={session.wrong_count}
        score={session.score ?? 0}
        durationSeconds={session.duration_seconds ?? undefined}
        isExam={isExam}
        onBack={() => router.push("/practice")}
        onViewBank={session.bank_id ? () => router.push(`/practice/banks/${session.bank_id}`) : undefined}
      />
    );
  }

  // ── 创建态 ──
  if (session.status === "created") {
    return (
      <div className="max-w-lg mx-auto px-4 py-20 text-center space-y-5">
        <div className="w-16 h-16 rounded-2xl bg-[var(--color-accent)]/10 flex items-center justify-center mx-auto">
          <BookOpen size={28} className="text-[var(--color-accent)]" />
        </div>
        <h1 className="text-lg font-semibold text-[var(--color-text)]">
          {isExam ? "考试准备就绪" : "练习准备就绪"}
        </h1>
        <p className="text-sm text-[var(--color-text-muted)]">
          {session.total_count} 道题
          {isExam && session.config?.duration_minutes
            ? ` · 限时 ${session.config.duration_minutes} 分钟`
            : ` · ${session.mode === "adaptive" ? "自适应" : session.mode}`}
        </p>
        <div className="flex justify-center gap-3">
          <button onClick={handleStart}
            className="px-6 py-2.5 rounded-xl bg-[var(--color-accent)] text-white text-sm font-medium hover:opacity-90 flex items-center gap-2">
            <Play size={16} />{isExam ? "开始考试" : "开始练习"}
          </button>
          <button onClick={handleCancel}
            className="px-6 py-2.5 rounded-xl border border-[var(--color-border)] text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            取消
          </button>
        </div>
      </div>
    );
  }

  // ── 暂停态 ──
  if (session.status === "paused") {
    return (
      <div className="max-w-lg mx-auto px-4 py-20 text-center space-y-5">
        <div className="w-16 h-16 rounded-2xl bg-amber-500/10 flex items-center justify-center mx-auto">
          <Pause size={28} className="text-amber-500" />
        </div>
        <h1 className="text-lg font-semibold text-[var(--color-text)]">练习已暂停</h1>
        <p className="text-sm text-[var(--color-text-muted)]">已完成 {answeredCount}/{session.total_count} 题</p>
        <div className="flex justify-center gap-3">
          <button onClick={handleResume}
            className="px-6 py-2.5 rounded-xl bg-[var(--color-accent)] text-white text-sm font-medium hover:opacity-90 flex items-center gap-2">
            <Play size={16} />继续练习
          </button>
          <button onClick={handleCancel}
            className="px-6 py-2.5 rounded-xl border border-[var(--color-border)] text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            取消
          </button>
        </div>
      </div>
    );
  }

  // ══════════════════ 答题态 ══════════════════
  return (
    <div className="max-w-3xl mx-auto px-4 py-5 space-y-4">
      {/* 顶部栏 */}
      <div className="flex items-center gap-3">
        {!isExam && (
          <button onClick={handlePause} className="p-1.5 rounded-lg hover:bg-[var(--color-surface)] text-[var(--color-text-muted)]">
            <Pause size={15} />
          </button>
        )}
        {isExam && (
          <span className="shrink-0 px-2 py-0.5 rounded text-[10px] font-bold bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400">考试</span>
        )}
        <ProgressBar answered={answeredCount} total={session.total_count} correct={correctCount} wrong={wrongCount} />

        {isExam && examDeadline ? (
          <SessionTimer startTime={questionStartRef.current} isExam running={session.status === "active"} examDeadline={examDeadline} />
        ) : (
          <SessionTimer startTime={questionStartRef.current} running={session.status === "active"} />
        )}
      </div>

      {/* 错误提示 */}
      {submitError && (
        <div className="p-2 rounded-lg bg-red-500/10 border border-red-500/20 text-[11px] text-red-600">
          {submitError}
        </div>
      )}

      {/* 题目卡片 */}
      {currentQuestion && (
        <QuestionCard
          question={currentQuestion}
          index={currentIdx}
          total={session.total_count}
          showFeedback={showFeedback}
          lastResult={lastResult}
          submitting={submitting}
          selected={selected}
          onSelect={handleSelect}
          onSubmit={handleSubmit}
          onSkip={handleSkip}
          onNext={handleNext}
          isLast={isLastQuestion}
          isExam={isExam}
          submitError={submitError}
        />
      )}
    </div>
  );
}
