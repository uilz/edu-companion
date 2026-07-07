"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  RotateCcw, Check, X, ChevronLeft,
} from "lucide-react";
import { PageSkeleton } from "@/components/ui/Skeleton";
import {
  submitAnswer, createPracticeSession, getQuestion,
  type V7Question, type V7SubmitResult,
} from "@/lib/api/practice-api";
import QuestionCard from "@/components/practice/components/QuestionCard";

export default function ReviewQuestionPage() {
  const { qid } = useParams<{ qid: string }>();
  const router = useRouter();

  const [question, setQuestion] = useState<V7Question | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string[]>([]);
  const [showFeedback, setShowFeedback] = useState(false);
  const [lastResult, setLastResult] = useState<V7SubmitResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [questionStart, setQuestionStart] = useState(0);

  // 加载题目并创建复习会话
  useEffect(() => {
    const init = async () => {
      setLoading(true);
      try {
        // 1. 直接获取题目信息，拿到 bank_id
        const question = await getQuestion(qid);
        const bankId = question.bank_id || "bnk_default";
        // 2. 为该题库创建单题复习会话
        const sess = await createPracticeSession(bankId, {
          mode: "review",
          count: 1,
          cognitive_node_ids: question.cognitive_node_ids ?? [],
          question_ids: [qid],
        });
        setSessionId(sess.session_id);
        const q = sess.questions?.[0];
        if (q) {
          setQuestion(q);
          setQuestionStart(Date.now());
        } else {
          setError("未找到该题目的复习内容");
        }
      } catch (e: any) {
        setError(e.message || "加载失败");
      } finally {
        setLoading(false);
      }
    };
    if (qid) init();
  }, [qid]);

  const handleSelect = (label: string) => {
    if (showFeedback || submitting) return;
    const t = question?.question_type;
    if (t === "single" || t === "judge" || t === "choice") setSelected([label]);
    else setSelected(p => p.includes(label) ? p.filter(l => l !== label) : [...p, label]);
  };

  const handleSubmit = async () => {
    if (!sessionId || !question || !selected.length || submitting) return;
    setSubmitting(true);
    const ts = Math.floor((Date.now() - questionStart) / 1000);
    try {
      const r = await submitAnswer(sessionId, question.id, selected, ts);
      setLastResult(r);
      setShowFeedback(true);
    } catch {
      setError("提交失败");
    }
    setSubmitting(false);
  };

  const handleBack = () => {
    router.push("/practice");
  };

  if (loading) {
    return <PageSkeleton />;
  }

  if (error && !question) {
    return (
      <div className="min-h-screen bg-page flex flex-col items-center justify-center px-6">
        <X size={22} className="text-danger mb-3" />
        <p className="text-sm text mb-4">{error}</p>
        <button onClick={handleBack}
          className="px-4 py-2 rounded-lg bg-accent text-white text-xs font-medium">
          返回练习
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-page">
      <div className="sticky top-0 z-10 bg-page/80 backdrop-blur-sm border-b border/50">
        <div className="max-w-3xl mx-auto px-4 flex items-center h-12 gap-3">
          <button onClick={handleBack}
            className="text-xs text-muted hover:text transition-colors">
            ← 返回
          </button>
          <span className="text-[11px] text-muted">|</span>
          <RotateCcw size={13} className="text-warning" />
          <span className="text-xs font-medium text">复习</span>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-6">
        {question && (
          <QuestionCard
            question={question}
            index={0}
            total={1}
            showFeedback={showFeedback}
            lastResult={lastResult}
            submitting={submitting}
            selected={selected}
            onSelect={handleSelect}
            onSubmit={handleSubmit}
            onSkip={handleBack}
            onNext={handleBack}
            isLast={true}
          />
        )}
      </div>
    </div>
  );
}
