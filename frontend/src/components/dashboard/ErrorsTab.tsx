"use client";

// ── 基础导入（React hooks + 图标组件） ──
import { useState, useEffect } from "react";
import {
  RotateCcw, CheckCircle, XCircle, Loader2, BookOpen,
  ChevronDown, ChevronUp, Brain, Sparkles,
} from "lucide-react";
// ── 自定义 UI 组件 ──
import Card from "@/components/ui/Card";
import MathContent from "@/components/ui/MathContent";
import { API_BASE } from "@/lib/api";

// ── 类型定义 ──

/** AI 错因归属分析结果 */
interface Attribution {
  primary: string;          // 一级错误归因
  secondary: string | null; // 二级错误归因（可为空）
  primary_label: string;    // 归因展示标签
  group: string;            // 所属分组（概念/计算/审题/方法）
  analysis: string;         // AI 分析详情
  recommendation: string;   // 改进建议
}

/** 错题条目 */
interface ErrorEntry {
  entry_id: string;         // 条目唯一标识
  question_id: string;      // 题目 ID
  skill_id: string;         // 技能 ID
  error_type: string;       // 错误类型（conceptual/procedural/computation 等）
  misconception?: string;   // 可能的误解描述
  user_answer: string;      // 用户的错误答案
  correct_answer: string;   // 正确答案
  question_text: string;    // 题目文字
  review_count: number;     // 复习次数
  is_resolved: boolean;     // 是否已解决
  created_at: string;       // 创建时间
  attribution?: Attribution | string; // AI 分析归属（对象或 JSON 字符串）
  referenced_materials: Array<{       // 关联的参考资料
    source_file: string;
    page_number?: number;
    preview: string;
  }>;
}

/** 错题统计概览 */
interface ErrorStats {
  total: number;                       // 错题总数
  by_group: Record<string, number>;    // 按分组统计
  by_category: Record<string, number>; // 按类别统计
  top_weak_skills: string[];           // 最薄弱技能列表
}

// ── 标签映射与配色 ──

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
  "计算": "var(--color-error)",
  "审题": "var(--color-warning)",
  "方法": "#8b5cf6",
  "未分类": "#737373",
};

// ── 解析 attribution 字段（可能是 JSON 字符串，统一转为对象） ──
function parseAttr(a: Attribution | string | undefined): Attribution | null {
  if (!a) return null;
  if (typeof a === "string") {
    try { return JSON.parse(a); } catch { return null; }
  }
  return a;
}

// ── 主组件：错题本 ──

export function ErrorsTab() {
  // ── 状态管理 ──
  const [entries, setEntries] = useState<ErrorEntry[]>([]);       // 错题列表
  const [stats, setStats] = useState<ErrorStats | null>(null);     // 错题统计
  const [filter, setFilter] = useState<"pending" | "resolved" | "all">("pending"); // 筛选：待解决/已解决/全部
  const [loading, setLoading] = useState(true);                    // 加载状态
  const [expandedId, setExpandedId] = useState<string | null>(null); // 当前展开分析的条目 ID
  const [analyzing, setAnalyzing] = useState<string | null>(null);   // 正在 AI 分析的条目 ID

  // ── 获取错题列表 ──
  const fetchErrors = async (status: string) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      // 根据筛选状态添加查询参数
      if (status === "pending") params.set("resolved", "false");
      else if (status === "resolved") params.set("resolved", "true");

      const res = await fetch(`${API_BASE}/api/practice/errors?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setEntries(data.entries || []);
    } catch (err) {
    }
    setLoading(false);
  };

  // ── 获取错题统计概览 ──
  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/practice/errors/stats`);
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (e) {
    }
  };

  // ── 筛选变化时重新加载数据 ──
  useEffect(() => {
    fetchErrors(filter);
    fetchStats();
  }, [filter]);

  // ── 标记错题为"已掌握" ──
  const markResolved = async (entryId: string) => {
    await fetch(`${API_BASE}/api/practice/errors/${entryId}/review?is_correct=true`, {
      method: "POST",
    });
    // 刷新列表和统计
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
      // 更新当前条目的 attribution 字段
      setEntries((prev) =>
        prev.map((e) =>
          e.entry_id === entryId ? { ...e, attribution: data.attribution } : e
        )
      );
      setExpandedId(entryId);
      fetchStats();
    } catch (err) {
    }
    setAnalyzing(null);
  };

  return (
    <div>
      <div className="max-w-3xl mx-auto px-6 py-16">
        {/* ── 顶部标题栏 + 筛选按钮 ── */}
        <div className="flex items-center justify-between mb-12">
          <h1 className="text-2xl md:text-4xl font-semibold tracking-tight text-[var(--color-text)]">
            <BookOpen size={28} className="inline mr-3 text-[var(--color-accent)]" />
            错题本
          </h1>
          {/* 筛选切换：未解决 / 已解决 / 全部 */}
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

        {/* ── 错因分布统计条 ── */}
        {stats && stats.total > 0 && (
          <div className="mb-8 p-4 border border-[var(--color-border)] bg-[var(--color-card)]">
            <div className="text-xs text-[var(--color-text-muted)] mb-3 flex items-center gap-2">
              <Brain size={14} />
              错因分布（未解决 {stats.total} 题）
            </div>
            {/* 按数量降序展示每个分组的错题数 */}
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
                    <span className="font-semibold">{count}</span>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* ── 加载中状态 ── */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="animate-spin text-[var(--color-accent)]" size={24} />
          </div>
        ) : entries.length === 0 ? (
          /* ── 空状态：无错题时的提示 ── */
          <div className="text-center py-20">
            <p className="text-[var(--color-text-muted)] text-lg mb-2">
              {filter === "pending" ? "🎉 没有待解决的错题！" : "暂无错题记录"}
            </p>
            <p className="text-[var(--color-text-muted)] text-sm">
              {filter === "pending" ? "继续保持！" : "去练习页开始做题吧"}
            </p>
          </div>
        ) : (
          /* ── 错题列表 ── */
          <div className="space-y-4">
            {entries.map((entry) => {
              const isExpanded = expandedId === entry.entry_id;
              const attr = parseAttr(entry.attribution);
              return (
                <Card key={entry.entry_id || Math.random().toString(36)}>
                  {/* ── 条目头部：错误标签 + 归因标签 + 日期 ── */}
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      {/* 错误类型标签 */}
                      <span
                        className={`text-xs px-2 py-0.5 ${
                          entry.is_resolved
                            ? "bg-[var(--color-success)]/10 text-[var(--color-success)]"
                            : "bg-[var(--color-error)]/10 text-[var(--color-error)]"
                        }`}
                      >
                        {errorLabel[entry.error_type] || entry.error_type || "未知错误"}
                      </span>
                      {/* AI 归因分组标签 */}
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
                      {/* 无 AI 归因时的原始误解描述 */}
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

                  {/* ── 题目文本（截断至 120 字） ── */}
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

                  {/* ── 答案对比与复习次数 ── */}
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

                  {/* ── 参考资料引用 ── */}
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

                  {/* ── AI 错因分析详情（展开态） ── */}
                  {isExpanded && attr && (
                    <div className="mb-3 p-4 border border-[var(--color-accent)]/30 bg-[var(--color-accent)]/5 active:scale-[0.97] transition-transform">
                      <div className="flex items-center gap-2 mb-2">
                        <Sparkles size={14} className="text-[var(--color-accent)]" />
                        <span className="text-xs font-semibold text-[var(--color-accent)]">AI 错因分析</span>
                      </div>
                      <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed mb-2">
                        {attr.analysis}
                      </p>
                      <p className="text-xs text-[var(--color-text-muted)]">
                        💡 {attr.recommendation}
                      </p>
                    </div>
                  )}

                  {/* ── 操作按钮区域 ── */}
                  <div className="flex items-center gap-3">
                    {/* 标记"已掌握"按钮（仅未解决状态显示） */}
                    {!entry.is_resolved && (
                      <button
                        onClick={() => markResolved(entry.entry_id)}
                        className="flex items-center gap-1.5 text-xs text-[var(--color-success)] hover:underline"
                      >
                        <CheckCircle size={12} />
                        已掌握
                      </button>
                    )}

                    {/* AI 分析错因按钮（仅未分析且未解决时显示） */}
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

                    {/* 展开/收起 AI 分析详情（已有分析结果时显示） */}
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
    </div>
  );
}
