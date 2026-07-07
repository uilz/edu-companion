"use client";

import React, { useState, useEffect } from "react";
import {
  Brain,
  X,
  Send,
  Sparkles,
  Clock,
  Award,
  Lightbulb,
  TrendingUp,
} from "lucide-react";

type ReflectionTrigger = "practice_done" | "node_mastered" | "cognitive_conflict" | "weekly_review";

interface ReflectionModalProps {
  open: boolean;
  trigger?: ReflectionTrigger;
  /** 关联知识点（标签或ID） */
  relatedNodes?: string[];
  /** 触发上下文描述 */
  context?: string;
  onClose: () => void;
  onSave: (reflection: {
    content: string;
    trigger: ReflectionTrigger | undefined;
    relatedNodes: string[];
    sentiment?: "positive" | "neutral" | "negative";
  }) => void;
}

/**
 * 反思机制（10.5）
 * 由系统引导的结构化元认知练习。
 * 练习后、掌握新知识、认知冲突、定时复盘四种触发场景。
 */
export default function ReflectionModal({
  open,
  trigger = "practice_done",
  relatedNodes = [],
  context,
  onClose,
  onSave,
}: ReflectionModalProps) {
  const [content, setContent] = useState("");
  const [step, setStep] = useState<"guide" | "input" | "done">("guide");

  // Reset on open
  useEffect(() => {
    if (open) {
      setContent("");
      setStep("guide");
    }
  }, [open]);

  if (!open) return null;

  // ----- Trigger-specific guidance -----
  const guideConfig: Record<
    ReflectionTrigger,
    { icon: React.ReactNode; title: string; prompt: string; hint: string }
  > = {
    practice_done: {
      icon: <TrendingUp size={16} />,
      title: "练习回顾",
      prompt: "你觉得这次练习和上一次相比，有什么新的收获或困惑？",
      hint: "思考你做对的题是靠理解还是记忆，做错的题反映了什么盲区",
    },
    node_mastered: {
      icon: <Award size={16} />,
      title: "知识巩固",
      prompt: `试着把这个概念讲给一个完全不懂的人听。你会怎么解释 "${relatedNodes[0] || '这个概念'}"？`,
      hint: "用最简单的语言、生活中的类比，检查自己是否真的理解了本质",
    },
    cognitive_conflict: {
      icon: <Lightbulb size={16} />,
      title: "认知突破",
      prompt: "你之前的理解和现在学到的新知识似乎有冲突。能说说你的想法发生了什么变化吗？",
      hint: "新旧知识的矛盾点是什么？是什么让你改变了看法？",
    },
    weekly_review: {
      icon: <Sparkles size={16} />,
      title: "周回顾",
      prompt: "这周你攻克的最大难题是什么？哪一刻你感觉自己「顿悟」了？",
      hint: "回顾这一周的学习过程，有什么可以保持的做法，有什么需要调整的",
    },
  };

  const config = guideConfig[trigger];

  const getSentiment = (): "positive" | "neutral" | "negative" => {
    const positiveWords = ["懂了", "理解", "突破", "进步", "简单", "容易", "好", "开心", "有帮助"];
    const negativeWords = ["难", "不懂", "困惑", "迷茫", "复杂", "失败", "挫败", "没"];
    const hasPositive = positiveWords.some((w) => content.includes(w));
    const hasNegative = negativeWords.some((w) => content.includes(w));
    if (hasPositive && !hasNegative) return "positive";
    if (hasNegative && !hasPositive) return "negative";
    return "neutral";
  };

  const handleSave = () => {
    if (!content.trim()) return;
    onSave({
      content: content.trim(),
      trigger,
      relatedNodes,
      sentiment: getSentiment(),
    });
    setStep("done");
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="w-full max-w-xl mx-4 bg-surface border border rounded-xl shadow-xl overflow-hidden">
        {/* ----- Step: Guidance intro ----- */}
        {step === "guide" && (
          <>
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center text-accent">
                  {config.icon}
                </div>
                <div>
                  <span className="text-sm font-semibold text">
                    {config.title}
                  </span>
                  <span className="text-[10px] text-muted block">
                    结构化反思练习
                  </span>
                </div>
              </div>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg hover:bg-surface-hover text-muted transition-colors"
              >
                <X size={14} />
              </button>
            </div>

            {/* Guidance */}
            <div className="px-5 py-5">
              <div className="flex items-start gap-3 p-4 rounded-xl bg-accent/5 border border-accent/10">
                <Brain size={20} className="text-accent flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm text font-medium leading-relaxed">
                    {config.prompt}
                  </p>
                  {context && (
                    <p className="text-xs text-muted mt-2 italic">
                      {context}
                    </p>
                  )}
                </div>
              </div>

              {/* Hints */}
              <div className="mt-4 flex items-start gap-2 text-[11px] text-muted">
                <Lightbulb size={12} className="flex-shrink-0 mt-0.5" />
                <span>{config.hint}</span>
              </div>

              {/* Related nodes */}
              {relatedNodes.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {relatedNodes.map((n, i) => (
                    <span
                      key={i}
                      className="text-[10px] px-2 py-0.5 rounded-full bg-surface-hover text-muted border border/50"
                    >
                      {n}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border">
              <button
                onClick={onClose}
                className="px-3 py-1.5 rounded-lg text-xs text-muted hover:bg-surface-hover transition-colors"
              >
                跳过
              </button>
              <button
                onClick={() => setStep("input")}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-medium bg-accent text-white hover:opacity-90 transition-opacity"
              >
                开始反思
                <Send size={12} />
              </button>
            </div>
          </>
        )}

        {/* ----- Step: Writing input ----- */}
        {step === "input" && (
          <>
            <div className="flex items-center justify-between px-5 py-4 border-b border">
              <div className="flex items-center gap-2">
                {config.icon}
                <span className="text-sm font-semibold">{config.title}</span>
              </div>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg hover:bg-surface-hover text-muted transition-colors"
              >
                <X size={14} />
              </button>
            </div>

            <div className="px-5 py-4">
              <p className="text-xs text-accent mb-3 font-medium leading-relaxed">
                {config.prompt}
              </p>

              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="在这里写下你的反思..."
                className="w-full h-40 px-4 py-3 text-sm rounded-xl border border bg-page resize-none focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20 transition-colors leading-relaxed"
                autoFocus
              />

              {/* Sentiment indicator */}
              {content.length > 5 && (
                <div className="mt-2 flex items-center gap-1.5 text-[10px] text-muted">
                  <span>情绪倾向：</span>
                  <span
                    className={`px-1.5 py-0.5 rounded ${
                      getSentiment() === "positive"
                        ? "bg-success/10 text-success"
                        : getSentiment() === "negative"
                          ? "bg-error/10 text-error"
                          : "bg-surface-hover text-muted"
                    }`}
                  >
                    {getSentiment() === "positive"
                      ? "😊 积极"
                      : getSentiment() === "negative"
                        ? "😟 困惑"
                        : "😐 中性"}
                  </span>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between px-5 py-4 border-t border">
              <button
                onClick={() => setStep("guide")}
                className="text-[11px] text-muted hover:text transition-colors"
              >
                ← 返回引导
              </button>
              <div className="flex items-center gap-2">
                <button
                  onClick={onClose}
                  className="px-3 py-1.5 rounded-lg text-xs text-muted hover:bg-surface-hover transition-colors"
                >
                  稍后再说
                </button>
                <button
                  onClick={handleSave}
                  disabled={!content.trim()}
                  className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-medium bg-accent text-white hover:opacity-90 disabled:opacity-40 transition-opacity"
                >
                  <Brain size={12} />
                  保存反思
                </button>
              </div>
            </div>
          </>
        )}

        {/* ----- Step: Done ----- */}
        {step === "done" && (
          <div className="flex flex-col items-center py-10 px-5">
            <div className="w-14 h-14 rounded-full bg-success/10 flex items-center justify-center mb-4">
              <Brain size={28} className="text-success" />
            </div>
            <p className="text-base font-semibold text">
              反思已记录
            </p>
            <p className="text-xs text-muted mt-1 text-center max-w-xs">
              你的反思已关联到知识点。系统会在适当的时候提醒你回顾。
            </p>
            <button
              onClick={onClose}
              className="mt-6 px-5 py-2 rounded-lg text-xs font-medium bg-accent text-white hover:opacity-90 transition-opacity"
            >
              完成
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
