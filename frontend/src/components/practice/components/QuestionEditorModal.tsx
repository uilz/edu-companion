"use client";

import { useState } from "react";
import { X, Check, Plus, Save } from "lucide-react";
import type { V7Option } from "@/lib/api/practice-api";

export interface EditableQuestion {
  id: string;
  stem: string;
  question_type: string;
  options: V7Option[];
  answer: string[];
  analysis: string;
  difficulty: number;
}

interface Props {
  question: EditableQuestion;
  isNew: boolean;
  onSave: (q: EditableQuestion) => void;
  onClose: () => void;
}

/** 题目编辑弹窗 — 浮层覆盖，不推内容 */
export default function QuestionEditorModal({ question: initial, isNew, onSave, onClose }: Props) {
  const [q, setQ] = useState<EditableQuestion>(initial);
  const isOption = q.question_type === "single" || q.question_type === "multiple" || q.question_type === "judge" || q.question_type === "choice";

  const updateOpt = (letter: string, field: "text" | "is_correct", value: string | boolean) => {
    setQ({
      ...q,
      options: q.options.map(o => o.letter === letter ? { ...o, [field]: value } : o),
    });
  };

  const addOption = () => {
    const nl = String.fromCharCode(65 + q.options.length);
    setQ({ ...q, options: [...q.options, { letter: nl, text: "", is_correct: false }] });
  };

  const removeOption = (letter: string) => {
    if (q.options.length <= 2) return;
    setQ({ ...q, options: q.options.filter(o => o.letter !== letter) });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onClose}>
      <div className="w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl bg-[var(--color-bg)] border border-[var(--color-border)] shadow-xl p-6 space-y-4" onClick={e => e.stopPropagation()}>
        {/* 头部 */}
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-[var(--color-accent)]">
            {isNew ? "添加新题目" : "编辑题目"}
          </h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-[var(--color-surface)] text-[var(--color-text-muted)]">
            <X size={16} />
          </button>
        </div>

        {/* 题型 + 难度 */}
        <div className="flex gap-3">
          <select value={q.question_type} onChange={e => setQ({ ...q, question_type: e.target.value })}
            className="px-3 py-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm">
            <option value="single">单选</option>
            <option value="multiple">多选</option>
            <option value="judge">判断</option>
            <option value="choice">单选(兼容)</option>
            <option value="fill">填空</option>
            <option value="free_form">简答</option>
          </select>
          <select value={q.difficulty} onChange={e => setQ({ ...q, difficulty: Number(e.target.value) })}
            className="px-3 py-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm">
            {[1, 2, 3, 4, 5].map(d => (
              <option key={d} value={d}>{"★".repeat(d).padEnd(5, "☆")}</option>
            ))}
          </select>
        </div>

        {/* 题干 */}
        <textarea value={q.stem} onChange={e => setQ({ ...q, stem: e.target.value })}
          placeholder="题干（支持 Markdown + LaTeX）..." rows={3}
          className="w-full px-4 py-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)] resize-none text-sm" />

        {/* 选项 */}
        {isOption && (
          <div className="space-y-2">
            <label className="text-xs text-[var(--color-text-muted)]">选项（点击右侧✓标记正确答案）</label>
            {q.options.map(opt => (
              <div key={opt.letter} className="flex items-center gap-2">
                <span className="shrink-0 w-7 text-center text-sm font-bold text-[var(--color-text-muted)]">{opt.letter}.</span>
                <input value={opt.text} onChange={e => updateOpt(opt.letter, "text", e.target.value)}
                  placeholder={`选项 ${opt.letter}`}
                  className="flex-1 px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm" />
                <button onClick={() => updateOpt(opt.letter, "is_correct", !opt.is_correct)}
                  className={`p-1.5 rounded-lg border transition-colors ${
                    opt.is_correct ? "border-green-400 bg-green-50 dark:bg-green-900/20 text-green-600" : "border-[var(--color-border)] text-[var(--color-text-muted)]"
                  }`}>
                  <Check size={14} />
                </button>
                <button onClick={() => removeOption(opt.letter)} className="p-1.5 rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-red-500">
                  <X size={12} />
                </button>
              </div>
            ))}
            <button onClick={addOption}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-dashed border-[var(--color-border)] text-xs text-[var(--color-text-muted)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]">
              <Plus size={12} />添加选项
            </button>
          </div>
        )}

        {/* 填空/简答答案 */}
        {(q.question_type === "fill" || q.question_type === "free_form") && (
          <div>
            <label className="text-xs text-[var(--color-text-muted)] block mb-1">参考答案</label>
            <input value={q.answer[0] || ""} onChange={e => setQ({ ...q, answer: [e.target.value] })}
              placeholder="输入参考答案..."
              className="w-full px-4 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm" />
          </div>
        )}

        {/* 解析 */}
        <textarea value={q.analysis} onChange={e => setQ({ ...q, analysis: e.target.value })}
          placeholder="题目解析（可选）..." rows={2}
          className="w-full px-4 py-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)] resize-none text-sm" />

        {/* 保存 */}
        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose}
            className="px-4 py-2 rounded-lg border border-[var(--color-border)] text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            取消
          </button>
          <button onClick={() => onSave(q)} disabled={!q.stem.trim()}
            className="px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white text-sm hover:opacity-90 disabled:opacity-30 flex items-center gap-1.5">
            <Save size={14} />保存题目
          </button>
        </div>
      </div>
    </div>
  );
}
