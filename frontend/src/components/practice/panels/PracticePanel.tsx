"use client";

import React, { useState, useCallback, useEffect } from "react";
import Link from "next/link";
import {
  Play, Check, X, ChevronRight,
  RotateCcw, Brain, Trophy, BarChart3,
  Lightbulb, BookOpen, Loader2, Sparkles,
  Volume2, SkipForward, Heart, EyeOff, Eye,
  Shuffle,
} from "lucide-react";
import {
  createPracticeSession,
  submitAnswer,
  completeSession,
  resolveBankForNode,
  generateQuestions,
  getQuestionExplanation,
  generateSimilarQuestions,
  toggleFavorite,
  toggleSlash,
  type V7Session,
  type V7Question,
  type V7SubmitResult,
  type MaterialItem,
} from "@/lib/api/practice-api";
import ReferencePanel from "./ReferencePanel";
import SecretaryProposals from "./../components/SecretaryProposals";
import QuestionStem from "@/components/practice/components/QuestionStem";

// ── 状态机 ──
type Phase = "idle" | "loading" | "answering" | "submitting" | "result" | "summary" | "error";

interface Props {
  nodeId?: string;
  nodeLabel?: string;
  bankId?: string;
  onClose?: () => void;
}

export default function PracticePanel({ nodeId, nodeLabel, bankId, onClose }: Props) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [session, setSession] = useState<V7Session | null>(null);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState<string[]>([]);
  const [lastResult, setLastResult] = useState<V7SubmitResult | null>(null);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<"adaptive" | "review" | "challenge">("adaptive");
  const [count, setCount] = useState(5);
  const [questionStart, setQuestionStart] = useState(0);

  // 参考资料出题 — 选择的资料 ID 列表
  const [selectedMaterialIds, setSelectedMaterialIds] = useState<string[]>([]);

  // 统计（在 summary 中展示）
  const [results, setResults] = useState<V7SubmitResult[]>([]);

  // —— 答题辅助 ——
  const [showHint, setShowHint] = useState(false);
  const [hintText, setHintText] = useState("");
  const [hintLoading, setHintLoading] = useState(false);
  const [isFav, setIsFav] = useState(false);
  const [isSlashed, setIsSlashed] = useState(false);
  const [similarQuestions, setSimilarQuestions] = useState<V7Question[]>([]);
  const [similarLoading, setSimilarLoading] = useState(false);
  const [skipped, setSkipped] = useState(false);

  const currentQuestion = session?.questions?.[currentIdx] ?? null;

  // ── 开始练习 ──
  const handleStart = useCallback(async () => {
    setPhase("loading");
    setError("");
    setResults([]);
    setCurrentIdx(0);

    try {
      let resolvedBankId: string;

      if (bankId) {
        resolvedBankId = bankId;
      } else if (nodeId) {
        const resolved = await resolveBankForNode(nodeId);
        resolvedBankId = resolved.bank_id;
      } else {
        // 无 node — 用默认题库
        const banks = await (await fetch("/api/v7/practice/banks")).json();
        resolvedBankId = banks?.[0]?.id || "bnk_default";
      }

      const sess = await createPracticeSession(resolvedBankId, {
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
            {
              bank_id: resolvedBankId,
              node_id: nodeId,
              material_ids: selectedMaterialIds.length > 0 ? selectedMaterialIds : undefined,
            }
          );
          if (genResult.generated > 0) {
            const sess2 = await createPracticeSession(resolvedBankId, {
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
  }, [nodeId, nodeLabel, mode, count, selectedMaterialIds]);

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
      setShowHint(false);
      setHintText("");
      setIsFav(false);
      setIsSlashed(false);
      setSimilarQuestions([]);
      setSkipped(false);
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
    setShowHint(false);
    setHintText("");
    setSimilarQuestions([]);
    setSkipped(false);
  }, []);

  // ── 跳过 / 我不会 ──
  const handleSkip = useCallback(async () => {
    if (!session || !currentQuestion) return;
    setPhase("submitting");
    try {
      const result = await submitAnswer(
        session.session_id,
        currentQuestion.id,
        [], // 空答案 = 跳过
        Math.floor((Date.now() - questionStart) / 1000),
      );
      setSkipped(true);
      setLastResult(result);
      setResults((prev) => [...prev, { ...result, is_correct: false }]);
      setPhase("result");
    } catch {
      setPhase("answering");
    }
  }, [session, currentQuestion, questionStart]);

  // ── 显示提示 ──
  const handleShowHint = useCallback(async () => {
    if (!currentQuestion || showHint) return;
    setHintLoading(true);
    try {
      const resp = await getQuestionExplanation(currentQuestion.id, "concise");
      setHintText(resp.explanation || "");
      setShowHint(true);
    } catch {
      setHintText("无法加载提示，请重试");
      setShowHint(true);
    }
    setHintLoading(false);
  }, [currentQuestion, showHint]);

  // ── TTS 朗读 ──
  const handleReadAloud = useCallback(() => {
    if (!currentQuestion) return;
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const text = currentQuestion.stem.replace(/[*_#`~>\[\]()]/g, "");
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "zh-CN";
      utterance.rate = 0.9;
      window.speechSynthesis.speak(utterance);
    }
  }, [currentQuestion]);

  // ── 收藏/取消收藏 ──
  const handleToggleFavorite = useCallback(async () => {
    if (!currentQuestion) return;
    try {
      const result = await toggleFavorite(currentQuestion.id);
      setIsFav(result.is_favorite);
    } catch {}
  }, [currentQuestion]);

  // ── 斩题/恢复 ──
  const handleToggleSlash = useCallback(async () => {
    if (!currentQuestion) return;
    try {
      const result = await toggleSlash(currentQuestion.id);
      setIsSlashed(result.is_slashed);
    } catch {}
  }, [currentQuestion]);

  // ── 生成同类变体 ──
  const handleGenerateSimilar = useCallback(async () => {
    if (!currentQuestion) return;
    setSimilarLoading(true);
    try {
      const resp = await generateSimilarQuestions(currentQuestion.id, 3);
      setSimilarQuestions(resp.questions || []);
    } catch {}
    setSimilarLoading(false);
  }, [currentQuestion]);

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
    return <IdleScreen mode={mode} setMode={setMode} count={count} setCount={setCount} onStart={handleStart} nodeLabel={nodeLabel}
      selectedMaterialIds={selectedMaterialIds} setSelectedMaterialIds={setSelectedMaterialIds} />;
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
            <div className="flex items-start justify-between gap-2 mb-2">
              <QuestionStem stem={currentQuestion.stem} className="text-base leading-relaxed flex-1" />
              {/* 工具栏 */}
              <div className="flex items-center gap-0.5 flex-shrink-0">
                <button
                  onClick={handleReadAloud}
                  className="p-1.5 rounded hover:bg-[var(--color-bg)] transition-colors"
                  title="朗读题目"
                >
                  <Volume2 size={14} className="text-[var(--color-text-muted)]" />
                </button>
                <button
                  onClick={handleToggleFavorite}
                  className={`p-1.5 rounded hover:bg-[var(--color-bg)] transition-colors ${isFav ? "text-red-500" : ""}`}
                  title={isFav ? "取消收藏" : "收藏"}
                >
                  {isFav ? <Heart size={14} className="text-red-500 fill-red-500" /> : <Heart size={14} className="text-[var(--color-text-muted)]" />}
                </button>
                <button
                  onClick={handleToggleSlash}
                  className={`p-1.5 rounded hover:bg-[var(--color-bg)] transition-colors ${isSlashed ? "text-[var(--color-text-muted)]" : ""}`}
                  title={isSlashed ? "已斩题" : "斩题"}
                >
                  {isSlashed ? <EyeOff size={14} className="text-[var(--color-text-muted)]" /> : <Eye size={14} className="text-[var(--color-text-muted)]" />}
                </button>
              </div>
            </div>
            {currentQuestion.difficulty > 0 && (
              <div className="flex items-center gap-1 mt-1">
                <span className="text-[9px] text-[var(--color-text-muted)]">
                  难度: {"★".repeat(currentQuestion.difficulty).padEnd(5, "☆")}
                </span>
              </div>
            )}
          </div>
        )}

        {/* 提示 */}
        {phase === "answering" && showHint && hintText && (
          <div className="mb-4 p-3 rounded-lg bg-blue-500/5 border border-blue-500/20">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Lightbulb size={12} className="text-blue-500" />
              <span className="text-[11px] font-medium text-blue-600">提示</span>
            </div>
            <p className="text-[12px] text-[var(--color-text)] leading-relaxed">{hintText}</p>
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
              skipped
                ? "bg-amber-500/10 border border-amber-500/30"
                : lastResult.is_correct
                ? "bg-green-500/10 border border-green-500/30"
                : "bg-red-500/10 border border-red-500/30"
            }`}>
              {skipped ? (
                <SkipForward size={18} className="text-amber-500" />
              ) : lastResult.is_correct ? (
                <Check size={18} className="text-green-500" />
              ) : (
                <X size={18} className="text-red-500" />
              )}
              <span className={`text-sm font-medium ${
                skipped ? "text-amber-600" : lastResult.is_correct ? "text-green-600" : "text-red-500"
              }`}>
                {skipped ? "已跳过" : lastResult.is_correct ? "回答正确！" : "回答错误"}
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

            {/* 同类变体题目 */}
            {!lastResult.is_correct && (
              <div className="mb-3">
                {similarQuestions.length > 0 ? (
                  <div className="p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]/60">
                    <p className="text-[11px] font-medium text-[var(--color-text-muted)] mb-2">
                      同类变体 ({similarQuestions.length} 题)
                    </p>
                    <div className="space-y-1.5">
                      {similarQuestions.map((q) => (
                        <p key={q.id} className="text-[11px] text-[var(--color-text)] leading-relaxed">
                          {q.stem.slice(0, 80)}{q.stem.length > 80 ? "..." : ""}
                        </p>
                      ))}
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={handleGenerateSimilar}
                    disabled={similarLoading}
                    className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border border-[var(--color-border)]/60 text-[11px] text-[var(--color-text-muted)] hover:border-[var(--color-accent)]/40 hover:text-[var(--color-accent)] transition-colors"
                  >
                    {similarLoading ? (
                      <Loader2 size={12} className="animate-spin" />
                    ) : (
                      <Shuffle size={12} />
                    )}
                    生成同类变体练习
                  </button>
                )}
              </div>
            )}

            {/* 视频讲解 */}
            {currentQuestion && (
              <div className="mb-3">
                <ReferencePanel
                  query={currentQuestion.stem.slice(0, 40)}
                  compact
                />
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
          <div className="space-y-2 mt-4">
            <button
              onClick={handleSubmit}
              disabled={selectedAnswers.length === 0}
              className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                selectedAnswers.length > 0
                  ? "bg-[var(--color-accent)] text-white hover:opacity-90"
                  : "bg-[var(--color-border)]/50 text-[var(--color-text-muted)] cursor-not-allowed"
              }`}
            >
              提交答案 <Check size={14} />
            </button>
            <div className="flex gap-2">
              <button
                onClick={handleShowHint}
                disabled={hintLoading || showHint}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border border-[var(--color-border)]/60 text-[11px] text-[var(--color-text-muted)] hover:border-blue-500/40 hover:text-blue-500 transition-colors disabled:opacity-50"
              >
                {hintLoading ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : (
                  <Lightbulb size={12} />
                )}
                {showHint ? "已显示提示" : "提示"}
              </button>
              <button
                onClick={handleSkip}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border border-[var(--color-border)]/60 text-[11px] text-[var(--color-text-muted)] hover:border-amber-500/40 hover:text-amber-500 transition-colors"
              >
                <SkipForward size={12} />
                我不会
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── 子组件 ──

function IdleScreen({
  mode, setMode, count, setCount, onStart, nodeLabel,
  selectedMaterialIds, setSelectedMaterialIds,
}: {
  mode: string; setMode: (m: "adaptive" | "review" | "challenge") => void;
  count: number; setCount: (n: number) => void;
  onStart: () => void; nodeLabel?: string;
  selectedMaterialIds: string[]; setSelectedMaterialIds: (ids: string[]) => void;
}) {
  const [reviewStats, setReviewStats] = useState<{ due_now: number; mastered: number; not_mastered: number } | null>(null);
  const [materials, setMaterials] = useState<MaterialItem[]>([]);
  const [showMaterialPicker, setShowMaterialPicker] = useState(false);
  const [loadingMaterials, setLoadingMaterials] = useState(false);

  useEffect(() => {
    import("@/lib/api/practice-api").then(({ getReviewStats }) => {
      getReviewStats().then(setReviewStats).catch(() => {});
    });
  }, []);

  // 加载用户的资料列表（初次显示或展开选择器时）
  useEffect(() => {
    if (showMaterialPicker && materials.length === 0) {
      setLoadingMaterials(true);
      import("@/lib/api/practice-api").then(({ listMaterials }) => {
        listMaterials({ purpose: "library", status: "indexed", page_size: 50 })
          .then((res) => setMaterials(res.items || []))
          .catch(() => {})
          .finally(() => setLoadingMaterials(false));
      });
    }
  }, [showMaterialPicker, materials.length]);

  const toggleMaterial = (id: string) => {
    if (selectedMaterialIds.includes(id)) {
      setSelectedMaterialIds(selectedMaterialIds.filter((x) => x !== id));
    } else {
      setSelectedMaterialIds([...selectedMaterialIds, id]);
    }
  };

  const clearMaterials = () => {
    setSelectedMaterialIds([]);
    setShowMaterialPicker(false);
  };

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

      {/* 参考资料选择 */}
      <div className="w-full mb-3">
        <button
          onClick={() => setShowMaterialPicker(!showMaterialPicker)}
          className={`w-full flex items-center gap-2 p-2.5 rounded-lg border text-left transition-all ${
            selectedMaterialIds.length > 0
              ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10"
              : "border-[var(--color-border)]/50 bg-[var(--color-surface)] hover:border-[var(--color-accent)]/30"
          }`}
        >
          <BookOpen size={14} className={selectedMaterialIds.length > 0 ? "text-[var(--color-accent)]" : "text-[var(--color-text-muted)]"} />
          <span className={`text-[11px] font-medium ${selectedMaterialIds.length > 0 ? "text-[var(--color-accent)]" : "text-[var(--color-text)]"}`}>
            {selectedMaterialIds.length > 0
              ? `参考资料 (${selectedMaterialIds.length} 份已选)`
              : "参考资料（可选）"}
          </span>
          <span className="ml-auto text-[10px] text-[var(--color-text-muted)]">
            {showMaterialPicker ? "收起" : "展开"}
          </span>
        </button>

        {/* 资料选择面板 */}
        {showMaterialPicker && (
          <div className="mt-2 p-3 rounded-lg border border-[var(--color-border)]/50 bg-[var(--color-surface)] max-h-[200px] overflow-y-auto">
            {loadingMaterials ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 size={14} className="animate-spin text-[var(--color-text-muted)]" />
                <span className="ml-2 text-[10px] text-[var(--color-text-muted)]">加载资料中...</span>
              </div>
            ) : materials.length === 0 ? (
              <div className="text-center py-4">
                <p className="text-[10px] text-[var(--color-text-muted)] mb-2">暂无已索引的资料</p>
                <p className="text-[9px] text-[var(--color-text-muted)]">请先上传文件到知识库</p>
              </div>
            ) : (
              <div className="space-y-1.5">
                {materials.map((m) => {
                  const selected = selectedMaterialIds.includes(m.material_id);
                  return (
                    <label
                      key={m.material_id}
                      className={`flex items-center gap-2.5 p-2 rounded-md cursor-pointer transition-colors ${
                        selected ? "bg-[var(--color-accent)]/10" : "hover:bg-[var(--color-bg)]"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => toggleMaterial(m.material_id)}
                        className="accent-[var(--color-accent)]"
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-[11px] text-[var(--color-text)] truncate">{m.file_name}</p>
                        <p className="text-[9px] text-[var(--color-text-muted)]">
                          {m.file_type} · {(m.file_size / 1024).toFixed(0)}KB · {m.chunk_count} 分块
                        </p>
                      </div>
                      {selected && (
                        <span className="text-[9px] text-[var(--color-accent)] font-medium">已选</span>
                      )}
                    </label>
                  );
                })}
              </div>
            )}

            {/* 操作按钮 */}
            {selectedMaterialIds.length > 0 && (
              <div className="flex items-center justify-end gap-2 mt-2 pt-2 border-t border-[var(--color-border)]/30">
                <button
                  onClick={clearMaterials}
                  className="text-[10px] text-[var(--color-text-muted)] hover:text-red-500 transition-colors"
                >
                  清空选择
                </button>
                <span className="text-[10px] text-[var(--color-text-muted)]">
                  已选 {selectedMaterialIds.length} 份
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 已选资料标签（折叠时展示） */}
      {selectedMaterialIds.length > 0 && !showMaterialPicker && (
        <div className="w-full mb-3 flex flex-wrap gap-1.5">
          {materials
            .filter((m) => selectedMaterialIds.includes(m.material_id))
            .map((m) => (
              <span
                key={m.material_id}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--color-accent)]/10 text-[9px] text-[var(--color-accent)] border border-[var(--color-accent)]/30"
              >
                <BookOpen size={8} />
                {m.file_name.slice(0, 20)}{m.file_name.length > 20 ? "…" : ""}
              </span>
            ))}
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
        <Play size={14} />
        {selectedMaterialIds.length > 0 ? "基于资料出题" : "开始练习"}
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

      {/* 秘书提案 — 错题诊断/反思引导 */}
      <SecretaryProposals sessionId={session?.session_id} />

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
        {session?.bank_id && (
          <Link href={`/practice/banks/${session.bank_id}`}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg border border-[var(--color-border)]/50 text-[12px] text-[var(--color-text)] hover:bg-[var(--color-surface)] transition-colors">
            <BookOpen size={13} />查看题库
          </Link>
        )}
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
