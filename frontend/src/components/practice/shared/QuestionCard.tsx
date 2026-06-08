"use client";

import { useState, useCallback } from "react";
import { Volume2, Heart, EyeOff, Eye, Lightbulb, SkipForward, Shuffle, Loader2, BookOpen, MessageSquareText } from "lucide-react";
import QuestionStem from "@/components/practice/components/QuestionStem";
import OptionButton from "./OptionButton";
import FeedbackPanel from "./FeedbackPanel";
import HintPanel from "./HintPanel";
import ExplanationPanel from "./ExplanationPanel";
import ReferencePanel from "./ReferencePanel";
import {
  getQuestionExplanation,
  generateSimilarQuestions,
  toggleFavorite,
  toggleSlash,
  type V7Question,
  type V7SubmitResult,
} from "@/lib/api/practice-api";

const TYPE_LABELS: Record<string, string> = {
  single: "单选", multiple: "多选", judge: "判断",
  fill: "填空", free_form: "简答", essay: "简答",
};

interface Props {
  question: V7Question;
  index: number;
  total: number;
  /** 外部控制提交/下一题 */
  showFeedback: boolean;
  lastResult: V7SubmitResult | null;
  submitting: boolean;
  selected: string[];
  onSelect: (label: string) => void;
  onSubmit: () => void;
  onSkip: () => void;
  onNext: () => void;
  isLast: boolean;
  isExam?: boolean;
}

/** 练习卡片 — 题干 + 选项 + 反馈 + 工具栏 一体化 */
export default function QuestionCard({
  question, index, total,
  showFeedback, lastResult, submitting, selected,
  onSelect, onSubmit, onSkip, onNext, isLast, isExam,
}: Props) {
  const [showHint, setShowHint] = useState(false);
  const [hintText, setHintText] = useState("");
  const [hintLoading, setHintLoading] = useState(false);
  const [isFav, setIsFav] = useState(false);
  const [similarLoading, setSimilarLoading] = useState(false);
  const [skipped, setSkipped] = useState(false);
  const [showExplanation, setShowExplanation] = useState(false);
  const [showReference, setShowReference] = useState(false);

  const qtype = question.question_type;
  const isOptionType = qtype === "single" || qtype === "multiple" || qtype === "judge";
  const canSubmit = isOptionType ? selected.length > 0 : false;

  const handleShowHint = useCallback(async () => {
    if (showHint) return;
    setHintLoading(true);
    try {
      const resp = await getQuestionExplanation(question.id, "concise");
      setHintText(resp.explanation || "");
      setShowHint(true);
    } catch {
      setHintText("无法加载提示");
      setShowHint(true);
    }
    setHintLoading(false);
  }, [question.id, showHint]);

  const handleReadAloud = () => {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const text = question.stem.replace(/[*_#`~>\[\]()]/g, "");
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "zh-CN"; u.rate = 0.9;
      window.speechSynthesis.speak(u);
    }
  };

  const handleFav = async () => {
    try { setIsFav((await toggleFavorite(question.id)).is_favorite); } catch {}
  };
  const handleSlash = async () => {
    try { /* no need to store state */ await toggleSlash(question.id); } catch {}
  };
  const handleSimilar = async () => {
    setSimilarLoading(true);
    try { await generateSimilarQuestions(question.id, 3); } catch {}
    setSimilarLoading(false);
  };

  // 处理跳过
  const handleSkip = () => {
    setSkipped(true);
    onSkip();
  };

  return (
    <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg)] overflow-hidden">
      {/* ── 头部 ── */}
      <div className="px-5 py-3 border-b border-[var(--color-border)]/50 flex items-center gap-2">
        <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--color-accent)]/10 text-[var(--color-accent)] font-medium">
          第 {index + 1} 题
        </span>
        <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--color-surface)] text-[var(--color-text-muted)]">
          {TYPE_LABELS[qtype] || qtype}
        </span>
        <div className="flex-1" />
        {!isExam && (
          <div className="flex items-center gap-0.5">
            <IconButton icon={<Volume2 size={13} />} title="朗读" onClick={handleReadAloud} />
            <IconButton
              icon={<Heart size={13} className={isFav ? "fill-red-500 text-red-500" : ""} />}
              title={isFav ? "取消收藏" : "收藏"}
              onClick={handleFav}
            />
            <IconButton icon={<EyeOff size={13} />} title="斩题" onClick={handleSlash} />
            {!showFeedback && (
              <IconButton icon={<Lightbulb size={13} />} title="提示" onClick={handleShowHint} />
            )}
            {!showFeedback && !isExam && (
              <IconButton icon={<SkipForward size={13} />} title="跳过" onClick={handleSkip} />
            )}
            {<IconButton
              icon={<MessageSquareText size={13} className={showExplanation ? "text-[var(--color-accent)]" : ""} />}
              title="讲解"
              onClick={() => setShowExplanation(!showExplanation)}
            />}
            {<IconButton
              icon={<BookOpen size={13} className={showReference ? "text-blue-500" : ""} />}
              title="参考资料"
              onClick={() => setShowReference(!showReference)}
            />}
            {!showFeedback && !isExam && (
              <IconButton
                icon={similarLoading ? <Loader2 size={13} className="animate-spin" /> : <Shuffle size={13} />}
                title="同类变体"
                onClick={handleSimilar}
              />
            )}
          </div>
        )}
      </div>

      {/* ── 题干 ── */}
      <div className="px-5 py-4">
        <QuestionStem stem={question.stem} className="text-base leading-relaxed" />
      </div>

      {/* ── 提示（仅答题前） ── */}
      {!showFeedback && (
        <div className="px-5 pb-3">
          <HintPanel
            visible={showHint}
            hintText={hintText}
            loading={hintLoading}
            onClose={() => setShowHint(false)}
          />
        </div>
      )}

      {/* ── 选项 ── */}
      {isOptionType && (
        <div className="px-5 pb-4 space-y-2">
          {(question.options || []).map((opt: any) => {
            const label = opt.letter || opt.label || "";
            const text = opt.text || opt.content || "";
            const isSelected = selected.includes(label);
            const isCorrectAnswer = showFeedback && lastResult?.correct_answer?.includes(label);
            const isWrongPick = showFeedback && isSelected && !lastResult?.correct_answer?.includes(label);

            return (
              <OptionButton
                key={label}
                label={label}
                text={text}
                selected={isSelected || isCorrectAnswer || false}
                showResult={showFeedback}
                isCorrect={isCorrectAnswer && !isWrongPick}
                disabled={showFeedback}
                onSelect={() => onSelect(label)}
              />
            );
          })}
        </div>
      )}

      {/* ── 反馈 ── */}
      {showFeedback && lastResult && (
        <div className="px-5 pb-4">
          <FeedbackPanel
            isCorrect={lastResult.is_correct}
            correctAnswer={lastResult.correct_answer || []}
            analysis={(lastResult as any).explanation || (lastResult as any).analysis || ""}
            skipped={skipped}
          />
        </div>
      )}

      {/* ── AI 讲解 ── */}
      <div className="px-5 pb-4">
        <ExplanationPanel
          questionId={question.id}
          stem={question.stem}
          visible={showExplanation}
          onClose={() => setShowExplanation(false)}
        />
      </div>

      {/* ── 参考资料 ── */}
      <div className="px-5 pb-4">
        <ReferencePanel
          questionId={question.id}
          query={question.stem}
          visible={showReference}
          onClose={() => setShowReference(false)}
        />
      </div>

      {/* ── 底部按钮 ── */}
      <div className="px-5 py-3 border-t border-[var(--color-border)]/50 flex justify-end gap-2">
        {!showFeedback ? (
          <button
            onClick={onSubmit}
            disabled={!canSubmit || submitting}
            className="px-5 py-2 rounded-xl bg-[var(--color-accent)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-30 transition-all flex items-center gap-1.5"
          >
            {submitting ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <svg viewBox="0 0 16 16" className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polyline points="3,8 7,12 13,4" />
              </svg>
            )}
            提交答案
          </button>
        ) : (
          <button
            onClick={onNext}
            className="px-5 py-2 rounded-xl bg-[var(--color-accent)] text-white text-sm font-medium hover:opacity-90 transition-all"
          >
            {isLast ? "完成练习" : "下一题"}
            <svg viewBox="0 0 16 16" className="w-3.5 h-3.5 inline ml-1.5" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="6,4 10,8 6,12" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}

function IconButton({ icon, title, onClick }: { icon: React.ReactNode; title: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="p-1.5 rounded-lg hover:bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
      title={title}
    >
      {icon}
    </button>
  );
}
