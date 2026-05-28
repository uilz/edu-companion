"use client";

// ── 导入依赖 ──
import { useState, useEffect } from "react";
import {
  RotateCcw, CheckCircle, XCircle, Loader2, BookOpen,
  ChevronDown, ChevronUp, Brain, Sparkles,
} from "lucide-react";
import Card from "@/components/ui/Card";
import MathContent from "@/components/ui/MathContent";
import { API_BASE } from "@/lib/api";

// ── Types ──
// 错因归因数据（AI 分析结果）
interface Attribution {
  primary: string;
  secondary: string | null;
  primary_label: string;
  group: string;
  analysis: string;
  recommendation: string;
}

// 错题条目结构
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
  attribution?: Attribution | string;
  referenced_materials: Array<{
    source_file: string;
    page_number?: number;
    preview: string;
  }>;
}

// 错题统计信息
interface ErrorStats {
  total: number;
  by_group: Record<string, number>;
  by_category: Record<string, number>;
  top_weak_skills: string[];
}

// ── 错误类型中文标签 ──

const errorLabel: Record<string, string> = {
  conceptual: "概念错误",
  procedural: "程序错误",
  computation: "计算错误",
  reading: "审题错误",
  transfer: "迁移错误",
  meta: "元认知错误",
  careless: "粗心大意",
};

const groupColors: Record<string, string> = {
  "概念": "#f97316",
  "计算": "#ef4444",
  "审题": "#f59e0b",
  "方法": "#8b5cf6",
  "未分类": "#737373",
};

// ── 解析归因数据（可能是 JSON 字符串） ──
function parseAttr(a: Attribution | string | undefined): Attribution | null {
  if (!a) return null;
  if (typeof a === "string") {
    try { return JSON.parse(a); } catch { return null; }
  }
  return a;
}

// ── 主页面：错题本 ──

export default function ErrorBookPage() {
  const [entries, setEntries] = useState<ErrorEntry[]>([]);
  const [stats, setStats] = useState<ErrorStats | null>(null);
  const [filter, setFilter] = useState<"pending" | "resolved" | "all">("pending");
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState<string | null>(null);

  // ── 获取错题列表（按过滤状态） ──
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

  // ── 获取错题统计 ──
  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/practice/errors/stats`);
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
      } catch { console.error("获取错题统计失败"); }
  };

  // ── 初始化：数据加载 ──
  useEffect(() => {
    fetchErrors(filter);
    fetchStats();
  }, [filter]);

  // ── 标记错题为"已掌握" ──
  const markResolved = async (entryId: string) => {
    await fetch(`${API_BASE}/api/practice/errors/${entryId}/review?is_correct=true`, {
      method: "POST",
    });
    fetchErrors(filter);
    fetchStats();
  };

  // ── AI 分析错因 ──
  const analyzeError = async (entryId: string) => {
    setAnalyzing(entryId);
    try {
      const res = await fetch(`${API_BASE}/api/practice/errors/${entryId}/analyze`, {
        method: "POST",
      });
      const data = await res.json();
      // Update the entry with the attribution
      setEntries((prev) =>
        prev.map((e) =>
          e.entry_id === entryId ? { ...e, attribution: data.attribution } : e
        )
      );
      setExpandedId(entryId);
      fetchStats();
    } catch (err) {
      console.error("Analysis failed:", err);
    }
    setAnalyzing(null);
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

        {/* ── Error Stats Bar ── */}
        {stats && stats.total > 0 && (
          <div className="mb-8 p-4 border border-[var(--color-border)] bg-[var(--color-card)]">
            <div className="text-xs text-[var(--color-text-muted)] mb-3 flex items-center gap-2">
              <Brain size={14} />
              错因分布（未解决 {stats.total} 题）
            </div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(stats.by_group)
                .sort(([, a], [, b]) => b - a)
                .map(([group, count]) => (
                  <div
                    key={group}
                    className="flex items-center gap-1.5 px-2.5 py-1 text-xs"
                    style={{
                      backgroundColor: `${groupColors[group] || "#737373"}15`,
                      color: groupColors[group] || "#737373",
                      border: `1px solid ${groupColors[group] || "#737373"}40`,
                    }}
                  >
                    <span>{group}</span>
                    <span className="font-bold">{count}</span>
                  </div>
                ))}
            </div>
          </div>
        )}

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
            {entries.map((entry) => {
              const isExpanded = expandedId === entry.entry_id;
              const attr = parseAttr(entry.attribution);
              return (
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
                      {attr && (
                        <span
                          className="text-xs px-2 py-0.5"
                          style={{
                            backgroundColor: `${groupColors[attr.group] || "#737373"}15`,
                            color: groupColors[attr.group] || "#737373",
                          }}
                        >
                          {attr.primary_label}
                        </span>
                      )}
                      {entry.misconception && !attr && (
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

                  {/* ── AI Attribution (expanded) ── */}
                  {isExpanded && attr && (
                    <div className="mb-3 p-4 border border-[var(--color-accent)]/30 bg-[var(--color-accent)]/5">
                      <div className="flex items-center gap-2 mb-2">
                        <Sparkles size={14} className="text-[var(--color-accent)]" />
                        <span className="text-xs font-bold text-[var(--color-accent)]">AI 错因分析</span>
                      </div>
                      <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed mb-2">
                        {attr.analysis}
                      </p>
                      <p className="text-xs text-[var(--color-text-muted)]">
                        💡 {attr.recommendation}
                      </p>
                    </div>
                  )}

                  {/* ── Actions ── */}
                  <div className="flex items-center gap-3">
                    {!entry.is_resolved && (
                      <button
                        onClick={() => markResolved(entry.entry_id)}
                        className="flex items-center gap-1.5 text-xs text-[var(--color-success)] hover:underline"
                      >
                        <CheckCircle size={12} />
                        已掌握
                      </button>
                    )}

                    {/* Analyze button */}
                    {!attr && !entry.is_resolved && (
                      <button
                        onClick={() => analyzeError(entry.entry_id)}
                        disabled={analyzing === entry.entry_id}
                        className="flex items-center gap-1.5 text-xs text-[var(--color-accent)] hover:underline"
                      >
                        {analyzing === entry.entry_id ? (
                          <Loader2 size={12} className="animate-spin" />
                        ) : (
                          <Brain size={12} />
                        )}
                        AI 分析错因
                      </button>
                    )}

                    {/* Expand/collapse */}
                    {attr && (
                      <button
                        onClick={() => setExpandedId(isExpanded ? null : entry.entry_id)}
                        className="flex items-center gap-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
                      >
                        {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                        {isExpanded ? "收起分析" : "展开分析"}
                      </button>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}
