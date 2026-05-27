// 知识拓展面板 — 智能创造扩展
//
// 显示:
// - 深入解释（比喻）
// - 前置知识链
// - 进阶方向
// - 真实案例
// - 常见误区
// - 冷知识
// - 变式题按钮

"use client";

import { useState, useEffect } from "react";
import {
  Lightbulb, Network, ArrowRight, AlertTriangle,
  Sparkles, Beaker, Loader2, BookOpen,
} from "lucide-react";
import Card from "@/components/ui/Card";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface KnowledgeExpansion {
  skill_name: string;
  deeper_explanation: string;
  prerequisite_chain: string[];
  next_steps: string[];
  real_world_example: string;
  common_misconception: string;
  fun_fact: string;
}

interface VariantQuestion {
  question: string;
  options: string[];
  correct: number;
  explanation: string;
}

export default function ExpandPanel({
  skillName,
  explanation,
  onClose,
}: {
  skillName: string;
  explanation?: string;
  onClose?: () => void;
}) {
  const [expansion, setExpansion] = useState<KnowledgeExpansion | null>(null);
  const [variant, setVariant] = useState<VariantQuestion | null>(null);
  const [loading, setLoading] = useState(false);
  const [variantLoading, setVariantLoading] = useState(false);
  const [showVariant, setShowVariant] = useState(false);

  // 加载拓展
  const loadExpansion = async () => {
    if (expansion) return; // 已加载
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v2/expand/knowledge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ skill_name: skillName, explanation: explanation || "" }),
      });
      if (res.ok) {
        setExpansion(await res.json());
      }
    } catch {
      // 静默失败
    }
    setLoading(false);
  };

  // 生成变式题
  const loadVariant = async () => {
    setVariantLoading(true);
    setShowVariant(true);
    try {
      const res = await fetch(`${API_BASE}/api/v2/expand/variant`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question_text: skillName,
          correct_answer: explanation || skillName,
        }),
      });
      if (res.ok) {
        setVariant(await res.json());
      }
    } catch {
      // 静默失败
    }
    setVariantLoading(false);
  };

  // 自动加载（组件首次渲染时触发）
  useEffect(() => { loadExpansion(); }, []);

  if (loading) {
    return (
      <Card title="✨ 智能拓展" className="relative">
        <div className="flex items-center justify-center py-6">
          <Loader2 className="animate-spin text-[var(--color-accent)]" size={18} />
        </div>
      </Card>
    );
  }

  if (!expansion) return null;

  return (
    <Card title={`智能拓展: ${expansion.skill_name}`}
      className="relative"
    >
      {/* 关闭按钮 */}
      {onClose && (
        <button
          onClick={onClose}
          className="absolute top-3 right-3 text-[var(--color-text-tertiary)] hover:text-[var(--color-text)] text-xs"
        >
          关闭
        </button>
      )}

      <div className="space-y-3 text-sm">
        {/* 深入解释 */}
        <div className="flex items-start gap-2">
          <Lightbulb size={14} className="mt-0.5 shrink-0 text-[#f59e0b]" />
          <div>
            <div className="text-[11px] font-medium text-[var(--color-text-tertiary)] uppercase tracking-wide mb-0.5">
              深入理解
            </div>
            <p className="text-[var(--color-text-secondary)] leading-relaxed">
              {expansion.deeper_explanation}
            </p>
          </div>
        </div>

        {/* 前置知识链 */}
        {expansion.prerequisite_chain.length > 0 && (
          <div className="flex items-start gap-2">
            <Network size={14} className="mt-0.5 shrink-0 text-[#3b82f6]" />
            <div>
              <div className="text-[11px] font-medium text-[var(--color-text-tertiary)] uppercase tracking-wide mb-0.5">
                前置知识
              </div>
              <div className="flex flex-wrap gap-1">
                {expansion.prerequisite_chain.map((p, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-0.5 text-[11px] px-1.5 py-0.5 rounded bg-[var(--color-accent-subtle)] text-[var(--color-accent)]"
                  >
                    {p}
                    {i < expansion.prerequisite_chain.length - 1 && (
                      <ArrowRight size={10} />
                    )}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* 进阶方向 */}
        {expansion.next_steps.length > 0 && (
          <div className="flex items-start gap-2">
            <ArrowRight size={14} className="mt-0.5 shrink-0 text-[#22c55e]" />
            <div>
              <div className="text-[11px] font-medium text-[var(--color-text-tertiary)] uppercase tracking-wide mb-0.5">
                可以继续学
              </div>
              <div className="flex flex-wrap gap-1">
                {expansion.next_steps.map((n, i) => (
                  <span
                    key={i}
                    className="text-[11px] px-1.5 py-0.5 rounded bg-[var(--color-accent-subtle)] text-[var(--color-accent)]"
                  >
                    {n}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* 双栏：案例 + 误区 */}
        <div className="grid grid-cols-2 gap-2">
          {expansion.real_world_example && (
            <div className="flex items-start gap-1.5 p-2 rounded bg-[var(--color-bg-subtle)]">
              <Beaker size={12} className="mt-0.5 shrink-0 text-[#06b6d4]" />
              <div>
                <div className="text-[10px] font-medium text-[var(--color-text-tertiary)] mb-0.5">
                  真实案例
                </div>
                <p className="text-[11px] text-[var(--color-text-secondary)] leading-relaxed">
                  {expansion.real_world_example}
                </p>
              </div>
            </div>
          )}
          {expansion.common_misconception && (
            <div className="flex items-start gap-1.5 p-2 rounded bg-[var(--color-bg-subtle)]">
              <AlertTriangle size={12} className="mt-0.5 shrink-0 text-[#f97316]" />
              <div>
                <div className="text-[10px] font-medium text-[var(--color-text-tertiary)] mb-0.5">
                  常见误区
                </div>
                <p className="text-[11px] text-[var(--color-text-secondary)] leading-relaxed">
                  {expansion.common_misconception}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* 冷知识 */}
        {expansion.fun_fact && (
          <div className="flex items-start gap-2 p-2 rounded bg-[var(--color-accent-subtle)]">
            <Sparkles size={12} className="mt-0.5 shrink-0 text-[#f59e0b]" />
            <p className="text-[11px] text-[var(--color-text-secondary)] leading-relaxed">
              💡 {expansion.fun_fact}
            </p>
          </div>
        )}

        {/* 变式题按钮 */}
        <button
          onClick={loadVariant}
          disabled={variantLoading}
          className="w-full flex items-center justify-center gap-1.5 text-xs py-2 rounded bg-[var(--color-accent-subtle)] text-[var(--color-accent)] hover:brightness-110 transition-all disabled:opacity-50"
        >
          {variantLoading ? (
            <Loader2 size={12} className="animate-spin" />
          ) : (
            <BookOpen size={12} />
          )}
          {variantLoading ? "生成中..." : "📝 出一道变式题"}
        </button>

        {/* 变式题结果 */}
        {showVariant && variant && (
          <div className="space-y-2 p-3 rounded border border-[var(--color-border)] mt-1">
            <p className="text-sm font-medium text-[var(--color-text)]">
              {variant.question}
            </p>
            <div className="space-y-1">
              {variant.options.map((opt, i) => (
                <div
                  key={i}
                  className={`text-xs p-2 rounded cursor-pointer transition-all ${
                    i === variant.correct
                      ? "bg-green-500/10 border border-green-500/30 text-green-600"
                      : "bg-[var(--color-bg-subtle)] text-[var(--color-text-secondary)]"
                  }`}
                >
                  {opt}
                </div>
              ))}
            </div>
            <p className="text-[11px] text-[var(--color-text-tertiary)] leading-relaxed">
              💡 {variant.explanation}
            </p>
          </div>
        )}
      </div>
    </Card>
  );
}
