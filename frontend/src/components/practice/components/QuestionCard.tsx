"use client";

import { useState, useCallback, useEffect, memo } from "react";
import { Volume2, Heart, EyeOff, Eye, Lightbulb, SkipForward, Shuffle, Loader2, BookOpen, MessageSquareText } from "lucide-react";
import QuestionStem from "@/components/practice/components/QuestionStem";
import OptionButton from "./OptionButton";
import FeedbackPanel from "./FeedbackPanel";
import HintPanel from "./HintPanel";
import ExplanationPanel from "./ExplanationPanel";
import ReferencePanel from "./ReferencePanel";
import {
  getQuestionHint,
  generateSimilarQuestions,
  toggleFavorite,
  toggleSlash,
  type V7Question,
  type V7SubmitResult,
} from "@/lib/api/practice-api";

const TYPE_LABELS: Record<string, string> = {
  single: "单选", multiple: "多选", judge: "判断",
  choice: "单选", fill: "填空", free_form: "简答", essay: "简答",
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
  onSubmit: (answer?: string[]) => void;
  onSkip: () => void;
  onNext: () => void;
  isLast: boolean;
  isExam?: boolean;
  submitError?: string;
  /** 自信度 */
  confidenceBefore?: number | null;
  onConfidenceChange?: (level: number) => void;
}

/** 练习卡片 — 题干 + 选项 + 反馈 + 工具栏 一体化 */
function QuestionCardImpl({
  question, index, total,
  showFeedback, lastResult, submitting, selected,
  onSelect, onSubmit, onSkip, onNext, isLast, isExam, submitError,
  confidenceBefore, onConfidenceChange,
}: Props) {
  const [showHint, setShowHint] = useState(false);
  const [hintText, setHintText] = useState("");
  const [hintLoading, setHintLoading] = useState(false);
  const [isFav, setIsFav] = useState(false);
  const [similarLoading, setSimilarLoading] = useState(false);
  const [skipped, setSkipped] = useState(false);
  const [showExplanation, setShowExplanation] = useState(false);
  const [showReference, setShowReference] = useState(false);
  const [fillAnswer, setFillAnswer] = useState("");

  const qtype = question.question_type;
  const isOptionType = qtype === "single" || qtype === "multiple" || qtype === "judge" || qtype === "choice";
  const canSubmit = (isOptionType ? selected.length > 0 : fillAnswer.trim().length > 0) && confidenceBefore !== null;

  const handleShowHint = useCallback(async () => {
    if (showHint) return;
    setHintLoading(true);
    try {
      const resp = await getQuestionHint(question.id, 0);
      setHintText(resp.hint?.text || "");
      setShowHint(true);
    } catch {
      setHintText("无法加载提示");
      setShowHint(true);
    }
    setHintLoading(false);
  }, [question.id, showHint]);

  const handleReadAloud = useCallback(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const text = question.stem.replace(/[*_#`~>\[\]()]/g, "");
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "zh-CN"; u.rate = 0.9;
    window.speechSynthesis.speak(u);
  }, [question.stem]);

  const handleFav = useCallback(async () => {
    try { setIsFav((await toggleFavorite(question.id)).is_favorite); } catch {}
  }, [question.id]);
  const handleSlash = useCallback(async () => {
    try { await toggleSlash(question.id); } catch {}
  }, [question.id]);
  const handleSimilar = useCallback(async () => {
    setSimilarLoading(true);
    try { await generateSimilarQuestions(question.id, 3); } catch {}
    setSimilarLoading(false);
  }, [question.id]);

  // 处理跳过
  const handleSkip = useCallback(() => {
    setSkipped(true);
    onSkip();
  }, [onSkip]);

  // 提交按钮点击：选择题直接提交，填空/简答直接传答案
  const handleSubmitClick = useCallback(() => {
    if (isOptionType) {
      onSubmit();
    } else {
      onSubmit([fillAnswer.trim()]);
    }
  }, [isOptionType, onSubmit, fillAnswer]);

  // 切换题目时重置填空答案
  useEffect(() => {
    setFillAnswer("");
    setSkipped(false);
    setShowHint(false);
    setHintText("");
    setShowExplanation(false);
    setShowReference(false);
  }, [question.id]);

  return (
    <div className="rounded-2xl border border bg-page overflow-hidden message-enter">
      {/* ── 头部 ── */}
      <div className="px-3 sm:px-5 py-3 border-b border/50 flex items-center gap-2 flex-wrap">
        <span className="text-xs px-2 py-0.5 rounded-full bg-accent/10 text-accent font-medium">
          第 {index + 1} 题
        </span>
        <span className="text-xs px-2 py-0.5 rounded-full bg-surface text-muted">
          {TYPE_LABELS[qtype] || qtype}
        </span>
        <div className="flex-1" />
        {!isExam && (
          <div className="flex items-center gap-0.5">
            <IconButton icon={<Volume2 size={13} />} title="朗读" onClick={handleReadAloud} />
            <IconButton
              icon={<Heart size={13} className={isFav ? "fill-danger text-danger" : ""} />}
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
              icon={<MessageSquareText size={13} className={showExplanation ? "text-accent" : ""} />}
              title="讲解"
              onClick={() => setShowExplanation(!showExplanation)}
            />}
            {<IconButton
              icon={<BookOpen size={13} className={showReference ? "text-info" : ""} />}
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
      <div className="px-3 sm:px-5 py-4">
        <QuestionStem stem={question.stem} className="text-base leading-relaxed" />
      </div>

      {/* ── 提示（仅答题前） ── */}
      {!showFeedback && (
        <div className="px-3 sm:px-5 pb-3">
          <HintPanel
            visible={showHint}
            hintText={hintText}
            loading={hintLoading}
            onClose={() => setShowHint(false)}
          />
        </div>
      )}

      {/* ── 自信度选择器（仅答题前） ── */}
      {!showFeedback && onConfidenceChange && (
        <div className="px-3 sm:px-5 pb-3">
          <p className="text-[10px] text-muted mb-2">答题前，请先评估你对本题的把握程度：</p>
          <div className="flex gap-2">
            {[
              { level: 1, label: "完全不确定", emoji: "🤔" },
              { level: 2, label: "有点不确定", emoji: "🤨" },
              { level: 3, label: "比较确定", emoji: "👍" },
              { level: 4, label: "非常确定", emoji: "💪" },
            ].map((item) => {
              const active = confidenceBefore === item.level;
              return (
                <button
                  key={item.level}
                  type="button"
                  data-testid={`confidence-level-${item.level}`}
                  onClick={() => onConfidenceChange(item.level)}
                  className={`flex-1 py-2 px-1 rounded-xl border text-xs font-medium transition-all ${
                    active
                      ? "border-accent bg-accent/10 text-accent"
                      : "border bg-page text-muted hover:border-accent/50"
                  }`}
                >
                  <div className="text-sm mb-0.5">{item.emoji}</div>
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* ── 选项 ── */}
      {isOptionType && (
        <div className="px-3 sm:px-5 pb-4 space-y-2">
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
                isCorrect={!!(isCorrectAnswer && !isWrongPick)}
                disabled={showFeedback}
                onSelect={() => onSelect(label)}
              />
            );
          })}
        </div>
      )}

      {/* ── 填空/简答输入框 ── */}
      {!isOptionType && !showFeedback && (
        <div className="px-3 sm:px-5 pb-4">
          <textarea
            value={fillAnswer}
            onChange={(e) => { setFillAnswer(e.target.value); }}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && canSubmit) handleSubmitClick(); }}
            placeholder={qtype === "fill" ? "输入你的答案...（Ctrl+Enter 提交）" : "输入你的回答...（Ctrl+Enter 提交）"}
            rows={qtype === "fill" ? 2 : 4}
            className="w-full px-4 py-3 rounded-xl border border bg-page text-sm resize-none focus:outline-none focus:border-accent transition-colors"
            disabled={showFeedback}
          />
        </div>
      )}

      {/* ── 填空/简答的反馈：显示用户的回答 ── */}
      {!isOptionType && showFeedback && selected.length > 0 && (
        <div className="px-3 sm:px-5 pb-4">
          <div className="p-3 rounded-xl border border/60 bg-surface">
            <p className="text-[10px] text-muted mb-1">你的回答</p>
            <p className="text-sm text whitespace-pre-wrap">{selected[0]}</p>
          </div>
        </div>
      )}

      {/* ── 反馈 ── */}
      {showFeedback && lastResult && (
        <div className="px-3 sm:px-5 pb-4">
          <FeedbackPanel
            isCorrect={lastResult.is_correct}
            correctAnswer={lastResult.correct_answer || []}
            analysis={(lastResult as any).explanation || (lastResult as any).analysis || ""}
            skipped={skipped}
            metacognitionFeedback={lastResult.metacognition_feedback}
            confidenceBefore={confidenceBefore}
          />
        </div>
      )}

      {/* ── AI 讲解 ── */}
      <div className="px-3 sm:px-5 pb-4">
        <ExplanationPanel
          questionId={question.id}
          stem={question.stem}
          visible={showExplanation}
          onClose={() => setShowExplanation(false)}
        />
      </div>

      {/* ── 参考资料 ── */}
      <div className="px-3 sm:px-5 pb-4">
        <ReferencePanel
          questionId={question.id}
          query={question.stem}
          visible={showReference}
          onClose={() => setShowReference(false)}
        />
      </div>

      {/* ── 底部按钮 ── */}
      <div className="px-3 sm:px-5 py-3 border-t border/50 flex flex-col gap-2">
        {submitError && (
          <div className="text-[10px] text-danger text-center">{submitError}</div>
        )}
        <div className="flex justify-end gap-2">
          {!showFeedback ? (
            <button
              onClick={handleSubmitClick}
              disabled={!canSubmit || submitting}
              data-testid="submit-answer-btn"
              className="px-5 py-2 rounded-xl bg-accent text-white text-sm font-medium hover:opacity-90 disabled:opacity-30 transition-all flex items-center gap-1.5"
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
              data-testid="next-question-btn"
              className="px-5 py-2 rounded-xl bg-accent text-white text-sm font-medium hover:opacity-90 transition-all"
            >
              {isLast ? "完成练习" : "下一题"}
              <svg viewBox="0 0 16 16" className="w-3.5 h-3.5 inline ml-1.5" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="6,4 10,8 6,12" />
              </svg>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function IconButton({ icon, title, onClick }: { icon: React.ReactNode; title: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="p-1.5 rounded-lg hover:bg-surface text-muted hover:text transition-colors"
      title={title}
    >
      {icon}
    </button>
  );
}

/**
 * React.memo 包裹 — 切题/改置信度不再触发整卡重渲
 * 自定义比较：question.id/showFeedback/submitting/selected 变化才重渲
 */
const QuestionCard = memo(QuestionCardImpl, (prev, next) => {
  return (
    prev.question.id === next.question.id &&
    prev.question.stem === next.question.stem &&
    prev.showFeedback === next.showFeedback &&
    prev.submitting === next.submitting &&
    prev.selected === next.selected &&
    prev.isLast === next.isLast &&
    prev.isExam === next.isExam &&
    prev.submitError === next.submitError &&
    prev.confidenceBefore === next.confidenceBefore &&
    prev.index === next.index &&
    prev.total === next.total
  );
});

export default QuestionCard;
