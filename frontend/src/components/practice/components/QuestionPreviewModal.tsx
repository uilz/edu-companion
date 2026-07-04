"use client";

import { X, Check, Eye, Edit3 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
// katex/dist/katex.min.css 已在 app/globals.css 统一 import
import type { V7Question } from "@/lib/api/practice-api";
import QuestionStem from "@/components/practice/components/QuestionStem";

const TYPE_LABELS: Record<string, string> = {
  single: "单选", multiple: "多选", judge: "判断",
  choice: "单选", fill: "填空", free_form: "简答", essay: "简答",
};
const TYPE_COLORS: Record<string, string> = {
  single: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  multiple: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
  judge: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  choice: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  fill: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  free_form: "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
  essay: "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
};

interface Props {
  question: V7Question;
  onClose: () => void;
  onEdit: () => void;
}

/** 题目预览弹窗 */
export default function QuestionPreviewModal({ question, onClose, onEdit }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onClose}>
      <div className="w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl bg-[var(--color-bg)] border border-[var(--color-border)] shadow-xl p-6 space-y-4" onClick={e => e.stopPropagation()}>
        {/* 头部 */}
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-blue-500 flex items-center gap-2">
            <Eye size={15} />题目预览
          </h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-[var(--color-surface)] text-[var(--color-text-muted)]">
            <X size={16} />
          </button>
        </div>

        {/* 标签 */}
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${TYPE_COLORS[question.question_type] || ""}`}>
            {TYPE_LABELS[question.question_type] || question.question_type}
          </span>
          <span className="text-xs text-[var(--color-text-muted)]">难度 {"★".repeat(question.difficulty).padEnd(5, "☆")}</span>
        </div>

        {/* 题干 */}
        <div className="p-4 rounded-xl bg-[var(--color-surface)]">
          <QuestionStem stem={question.stem} className="text-base leading-relaxed" />
        </div>

        {/* 选项 */}
        {(question.options || []).length > 0 && (
          <div className="space-y-2">
            <label className="text-xs text-[var(--color-text-muted)]">选项</label>
            {question.options.map((opt: any) => (
              <div key={opt.letter} className={`flex items-center gap-2 px-4 py-3 rounded-xl border ${
                opt.is_correct ? "border-green-300 dark:border-green-700 bg-green-50 dark:bg-green-900/10" : "border-[var(--color-border)]"
              }`}>
                <span className="font-medium mr-2 text-sm">{opt.letter}.</span>
                <span className="text-sm [&_p]:m-0 [&_.katex]:text-sm">
                  <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]} components={{ p: ({ children }) => <>{children}</> }}>
                    {opt.text}
                  </ReactMarkdown>
                </span>
                {opt.is_correct && <Check size={14} className="ml-auto text-green-500" />}
              </div>
            ))}
          </div>
        )}

        {/* 解析 */}
        {(question as any).analysis && (
          <div>
            <label className="text-xs text-[var(--color-text-muted)] block mb-1">解析</label>
            <div className="text-sm text-[var(--color-text-muted)] bg-[var(--color-surface)] p-3 rounded-xl [&_p]:m-0 [&_.katex]:text-xs">
            <QuestionStem stem={(question as any).analysis || ""} />
          </div>
          </div>
        )}

        {/* 操作 */}
        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose}
            className="px-4 py-2 rounded-lg border border-[var(--color-border)] text-sm text-[var(--color-text-muted)]">
            关闭
          </button>
          <button onClick={onEdit}
            className="px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white text-sm hover:opacity-90 flex items-center gap-1.5">
            <Edit3 size={14} />编辑此题
          </button>
        </div>
      </div>
    </div>
  );
}
