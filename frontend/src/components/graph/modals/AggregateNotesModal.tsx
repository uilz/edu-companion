"use client";

import React, { useState } from "react";
import { FileText, X, Sparkles, Clock, Loader2 } from "lucide-react";
import { aggregateNotes } from "@/lib/api/learning-api";

interface AggregateNotesModalProps {
  open: boolean;
  nodeIds?: string[];
  onClose: () => void;
}

type TimeRange = "week" | "month" | "all";

/**
 * LLM 整理笔记模态框（10.7）
 * 调用后端 LLM 将笔记整理为结构化复习文档。
 */
export default function AggregateNotesModal({
  open,
  nodeIds,
  onClose,
}: AggregateNotesModalProps) {
  const [timeRange, setTimeRange] = useState<TimeRange>("week");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    organized?: string;
    notes?: any[];
    total: number;
    message: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const handleAggregate = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await aggregateNotes({
        node_ids: nodeIds,
        time_range: timeRange,
      });
      setResult(data);
    } catch (e: any) {
      setError(e.message || "整理失败");
    } finally {
      setLoading(false);
    }
  };

  const timeLabels: Record<TimeRange, string> = {
    week: "本周",
    month: "本月",
    all: "全部",
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="w-full max-w-2xl mx-4 max-h-[80vh] flex flex-col bg-surface border border rounded-xl shadow-xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center text-accent">
              <FileText size={16} />
            </div>
            <div>
              <span className="text-sm font-semibold">整理笔记</span>
              <p className="text-[10px] text-muted">
                LLM 将笔记整理为结构化复习文档
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-surface-hover text-muted"
          >
            <X size={14} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {!result && !loading && !error && (
            <div className="space-y-4">
              {/* Time range selector */}
              <div>
                <label className="flex items-center gap-1.5 text-[11px] text-muted mb-2">
                  <Clock size={11} />
                  时间范围
                </label>
                <div className="flex gap-2">
                  {(["week", "month", "all"] as TimeRange[]).map((t) => (
                    <button
                      key={t}
                      onClick={() => setTimeRange(t)}
                      className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium border transition-all ${
                        timeRange === t
                          ? "border-accent bg-accent/10 text-accent"
                          : "border text-muted hover:border-accent/30"
                      }`}
                    >
                      {timeLabels[t]}
                    </button>
                  ))}
                </div>
              </div>

              {/* Description */}
              <div className="p-4 rounded-xl bg-accent/5 border border-accent/10 text-xs text-muted leading-relaxed">
                <p>
                  LLM 会将你的笔记按知识点分类整理，添加掌握度评价和复习建议，
                  生成一份可以直接用于复习的结构化文档。
                </p>
              </div>

              {/* Generate button */}
              <button
                onClick={handleAggregate}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium bg-accent text-white hover:opacity-90 transition-opacity"
              >
                <Sparkles size={14} />
                AI 一键整理
              </button>
            </div>
          )}

          {/* Loading */}
          {loading && (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2 size={28} className="animate-spin text-accent" />
              <p className="text-xs text-muted mt-3">
                LLM 正在整理笔记...
              </p>
              <p className="text-[10px] text-muted mt-1 opacity-60">
                根据笔记数量，可能需要几秒到十几秒
              </p>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="p-4 rounded-xl bg-error/10 border border-error/20 text-xs text-error">
              {error}
              <button
                onClick={handleAggregate}
                className="block mt-2 text-accent hover:underline"
              >
                重试
              </button>
            </div>
          )}

          {/* Result */}
          {result && !loading && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-muted">
                  基于 {result.total} 条笔记 · {timeLabels[timeRange]}
                </span>
                <button
                  onClick={() => setResult(null)}
                  className="text-[10px] text-accent hover:underline"
                >
                  重新整理
                </button>
              </div>

              {result.organized ? (
                <div className="prose prose-sm max-w-none bg-page rounded-xl border border p-5">
                  <div className="markdown-content text-sm leading-relaxed">
                    {result.organized.split("\n").map((line, i) => {
                      if (line.startsWith("# ")) {
                        return (
                          <h1 key={i} className="text-base font-bold mb-3 mt-0">
                            {line.slice(2)}
                          </h1>
                        );
                      }
                      if (line.startsWith("## ")) {
                        return (
                          <h2
                            key={i}
                            className="text-sm font-semibold mb-2 mt-4 text-accent"
                          >
                            {line.slice(3)}
                          </h2>
                        );
                      }
                      if (line.startsWith("### ")) {
                        return (
                          <h3 key={i} className="text-xs font-medium mb-1 mt-3">
                            {line.slice(4)}
                          </h3>
                        );
                      }
                      if (line.startsWith("- **")) {
                        return (
                          <p
                            key={i}
                            className="text-xs text mb-1 ml-3"
                          >
                            {line.replace(/^\*\*/g, "• ").replace(/\*\*/g, "")}
                          </p>
                        );
                      }
                      if (line.startsWith("- ")) {
                        return (
                          <p
                            key={i}
                            className="text-xs text-muted mb-0.5 ml-3"
                          >
                            {line.slice(2)}
                          </p>
                        );
                      }
                      if (line.startsWith("---")) {
                        return <hr key={i} className="my-3 border/50" />;
                      }
                      if (line.trim() === "") {
                        return <div key={i} className="h-1" />;
                      }
                      return (
                        <p key={i} className="text-xs text leading-relaxed mb-1">
                          {line}
                        </p>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <p className="text-xs text-muted text-center py-8">
                  笔记数量太少，暂无法生成有意义的整理结果
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
