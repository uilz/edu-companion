"use client";

import { useState, useEffect, useCallback } from "react";
import {
  BookOpen, CheckCircle2, Circle, RefreshCw, Loader2,
  Clock, Target, TrendingUp, AlertCircle, ChevronRight, Zap,
} from "lucide-react";
import Card from "@/components/ui/Card";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Types ──
interface PlanItem {
  task_id: string;
  skill_id: string;
  title: string;
  description: string;
  subject: string;
  estimated_minutes: number;
  difficulty: number;
  priority: number;
  daily_questions: number;
  completed: boolean;
  level: string;
}

interface PlanData {
  items: PlanItem[];
  total_items: number;
  estimated_total_minutes: number;
  daily_questions: number;
  habit_level: string;
  difficulty_bias: number;
  recent_accuracy: number;
  week_number: number;
}

interface Suggestion {
  skill_id: string;
  label: string;
  level: string;
  p_known: number;
  subject: string;
}

export default function StudyPage() {
  // State
  const [planItems, setPlanItems] = useState<PlanItem[]>([]);
  const [planMeta, setPlanMeta] = useState<PlanData | null>(null);
  const [progress, setProgress] = useState<{
    completed_tasks: number; total_tasks: number; completion_rate: number;
  } | null>(null);
  const [suggestions, setSuggestions] = useState<{
    urgent: Suggestion[]; building: Suggestion[]; new_topic: Suggestion[];
    suggestion: string;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  // ── Fetch all data on mount ──
  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [planRes, progRes, suggRes] = await Promise.all([
        fetch(`${API_BASE}/api/study/plan/default_user`),
        fetch(`${API_BASE}/api/study/plan/default_user/progress`),
        fetch(`${API_BASE}/api/study/suggestions`),
      ]);
      
      if (planRes.ok) {
        const d = await planRes.json();
        setPlanItems(d.plan?.items || []);
        setPlanMeta(d.plan || null);
      }
      if (progRes.ok) {
        const p = await progRes.json();
        setProgress(p);
      }
      if (suggRes.ok) {
        setSuggestions(await suggRes.json());
      }
    } catch (e) {
      setError("加载失败，请检查后端服务");
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // ── Generate / Refresh plan ──
  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const res = await fetch(`${API_BASE}/api/study/plan/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: "default_user", reason: "manual" }),
      });
      if (res.ok) {
        await loadData();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setGenerating(false);
    }
  };

  // ── Complete task ──
  const handleComplete = async (taskId: string) => {
    try {
      const res = await fetch(
        `${API_BASE}/api/study/plan/default_user/${taskId}/complete`,
        { method: "PUT" }
      );
      if (res.ok) {
        // Refetch progress
        const progRes = await fetch(`${API_BASE}/api/study/plan/default_user/progress`);
        if (progRes.ok) setProgress(await progRes.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

  // ── Helpers ──
  const completionRate = progress?.completion_rate ?? 0;
  const habitLabel: Record<string, string> = {
    beginner: "🌱 初学", regular: "📚 日常", intensive: "💪 强化",
  };

  // ── Loading state ──
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-[var(--color-text-muted)]" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl font-bold text-[var(--color-text)] tracking-tight">
              学习规划
            </h1>
            <p className="text-sm text-[var(--color-text-muted)] mt-1">
              第 {planMeta?.week_number ?? "?"} 周 · 
              {planMeta ? ` ${habitLabel[planMeta.habit_level] || planMeta.habit_level}` : ""}
              {planMeta && ` · 准确率 ${(planMeta.recent_accuracy * 100).toFixed(0)}%`}
            </p>
          </div>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium bg-[var(--color-accent)] text-white hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {generating ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <RefreshCw size={15} />
            )}
            {planItems.length ? "刷新计划" : "生成计划"}
          </button>
        </div>

        {error && (
          <div className="mb-6 px-4 py-3 border border-[var(--color-border)] text-sm text-[var(--color-text-muted)] flex items-center gap-2">
            <AlertCircle size={15} /> {error}
          </div>
        )}

        {/* Empty state */}
        {!planItems.length && !loading && (
          <div className="text-center py-16">
            <div className="w-16 h-16 mx-auto mb-4 border border-[var(--color-border)] flex items-center justify-center">
              <BookOpen size={28} className="text-[var(--color-text-muted)]" />
            </div>
            <h2 className="text-lg font-semibold text-[var(--color-text)] mb-2">
              还没有学习计划
            </h2>
            <p className="text-sm text-[var(--color-text-muted)] max-w-sm mx-auto mb-6">
              基于你的知识掌握情况和前置依赖关系，AI 会为你生成个性化的学习计划
            </p>
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium bg-[var(--color-accent)] text-white hover:opacity-90 transition-opacity"
            >
              {generating ? <Loader2 size={15} className="animate-spin" /> : <Zap size={15} />}
              生成我的学习计划
            </button>
          </div>
        )}

        {/* Plan content */}
        {planItems.length > 0 && (
          <>
            {/* ── Overview cards ── */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
              <OverviewCard
                icon={<CheckCircle2 size={16} />}
                label="已完成"
                value={`${progress?.completed_tasks ?? 0}/${progress?.total_tasks ?? planItems.length}`}
              />
              <OverviewCard
                icon={<Clock size={16} />}
                label="预计耗时"
                value={`${planMeta?.estimated_total_minutes ?? 0} 分钟`}
              />
              <OverviewCard
                icon={<Target size={16} />}
                label="每日题量"
                value={`${planMeta?.daily_questions ?? 0} 题`}
              />
              <OverviewCard
                icon={<TrendingUp size={16} />}
                label="完成率"
                value={`${(completionRate * 100).toFixed(0)}%`}
              />
            </div>

            {/* ── Progress bar ── */}
            <div className="mb-8">
              <div className="h-1.5 bg-[var(--color-surface)] overflow-hidden">
                <div
                  className="h-full bg-[var(--color-accent)] transition-all duration-500"
                  style={{ width: `${Math.min(completionRate * 100, 100)}%` }}
                />
              </div>
            </div>

            {/* ── Task list ── */}
            <h2 className="text-sm font-semibold text-[var(--color-text)] uppercase tracking-widest mb-4">
              本周任务
            </h2>
            <div className="space-y-3 mb-10">
              {planItems.map((item, i) => (
                <TaskCard
                  key={item.task_id}
                  item={item}
                  index={i}
                  onComplete={() => handleComplete(item.task_id)}
                />
              ))}
            </div>

            {/* ── Suggestions ── */}
            {suggestions && (suggestions.urgent.length > 0 || suggestions.building.length > 0) && (
              <>
                <h2 className="text-sm font-semibold text-[var(--color-text)] uppercase tracking-widest mb-4">
                  学习建议
                </h2>
                <p className="text-sm text-[var(--color-text-muted)] mb-4">
                  {suggestions.suggestion}
                </p>
                <div className="grid sm:grid-cols-3 gap-4 mb-10">
                  <SuggestionColumn
                    title="🔴 急需突破"
                    items={suggestions.urgent}
                    color="border-l-[#ef4444]"
                  />
                  <SuggestionColumn
                    title="🟡 稳步推进"
                    items={suggestions.building}
                    color="border-l-[#f59e0b]"
                  />
                  <SuggestionColumn
                    title="🟢 新主题"
                    items={suggestions.new_topic}
                    color="border-l-[#10b981]"
                  />
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ──

function OverviewCard({ icon, label, value }: {
  icon: React.ReactNode; label: string; value: string;
}) {
  return (
    <div className="px-4 py-3 border border-[var(--color-border)] bg-[var(--color-bg)]">
      <div className="flex items-center gap-2 text-[var(--color-text-muted)] mb-1">
        {icon}
        <span className="text-[10px] uppercase tracking-wider">{label}</span>
      </div>
      <div className="text-lg font-bold text-[var(--color-text)]">{value}</div>
    </div>
  );
}

function TaskCard({ item, index, onComplete }: {
  item: PlanItem; index: number; onComplete: () => void;
}) {
  const levelColors: Record<string, string> = {
    "未接触": "text-[var(--color-text-muted)]", "初学": "text-[#f59e0b]",
    "发展中": "text-[#3b82f6]", "接近掌握": "text-[#10b981]", "已掌握": "text-[var(--color-text-muted)]",
  };

  return (
    <div className="flex items-start gap-3 px-4 py-3.5 border border-[var(--color-border)] bg-[var(--color-bg)] hover:border-[var(--color-border-hover)] transition-colors group">
      <button
        onClick={onComplete}
        className="flex-shrink-0 mt-0.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors"
        title="标记完成"
      >
        <Circle size={18} />
      </button>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[10px] font-mono text-[var(--color-text-muted)]">
            #{index + 1}
          </span>
          <span className={`text-[10px] font-medium ${levelColors[item.level] || ""}`}>
            {item.level}
          </span>
          <span className="text-[10px] text-[var(--color-text-muted)]">
            {item.subject}
          </span>
        </div>
        <h3 className="text-sm font-semibold text-[var(--color-text)] truncate">
          {item.title}
        </h3>
        <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
          {item.description}
        </p>
      </div>
      <div className="flex-shrink-0 flex flex-col items-end gap-1 text-[10px] text-[var(--color-text-muted)]">
        <span className="flex items-center gap-1">
          <Clock size={10} /> {item.estimated_minutes}分钟
        </span>
        <span>难度 {item.difficulty.toFixed(1)}</span>
        <span>{item.daily_questions}题/天</span>
      </div>
    </div>
  );
}

function SuggestionColumn({ title, items, color }: {
  title: string; items: Suggestion[]; color: string;
}) {
  if (!items.length) return null;
  return (
    <div className={`border-l-2 ${color} pl-3`}>
      <h3 className="text-[11px] font-semibold text-[var(--color-text)] uppercase tracking-wider mb-3">
        {title}
      </h3>
      <div className="space-y-2">
        {items.map((s) => (
          <div key={s.skill_id} className="flex items-center justify-between text-xs">
            <span className="text-[var(--color-text)] truncate">{s.label}</span>
            <span className="text-[var(--color-text-muted)] ml-2 flex-shrink-0">
              {s.subject}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
