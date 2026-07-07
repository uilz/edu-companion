"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Check, Save } from "lucide-react";
import type { PreviewQuestion } from "./types";

// ── Zod schema ──

const editQuestionSchema = z.object({
  stem: z.string().min(1, "请输入题干"),
  question_type: z.enum(["single", "multiple", "judge", "fill", "essay"]),
  options: z
    .array(
      z.object({
        label: z.string(),
        content: z.string(),
        is_correct: z.boolean().optional(),
      }),
    )
    .optional(),
  answer: z.string(),
  analysis: z.string(),
});

type EditQuestionFormData = z.infer<typeof editQuestionSchema>;

const TYPE_OPTIONS = [
  { value: "single", label: "单选" },
  { value: "multiple", label: "多选" },
  { value: "judge", label: "判断" },
  { value: "fill", label: "填空" },
  { value: "essay", label: "简答" },
] as const;

// ── Component ──

export default function EditCard({
  form,
  onSave,
  onCancel,
}: {
  form: PreviewQuestion;
  onSave: (data: PreviewQuestion) => void;
  onCancel: () => void;
}) {
  const {
    register,
    handleSubmit,
    setValue,
    getValues,
    watch,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<EditQuestionFormData>({
    resolver: zodResolver(editQuestionSchema),
    defaultValues: {
      stem: form.stem,
      question_type: form.question_type as EditQuestionFormData["question_type"],
      options: form.options,
      answer: form.answer,
      analysis: form.analysis || "",
    },
  });

  // Reset form when the form prop changes (editing a different question)
  useEffect(() => {
    reset({
      stem: form.stem,
      question_type: form.question_type as EditQuestionFormData["question_type"],
      options: form.options,
      answer: form.answer,
      analysis: form.analysis || "",
    });
  }, [form, reset]);

  const currentType = watch("question_type");
  const currentOptions = watch("options");

  const toggleOptionCorrect = (oi: number) => {
    const opts = getValues("options");
    if (!opts) return;
    const updated = [...opts];
    updated[oi] = { ...updated[oi], is_correct: !updated[oi].is_correct };
    // 单选时只能有一个正确
    if (currentType === "single" && updated[oi].is_correct) {
      for (let i = 0; i < updated.length; i++) {
        if (i !== oi) updated[i] = { ...updated[i], is_correct: false };
      }
    }
    // 自动更新答案
    const correctLetters = updated
      .filter((o) => o.is_correct)
      .map((o) => o.label);
    setValue("options", updated);
    setValue("answer", correctLetters.join(""));
  };

  const onSubmit = (data: EditQuestionFormData) => {
    onSave({
      stem: data.stem,
      question_type: data.question_type,
      options: data.options,
      answer: data.answer,
      analysis: data.analysis || "",
      confidence: form.confidence,
      suggested_node_ids: form.suggested_node_ids,
      ai_corrected: form.ai_corrected,
      source_line: form.source_line,
    });
  };

  return (
    <div className="p-4 rounded-xl border-2 border-info/40 bg-info/[0.02] space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-medium text-info">编辑模式</span>
        <div className="flex gap-1.5">
          <button
            onClick={handleSubmit(onSubmit) as unknown as React.MouseEventHandler}
            disabled={isSubmitting}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-info text-white text-[10px] font-medium hover:opacity-90 disabled:opacity-50"
          >
            <Save size={10} /> {isSubmitting ? "保存中..." : "保存"}
          </button>
          <button
            onClick={onCancel}
            className="px-2.5 py-1.5 rounded-lg border border/50 text-[10px] text-muted hover:text"
          >
            取消
          </button>
        </div>
      </div>

      {/* 题型选择 */}
      <div className="flex gap-2">
        {TYPE_OPTIONS.map((t) => (
          <button
            key={t.value}
            type="button"
            onClick={() => setValue("question_type", t.value)}
            className={`px-2.5 py-1 rounded-lg text-[10px] font-medium border transition-all ${
              currentType === t.value
                ? "border-info/40 bg-info/10 text-info"
                : "border/50 text-muted"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* 题干 */}
      <div>
        <label className="text-[9px] text-muted mb-1 block">
          题干
        </label>
        <textarea
          {...register("stem")}
          className="w-full p-2 rounded-lg border border/60 bg-surface text-[12px] text resize-none h-16 focus:outline-none focus:border-info/40"
        />
        {errors.stem && (
          <p className="text-[9px] text-danger mt-0.5">{errors.stem.message}</p>
        )}
      </div>

      {/* 选项 */}
      {currentOptions && currentOptions.length > 0 && (
        <div>
          <label className="text-[9px] text-muted mb-1 block">
            选项（点击标签切换是否正确）
          </label>
          <div className="grid grid-cols-1 gap-1.5">
            {currentOptions.map((opt, oi) => (
              <div key={oi} className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => toggleOptionCorrect(oi)}
                  className={`w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold border shrink-0 ${
                    opt.is_correct
                      ? "bg-success text-white border-success"
                      : "bg-surface text-muted border/50"
                  }`}
                >
                  {opt.is_correct ? <Check size={8} /> : opt.label}
                </button>
                <input
                  {...register(`options.${oi}.content`)}
                  className="flex-1 p-1.5 rounded-lg border border/60 bg-surface text-[11px] text focus:outline-none focus:border-info/40"
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 答案 */}
      <div>
        <label className="text-[9px] text-muted mb-1 block">
          答案
        </label>
        <input
          {...register("answer")}
          className="w-full p-2 rounded-lg border border/60 bg-surface text-[12px] text focus:outline-none focus:border-info/40"
        />
      </div>

      {/* 解析 */}
      <div>
        <label className="text-[9px] text-muted mb-1 block">
          解析
        </label>
        <textarea
          {...register("analysis")}
          className="w-full p-2 rounded-lg border border/60 bg-surface text-[12px] text resize-none h-14 focus:outline-none focus:border-info/40"
        />
      </div>
    </div>
  );
}