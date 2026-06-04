"use client";

import React, { useState, useCallback, useEffect, useRef } from "react";
import {
  Play, Check, X, ChevronRight, ChevronLeft,
  RotateCcw, Clock, Brain, Trophy, BarChart3,
  Lightbulb, BookOpen, Loader2, Sparkles,
  Volume2,
} from "lucide-react";
import {
  createPracticeSession,
  submitAnswer,
  completeSession,
  resolveBankForNode,
  generateQuestions,
  type V7Session,
  type V7Question,
  type V7SubmitResult,
} from "@/lib/practice-api";

// ── 状态机 ──
type Phase = "idle" | "loading" | "answering" | "submitting" | "result" | "summary" | "error";

interface Props {
  nodeId?: string;
  nodeLabel?: string;
  onClose?: () => void;
}

export default function PracticePanel({ nodeId, nodeLabel, onClose }: Props) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [session, setSession] = useState<V7Session | null>(null);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState<string[]>([]);
  const [lastResult, setLastResult] = useState<V7SubmitResult | null>(null);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<"adaptive" | "review" | "challenge">("adaptive");
  const [count, setCount] = useState(5);
  const [questionStart, setQuestionStart] = useState(0);

  // 统计（在 summary 中展示）
  const [results, setResults] = useState<V7SubmitResult[]>([]);

  const currentQuestion = session?.questions?.[currentIdx] ?? null;

  // ── 开始练习 ──
  const handleStart = useCallback(async () => {
    setPhase("loading");
    setError("");
    setResults([]);
    setCurrentIdx(0);

    try {
      let bankId: string;

      if (nodeId) {
        const resolved = await resolveBankForNode(nodeId);
        bankId = resolved.bank_id;
      } else {
        // 无 node — 用默认题库
        const banks = await (await fetch("/api/v7/practice/banks")).json();
        bankId = banks?.[0]?.id || "bnk_default";
      }

      const sess = await createPracticeSession(bankId, {
        mode,
        count,
        cognitive_node_ids: nodeId ? [nodeId] : undefined,
      });

      setSession(sess);
      if (sess.questions?.length > 0) {
        setPhase("answering");
        setSelectedAnswers([]);
        setLastResult(null);
        setQuestionStart(Date.now());
      } else {
        // 题库无题，尝试 AI 出题
        try {
          const genResult = await generateQuestions(
            `关于${nodeLabel || "当前知识点"}的练习题`,
            { bank_id: bankId, node_id: nodeId }
          );
          if (genResult.generated > 0) {
            const sess2 = await createPracticeSession(bankId, {
              mode, count: Math.min(count, genResult.generated),
              cognitive_node_ids: nodeId ? [nodeId] : undefined,
            });
            setSession(sess2);
            setPhase("answering");
            setSelectedAnswers([]);
            setLastResult(null);
            setQuestionStart(Date.now());
          } else {
            setPhase("error");
            setError("题库暂无题，AI 出题也未成功。请在对话中先学习相关内容。");
          }
        } catch {
          setPhase("error");
          setError("当前题库无题目，请先学习后重试。");
        }
      }
    } catch (e: any) {
      setPhase("error");
      setError(e?.message || "创建练习失败，请检查后端服务");
    }
  }, [nodeId, nodeLabel, mode, count]);

  // ── 选择答案 ──
  const toggleAnswer = useCallback((letter: string) => {
    if (!currentQuestion) return;
    if (currentQuestion.question_type === "single") {
      setSelectedAnswers([letter]);
    } else {
      setSelectedAnswers((prev) =>
        prev.includes(letter) ? prev.filter((a) => a !== letter) : [...prev, letter]
      );
    }
  }, [currentQuestion]);

  // ── 提交答案 ──
  const handleSubmit = useCallback(async () => {
    if (!session || !currentQuestion || selectedAnswers.length === 0) return;

    setPhase("submitting");
    const timeSpent = Math.floor((Date.now() - questionStart) / 1000);

    try {
      const result = await submitAnswer(
        session.session_id,
        currentQuestion.id,
        selectedAnswers,
        timeSpent
      );
      setLastResult(result);
      setResults((prev) => [...prev, result]);
      setPhase("result");
    } catch (e: any) {
      setPhase("answering");
      setError(e?.message || "提交失败");
    }
  }, [session, currentQuestion, selectedAnswers, questionStart]);

  // ── 下一题 ──
  const handleNext = useCallback(async () => {
    if (!session) return;

    const nextIdx = currentIdx + 1;
    if (nextIdx >= session.total_count) {
      // 全部完成
      setPhase("loading");
      try {
        const completed = await completeSession(session.session_id);
        setSession(completed);
        setPhase("summary");
      } catch {
        setPhase("summary"); // 即使 complete 失败也展示结果
      }
    } else {
      setCurrentIdx(nextIdx);
      setSelectedAnswers([]);
      setLastResult(null);
      setPhase("answering");
      setQuestionStart(Date.now());
      setError("");
    }
  }, [session, currentIdx]);

  // ── 重新练习 ──
  const handleRetry = useCallback(() => {
    setPhase("idle");
    setSession(null);
    setCurrentIdx(0);
    setResults([]);
    setLastResult(null);
    setError("");
  }, []);

  // ── 键盘快捷键 ──
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (phase === "answering" && currentQuestion?.options) {
        // 数字键 1-4 选 ABCD
        const idx = parseInt(e.key) - 1;
        if (idx >= 0 && idx < currentQuestion.options.length) {
          toggleAnswer(currentQuestion.options[idx].letter);
          return;
        }
        // 字母键直接选
        const letter = e.key.toUpperCase();
        if (/^[A-D]$/.test(letter) && currentQuestion.options.some((o) => o.letter === letter)) {
          toggleAnswer(letter);
          return;
        }
      }
      if (e.key === "Enter") {
        if (phase === "answering" && selectedAnswers.length > 0) {
          handleSubmit();
        } else if (phase === "result") {
          handleNext();
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [phase, currentQuestion, selectedAnswers, handleSubmit, handleNext, toggleAnswer]);

  // ── 题号渲染 ──
  if (phase === "idle") {
    return <IdleScreen mode={mode} setMode={setMode} count={count} setCount={setCount} onStart={handleStart} nodeLabel={nodeLabel} />;
  }

  if (phase === "loading") {
    return <LoadingScreen />;
  }

  if (phase === "error") {
    return <ErrorScreen message={error} onRetry={() => setPhase("idle")} />;
  }

  if (phase === "summary") {
    return <SummaryScreen session={session} results={results} onRetry={handleRetry} onClose={onClose} />;
  }

  return (
    <div className="flex flex-col h-full">
      {/* 进度条 */}
      <div className="px-4 pt-3 pb-2">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[11px] text-[var(--color-text-muted)]">
            第 {currentIdx + 1} / {session?.total_count ?? "?"} 题
          </span>
          <span className="text-[11px] text-[var(--color-text-muted)] flex items-center gap-1">
            <Brain size={10} />
            {results.filter((r) => r.is_correct).length} 正确
            <span className="text-[var(--color-text-muted)]">·</span>
            {results.filter((r) => !r.is_correct).length} 错误
          </span>
        </div>
        <div className="w-full h-1 bg-[var(--color-border)]/50 rounded-full overflow-hidden">
          <div
            className="h-full bg-[var(--color-accent)] rounded-full transition-all duration-300"
            style={{ width: `${((currentIdx + 1) / (session?.total_count ?? 1)) * 100}%` }}
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 pb-4">
        {/* 题干 */}
        {currentQuestion && (
          <div className="mb-4">
            <h3 className="text-sm font-medium text-[var(--color-text)] leading-relaxed">
              {currentQuestion.stem}
            </h3>
            {currentQuestion.difficulty > 0 && (
              <div className="flex items-center gap-1 mt-1">
                <span className="text-[9px] text-[var(--color-text-muted)]">
                  难度: {"★".repeat(currentQuestion.difficulty).padEnd(5, "☆")}
                </span>
              </div>
            )}
          </div>
        )}

        {/* 选项 */}
        {phase === "answering" && currentQuestion?.options && (
          <div className="space-y-2">
            {currentQuestion.options.map((opt) => {
              const isSelected = selectedAnswers.includes(opt.letter);
              return (
                <button
                  key={opt.letter}
                  onClick={() => toggleAnswer(opt.letter)}
                  className={`w-full flex items-start gap-3 p-3 rounded-lg border text-left transition-all ${
                    isSelected
                      ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10"
                      : "border-[var(--color-border)]/60 bg-[var(--color-surface)] hover:border-[var(--color-accent)]/40"
                  }`}
                >
                  <span className={`flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full text-[11px] font-medium ${
                    isSelected
                      ? "bg-[var(--color-accent)] text-white"
                      : "bg-[var(--color-bg)] text-[var(--color-text-muted)] border border-[var(--color-border)]"
                  }`}>
                    {opt.letter}
                  </span>
                  <span className="text-[13px] text-[var(--color-text)] leading-relaxed pt-0.5">
                    {opt.text}
                  </span>
                </button>
              );
            })}
          </div>
        )}

        {/* 答题结果 */}
        {phase === "result" && lastResult && (
          <div>
            {/* 对错徽章 */}
            <div className={`flex items-center gap-2 p-3 rounded-lg mb-4 ${
              lastResult.is_correct
                ? "bg-green-500/10 border border-green-500/30"
                : "bg-red-500/10 border border-red-500/30"
            }`}>
              {lastResult.is_correct ? (
                <Check size={18} className="text-green-500" />
              ) : (
                <X size={18} className="text-red-500" />
              )}
              <span className={`text-sm font-medium ${
                lastResult.is_correct ? "text-green-600" : "text-red-500"
              }`}>
                {lastResult.is_correct ? "回答正确！" : "回答错误"}
              </span>
              {lastResult.mastered && (
                <span className="ml-auto flex items-center gap-1 text-[11px] text-green-500">
                  <Trophy size={12} />已掌握
                </span>
              )}
            </div>

            {/* 正确答案 */}
            {!lastResult.is_correct && lastResult.correct_answer?.length > 0 && (
              <div className="p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]/60 mb-3">
                <p className="text-[11px] text-[var(--color-text-muted)] mb-1">正确答案</p>
                <p className="text-sm font-medium text-[var(--color-text)]">
                  {lastResult.correct_answer.join("、")}
                </p>
              </div>
            )}

            {/* 解析 */}
            {lastResult.analysis && (
              <div className="p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]/60 mb-3">
                <div className="flex items-center gap-1 mb-2">
                  <Lightbulb size={12} className="text-[var(--color-accent)]" />
                  <span className="text-[11px] font-medium text-[var(--color-text-muted)]">解析</span>
                </div>
                <p className="text-[13px] text-[var(--color-text)] leading-relaxed whitespace-pre-wrap">
                  {lastResult.analysis}
                </p>
              </div>
            )}

            {/* 下一题按钮 */}
            <button
              onClick={handleNext}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-[var(--color-accent)] text-white text-sm font-medium hover:opacity-90 transition-opacity"
            >
              {currentIdx + 1 >= (session?.total_count ?? 0) ? (
                <>查看结果 <BarChart3 size={14} /></>
              ) : (
                <>下一题 <ChevronRight size={14} /></>
              )}
            </button>
          </div>
        )}

        {/* 提交按钮（答题阶段） */}
        {phase === "answering" && (
          <button
            onClick={handleSubmit}
            disabled={selectedAnswers.length === 0}
            className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg text-sm font-medium transition-all mt-4 ${
              selectedAnswers.length > 0
                ? "bg-[var(--color-accent)] text-white hover:opacity-90"
                : "bg-[var(--color-border)]/50 text-[var(--color-text-muted)] cursor-not-allowed"
            }`}
          >
            提交答案 <Check size={14} />
          </button>
        )}
      </div>
    </div>
  );
}

// ── 子组件 ──

function IdleScreen({
  mode, setMode, count, setCount, onStart, nodeLabel,
}: {
  mode: string; setMode: (m: "adaptive" | "review" | "challenge") => void;
  count: number; setCount: (n: number) => void;
  onStart: () => void; nodeLabel?: string;
}) {
  const [reviewStats, setReviewStats] = useState<{ due_now: number; mastered: number; not_mastered: number } | null>(null);

  useEffect(() => {
    import("@/lib/practice-api").then(({ getReviewStats }) => {
      getReviewStats().then(setReviewStats).catch(() => {});
    });
  }, []);

  return (
    <div className="flex flex-col items-center justify-center h-full px-6 py-8">
      <div className="w-12 h-12 rounded-full bg-[var(--color-accent)]/10 flex items-center justify-center mb-4">
        <Play size={20} className="text-[var(--color-accent)]" />
      </div>
      <h3 className="text-base font-semibold text-[var(--color-text)] mb-1">
        {nodeLabel ? `「${nodeLabel}」练习` : "智能练习"}
      </h3>
      <p className="text-[11px] text-[var(--color-text-muted)] text-center mb-6 leading-relaxed">
        自适应出题 · 实时判题 · 知识点联动
      </p>

      {/* 复习概览 */}
      {reviewStats && reviewStats.due_now > 0 && (
        <div className="w-full mb-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30">
          <div className="flex items-center gap-2">
            <RotateCcw size={14} className="text-amber-500" />
            <span className="text-[12px] font-medium text-amber-600">待复习</span>
            <span className="ml-auto text-lg font-bold text-amber-500">{reviewStats.due_now}</span>
            <span className="text-[10px] text-amber-500/70">题到期</span>
          </div>
          <div className="flex items-center gap-3 mt-1.5 text-[10px] text-[var(--color-text-muted)]">
            <span>已掌握 {reviewStats.mastered}</span>
            <span>·</span>
            <span>待掌握 {reviewStats.not_mastered}</span>
          </div>
        </div>
      )}

      {/* 模式选择 */}
      <div className="w-full mb-4">
        <p className="text-[10px] text-[var(--color-text-muted)] mb-2 font-medium">练习模式</p>
        <div className="grid grid-cols-3 gap-2">
          {[
            { key: "adaptive", label: "自适应", desc: "薄弱优先", icon: <Brain size={14} /> },
            { key: "review", label: "复习", desc: "错题为主", icon: <RotateCcw size={14} /> },
            { key: "challenge", label: "挑战", desc: "高难度", icon: <Sparkles size={14} /> },
          ].map((m) => (
            <button
              key={m.key}
              onClick={() => setMode(m.key as any)}
              className={`flex flex-col items-center gap-1 p-3 rounded-lg border transition-all ${
                mode === m.key
                  ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10"
                  : "border-[var(--color-border)]/50 bg-[var(--color-surface)] hover:border-[var(--color-accent)]/30"
              }`}
            >
              <span className={mode === m.key ? "text-[var(--color-accent)]" : "text-[var(--color-text-muted)]"}>{m.icon}</span>
              <span className={`text-[11px] font-medium ${mode === m.key ? "text-[var(--color-accent)]" : "text-[var(--color-text)]"}`}>{m.label}</span>
              <span className="text-[9px] text-[var(--color-text-muted)]">{m.desc}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 题数选择 */}
      <div className="w-full mb-6">
        <p className="text-[10px] text-[var(--color-text-muted)] mb-2 font-medium">题数</p>
        <div className="flex gap-2">
          {[3, 5, 10].map((n) => (
            <button
              key={n}
              onClick={() => setCount(n)}
              className={`flex-1 py-2 rounded-lg border text-center text-sm font-medium transition-all ${
                count === n
                  ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                  : "border-[var(--color-border)]/50 bg-[var(--color-surface)] text-[var(--color-text)] hover:border-[var(--color-accent)]/30"
              }`}
            >
              {n} 题
            </button>
          ))}
        </div>
      </div>

      <button
        onClick={onStart}
        className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-[var(--color-accent)] text-white text-sm font-medium hover:opacity-90 transition-opacity"
      >
        <Play size={14} />开始练习
      </button>

      <p className="mt-3 text-[9px] text-[var(--color-text-muted)]">支持键盘操作：1-4 选答案 · Enter 提交/下一题</p>
    </div>
  );
}

function LoadingScreen() {
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <Loader2 size={24} className="animate-spin text-[var(--color-accent)] mb-3" />
      <p className="text-xs text-[var(--color-text-muted)]">正在出题...</p>
    </div>
  );
}

function ErrorScreen({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-6">
      <X size={24} className="text-red-500 mb-3" />
      <p className="text-sm text-[var(--color-text)] mb-4 text-center">{message}</p>
      <button
        onClick={onRetry}
        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white text-xs font-medium"
      >
        <RotateCcw size={12} />返回重试
      </button>
    </div>
  );
}

function SummaryScreen({
  session, results, onRetry, onClose,
}: {
  session: V7Session | null; results: V7SubmitResult[];
  onRetry: () => void; onClose?: () => void;
}) {
  const total = results.length;
  const correct = results.filter((r) => r.is_correct).length;
  const wrong = total - correct;
  const score = total > 0 ? Math.round((correct / total) * 100) : 0;
  const mastered = results.filter((r) => r.mastered).length;

  return (
    <div className="flex flex-col h-full px-4 py-6">
      <div className="text-center mb-6">
        <div className="w-14 h-14 rounded-full bg-[var(--color-accent)]/10 flex items-center justify-center mx-auto mb-3">
          <Trophy size={24} className="text-[var(--color-accent)]" />
        </div>
        <h3 className="text-lg font-bold text-[var(--color-text)]">练习完成！</h3>
        <p className="text-[11px] text-[var(--color-text-muted)] mt-1">
          {session?.mode === "review" ? "复习模式" : session?.mode === "challenge" ? "挑战模式" : "自适应模式"}
        </p>
      </div>

      {/* 成绩卡片 */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="col-span-2 p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/60 text-center">
          <span className={`text-4xl font-bold ${
            score >= 80 ? "text-green-500" : score >= 60 ? "text-yellow-500" : "text-red-500"
          }`}>{score}</span>
          <span className="text-sm text-[var(--color-text-muted)] ml-1">分</span>
          <p className="text-[10px] text-[var(--color-text-muted)] mt-1">
            {score >= 80 ? "优秀！" : score >= 60 ? "加油，继续进步！" : "薄弱知识点较多，建议复习"}
          </p>
        </div>
        <div className="p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]/60 text-center">
          <span className="text-lg font-semibold text-green-500">{correct}</span>
          <p className="text-[10px] text-[var(--color-text-muted)]">正确</p>
        </div>
        <div className="p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]/60 text-center">
          <span className="text-lg font-semibold text-red-500">{wrong}</span>
          <p className="text-[10px] text-[var(--color-text-muted)]">错误</p>
        </div>
        <div className="p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]/60 text-center">
          <span className="text-lg font-semibold text-[var(--color-text)]">{mastered}</span>
          <p className="text-[10px] text-[var(--color-text-muted)]">已掌握</p>
        </div>
        <div className="p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]/60 text-center">
          <span className="text-lg font-semibold text-[var(--color-text)]">
            {session?.duration_seconds
              ? `${Math.floor(session.duration_seconds / 60)}:${String(session.duration_seconds % 60).padStart(2, "0")}`
              : "--"}
          </span>
          <p className="text-[10px] text-[var(--color-text-muted)]">用时</p>
        </div>
      </div>

      {/* 错题回顾 */}
      {results.filter((r) => !r.is_correct).length > 0 && (
        <div className="mb-4">
          <p className="text-[11px] text-[var(--color-text-muted)] font-medium mb-2">需要复习的知识点</p>
          <div className="space-y-2">
            {results.filter((r) => !r.is_correct).slice(0, 5).map((r, i) => (
              <div key={i} className="p-2.5 rounded-lg bg-red-500/5 border border-red-500/20">
                <p className="text-[12px] text-[var(--color-text)] leading-relaxed">
                  第 {results.indexOf(r) + 1} 题：{r.analysis?.slice(0, 80)}...
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-auto space-y-2">
        <button
          onClick={onRetry}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-[var(--color-accent)] text-white text-sm font-medium hover:opacity-90 transition-opacity"
        >
          <RotateCcw size={14} />再来一组
        </button>
        {onClose && (
          <button
            onClick={onClose}
            className="w-full py-2 text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
          >
            返回对话
          </button>
        )}
      </div>
    </div>
  );
}
