// ============================================================
// EXP-04 V2 · SELF VALIDATION Screen (Practice)
//
// 对齐 Vision (preview.html) 的 practice 阶段：
//   1. 进入后加载一道练习题
//   2. 用户答题 → 反馈正确/错误
//   3. "做成一张卡记住它" + "再来一道" / "去反思"
//   4. 可选自由文本"用自己的话写"
// ============================================================

"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { Loader2, Sparkles, Check } from "lucide-react";
import { generateQuestions } from "@/lib/api/practice-api";
import type { V7Question } from "@/lib/api/practice-api";
import OptionButton from "@/components/practice/components/OptionButton";
import { createSessionFlashcard } from "@/lib/api/session-tool-api";


interface SelfValidationScreenProps {
  engine: any;
  currentState: any;
  mission: { title: string; steps: { order: number; description: string; type: string }[] } | null;
  referenceText: string | null;
  onBackToLearn: () => Promise<void>;
  onContinue: () => Promise<void>;
  transitioning: boolean;
  sessionId?: string;
  missionTitle?: string;
}

// ── 备用题目 ──
const FALLBACK_QUESTION: V7Question = {
  id: "fallback_practice",
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

export default function Exp04SelfValidationScreen({
  mission,
  onBackToLearn,
  onContinue,
  transitioning,
  missionTitle,
}: SelfValidationScreenProps) {
  // ── 练习状态 ──
  const [question, setQuestion] = useState<V7Question | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [flashcardCreating, setFlashcardCreating] = useState(false);
  const [flashcardCreated, setFlashcardCreated] = useState(false);

  // ── 反思文字（可选） ──
  const [text, setText] = useState("");

  // 正确选项
  const correctLetters = useMemo(
    () => question?.options.filter((o) => o.is_correct).map((o) => o.letter) ?? [],
    [question?.options],
  );
  const isCorrect = selected !== null && correctLetters.includes(selected);

  // 加载题目
  const loadQuestion = useCallback(async () => {
    setLoading(true);
    setSelected(null);
    setSubmitted(false);
    try {
      const topic = missionTitle || mission?.title || "当前学习内容";
      const result = await generateQuestions(topic);
      setQuestion(result.questions?.[0] || FALLBACK_QUESTION);
    } catch {
      setQuestion(FALLBACK_QUESTION);
    } finally {
      setLoading(false);
    }
  }, [missionTitle, mission?.title]);

  useEffect(() => {
    loadQuestion();
  }, [loadQuestion]);

  // 再来一道
  const handleRetry = () => {
    setFlashcardCreated(false);
    loadQuestion();
  };

  // 去反思
  const handleGoReflect = () => {
    onContinue();
  };

  // 创建闪卡
  const handleCreateFlashcard = async () => {
    if (!sessionId || flashcardCreating || flashcardCreated) return;
    setFlashcardCreating(true);
    try {
      await createSessionFlashcard(sessionId, {
        front_text: question?.stem || "",
        tags: ["practice", "session"],
      });
      setFlashcardCreated(true);
    } catch {
      // 静默失败
    } finally {
      setFlashcardCreating(false);
    }
  };

  return (
    <div className="min-h-screen bg-page flex flex-col">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-lg mx-auto px-5 pt-10">
          {/* 引导 */}
          <p className="text-xs text-ink-muted tracking-[2px] uppercase mb-4 font-medium">
            练一练
          </p>
          <h1 className="text-[22px] font-bold text-ink-primary leading-[1.3] mb-3 tracking-tight">
            来检验一下吧
          </h1>
          <p className="text-sm text-ink-muted leading-relaxed mb-8">
            {missionTitle ? `关于「${missionTitle}」的一道题` : "一道关于今天内容的题"}
          </p>

          {/* ── 题目区 ── */}
          {loading ? (
            <div className="flex flex-col items-center py-16 gap-3">
              <Loader2 size={24} className="animate-spin text-ink-muted" />
              <span className="text-sm text-ink-muted">苹果果在出题…</span>
            </div>
          ) : question ? (
            <div className="bg-surface rounded-2xl border border-border/50 p-5 sm:p-6 mb-6">
              {/* 题干 */}
              <p className="text-base leading-relaxed text-ink-primary mb-5">
                {question.stem}
              </p>

              {/* 选项 */}
              <div className="flex flex-col gap-3">
                {question.options.map((option) => (
                  <OptionButton
                    key={option.letter}
                    label={option.letter}
                    text={option.text}
                    selected={selected === option.letter}
                    disabled={submitted}
                    showResult={submitted}
                    isCorrect={option.is_correct}
                    onSelect={() => {
                      if (!submitted) {
                        setSelected(option.letter);
                        setSubmitted(true);
                      }
                    }}
                  />
                ))}
              </div>

              {/* 答题反馈 */}
              {submitted && (
                <div className="mt-5 pt-4 border-t border-border/40">
                  <div className={`flex items-start gap-3 p-4 rounded-xl ${isCorrect ? "bg-green-50" : "bg-amber-50"}`}>
                    <Sparkles size={18} className={isCorrect ? "text-green-500" : "text-amber-500 mt-0.5"} />
                    <div>
                      <p className={`text-sm font-semibold ${isCorrect ? "text-green-700" : "text-amber-700"}`}>
                        {isCorrect ? "算对了。" : "这里有点绕。"}
                      </p>
                      <p className={`text-sm mt-1 ${isCorrect ? "text-green-600" : "text-amber-600"}`}>
                        {isCorrect
                          ? "这个思路很清晰。"
                          : "没关系，这正好说明这里值得多想想。"}
                      </p>
                    </div>
                  </div>

                  {/* 做成一张卡记住它 */}
                  {sessionId && (
                    <div className="mt-4 p-4 rounded-xl bg-surface border border-border/50">
                      <p className="text-sm font-medium text-ink-primary mb-3">做成一张卡记住它</p>
                      {flashcardCreated ? (
                        <p className="text-sm text-success flex items-center gap-1.5">
                          <Check size={16} />
                          已经加进你的卡片了。下次复习会再见到。
                        </p>
                      ) : (
                        <button
                          onClick={handleCreateFlashcard}
                          disabled={flashcardCreating}
                          className="flex items-center gap-1.5 text-sm font-medium text-[#F4B400] hover:text-[#e5a800] transition-colors disabled:opacity-40"
                        >
                          {flashcardCreating ? <Loader2 size={16} className="animate-spin" /> : <span className="text-base leading-none">＋</span>}
                          {flashcardCreating ? "创建中…" : "创建"}
                        </button>
                      )}
                    </div>
                  )}

                  {/* 再来一道 / 去反思 */}
                  <div className="flex gap-3 mt-4">
                    <button
                      onClick={handleRetry}
                      className="flex-1 h-12 rounded-xl bg-white border border-border/60 text-ink-primary text-sm font-medium hover:bg-surface transition-colors"
                    >
                      再来一道
                    </button>
                    <button
                      onClick={handleGoReflect}
                      disabled={transitioning}
                      className="flex-1 h-12 rounded-xl bg-[#F4B400] text-white text-sm font-semibold hover:bg-[#e5a800] transition-colors disabled:opacity-50"
                    >
                      去反思
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : null}

          {/* ── 可选：用自己的话写 ── */}
          <div className="mb-6">
            <p className="text-sm text-ink-muted mb-3">
              你也可以用自己的话写下理解（可选）：
            </p>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={`说说你对${missionTitle || "今天的内容"}的理解……`}
              className="w-full min-h-[100px] p-4 rounded-xl bg-white border border-border/60 text-sm leading-relaxed text-ink-primary resize-none outline-none focus:border-[#F4B400] transition-colors placeholder:text-ink-muted/50"
            />
          </div>
        </div>
      </div>

      {/* 底部 */}
      <div className="border-t border-border/50 px-5 py-4">
        <div className="max-w-lg mx-auto flex gap-3">
          <button
            onClick={onBackToLearn}
            disabled={transitioning}
            className="flex-1 h-14 rounded-xl bg-white border border-border/60 text-ink-primary text-base font-medium hover:bg-surface transition-colors disabled:opacity-40"
          >
            返回学习
          </button>
          <button
            onClick={handleGoReflect}
            disabled={transitioning}
            className="flex-1 h-14 rounded-xl bg-[#F4B400] text-white text-base font-semibold hover:bg-[#e5a800] transition-colors disabled:opacity-50"
          >
            {transitioning ? "准备中…" : "继续"}
          </button>
        </div>
      </div>
    </div>
  );
}
