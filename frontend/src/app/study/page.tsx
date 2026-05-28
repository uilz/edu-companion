// 客户端组件声明，启用 React 客户端交互功能
"use client";

// 导入 React 状态管理与副作用钩子
import { useState, useEffect, useCallback } from "react";
// 导入 UI 图标组件
import {
  BookOpen, CheckCircle2, Circle, RefreshCw, Loader2,
  Clock, Target, TrendingUp, AlertCircle, ChevronRight, Zap,
} from "lucide-react";
// 导入自定义卡片组件
import Card from "@/components/ui/Card";
import { API_BASE } from "@/lib/api";

// ── 类型定义 ──

/** 学习计划中的单个任务项 */
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

/** 学习计划整体数据 */
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

/** AI 学习建议项 */
interface Suggestion {
  skill_id: string;
  label: string;
  level: string;
  p_known: number;
  subject: string;
}

// 学习页面主组件
export default function StudyPage() {
  // 页面状态：学习计划列表、元数据、进度、建议、加载与错误状态
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

  // ── 组件挂载时加载所有数据（计划、进度、建议） ──
  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      // 并行请求：学习计划、进度数据、AI 建议
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

  // 页面加载时自动获取数据
  useEffect(() => { loadData(); }, [loadData]);

  // ── 生成/刷新学习计划（用户手动触发） ──
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

  // ── 标记任务完成 ──
  const handleComplete = async (taskId: string) => {
    try {
      const res = await fetch(
        `${API_BASE}/api/study/plan/default_user/${taskId}/complete`,
        { method: "PUT" }
      );
      if (res.ok) {
        // 完成后续刷新进度数据
        const progRes = await fetch(`${API_BASE}/api/study/plan/default_user/progress`);
        if (progRes.ok) setProgress(await progRes.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

  // ── 辅助函数 ──
  const completionRate = progress?.completion_rate ?? 0;
  // 学习习惯等级对应的中文标签
  const habitLabel: Record<string, string> = {
    beginner: "🌱 初学", regular: "📚 日常", intensive: "💪 强化",
  };

  // ── 加载状态：显示旋转加载图标 ──
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
        {/* 页面头部：标题、学习阶段与操作按钮 */}
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
          {/* 生成/刷新计划按钮 */}
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

        {/* 错误提示信息 */}
        {error && (
          <div className="mb-6 px-4 py-3 border border-[var(--color-border)] text-sm text-[var(--color-text-muted)] flex items-center gap-2">
            <AlertCircle size={15} /> {error}
          </div>
        )}

        {/* 空状态：尚无学习计划时的引导界面 */}
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

        {/* 计划内容（有任务时渲染） */}
        {planItems.length > 0 && (
          <>
            {/* ── 概览卡片：已完成数、预计耗时、每日题量、完成率 ── */}
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

            {/* ── 进度条：直观展示整体完成进度 ── */}
            <div className="mb-8">
              <div className="h-1.5 bg-[var(--color-surface)] overflow-hidden">
                <div
                  className="h-full bg-[var(--color-accent)] transition-all duration-500"
                  style={{ width: `${Math.min(completionRate * 100, 100)}%` }}
                />
              </div>
            </div>

            {/* ── 本周任务列表 ── */}
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

            {/* ── AI 学习建议：分"急需突破""稳步推进""新主题"三个栏目 ── */}
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

// ── 子组件 ──

/** 概览卡片：展示某项统计数据的图标、标签和数值 */
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

/** 任务卡片：展示单个学习任务的详情，包含完成按钮、标题、描述、预估时间和难度 */
function TaskCard({ item, index, onComplete }: {
  item: PlanItem; index: number; onComplete: () => void;
}) {
  // 掌握等级对应的文字颜色
  const levelColors: Record<string, string> = {
    "未接触": "text-[var(--color-text-muted)]", "初学": "text-[#f59e0b]",
    "发展中": "text-[#3b82f6]", "接近掌握": "text-[#10b981]", "已掌握": "text-[var(--color-text-muted)]",
  };

  return (
    <div className="flex items-start gap-3 px-4 py-3.5 border border-[var(--color-border)] bg-[var(--color-bg)] hover:border-[var(--color-border-hover)] transition-colors group">
      {/* 标记完成按钮 */}
      <button
        onClick={onComplete}
        className="flex-shrink-0 mt-0.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors"
        title="标记完成"
      >
        <Circle size={18} />
      </button>
      <div className="flex-1 min-w-0">
        {/* 任务元数据：序号、掌握等级、学科 */}
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
        {/* 任务标题 */}
        <h3 className="text-sm font-semibold text-[var(--color-text)] truncate">
          {item.title}
        </h3>
        {/* 任务描述 */}
        <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
          {item.description}
        </p>
      </div>
      {/* 右侧信息：预估时间、难度、每日题量 */}
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

/** 建议列：按类别展示 AI 推荐的学习主题列表 */
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
