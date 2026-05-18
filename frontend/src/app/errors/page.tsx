"use client";

import { useState, useEffect } from "react";
import { RotateCcw, CheckCircle, XCircle, Loader2, BookOpen } from "lucide-react";
import Card from "@/components/ui/Card";
import MathContent from "@/components/ui/MathContent";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ErrorEntry {
  entry_id: string;
  question_id: string;
  skill_id: string;
  error_type: string;
  misconception?: string;
  user_answer: string;
  correct_answer: string;
  question_text: string;
  review_count: number;
  is_resolved: boolean;
  created_at: string;
  referenced_materials: Array<{
    source_file: string;
    page_number?: number;
    preview: string;
  }>;
}

export default function ErrorBookPage() {
  const [entries, setEntries] = useState<ErrorEntry[]>([]);
  const [filter, setFilter] = useState<"pending" | "resolved" | "all">("pending");
  const [loading, setLoading] = useState(true);

  const fetchErrors = async (status: string) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (status === "pending") params.set("resolved", "false");
      else if (status === "resolved") params.set("resolved", "true");

      const res = await fetch(`${API_BASE}/api/practice/errors?${params}`);
      const data = await res.json();
      setEntries(data.entries || []);
    } catch (err) {
      console.error("Failed to fetch errors:", err);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchErrors(filter);
  }, [filter]);

  const markResolved = async (entryId: string) => {
    await fetch(`${API_BASE}/api/practice/errors/${entryId}/review?is_correct=true`, {
      method: "POST",
    });
    fetchErrors(filter);
  };

  const errorLabel: Record<string, string> = {
    conceptual: "概念错误",
    procedural: "程序错误",
    computation: "计算错误",
    reading: "审题错误",
    transfer: "迁移错误",
    meta: "元认知错误",
    careless: "粗心大意",
  };

  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-3xl mx-auto px-6 py-16">
        <div className="flex items-center justify-between mb-12">
          <h1 className="text-4xl font-bold tracking-tight text-[var(--color-text)]">
            <BookOpen size={28} className="inline mr-3 text-[var(--color-accent)]" />
            错题本
          </h1>
          <div className="flex gap-1">
            {[
              ["pending", "未解决"],
              ["resolved", "已解决"],
              ["all", "全部"],
            ].map(([k, label]) => (
              <button
                key={k}
                onClick={() => setFilter(k as typeof filter)}
                className={`text-xs px-3 py-1.5 border transition-colors ${
                  filter === k
                    ? "border-[var(--color-accent)] text-[var(--color-accent)] bg-[var(--color-accent)]/10"
                    : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-border-hover)]"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="animate-spin text-[var(--color-accent)]" size={24} />
          </div>
        ) : entries.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-[var(--color-text-muted)] text-lg mb-2">
              {filter === "pending" ? "🎉 没有待解决的错题！" : "暂无错题记录"}
            </p>
            <p className="text-[var(--color-text-muted)] text-sm">
              {filter === "pending" ? "继续保持！" : "去练习页开始做题吧"}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {entries.map((entry) => (
              <Card key={entry.entry_id || Math.random().toString(36)}>
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs px-2 py-0.5 ${
                        entry.is_resolved
                          ? "bg-[var(--color-success)]/10 text-[var(--color-success)]"
                          : "bg-[var(--color-error)]/10 text-[var(--color-error)]"
                      }`}
                    >
                      {errorLabel[entry.error_type] || entry.error_type || "未知错误"}
                    </span>
                    {entry.misconception && (
                      <span className="text-xs text-[var(--color-text-muted)]">
                        {entry.misconception}
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-[var(--color-text-muted)]">
                    {entry.created_at ? new Date(entry.created_at).toLocaleDateString() : ""}
                  </span>
                </div>

                {entry.question_text ? (
                  <p className="text-sm text-[var(--color-text)] mb-3 message-content">
                    {entry.question_text.slice(0, 120)}
                    {entry.question_text.length > 120 && "..."}
                  </p>
                ) : (
                  <p className="text-sm text-[var(--color-text-muted)] mb-3 italic">
                    题目数据丢失 — skill_id: {entry.skill_id || "未知"}
                  </p>
                )}

                <div className="flex items-center gap-4 text-xs mb-3">
                  <span className="text-[var(--color-error)]">
                    ❌ 你的答案：{entry.user_answer}
                  </span>
                  <span className="text-[var(--color-success)]">
                    ✅ 正确答案：{entry.correct_answer}
                  </span>
                  <span className="text-[var(--color-text-muted)]">
                    复习 {entry.review_count} 次
                  </span>
                </div>

                {entry.referenced_materials && entry.referenced_materials.length > 0 && (
                  <div className="mb-3 p-2 bg-[var(--color-surface)] text-xs text-[var(--color-text-muted)]">
                    📚 资料引用：
                    {entry.referenced_materials.map((m, i) => (
                      <span key={i} className="ml-2">
                        {m.source_file}
                        {m.page_number ? ` 第${m.page_number}页` : ""}
                      </span>
                    ))}
                  </div>
                )}

                {!entry.is_resolved && (
                  <button
                    onClick={() => markResolved(entry.entry_id)}
                    className="flex items-center gap-1.5 text-xs text-[var(--color-success)] hover:underline"
                  >
                    <CheckCircle size={12} />
                    标记为已掌握
                  </button>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
