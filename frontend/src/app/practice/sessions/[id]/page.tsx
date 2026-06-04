"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, Check, X, ChevronLeft, ChevronRight,
  Clock, Lightbulb, Star, Play, Pause, RotateCcw,
  Loader2, BookOpen,
} from "lucide-react";

// ── 类型 ──
interface Question {
  id: string;
  stem: string;
  options?: { label: string; content: string }[];
  question_type: string;
  difficulty: number;
  cognitive_node_ids: string[];
  answered?: boolean;
  is_correct?: boolean | null;
  time_spent?: number;
}

interface SessionData {
  session_id: string;
  bank_id: string;
  mode: string;
  session_type: string;
  status: string;
  total_count: number;
  correct_count: number;
  wrong_count: number;
  score: number | null;
  duration_seconds?: number | null;
  questions: Question[];
  config: any;
  created_at: string;
  started_at: string;
  finished_at: string | null;
}

// ── 题型标签 ──
const TYPE_MAP: Record<string, string> = { single: "单选", multiple: "多选", judge: "判断", fill: "填空" };

// ── 选项字母 ──
const OPTION_LETTERS = ["A", "B", "C", "D", "E", "F"];

export default function PracticeSessionPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.id as string;

  const [session, setSession] = useState<SessionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [showFeedback, setShowFeedback] = useState(false);
  const [lastResult, setLastResult] = useState<any>(null);
  const [submitting, setSubmitting] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<any>(null);
  const questionStartRef = useRef(Date.now());

  // ── 获取会话 ──
  const loadSession = async () => {
    try {
      const res = await fetch(`/api/v7/practice/sessions/${sessionId}`);
      if (!res.ok) { router.push("/practice"); return; }
      const data = await res.json();
      setSession(data);

      // 找当前未答的题
      const firstUnanswered = data.questions?.findIndex((q: Question) => !q.answered) ?? 0;
      setCurrentIdx(firstUnanswered >= 0 ? firstUnanswered : 0);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadSession(); }, [sessionId]);

  // ── 计时器 ──
  useEffect(() => {
    if (session?.status === "active") {
      timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000);
      questionStartRef.current = Date.now();
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [session?.status]);

  const currentQuestion = session?.questions?.[currentIdx];
  const isLastQuestion = currentIdx === (session?.questions?.length ?? 1) - 1;
  const answeredCount = session?.questions?.filter(q => q.answered).length ?? 0;

  // ── 选择选项 ──
  const handleSelect = (label: string) => {
    if (showFeedback || submitting) return;
    if (currentQuestion?.question_type === "single" || currentQuestion?.question_type === "judge") {
      setSelected([label]);
    } else {
      setSelected(prev =>
        prev.includes(label) ? prev.filter(l => l !== label) : [...prev, label]
      );
    }
  };

  // ── 提交答案 ──
  const handleSubmit = async () => {
    if (!selected.length || !currentQuestion || submitting) return;
    setSubmitting(true);
    const timeSpent = Math.floor((Date.now() - questionStartRef.current) / 1000);

    try {
      const res = await fetch(`/api/v7/practice/sessions/${sessionId}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question_id: currentQuestion.id,
          answer: currentQuestion.question_type === "single" || currentQuestion.question_type === "judge" ? [selected[0]] : selected,
          time_spent: timeSpent,
        }),
      });
      const result = await res.json();
      setLastResult(result);
      setShowFeedback(true);
    } catch (e) {
      console.error(e);
    } finally {
      setSubmitting(false);
    }
  };

  // ── 下一题或完成 ──
  const handleNext = async () => {
    setShowFeedback(false);
    setSelected([]);
    setLastResult(null);
    questionStartRef.current = Date.now();

    if (isLastQuestion) {
      // 完成会话
      await fetch(`/api/v7/practice/sessions/${sessionId}/complete`, { method: "POST" });
      loadSession();
    } else {
      setCurrentIdx(i => i + 1);
    }
  };

  // ── 开始/暂停 ——
  const handleStart = async () => {
    await fetch(`/api/v7/practice/sessions/${sessionId}/start`, { method: "PATCH" });
    loadSession();
  };
  const handlePause = async () => {
    await fetch(`/api/v7/practice/sessions/${sessionId}/pause`, { method: "PATCH" });
    loadSession();
  };
  const handleResume = async () => {
    await fetch(`/api/v7/practice/sessions/${sessionId}/resume`, { method: "PATCH" });
    loadSession();
  };
  const handleCancel = async () => {
    if (!confirm("确认取消本次练习？进度将丢失。")) return;
    await fetch(`/api/v7/practice/sessions/${sessionId}`, { method: "DELETE" });
    router.push("/practice");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  if (!session) return null;

  // ── 完成态：展示结果 ──
  if (session.status === "completed" || session.status === "timeout") {
    const total = session.total_count;
    const correct = session.correct_count;
    const wrong = session.wrong_count;
    const score = session.score ?? 0;
    const passed = score >= 60;

    return (
      <div className="max-w-2xl mx-auto px-4 py-10 text-center space-y-6">
        <div className={`w-20 h-20 rounded-full mx-auto flex items-center justify-center text-3xl ${passed ? "bg-green-100 dark:bg-green-900/30 text-green-500" : "bg-red-100 dark:bg-red-900/30 text-red-500"}`}>
          {passed ? "🎉" : "💪"}
        </div>
        <h1 className="text-2xl font-bold">{passed ? "练习完成！" : "继续加油！"}</h1>
        <div className="text-5xl font-bold text-indigo-500">{score}<span className="text-lg text-gray-400">分</span></div>
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

  // ── 创建态：等待开始 ──
  if (session.status === "created") {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16 text-center space-y-6">
        <BookOpen className="w-16 h-16 mx-auto text-indigo-400" />
        <h1 className="text-xl font-semibold">练习准备就绪</h1>
        <p className="text-gray-500">共 {session.total_count} 道题 · {session.mode === "adaptive" ? "自适应模式" : session.mode}</p>
        <div className="flex justify-center gap-3">
          <button onClick={handleStart} className="px-6 py-3 rounded-xl bg-indigo-500 text-white hover:bg-indigo-600 flex items-center gap-2">
            <Play className="w-5 h-5" />开始练习
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
        <button onClick={handleResume} className="px-6 py-3 rounded-xl bg-indigo-500 text-white hover:bg-indigo-600 flex items-center gap-2 mx-auto">
          <Play className="w-5 h-5" />继续练习
        </button>
      </div>
    );
  }

  // ── 答题态 ──
  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
      {/* ── 顶部进度条 ── */}
      <div className="flex items-center gap-3 mb-2">
        <button onClick={handlePause} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800">
          <Pause className="w-4 h-4" />
        </button>
        <div className="flex-1 h-2 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
          <div className="h-full bg-indigo-500 rounded-full transition-all" style={{ width: `${(answeredCount / session.total_count) * 100}%` }} />
        </div>
        <span className="text-xs text-gray-500 shrink-0">{answeredCount}/{session.total_count}</span>
        <span className="text-xs text-gray-400 shrink-0 flex items-center gap-1"><Clock className="w-3 h-3" />{Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")}</span>
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
              {TYPE_MAP[currentQuestion.question_type] || currentQuestion.question_type}
            </span>
            <div className="flex-1" />
            {currentQuestion.difficulty >= 4 ? "🔥" : currentQuestion.difficulty >= 3 ? "⭐" : "✅"}
          </div>

          {/* 题干 */}
          <div className="px-5 py-4">
            <p className="text-base leading-relaxed">{currentQuestion.stem}</p>
          </div>

          {/* 选项 */}
          {(currentQuestion.question_type === "single" || currentQuestion.question_type === "multiple" || currentQuestion.question_type === "judge") && (
            <div className="px-5 pb-4 space-y-2">
              {(currentQuestion.options || []).map((opt) => {
                const isSelected = selected.includes(opt.label);
                const isCorrectAnswer = showFeedback && lastResult?.correct_answer?.includes(opt.label);
                const isWrongPick = showFeedback && isSelected && !lastResult?.correct_answer?.includes(opt.label);

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
                  <button key={opt.label} onClick={() => handleSelect(opt.label)} className={btnClass} disabled={showFeedback}>
                    <span className="font-medium mr-2">{opt.label}.</span>
                    {opt.content}
                    {showFeedback && isCorrectAnswer && <Check className="w-4 h-4 inline ml-2 text-green-500" />}
                    {showFeedback && isWrongPick && <X className="w-4 h-4 inline ml-2 text-red-500" />}
                  </button>
                );
              })}
            </div>
          )}

          {/* 填空 */}
          {currentQuestion.question_type === "fill" && !showFeedback && (
            <div className="px-5 pb-4">
              <input
                value={selected[0] || ""}
                onChange={(e) => setSelected([e.target.value])}
                placeholder="输入你的答案..."
                className="w-full px-4 py-3 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              />
            </div>
          )}

          {/* 提交按钮 */}
          <div className="px-5 pb-4 flex items-center gap-3">
            <button
              onClick={showFeedback ? handleNext : handleSubmit}
              disabled={!selected.length || submitting}
              className="px-6 py-2.5 rounded-xl bg-indigo-500 text-white hover:bg-indigo-600 disabled:opacity-30 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : showFeedback ? (isLastQuestion ? "完成 ✓" : "下一题 →") : "提交"}
            </button>
            <span className="text-xs text-gray-400">{currentQuestion.question_type === "multiple" ? "（可多选）" : ""}</span>
          </div>
        </div>
      )}

      {/* ── 反馈区 ── */}
      {showFeedback && lastResult && (
        <div className={`rounded-2xl border p-5 ${lastResult.is_correct ? "border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/10" : "border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/10"}`}>
          <div className="flex items-center gap-2 mb-3">
            {lastResult.is_correct ? (
              <><Check className="w-5 h-5 text-green-500" /><span className="font-medium text-green-700 dark:text-green-300">回答正确！</span></>
            ) : (
              <><X className="w-5 h-5 text-red-500" /><span className="font-medium text-red-700 dark:text-red-300">回答错误</span></>
            )}
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">{lastResult.analysis || "暂无解析"}</p>
          {lastResult.mastered && <p className="text-xs text-green-500 mt-2">✅ 已连续答对 3 次，该知识点已掌握</p>}
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
            {session.questions.map((q, i) => (
              <button
                key={q.id}
                onClick={() => { if (!showFeedback) setCurrentIdx(i); }}
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
