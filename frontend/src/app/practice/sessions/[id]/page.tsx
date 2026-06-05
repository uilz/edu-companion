"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Check, X,
  Clock, Lightbulb, Play, Pause, Timer,
  Loader2, BookOpen, SkipForward, Volume2,
  Heart, EyeOff, Eye, Shuffle, AlertOctagon,
} from "lucide-react";
import {
  getSession, submitAnswer, completeSession,
  getQuestionExplanation, generateSimilarQuestions,
  toggleFavorite, toggleSlash,
  startSession, pauseSession, resumeSession, cancelSession,
  type V7Session, type V7SubmitResult,
} from "@/lib/api/practice-api";
import QuestionStem from "@/components/practice/components/QuestionStem";
import ReferencePanel from "@/components/practice/panels/ReferencePanel";

// ── 题型标签 ──
const TYPE_MAP: Record<string, string> = {
  single: "单选", multiple: "多选", judge: "判断",
  fill: "填空", free_form: "简答", essay: "简答",
};

// ── 格式化时间 ──
function fmtTime(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function PracticeSessionPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.id as string;

  const [session, setSession] = useState<V7Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [freeText, setFreeText] = useState("");
  const [showFeedback, setShowFeedback] = useState(false);
  const [lastResult, setLastResult] = useState<V7SubmitResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const questionStartRef = useRef(Date.now());

  // —— 答题辅助 ——
  const [showHint, setShowHint] = useState(false);
  const [hintText, setHintText] = useState("");
  const [hintLoading, setHintLoading] = useState(false);
  const [isFav, setIsFav] = useState(false);
  const [isSlashed, setIsSlashed] = useState(false);
  const [similarQuestions, setSimilarQuestions] = useState<any[]>([]);
  const [similarLoading, setSimilarLoading] = useState(false);
  const [skipped, setSkipped] = useState(false);

  // ── 获取会话 ──
  const loadSession = useCallback(async () => {
    try {
      const data = await getSession(sessionId);
      setSession(data);
      const firstUnanswered = data.questions?.findIndex((q: any) => !q.answered) ?? 0;
      setCurrentIdx(firstUnanswered >= 0 ? firstUnanswered : 0);
    } catch {
      router.push("/practice");
    } finally {
      setLoading(false);
    }
  }, [sessionId, router]);

  useEffect(() => { loadSession(); }, [loadSession]);

  // ── 计时器 ──
  useEffect(() => {
    if (session?.status === "active") {
      timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
      questionStartRef.current = Date.now();
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [session?.status]);

  const currentQuestion = session?.questions?.[currentIdx] ?? null;
  const isLastQuestion = currentIdx === (session?.questions?.length ?? 1) - 1;
  const answeredCount = session?.questions?.filter((q: any) => q.answered).length ?? 0;
  const isExam = session?.session_type === "exam";
  // 考试模式下取 deadline 倒计时
  const examDeadline = isExam && session?.config?.deadline ? new Date(session.config.deadline).getTime() : null;
  const [examRemaining, setExamRemaining] = useState(0);

  useEffect(() => {
    if (!examDeadline || session?.status !== "active") return;
    const update = () => {
      const remain = Math.max(0, Math.floor((examDeadline - Date.now()) / 1000));
      setExamRemaining(remain);
    };
    update();
    const t = setInterval(update, 1000);
    return () => clearInterval(t);
  }, [examDeadline, session?.status]);

  // ── 重置题目状态 ──
  const resetQuestionState = useCallback(() => {
    setShowFeedback(false);
    setSelected([]);
    setFreeText("");
    setLastResult(null);
    setShowHint(false);
    setHintText("");
    setIsFav(false);
    setIsSlashed(false);
    setSimilarQuestions([]);
    setSkipped(false);
    questionStartRef.current = Date.now();
  }, []);

  // ── 选择选项 ──
  const handleSelect = (label: string) => {
    if (showFeedback || submitting) return;
    const t = currentQuestion?.question_type;
    if (t === "single" || t === "judge") {
      setSelected([label]);
    } else {
      setSelected((prev) =>
        prev.includes(label) ? prev.filter((l) => l !== label) : [...prev, label]
      );
    }
  };

  // ── 提交答案 ──
  const handleSubmit = async () => {
    const t: string = currentQuestion?.question_type ?? "";
    const answer = t === "fill" || t === "free_form" || t === "essay"
      ? (freeText.trim() ? [freeText.trim()] : [])
      : selected;

    if (!answer.length || submitting) return;
    setSubmitting(true);
    const timeSpent = Math.floor((Date.now() - questionStartRef.current) / 1000);
    try {
      const result = await submitAnswer(sessionId, currentQuestion!.id, answer, timeSpent);
      setLastResult(result);
      setShowFeedback(true);
      // 更新本地会话状态，进度条即时反映
      setSession((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          questions: prev.questions?.map((q: any, i: number) =>
            i === currentIdx ? { ...q, answered: true } : q
          ),
        };
      });
    } catch {}
    setSubmitting(false);
  };

  // ── 跳过 / 我不会 ──
  const handleSkip = async () => {
    if (!currentQuestion || submitting) return;
    setSubmitting(true);
    try {
      const result = await submitAnswer(sessionId, currentQuestion.id, [],
        Math.floor((Date.now() - questionStartRef.current) / 1000));
      setSkipped(true);
      setLastResult({ ...result, is_correct: false });
      setShowFeedback(true);
    } catch {}
    setSubmitting(false);
  };

  // ── 下一题 ──
  const handleNext = async () => {
    if (isLastQuestion) {
      await completeSession(sessionId);
      loadSession();
    } else {
      setCurrentIdx((i) => i + 1);
      resetQuestionState();
    }
  };

  // ── 显示提示 ──
  const handleShowHint = async () => {
    if (!currentQuestion || showHint) return;
    setHintLoading(true);
    try {
      const resp = await getQuestionExplanation(currentQuestion.id, "concise");
      setHintText(resp.explanation || "");
      setShowHint(true);
    } catch {
      setHintText("无法加载提示");
      setShowHint(true);
    }
    setHintLoading(false);
  };

  // ── TTS 朗读 ──
  const handleReadAloud = () => {
    if (!currentQuestion) return;
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const text = currentQuestion.stem.replace(/[*_#`~>\[\]()]/g, "");
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "zh-CN";
      utterance.rate = 0.9;
      window.speechSynthesis.speak(utterance);
    }
  };

  // ── 收藏 ──
  const handleToggleFavorite = async () => {
    if (!currentQuestion) return;
    try {
      const result = await toggleFavorite(currentQuestion.id);
      setIsFav(result.is_favorite);
    } catch {}
  };

  // ── 斩题 ──
  const handleToggleSlash = async () => {
    if (!currentQuestion) return;
    try {
      const result = await toggleSlash(currentQuestion.id);
      setIsSlashed(result.is_slashed);
    } catch {}
  };

  // ── 生成同类变体 ──
  const handleGenerateSimilar = async () => {
    if (!currentQuestion) return;
    setSimilarLoading(true);
    try {
      const resp = await generateSimilarQuestions(currentQuestion.id, 3);
      setSimilarQuestions(resp.questions || []);
    } catch {}
    setSimilarLoading(false);
  };

  // ── 会话控制 ──
  const handleStart = async () => {
    await startSession(sessionId);
    loadSession();
  };
  const handleCancel = async () => {
    if (!confirm("确认取消？进度将丢失。")) return;
    try {
      await cancelSession(sessionId);
      router.push("/practice");
    } catch {
      // 会话已结束则直接返回
      router.push("/practice");
    }
  };

  const handlePause = async () => {
    try {
      await pauseSession(sessionId);
      loadSession();
    } catch {}
  };

  const handleResume = async () => {
    try {
      await resumeSession(sessionId);
      loadSession();
    } catch {}
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  if (!session) return null;

  // ── 完成 / 超时态 ──
  if (session.status === "completed" || session.status === "timeout" || session.status === "cancelled") {
    const total = session.total_count;
    const correct = session.correct_count;
    const wrong = session.wrong_count;
    const score = session.score ?? 0;
    const passed = score >= 60;
    const isTimeout = session.status === "timeout";

    return (
      <div className="max-w-2xl mx-auto px-4 py-10 text-center space-y-6">
        <div className={`w-20 h-20 rounded-full mx-auto flex items-center justify-center text-3xl ${
          session.status === "cancelled" ? "bg-gray-100 dark:bg-gray-800 text-gray-400" :
          passed ? "bg-green-100 dark:bg-green-900/30 text-green-500" :
          "bg-red-100 dark:bg-red-900/30 text-red-500"
        }`}>
          {session.status === "cancelled" ? "✖" : passed ? "🎉" : "💪"}
        </div>
        {isTimeout && (
          <div className="flex items-center justify-center gap-2 text-amber-600 dark:text-amber-400">
            <AlertOctagon size={16} /><span className="text-sm font-medium">考试时间到，已自动交卷</span>
          </div>
        )}
        <h1 className="text-2xl font-bold">
          {isExam
            ? (passed ? "考试通过！" : "考试未通过")
            : (passed ? "练习完成！" : "继续加油！")}
        </h1>
        <div className="text-5xl font-bold text-indigo-500">
          {score}<span className="text-lg text-gray-400">分</span>
        </div>
        <div className="flex justify-center gap-6">
          <div className="text-center"><div className="text-2xl font-semibold text-green-500">{correct}</div><div className="text-xs text-gray-400">正确</div></div>
          <div className="text-center"><div className="text-2xl font-semibold text-red-500">{wrong}</div><div className="text-xs text-gray-400">错误</div></div>
          <div className="text-center"><div className="text-2xl font-semibold text-gray-500">{total}</div><div className="text-xs text-gray-400">总题数</div></div>
        </div>
        {session.duration_seconds && (
          <p className="text-sm text-gray-400">用时 {Math.floor(session.duration_seconds / 60)}分{session.duration_seconds % 60}秒</p>
        )}
        <div className="flex justify-center gap-3 pt-4">
          <button onClick={() => router.push("/practice")} className="px-5 py-2.5 rounded-xl bg-indigo-500 text-white hover:bg-indigo-600">返回练习</button>
          <button onClick={() => router.push(`/practice/banks/${session.bank_id}`)} className="px-5 py-2.5 rounded-xl border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800">查看题库</button>
        </div>
      </div>
    );
  }

  // ── 创建态 ──
  if (session.status === "created") {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16 text-center space-y-6">
        <BookOpen className="w-16 h-16 mx-auto text-indigo-400" />
        <h1 className="text-xl font-semibold">
          {isExam ? "考试准备就绪" : "练习准备就绪"}
        </h1>
        <p className="text-gray-500">
          共 {session.total_count} 道题
          {isExam && session.config?.duration_minutes
            ? ` · 限时 ${session.config.duration_minutes} 分钟`
            : ` · ${session.mode === "adaptive" ? "自适应模式" : session.mode}`}
        </p>
        {isExam && (
          <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800 text-sm text-amber-700 dark:text-amber-300 max-w-sm mx-auto">
            考试开始后将计时，时间到自动交卷。不可暂停，不可使用提示。
          </div>
        )}
        <div className="flex justify-center gap-3">
          <button onClick={handleStart} className="px-6 py-3 rounded-xl bg-indigo-500 text-white hover:bg-indigo-600 flex items-center gap-2">
            <Play className="w-5 h-5" />{isExam ? "开始考试" : "开始练习"}
          </button>
          <button onClick={handleCancel} className="px-6 py-3 rounded-xl border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800">取消</button>
        </div>
      </div>
    );
  }

  // ── 暂停态 ──
  if (session.status === "paused") {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16 text-center space-y-6">
        <Pause className="w-16 h-16 mx-auto text-amber-400" />
        <h1 className="text-xl font-semibold">练习已暂停</h1>
        <p className="text-gray-500">已完成 {answeredCount}/{session.total_count} 题</p>
        <div className="flex justify-center gap-3">
          <button onClick={handleResume} className="px-6 py-3 rounded-xl bg-indigo-500 text-white hover:bg-indigo-600 flex items-center gap-2 mx-auto">
            <Play className="w-5 h-5" />继续练习
          </button>
          <button onClick={handleCancel} className="px-6 py-3 rounded-xl border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800">取消</button>
        </div>
      </div>
    );
  }

  // ══════════════════════ 答题态 ══════════════════════
  const qtype: string = currentQuestion?.question_type ?? "";
  const isOptionType = qtype === "single" || qtype === "multiple" || qtype === "judge";
  const isTextType = qtype === "fill" || qtype === "free_form" || qtype === "essay";

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
      {/* ── 顶部信息栏 ── */}
      <div className="flex items-center gap-3 mb-2">
        {/* 暂停按钮 — 考试模式不可暂停 */}
        {!isExam && (
          <button onClick={handlePause} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800">
            <Pause className="w-4 h-4" />
          </button>
        )}
        {isExam && (
          <span className="shrink-0 px-2 py-0.5 rounded text-[10px] font-bold bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400">考试</span>
        )}

        <div className="flex-1 h-2 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
          <div className="h-full bg-indigo-500 rounded-full transition-all"
            style={{ width: `${(answeredCount / session.total_count) * 100}%` }} />
        </div>
        <span className="text-xs text-gray-500 shrink-0">{answeredCount}/{session.total_count}</span>

        {/* 计时器 */}
        {isExam && examRemaining > 0 ? (
          <span className={`text-xs shrink-0 flex items-center gap-1 font-mono ${
            examRemaining < 60 ? "text-red-500 animate-pulse" : "text-gray-400"
          }`}>
            <Timer className="w-3 h-3" />{fmtTime(examRemaining)}
          </span>
        ) : (
          <span className="text-xs text-gray-400 shrink-0 flex items-center gap-1">
            <Clock className="w-3 h-3" />{fmtTime(elapsed)}
          </span>
        )}
      </div>

      {/* ── 题目卡片 ── */}
      {currentQuestion && (
        <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/60 overflow-hidden">
          {/* 头部 */}
          <div className="px-5 py-3 border-b border-gray-100 dark:border-gray-700/50 flex items-center gap-2">
            <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-300">
              第 {currentIdx + 1} 题
            </span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-500">
              {TYPE_MAP[qtype] || qtype}
            </span>
            {currentQuestion.difficulty > 0 && (
              <span className="text-[9px] text-gray-400">
                难度: {"★".repeat(currentQuestion.difficulty).padEnd(5, "☆")}
              </span>
            )}
            <div className="flex-1" />

            {/* 工具栏 — 考试模式不显示收藏/斩题 */}
            {!isExam && (
              <div className="flex items-center gap-0.5">
                <button onClick={handleReadAloud} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700" title="朗读">
                  <Volume2 size={13} className="text-gray-400" />
                </button>
                <button onClick={handleToggleFavorite} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700" title={isFav ? "取消收藏" : "收藏"}>
                  {isFav ? <Heart size={13} className="text-red-500 fill-red-500" /> : <Heart size={13} className="text-gray-400" />}
                </button>
                <button onClick={handleToggleSlash} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700" title={isSlashed ? "已斩题" : "斩题"}>
                  {isSlashed ? <EyeOff size={13} className="text-gray-400" /> : <Eye size={13} className="text-gray-400" />}
                </button>
              </div>
            )}
          </div>

          {/* 题干 */}
          <div className="px-5 py-4">
            <QuestionStem stem={currentQuestion.stem} className="text-base leading-relaxed" />
          </div>

          {/* 提示 — 考试模式不显示 */}
          {!showFeedback && showHint && hintText && !isExam && (
            <div className="px-5 pb-3">
              <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800">
                <div className="flex items-center gap-1.5 mb-1.5">
                  <Lightbulb size={12} className="text-blue-500" />
                  <span className="text-[11px] font-medium text-blue-600">提示</span>
                </div>
                <p className="text-[12px] text-gray-600 dark:text-gray-400 leading-relaxed">{hintText}</p>
              </div>
            </div>
          )}

          {/* 选项（单选/多选/判断） */}
          {isOptionType && (
            <div className="px-5 pb-4 space-y-2">
              {(currentQuestion.options || []).map((opt: any) => {
                const label = opt.letter || opt.label || "";
                const text = opt.text || opt.content || "";
                const isSelected = selected.includes(label);
                const isCorrectAnswer = showFeedback && lastResult?.correct_answer?.includes(label);
                const isWrongPick = showFeedback && isSelected && !lastResult?.correct_answer?.includes(label);

                let btnClass = "w-full text-left px-4 py-3 rounded-xl border transition-all ";
                if (showFeedback) {
                  if (isCorrectAnswer) btnClass += "border-green-400 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 ";
                  else if (isWrongPick) btnClass += "border-red-400 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 ";
                  else btnClass += "border-gray-200 dark:border-gray-600 opacity-50 ";
                } else {
                  btnClass += isSelected
                    ? "border-indigo-400 bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-300 "
                    : "border-gray-200 dark:border-gray-600 hover:border-indigo-300 dark:hover:border-indigo-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 ";
                }

                return (
                  <button key={label} onClick={() => handleSelect(label)} className={btnClass} disabled={showFeedback}>
                    <span className="font-medium mr-2">{label}.</span>
                    {text}
                    {showFeedback && isCorrectAnswer && <Check className="w-4 h-4 inline ml-2 text-green-500" />}
                    {showFeedback && isWrongPick && <X className="w-4 h-4 inline ml-2 text-red-500" />}
                  </button>
                );
              })}
            </div>
          )}

          {/* 填空 / 简答 答题框 */}
          {isTextType && !showFeedback && (
            <div className="px-5 pb-4">
              {qtype === "free_form" ? (
                <textarea
                  value={freeText}
                  onChange={(e) => setFreeText(e.target.value)}
                  placeholder="输入你的答案..."
                  rows={4}
                  className="w-full px-4 py-3 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 resize-none text-sm leading-relaxed focus:outline-none focus:border-indigo-400 dark:focus:border-indigo-600"
                />
              ) : (
                <input
                  value={freeText}
                  onChange={(e) => setFreeText(e.target.value)}
                  placeholder="输入你的答案..."
                  className="w-full px-4 py-3 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 focus:outline-none focus:border-indigo-400 dark:focus:border-indigo-600"
                  onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
                />
              )}
              {qtype === "free_form" && (
                <p className="mt-1 text-[11px] text-gray-400">简答题请自行表述，提交后将由系统判定</p>
              )}
            </div>
          )}

          {/* 操作按钮 */}
          <div className="px-5 pb-4 flex items-center gap-3 flex-wrap">
            {showFeedback ? (
              <button onClick={handleNext} className="px-6 py-2.5 rounded-xl bg-indigo-500 text-white hover:bg-indigo-600 flex items-center gap-2">
                {isLastQuestion ? "完成 ✓" : "下一题 →"}
              </button>
            ) : (
              <>
                <button
                  onClick={handleSubmit}
                  disabled={submitting || (isOptionType ? !selected.length : !freeText.trim())}
                  className="px-6 py-2.5 rounded-xl bg-indigo-500 text-white hover:bg-indigo-600 disabled:opacity-30 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : "提交"}
                </button>
                {/* 提示 / 跳过 — 考试模式不显示 */}
                {!isExam && (
                  <>
                    <button
                      onClick={handleShowHint}
                      disabled={hintLoading || showHint}
                      className="px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-xs text-gray-500 hover:border-blue-400 hover:text-blue-500 disabled:opacity-50 flex items-center gap-1"
                    >
                      {hintLoading ? <Loader2 size={12} className="animate-spin" /> : <Lightbulb size={12} />}
                      {showHint ? "已提示" : "提示"}
                    </button>
                    <button
                      onClick={handleSkip}
                      className="px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-xs text-gray-500 hover:border-amber-400 hover:text-amber-500 flex items-center gap-1"
                    >
                      <SkipForward size={12} />我不会
                    </button>
                  </>
                )}
              </>
            )}
            {qtype === "multiple" && !showFeedback && (
              <span className="text-xs text-gray-400">（可多选）</span>
            )}
          </div>
        </div>
      )}

      {/* ── 反馈区 ── */}
      {showFeedback && lastResult && (
        <div className={`rounded-2xl border p-5 ${
          skipped ? "border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/10" :
          lastResult.is_correct ? "border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/10" :
          "border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/10"
        }`}>
          <div className="flex items-center gap-2 mb-3">
            {skipped ? (
              <><SkipForward className="w-5 h-5 text-amber-500" /><span className="font-medium text-amber-700 dark:text-amber-300">已跳过</span></>
            ) : lastResult.is_correct ? (
              <><Check className="w-5 h-5 text-green-500" /><span className="font-medium text-green-700 dark:text-green-300">回答正确！</span></>
            ) : (
              <><X className="w-5 h-5 text-red-500" /><span className="font-medium text-red-700 dark:text-red-300">回答错误</span></>
            )}
          </div>
          {lastResult.analysis && (
            <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">{lastResult.analysis}</p>
          )}
          {lastResult.mastered && <p className="text-xs text-green-500 mt-2">已连续答对 3 次，该知识点已掌握</p>}

          {/* 同类变体 — 考试模式不显示 */}
          {!lastResult.is_correct && !isExam && (
            <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
              {similarQuestions.length > 0 ? (
                <div>
                  <p className="text-[11px] font-medium text-gray-500 mb-2">同类变体 ({similarQuestions.length} 题)</p>
                  <div className="space-y-1">
                    {similarQuestions.map((q: any) => (
                      <p key={q.id} className="text-[11px] text-gray-600 dark:text-gray-400">{q.stem?.slice(0, 80)}{q.stem?.length > 80 ? "..." : ""}</p>
                    ))}
                  </div>
                </div>
              ) : (
                <button
                  onClick={handleGenerateSimilar}
                  disabled={similarLoading}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-xs text-gray-500 hover:border-indigo-400 hover:text-indigo-500"
                >
                  {similarLoading ? <Loader2 size={12} className="animate-spin" /> : <Shuffle size={12} />}
                  生成同类变体
                </button>
              )}
            </div>
          )}

          {/* 视频讲解 — 考试模式下也不显示 */}
          {currentQuestion && !isExam && (
            <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
              <ReferencePanel query={currentQuestion.stem.slice(0, 40)} compact />
            </div>
          )}
        </div>
      )}

      {/* ── 答题卡 ── */}
      {session.questions?.length > 0 && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 p-3">
          <div className="flex items-center gap-2 mb-2 text-xs text-gray-400">
            <span>答题卡</span>
            <span className="ml-auto">{answeredCount}/{session.total_count}</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {session.questions.map((q: any, i: number) => (
              <button
                key={q.id}
                onClick={() => { if (!showFeedback) { setCurrentIdx(i); resetQuestionState(); } }}
                className={`w-8 h-8 rounded-lg text-xs font-medium transition-colors ${
                  i === currentIdx ? "ring-2 ring-indigo-400 ring-offset-1 dark:ring-offset-gray-900" : ""
                } ${
                  q.answered ? (q.is_correct ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300" : "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300") : "bg-gray-100 dark:bg-gray-700 text-gray-500"
                }`}
              >
                {i + 1}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}