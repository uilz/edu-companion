"use client";

import { Check, X, AlertTriangle, Loader2, TrendingUp, Brain, Target } from "lucide-react";
import QuestionStem from "@/components/practice/components/QuestionStem";
import { useAttemptFeedback } from "@/hooks/practice/useAttemptFeedback";
import type { AttemptFeedback, AttemptFeedbackNode } from "@/lib/api/practice-api";

interface Props {
  isCorrect: boolean;
  correctAnswer: string[];
  analysis?: string;
  skipped?: boolean;
  score?: number;
  /** 元认知反馈 */
  metacognitionFeedback?: string;
  confidenceBefore?: number | null;
  /** 答题尝试 ID，用于拉取信息增益 */
  attemptId?: string;
}

/** 答题反馈面板 — 正确/错误 + 解析 + 元认知反馈 + 信息增益 */
export default function FeedbackPanel({
  isCorrect,
  correctAnswer,
  analysis,
  skipped,
  score,
  metacognitionFeedback,
  confidenceBefore,
  attemptId,
}: Props) {
  const { feedback, loading, error } = useAttemptFeedback(attemptId);

  return (
    <div className={`rounded-xl p-4 border ${
      isCorrect
        ? "bg-success/10 dark:bg-success/10 border-success/20 dark:border-success/20"
        : "bg-danger/10 dark:bg-danger/10 border-danger/20 dark:border-danger/20"
    }`}>
      <div className="flex items-center gap-2 mb-2">
        {isCorrect ? (
          <Check size={16} className="text-success dark:text-success" />
        ) : (
          skipped
            ? <AlertTriangle size={16} className="text-warning" />
            : <X size={16} className="text-danger dark:text-danger" />
        )}
        <span className={`text-sm font-semibold ${
          isCorrect
            ? "text-success dark:text-success"
            : skipped
              ? "text-warning dark:text-warning"
              : "text-danger dark:text-danger"
        }`}>
          {isCorrect ? "回答正确！" : skipped ? "已跳过" : "回答错误"}
        </span>
        {score != null && (
          <span className={`ml-auto text-xs font-bold ${score >= 80 ? "text-success" : score >= 60 ? "text-warning" : "text-danger"}`}>
            +{score}
          </span>
        )}
      </div>

      {!isCorrect && correctAnswer.length > 0 && (
        <p className="text-xs text-muted mb-2">
          正确答案：<span className="font-medium text">{correctAnswer.join("、")}</span>
        </p>
      )}

      {analysis && (
        <div className="mt-2 text-xs text-muted leading-relaxed [&_p]:m-0 [&_.katex]:text-xs">
          <span className="font-medium text">解析：</span>
          <QuestionStem stem={analysis} />
        </div>
      )}

      {metacognitionFeedback && (
        <div className={`mt-3 pt-3 border-t border/40 text-xs leading-relaxed ${
          isCorrect
            ? confidenceBefore && confidenceBefore >= 3
              ? "text-success dark:text-success"
              : "text-info dark:text-info"
            : confidenceBefore && confidenceBefore >= 3
              ? "text-danger dark:text-danger"
              : "text-warning dark:text-warning"
        }`}>
          {metacognitionFeedback}
        </div>
      )}

      {/* 信息增益区域 */}
      {attemptId && (
        <div className="mt-3 pt-3 border-t border/40">
          {loading && !feedback && (
            <div className="flex items-center gap-2 text-xs text-muted">
              <Loader2 size={12} className="animate-spin" />
              认知分析中…
            </div>
          )}

          {error && !loading && (
            <div className="text-xs text-danger">
              反馈加载失败：{error}
            </div>
          )}

          {feedback && (
            <InformationGainSection feedback={feedback} />
          )}
        </div>
      )}
    </div>
  );
}

function InformationGainSection({ feedback }: { feedback: AttemptFeedback }) {
  const { feedback: fb, metacognition, suggestions } = feedback;
  const mainNode = fb.nodes[0];
  const gain = fb.information_gain ?? 0;
  const reduction = fb.uncertainty_reduction_percent ?? 0;
  const before = fb.proficiency_before ?? 0;
  const after = fb.proficiency_after ?? 0;
  const delta = after - before;

  return (
    <div className="space-y-3">
      {/* 核心指标 */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg bg-surface/60 p-2.5">
          <div className="flex items-center gap-1 text-[10px] text-muted mb-1">
            <TrendingUp size={10} /> 信息增益
          </div>
          <div className={`text-sm font-bold ${gain > 0 ? "text-success" : "text-muted"}`}>
            {gain > 0 ? `+${gain.toFixed(2)}` : gain.toFixed(2)} <span className="text-[10px] font-normal">nats</span>
          </div>
        </div>
        <div className="rounded-lg bg-surface/60 p-2.5">
          <div className="flex items-center gap-1 text-[10px] text-muted mb-1">
            <Brain size={10} /> 不确定性降低
          </div>
          <div className={`text-sm font-bold ${reduction > 0 ? "text-info" : "text-muted"}`}>
            {reduction > 0 ? `-${reduction.toFixed(1)}%` : `${reduction.toFixed(1)}%`}
          </div>
        </div>
      </div>

      {/* 掌握度变化 */}
      <div className="rounded-lg bg-surface/60 p-2.5">
        <div className="flex items-center justify-between text-[10px] text-muted mb-1.5">
          <span className="flex items-center gap-1"><Target size={10} /> 掌握度变化</span>
          <span>{(before * 100).toFixed(0)}% → {(after * 100).toFixed(0)}%</span>
        </div>
        <div className="relative h-2 bg-page rounded-full overflow-hidden">
          <div
            className="absolute top-0 left-0 h-full bg-info/30 rounded-full transition-all"
            style={{ width: `${Math.max(0, Math.min(100, before * 100))}%` }}
          />
          <div
            className={`absolute top-0 left-0 h-full rounded-full transition-all ${delta >= 0 ? "bg-success" : "bg-danger"}`}
            style={{ width: `${Math.max(0, Math.min(100, after * 100))}%` }}
          />
        </div>
        <div className="mt-1 text-[10px] text-muted">
          {delta > 0 ? `掌握度提升 ${(delta * 100).toFixed(1)}%` : delta < 0 ? `掌握度下降 ${(Math.abs(delta) * 100).toFixed(1)}%` : "掌握度暂无变化"}
          {!feedback.is_final && " · 认知结果仍在计算中"}
        </div>
      </div>

      {/* 涉及知识点 */}
      {mainNode && (
        <div className="flex flex-wrap gap-1.5">
          {fb.nodes.map((node: AttemptFeedbackNode) => (
            <span
              key={node.node_id || node.label}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-accent/10 text-accent text-[10px]"
            >
              {node.label || "未命名知识点"}
              {node.information_gain > 0 && ` +${node.information_gain.toFixed(2)}`}
            </span>
          ))}
        </div>
      )}

      {/* 元认知建议（API 返回版本） */}
      {metacognition.advice && (
        <div className={`text-xs leading-relaxed ${
          isPositiveBias(metacognition.bias) ? "text-success" : "text-warning"
        }`}>
          {metacognition.advice}
        </div>
      )}

      {/* 学习建议 */}
      {suggestions.length > 0 && (
        <div className="space-y-1.5">
          {suggestions.map((s: { title: string; reason: string }, i: number) => (
            <div key={i} className="flex items-start gap-1.5 text-xs text-muted">
              <span className="text-accent mt-0.5">•</span>
              <span>{s.title} <span className="text-[10px] opacity-70">({s.reason})</span></span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function isPositiveBias(bias: string): boolean {
  return bias === "accurate";
}
