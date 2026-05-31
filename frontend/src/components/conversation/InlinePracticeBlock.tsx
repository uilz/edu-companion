"use client";

// ===== React Hooks =====
import { useState, useMemo, useCallback } from "react";
// ===== 图标组件 =====
import { BookOpen, Lightbulb, Check, X, Loader2 } from "lucide-react";
import MathContent from "@/components/ui/MathContent";
import { renderMath, renderMarkdown } from "@/lib/math";
import { sanitizeHtml } from "@/lib/sanitize";

// ===== 选项接口 =====
interface Option {
  letter: string;
  text: string;
}

// ===== 内联练习块属性接口 =====
interface InlinePracticeBlockProps {
  blockId: string;
  questionId: string;
  stem: string;
  options: Option[];
  answerType: string;
  hint: string;
  onAnswer: (blockId: string, answer: string) => Promise<void>;
}

// ===== API 请求封装 =====
async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

// ===== 内联练习块主组件 =====
export default function InlinePracticeBlock({
  blockId,
  questionId,
  stem,
  options,
  answerType,
  hint,
  onAnswer,
}: InlinePracticeBlockProps) {
  // ===== 状态管理 =====
  const [selectedAnswer, setSelectedAnswer] = useState<string>("");   // 用户选择的答案
  const [submitted, setSubmitted] = useState(false);                  // 是否已提交
  const [isCorrect, setIsCorrect] = useState<boolean | null>(null);   // 答案是否正确
  const [replyText, setReplyText] = useState("");                     // 提交后回复文本
  const [showHint, setShowHint] = useState(false);                    // 是否显示提示
  const [currentHint, setCurrentHint] = useState(hint);               // 当前提示内容
  const [hintLevel, setHintLevel] = useState(1);                     // 提示层级
  const [isSubmitting, setIsSubmitting] = useState(false);            // 是否正在提交
  const [skipped, setSkipped] = useState(false);                      // 是否已跳过

  // ===== 渲染题干（支持数学公式与 Markdown）=====
  const stemHtml = useMemo(() => {
    const withMath = renderMath(stem);
    return renderMarkdown(withMath);
  }, [stem]);

  // ===== 提交答案 =====
  const handleSubmit = useCallback(async () => {
    if (!selectedAnswer || isSubmitting) return;
    setIsSubmitting(true);

    try {
      const result = await apiFetch<{
        is_correct: boolean;
        reply_text: string;
        knowledge_update: Record<string, unknown>;
      }>("/practice/inline/answer", {
        method: "POST",
        body: JSON.stringify({
          block_id: blockId,
          answer: selectedAnswer,
        }),
      });

      setIsCorrect(result.is_correct);
      setReplyText(result.reply_text);
      setSubmitted(true);
      onAnswer(blockId, selectedAnswer);
    } catch (e) {

    } finally {
      setIsSubmitting(false);
    }
  }, [blockId, selectedAnswer, isSubmitting, onAnswer]);

  // ===== 获取提示 =====
  const handleGetHint = useCallback(async () => {
    try {
      const result = await apiFetch<{
        hint_text: string;
        level: number;
      }>("/practice/inline/hint", {
        method: "POST",
        body: JSON.stringify({ block_id: blockId }),
      });
      setCurrentHint(result.hint_text);
      setHintLevel(result.level);
      setShowHint(true);
    } catch (e) {

    }
  }, [blockId]);

  // ===== 跳过题目 =====
  const handleSkip = useCallback(async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      // Just mark as skipped locally
      setSkipped(true);
      setIsCorrect(false);
      setReplyText("已跳过这道题");
      setSubmitted(true);
    } finally {
      setIsSubmitting(false);
    }
  }, [isSubmitting]);

  // ===== 已提交状态：显示结果 =====
  if (submitted) {
    return (
      <div className="border border-[var(--color-border)] bg-[var(--color-surface)] mt-2">
        <div className="px-3 py-2 border-b border-[var(--color-border)] flex items-center gap-2">
          {isCorrect ? (
            <Check size={14} className="text-[var(--color-success)]" />
          ) : (
            <X size={14} className="text-[var(--color-error)]" />
          )}
          <span className="text-xs font-medium text-[var(--color-text)]">
            {isCorrect ? "回答正确!" : skipped ? "已跳过" : "回答错误"}
          </span>
        </div>
        <div className="px-3 py-3">
          <div className="text-sm text-[var(--color-text-secondary)] leading-relaxed">
            {replyText}
          </div>
        </div>
      </div>
    );
  }

  // ===== 未提交状态：显示练习题 =====
  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-surface)] mt-2">
      {/* Header */}
      <div className="px-3 py-2 border-b border-[var(--color-border)] flex items-center gap-2">
        <BookOpen size={14} className="text-[var(--color-accent)]" />
        <span className="text-xs font-medium text-[var(--color-text)]">
          练习题
        </span>
        {answerType === "choice" && (
          <span className="text-[10px] text-[var(--color-text-muted)]">
            · 选择题
          </span>
        )}
      </div>

      {/* Question stem */}
      <div className="px-3 py-3">
        <div
          className="text-sm text-[var(--color-text)] leading-relaxed mb-3"
          dangerouslySetInnerHTML={{ __html: sanitizeHtml(stemHtml) }}
        />

        {/* Options - choice type */}
        {answerType === "choice" && options.length > 0 && (
          <div className="space-y-1.5 mb-3">
            {options.map((opt) => {
              const isSelected = selectedAnswer === opt.letter;
              return (
                <button
                  key={opt.letter}
                  onClick={() => setSelectedAnswer(opt.letter)}
                  className="w-full flex items-start gap-2 text-sm px-3 py-2.5 border transition-colors text-left"
                  style={{
                    backgroundColor: isSelected
                      ? "rgba(0, 102, 255, 0.08)"
                      : "transparent",
                    borderColor: isSelected
                      ? "var(--color-accent)"
                      : "var(--color-border)",
                  }}
                >
                  <span className="text-[var(--color-text-muted)] font-mono text-xs w-5 flex-shrink-0">
                    {opt.letter}.
                  </span>
                  <span className="text-[var(--color-text-secondary)]">
                    {opt.text}
                  </span>
                </button>
              );
            })}
          </div>
        )}

        {/* Fill-in type */}
        {answerType === "fill" && (
          <div className="mb-3">
            <input
              type="text"
              value={selectedAnswer}
              onChange={(e) => setSelectedAnswer(e.target.value)}
              placeholder="输入你的答案..."
              className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2.5 focus:outline-none focus:border-[var(--color-accent)] transition-colors"
              onKeyDown={(e) => {
                if (e.key === "Enter" && selectedAnswer.trim()) {
                  handleSubmit();
                }
              }}
            />
          </div>
        )}

        {/* Hint box */}
        {showHint && (
          <div className="mb-3 px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)]">
            <div className="flex items-center gap-1.5 mb-1">
              <Lightbulb size={12} className="text-[var(--color-warning)]" />
              <span className="text-[10px] text-[var(--color-text-muted)]">
                提示 {hintLevel}
              </span>
            </div>
            <div className="text-xs text-[var(--color-text-secondary)] leading-relaxed">
              {currentHint}
            </div>
          </div>
        )}

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleSubmit}
            disabled={!selectedAnswer.trim() || isSubmitting}
            className="flex-1 px-4 py-2 bg-[var(--color-accent)] text-white text-sm disabled:opacity-30 hover:bg-[var(--color-accent-hover)] active:scale-[0.97] transition-colors flex items-center justify-center gap-1.5"
          >
            {isSubmitting ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                提交中...
              </>
            ) : (
              "提交答案"
            )}
          </button>
          <button
            onClick={handleGetHint}
            disabled={isSubmitting}
            className="px-3 py-2 border border-[var(--color-border)] text-[var(--color-text-secondary)] text-sm hover:bg-[var(--color-surface-hover)] active:scale-[0.97] transition-all disabled:opacity-30 flex items-center gap-1"
          >
            <Lightbulb size={14} />
            提示
          </button>
          <button
            onClick={handleSkip}
            disabled={isSubmitting}
            className="px-3 py-2 border border-[var(--color-border)] text-[var(--color-text-muted)] text-sm hover:bg-[var(--color-surface-hover)] active:scale-[0.97] transition-all disabled:opacity-30"
          >
            跳过
          </button>
        </div>
      </div>
    </div>
  );
}
