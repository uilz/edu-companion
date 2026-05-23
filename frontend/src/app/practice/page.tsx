"use client";

/**
 * 练习页面 - Practice Page
 * 提供自适应练习题练习功能，包含答题、提示、知识状态追踪和错因分析。
 * 用户可通过 URL 参数 (skill) 指定练习的技能领域。
 */

import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  CheckCircle,
  XCircle,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  Lightbulb,
  Loader2,
} from "lucide-react";
import Card from "@/components/ui/Card";
import MathContent from "@/components/ui/MathContent";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * 题目选项接口：字母标识 + 选项文本 + 是否正确
 */
interface QuestionOption {
  letter: string;
  text: string;
  is_correct: boolean;
}

/**
 * 题目接口：包含题目元数据、选项、正确答案、解析和提示
 */
interface Question {
  question_id: string;
  skill_id: string;
  subject: string;
  bloom_level: string;
  text: string;
  options: QuestionOption[] | null;
  correct_answer: string;
  explanation: string;
  hints: string[];
  difficulty: number;
}

/**
 * 练习会话接口：会话 ID、题目列表、技能规划和模式
 */
interface Session {
  session_id: string;
  question_ids: string[];
  planned_skills: string[];
  mode: string;
  status: string;
}

/**
 * 提交答案结果接口：正确性、解析、知识状态更新、错因分析和情感反馈
 */
interface SubmitResult {
  is_correct: boolean;
  correct_answer: string;
  explanation: string;
  knowledge_update?: {
    skill_id: string;
    p_known_before: number;
    p_known_after: number;
    mastery_level: string;
  };
  error_analysis?: {
    type: string;
    suggestion: string;
  };
  emotional_feedback?: string;
}

/**
 * 提示结果接口：提示层级、文本内容和类型
 */
interface HintResult {
  level: number;
  text: string;
  type: string;
}

export const dynamic = 'force-dynamic';

function PracticeContent() {
  // --- URL 参数与状态管理 ---
  const searchParams = useSearchParams();
  const skillParam = searchParams.get('skill');
  const [initialSkill] = useState<string | null>(skillParam);

  // 练习会话、题目列表、当前进度
  const [session, setSession] = useState<Session | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  // 用户选择、提交状态、提交结果
  const [selected, setSelected] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [submitResult, setSubmitResult] = useState<SubmitResult | null>(null);
  // 加载状态、提示信息、计时
  const [loading, setLoading] = useState(false);
  const [hint, setHint] = useState<HintResult | null>(null);
  const [hintLevel, setHintLevel] = useState(0);
  const [startTime, setStartTime] = useState<number>(0);

  // 当前题目与正确性快捷引用
  const q = questions[currentIndex];
  const isCorrect = submitResult?.is_correct;

  // 创建练习会话
  const createSession = useCallback(async (skillIds?: string[]) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/practice/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          skill_ids: skillIds || [],
          duration_minutes: 30,
          mode: "adaptive",
        }),
      });
      const data = await res.json();
      setSession(data.session);
      setQuestions(data.questions);
      setCurrentIndex(0);
      setSelected(null);
      setSubmitted(false);
      setSubmitResult(null);
      setHint(null);
      setHintLevel(0);
      setStartTime(Date.now());
    } catch (err) {
      console.error("Failed to create session:", err);
    }
    setLoading(false);
  }, []);

  // 自动创建会话（支持跨页 skill 参数）
  useEffect(() => {
    if (!session) {
      const skillIds = initialSkill ? [initialSkill] : [];
      createSession(skillIds);
    }
  }, [session, createSession, initialSkill]);

  // 提交答案
  const handleSubmit = async () => {
    if (!selected || !session || !q) return;

    setLoading(true);
    try {
      const timeSpent = (Date.now() - startTime) / 1000;
      const res = await fetch(`${API_BASE}/api/practice/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: session.session_id,
          question_id: q.question_id,
          answer: selected,
          time_spent_seconds: timeSpent,
          hints_used: hintLevel,
        }),
      });
      const result: SubmitResult = await res.json();
      setSubmitResult(result);
      setSubmitted(true);
    } catch (err) {
      console.error("Submit failed:", err);
    }
    setLoading(false);
  };

  // 获取提示
  const handleHint = async () => {
    if (!q) return;
    try {
      const res = await fetch(`${API_BASE}/api/practice/hint`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question_id: q.question_id,
          current_level: hintLevel,
        }),
      });
      const data = await res.json();
      setHint(data.hint);
      setHintLevel(data.hint.level);
    } catch (err) {
      console.error("Hint failed:", err);
    }
  };

  // 下一题
  const handleNext = () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex((i) => i + 1);
      setSelected(null);
      setSubmitted(false);
      setSubmitResult(null);
      setHint(null);
      setHintLevel(0);
      setStartTime(Date.now());
    }
  };

  // 上一题
  const handlePrev = () => {
    if (currentIndex > 0) {
      setCurrentIndex((i) => i - 1);
      setSelected(null);
      setSubmitted(false);
      setSubmitResult(null);
      setHint(null);
      setHintLevel(0);
      setStartTime(Date.now());
    }
  };

  // 重新开始
  const handleRestart = () => {
    createSession();
  };

  // 完成练习（通知后端写入对话branch）
  const [completed, setCompleted] = useState(false);
  const handleComplete = async () => {
    if (!session || completed) return;
    setCompleted(true);
    const sp = new URLSearchParams(window.location.search);
    const pid = sp.get("partition_id");
    const bid = sp.get("branch_id");
    if (!pid || !bid) return;  // 不是从对话来的，无需写入
    try {
      await fetch(
        `${API_BASE}/api/practice/sessions/${session.session_id}/complete?partition_id=${pid}&branch_id=${bid}`,
        { method: "POST" }
      );
    } catch (e) {
      console.error("Complete failed:", e);
    }
  };

  // --- 渲染：加载中 ---
  if (loading && !q) {
    return (
      <main className="min-h-screen bg-[var(--color-bg)]">
        <div className="max-w-3xl mx-auto px-6 py-16 flex items-center justify-center">
          <Loader2 className="animate-spin text-[var(--color-accent)]" size={24} />
          <span className="ml-3 text-[var(--color-text-muted)]">加载中...</span>
        </div>
      </main>
    );
  }

  // --- 渲染：无可用题目（提示重新生成） ---
  if (!q) {
    return (
      <main className="min-h-screen bg-[var(--color-bg)]">
        <div className="max-w-3xl mx-auto px-6 py-16 text-center">
          <h1 className="text-4xl font-bold tracking-tight text-[var(--color-text)] mb-4">
            练习
          </h1>
          <p className="text-[var(--color-text-muted)] mb-8">暂无可用题目</p>
          <button
            onClick={handleRestart}
            className="px-6 py-2.5 bg-[var(--color-accent)] text-[var(--color-text)] text-sm font-medium hover:bg-[var(--color-accent-hover)] transition-colors"
          >
            重新生成
          </button>
        </div>
      </main>
    );
  }

  // --- 渲染：主练习界面 ---
  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-3xl mx-auto px-6 py-16">
        {/* 顶栏：标题 + 重新开始按钮 */}
        <div className="flex items-center justify-between mb-12">
          <h1 className="text-4xl font-bold tracking-tight text-[var(--color-text)]">
            练习
          </h1>
          <button
            onClick={handleRestart}
            className="flex items-center gap-1.5 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
          >
            <RotateCcw size={14} />
            重新开始
          </button>
        </div>

        {/* 进度条：显示科目 / 认知层级 / 难度与题号进度 */}
        <div className="mb-8">
          <div className="flex items-center justify-between text-xs text-[var(--color-text-muted)] mb-2">
            <span>
              {q.subject} · {q.bloom_level} · 难度 {q.difficulty}
            </span>
            <span>
              {currentIndex + 1} / {questions.length}
            </span>
          </div>
          <div className="w-full bg-[var(--color-surface)] h-1">
            <div
              className="h-full bg-[var(--color-accent)] transition-all"
              style={{
                width: `${((currentIndex + 1) / questions.length) * 100}%`,
              }}
            />
          </div>
        </div>

        {/* 题目卡片：题目文本 + 选项 + 提示 + 操作按钮 + 结果反馈 */}
        <Card>
          {/* 题目内容（支持 LaTeX 数学公式渲染） */}
          <MathContent
            text={q.text}
            className="text-base text-[var(--color-text)] leading-relaxed mb-8 message-content"
          />

          {/* 选项列表：单选按钮，提交后显示正确/错误状态 */}
          {q.options && (
            <div className="space-y-3">
              {q.options.map((opt) => {
                const isSelected = selected === opt.letter;
                const showResult = submitted;
                const isCorrectOption = opt.is_correct;

                return (
                  <button
                    key={opt.letter}
                    onClick={() => !submitted && setSelected(opt.letter)}
                    disabled={submitted}
                    className={`w-full text-left p-4 border text-sm transition-colors ${
                      showResult
                        ? isCorrectOption
                          ? "border-[var(--color-success)] bg-[var(--color-success)]/10 text-[var(--color-success)]"
                          : isSelected && !isCorrectOption
                          ? "border-[var(--color-error)] bg-[var(--color-error)]/10 text-[var(--color-error)]"
                          : "border-[var(--color-border)] text-[var(--color-text-muted)]"
                        : isSelected
                        ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-text)]"
                        : "border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-hover)]"
                    }`}
                  >
                    <span className="font-semibold mr-3">{opt.letter}.</span>
                    {opt.text}
                  </button>
                );
              })}
            </div>
          )}

          {/* 提示区域：显示分层提示内容 */}
          {hint && (
            <div className="mt-4 p-4 border border-[var(--color-accent)]/30 bg-[var(--color-accent)]/5 text-sm">
              <div className="flex items-center gap-2 mb-1 text-[var(--color-accent)] font-semibold">
                <Lightbulb size={14} />
                提示 Level {hint.level}
              </div>
              <div className="text-[var(--color-text-secondary)]">
                {hint.text}
              </div>
            </div>
          )}

          {/* 操作按钮：提交答案 / 获取提示（未提交时）；重新开始（已提交后） */}
          <div className="flex items-center gap-3 mt-8">
            {!submitted ? (
              <>
                <button
                  onClick={handleSubmit}
                  disabled={!selected || loading}
                  className="px-6 py-2.5 bg-[var(--color-accent)] text-[var(--color-text)] text-sm font-medium disabled:opacity-30 hover:bg-[var(--color-accent-hover)] transition-colors"
                >
                  {loading ? (
                    <Loader2 className="animate-spin inline" size={14} />
                  ) : (
                    "提交答案"
                  )}
                </button>
                <button
                  onClick={handleHint}
                  className="flex items-center gap-1.5 px-4 py-2.5 border border-[var(--color-border)] text-[var(--color-text-secondary)] text-sm hover:border-[var(--color-border-hover)] transition-colors"
                >
                  <Lightbulb size={14} />
                  提示
                </button>
              </>
            ) : (
              <button
                onClick={handleRestart}
                className="px-6 py-2.5 border border-[var(--color-border)] text-[var(--color-text-secondary)] text-sm hover:border-[var(--color-border-hover)] transition-colors"
              >
                <RotateCcw size={14} className="inline mr-1.5" />
                重新开始
              </button>
            )}
          </div>

          {/* 结果反馈区域：正确/错误提示、知识更新、解析、错因分析、情感反馈 */}
          {submitted && submitResult && (
            <div
              className={`mt-6 p-5 border text-sm leading-relaxed ${
                isCorrect
                  ? "border-[var(--color-success)]/30 bg-[var(--color-success)]/5"
                  : "border-[var(--color-error)]/30 bg-[var(--color-error)]/5"
              }`}
            >
              <div className="flex items-center gap-2 mb-3 font-semibold">
                {isCorrect ? (
                  <>
                    <CheckCircle
                      size={16}
                      className="text-[var(--color-success)]"
                    />
                    <span className="text-[var(--color-success)]">
                      回答正确！
                    </span>
                  </>
                ) : (
                  <>
                    <XCircle
                      size={16}
                      className="text-[var(--color-error)]"
                    />
                    <span className="text-[var(--color-error)]">
                      回答错误，正确答案是 {submitResult.correct_answer}
                    </span>
                  </>
                )}
              </div>

              {/* 知识状态更新 */}
              {submitResult.knowledge_update && (
                <div className="text-xs text-[var(--color-text-muted)] mb-3">
                  掌握度：{(submitResult.knowledge_update.p_known_before * 100).toFixed(0)}%
                  → {(submitResult.knowledge_update.p_known_after * 100).toFixed(0)}%
                  （{submitResult.knowledge_update.mastery_level}）
                </div>
              )}

              {/* 解析 */}
              <div className="text-[var(--color-text-secondary)] message-content">
                {submitResult.explanation
                  .split("\n\n")
                  .map((para, i) => (
                    <p key={i} className="mb-2 last:mb-0">
                      <MathContent text={para.replace(/\n/g, " ")} as="span" />
                    </p>
                  ))}
              </div>

              {/* 错因分析 */}
              {submitResult.error_analysis && (
                <div className="mt-3 p-3 bg-[var(--color-surface)] text-xs">
                  <span className="font-semibold">错因分析：</span>
                  {submitResult.error_analysis.suggestion}
                </div>
              )}

              {/* 情感反馈 */}
              {submitResult.emotional_feedback && (
                <div className="mt-3 text-sm text-[var(--color-accent)]">
                  {submitResult.emotional_feedback}
                </div>
              )}
            </div>
          )}
        </Card>

        {/* 完成按钮：最后一题提交后出现，通知后端写入对话分支 */}
        {submitted && currentIndex >= questions.length - 1 && !completed && (
          <div className="flex justify-center mb-4">
            <button
              onClick={handleComplete}
              className="px-8 py-3 bg-[var(--color-accent)] text-[var(--color-text)] text-sm font-medium hover:bg-[var(--color-accent-hover)] transition-colors"
            >
              完成练习 ✓
            </button>
          </div>
        )}

        {/* 导航按钮：上一题 / 下一题 */}
        <div className="flex items-center justify-between mt-6">
          <button
            onClick={handlePrev}
            disabled={currentIndex === 0}
            className="flex items-center gap-1 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors disabled:opacity-30"
          >
            <ChevronLeft size={16} />
            上一题
          </button>
          <button
            onClick={handleNext}
            disabled={currentIndex >= questions.length - 1 || !submitted}
            className="flex items-center gap-1 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors disabled:opacity-30"
          >
            下一题
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </main>
  );
}

/**
 * 练习页面入口组件
 * 使用 Suspense 包裹以支持 useSearchParams() 的客户端渲染
 */
export default function PracticePage() {
  return (
    <Suspense fallback={
      // 外层加载状态（Suspense fallback）
      <main className="min-h-screen bg-[var(--color-bg)] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 size={24} className="animate-spin text-[var(--color-accent)]" />
          <span className="text-sm text-[var(--color-text-muted)]">加载中…</span>
        </div>
      </main>
    }>
      <PracticeContent />
    </Suspense>
  );
}
