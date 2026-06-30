"use client";

import React, { useState, useCallback } from "react";
import { Pencil, Check, X, Loader2, ChevronDown, Lightbulb, GitCompare, MessageSquare } from "lucide-react";
import { submitSelfExplain } from "@/lib/api/practice-api";
import type { SelfExplainResult, SelfExplainPromptType } from "@/types";

// ── 提示类型配置 ──

interface PromptConfig {
  icon: React.ReactNode;
  label: string;
  question: (concept: string) => string;
  description: string;
}

const PROMPT_CONFIGS: Record<SelfExplainPromptType, PromptConfig> = {
  retell: {
    icon: <MessageSquare size={14} />,
    label: "复述型",
    description: "用自己的话解释概念",
    question: (c) => `你能用你自己的话解释一下「${c}」是什么吗？`,
  },
  example: {
    icon: <Lightbulb size={14} />,
    label: "举例型",
    description: "举一个生活中的例子",
    question: (c) => `你能举一个生活中用到「${c}」的例子吗？`,
  },
  contrast: {
    icon: <GitCompare size={14} />,
    label: "对比型",
    description: "找出本质区别",
    question: (c) => `你觉得「${c}」和相关概念有什么本质区别？`,
  },
};

// ── 评估结果颜色 ──

const ACCURACY_COLORS: Record<string, string> = {
  A: "text-emerald-600 bg-emerald-50 border-emerald-200",
  B: "text-amber-600 bg-amber-50 border-amber-200",
  C: "text-red-600 bg-red-50 border-red-200",
};

const COMPLETENESS_COLORS: Record<string, string> = {
  "完整": "text-emerald-600",
  "部分": "text-amber-600",
  "缺失核心": "text-red-600",
};

const CLARITY_COLORS: Record<string, string> = {
  "清晰": "text-emerald-600",
  "模糊": "text-amber-600",
  "混乱": "text-red-600",
};

// ── Props ──

interface SelfExplainCardProps {
  knowledgeNodeId: string;
  messageId: string;
  conceptName?: string;
}

// ── Component ──

export default function SelfExplainCard({
  knowledgeNodeId,
  messageId,
  conceptName,
}: SelfExplainCardProps) {
  const displayConcept = conceptName || knowledgeNodeId;
  const [promptType, setPromptType] = useState<SelfExplainPromptType>("retell");
  const [explanation, setExplanation] = useState("");
  const [result, setResult] = useState<SelfExplainResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [skipped, setSkipped] = useState(false);
  const [showTypePicker, setShowTypePicker] = useState(false);

  const config = PROMPT_CONFIGS[promptType];

  const handleSubmit = useCallback(async () => {
    if (!explanation.trim() || loading) return;
    setLoading(true);
    try {
      const res = await submitSelfExplain({
        explanation_text: explanation.trim(),
        knowledge_node_id: knowledgeNodeId,
        prompt_type: promptType,
      });
      setResult(res);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [explanation, knowledgeNodeId, promptType, loading]);

  const handleSkip = useCallback(() => {
    setSkipped(true);
  }, []);

  const handleRetry = useCallback(() => {
    setExplanation("");
    setResult(null);
    setSkipped(false);
  }, []);

  // 已跳过
  if (skipped) {
    return (
      <div className="mt-3 border border-dashed border-[var(--color-border)] rounded-xl px-4 py-3 bg-[var(--color-surface)]/50">
        <div className="flex items-center justify-between">
          <span className="text-xs text-[var(--color-text-muted)]">✍️ 自我解释已跳过</span>
          <button
            onClick={handleRetry}
            className="text-xs text-[var(--color-info)] hover:underline"
          >
            再试一次
          </button>
        </div>
      </div>
    );
  }

  // 已有评估结果
  if (result) {
    return (
      <div className="mt-3 border border-[var(--color-border)] rounded-xl px-4 py-3 bg-[var(--color-surface)]/50 space-y-2.5">
        {/* 标题行 */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-[var(--color-text)]">✍️ 自我解释评估</span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded-full border font-medium ${ACCURACY_COLORS[result.accuracy] || ACCURACY_COLORS.B}`}>
            {result.accuracy === "A" ? "✓ 准确" : result.accuracy === "B" ? "~ 部分准确" : "✗ 有误"}
          </span>
        </div>

        {/* 你的解释 */}
        <div className="text-xs text-[var(--color-text-secondary)] leading-relaxed bg-[var(--color-surface-hover)] rounded-lg px-3 py-2 max-h-20 overflow-y-auto">
          {explanation}
        </div>

        {/* 三维度评估 */}
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
          <span className="text-[var(--color-text-muted)]">
            完整性：<span className={COMPLETENESS_COLORS[result.completeness] || ""}>{result.completeness}</span>
          </span>
          <span className="text-[var(--color-text-muted)]">
            清晰度：<span className={CLARITY_COLORS[result.clarity] || ""}>{result.clarity}</span>
          </span>
        </div>

        {/* 反馈 */}
        <div className="text-xs text-[var(--color-text-secondary)] leading-relaxed border-l-2 border-[var(--color-accent)] pl-2.5 py-0.5">
          {result.feedback}
        </div>

        {/* 再试一次 */}
        <button
          onClick={handleRetry}
          className="text-[10px] text-[var(--color-info)] hover:underline"
        >
          再试一次
        </button>
      </div>
    );
  }

  // 输入状态
  return (
    <div className="mt-3 border border-[var(--color-border)] rounded-xl px-4 py-3 bg-[var(--color-surface)]/50 space-y-3">
      {/* 标题行 + 类型选择器 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-semibold text-[var(--color-text)]">✍️ 用自己的话解释</span>
        </div>
        <div className="relative">
          <button
            onClick={() => setShowTypePicker(!showTypePicker)}
            className="flex items-center gap-1 text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] px-2 py-1 rounded bg-[var(--color-surface-hover)] border border-[var(--color-border)] transition-colors"
          >
            {config.icon}
            {config.label}
            <ChevronDown size={10} />
          </button>
          {showTypePicker && (
            <div className="absolute right-0 top-full mt-1 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-lg p-1 z-20 min-w-[120px]">
              {(Object.entries(PROMPT_CONFIGS) as [SelfExplainPromptType, PromptConfig][]).map(
                ([type, cfg]) => (
                  <button
                    key={type}
                    onClick={() => {
                      setPromptType(type);
                      setShowTypePicker(false);
                    }}
                    className={`flex items-center gap-2 w-full text-left px-2.5 py-1.5 rounded text-[11px] transition-colors ${
                      type === promptType
                        ? "bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                        : "text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]"
                    }`}
                  >
                    {cfg.icon}
                    <div>
                      <div className="text-[11px] font-medium">{cfg.label}</div>
                      <div className="text-[9px] text-[var(--color-text-muted)]">{cfg.description}</div>
                    </div>
                  </button>
                )
              )}
            </div>
          )}
        </div>
      </div>

      {/* 提示问题 */}
      <div className="text-xs text-[var(--color-text-secondary)] leading-relaxed italic">
        {config.question(displayConcept)}
      </div>

      {/* 输入区域 */}
      <textarea
        value={explanation}
        onChange={(e) => setExplanation(e.target.value)}
        placeholder="输入你的解释..."
        rows={3}
        className="w-full resize-none rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)] focus:border-[var(--color-accent)]"
      />

      {/* 操作按钮 */}
      <div className="flex items-center gap-2">
        <button
          onClick={handleSubmit}
          disabled={!explanation.trim() || loading}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
            explanation.trim() && !loading
              ? "bg-[var(--color-accent)] text-white hover:opacity-90"
              : "bg-[var(--color-border)] text-[var(--color-text-muted)] cursor-not-allowed"
          }`}
        >
          {loading ? (
            <Loader2 size={12} className="animate-spin" />
          ) : (
            <Check size={12} />
          )}
          提交解释
        </button>
        <button
          onClick={handleSkip}
          disabled={loading}
          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
        >
          <X size={12} />
          跳过
        </button>
      </div>
    </div>
  );
}
