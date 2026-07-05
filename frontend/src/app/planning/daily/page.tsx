"use client";

import { useState, useCallback } from "react";
import {
  Calendar, Play, CheckCircle2, SkipForward, Plus, Clock, Tag,
  Loader2, AlertCircle, Lightbulb, RotateCcw, Link2,
} from "lucide-react";
import { useDailyView, completePlanItem, startPlanItem, skipPlanItem, updatePlanItem, PlanItem, createPlanItem } from "@/hooks/planning/usePlanning";
import { useAuth } from "@/contexts/AuthContext";
import Card from "@/components/ui/Card";

const HABIT_LABELS: Record<string, string> = {
  beginner: "🌱 初学",
  regular: "📚 日常",
  intensive: "💪 强化",
};

const FATIGUE_LABELS: Record<string, string> = {
  low: "疲劳低",
  medium: "疲劳中等",
  high: "疲劳高",
};

const SOURCE_LABELS: Record<string, string> = {
  flashcard: "卡片",
  practice: "练习",
  project: "项目",
  reading: "阅读",
  language_room: "语言房",
  manual: "手动",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "待安排",
  scheduled: "已安排",
  in_progress: "进行中",
  completed: "已完成",
  skipped: "已跳过",
  extended: "已延长",
};

const STATUS_COLORS: Record<string, string> = {
  pending: "border-l-[var(--color-border)]",
  scheduled: "border-l-[var(--color-accent)]",
  in_progress: "border-l-amber-500",
  completed: "border-l-emerald-500",
  skipped: "border-l-zinc-400",
  extended: "border-l-blue-500",
};

// 时间轴小时
const HOURS = Array.from({ length: 16 }, (_, i) => i + 7); // 07:00 - 22:00

function formatHour(h: number): string {
  return `${h.toString().padStart(2, "0")}:00`;
}

function timeOf(iso: string | null | undefined): number {
  if (!iso) return -1;
  const d = new Date(iso);
  return d.getHours() + d.getMinutes() / 60;
}

export default function DailyPage() {
  const { user } = useAuth();
  const { data, loading, error, reload } = useDailyView();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [manualTitle, setManualTitle] = useState("");
  const [manualMinutes, setManualMinutes] = useState(20);
  const [manualHour, setManualHour] = useState(10);

  const onDragStart = useCallback((id: string) => setDraggingId(id), []);
  const onDragEnd = useCallback(() => setDraggingId(null), []);

  const onTimelineDrop = useCallback(
    async (hour: number, itemId?: string) => {
      if (!data) return;
      const target = itemId || draggingId;
      if (!target) return;
      try {
        const [yr, mo, da] = data.date.split("-").map(Number);
        const dt = new Date(yr, mo - 1, da, hour, 0, 0);
        await updatePlanItem(target, {
          scheduled_for: dt.toISOString(),
          plan_date: data.date,
          status: "scheduled",
        });
        await reload();
      } catch (e) {
        console.error("安排失败:", e);
      } finally {
        setDraggingId(null);
      }
    },
    [data, draggingId, reload],
  );

  const handleComplete = async (id: string) => {
    if (!data) return;
    const it = [...data.timeline_items, ...data.pending_pool].find((x) => x.id === id);
    const minutes = it?.estimated_minutes ?? 0;
    setBusyId(id);
    try {
      await completePlanItem(id, minutes);
      await reload();
    } catch (e) {
      console.error(e);
    } finally {
      setBusyId(null);
    }
  };

  const handleStart = async (id: string) => {
    setBusyId(id);
    try {
      await startPlanItem(id);
      await reload();
    } catch (e) {
      console.error(e);
    } finally {
      setBusyId(null);
    }
  };

  const handleSkip = async (id: string) => {
    setBusyId(id);
    try {
      await skipPlanItem(id);
      await reload();
    } catch (e) {
      console.error(e);
    } finally {
      setBusyId(null);
    }
  };

  const handleAddManual = async () => {
    if (!user || !data || !manualTitle.trim()) return;
    const [yr, mo, da] = data.date.split("-").map(Number);
    const dt = new Date(yr, mo - 1, da, manualHour, 0, 0);
    try {
      await createPlanItem({
        source_module: "manual",
        target_type: "manual",
        target_ref_id: `manual_${Date.now()}`,
        title: manualTitle,
        estimated_minutes: manualMinutes,
        scheduled_for: dt.toISOString(),
        plan_date: data.date,
      });
      setManualTitle("");
      setShowCreate(false);
      await reload();
    } catch (e) {
      console.error(e);
    }
  };

  const adoptRecommendation = async (rec: { title?: string; skill_id?: string; estimated_minutes?: number }) => {
    if (!userId || !data) return;
    try {
      await createPlanItem({
        source_module: "manual",
        target_type: "adaptive_recommendation",
        target_ref_id: rec.skill_id || `rec_${Date.now()}`,
        title: rec.title || "自适应推荐",
        estimated_minutes: rec.estimated_minutes || 20,
        plan_date: data.date,
      });
      await reload();
    } catch (e) {
      console.error(e);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-[var(--color-text-muted)]" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <Card>
          <div className="flex items-center gap-2 text-sm text-red-600">
            <AlertCircle size={15} /> {error}
          </div>
        </Card>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {/* 头部 */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-[var(--color-text)] tracking-tight flex items-center gap-2">
              <Calendar size={20} /> 日视图
            </h1>
            <p className="text-sm text-[var(--color-text-muted)] mt-1">{data.date}</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => reload()}
              className="inline-flex items-center gap-2 px-3 py-2 text-sm border border-[var(--color-border)] hover:bg-[var(--color-card)]"
            >
              <RotateCcw size={14} /> 刷新
            </button>
            <button
              onClick={() => setShowCreate((s) => !s)}
              className="inline-flex items-center gap-2 px-3 py-2 text-sm bg-[var(--color-accent)] text-white hover:opacity-90"
            >
              <Plus size={14} /> 新增待办
            </button>
          </div>
        </div>

        {/* 顶部状态条 */}
        <Card title="状态条">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <div>
              <span className="text-[var(--color-text-muted)]">疲劳</span>
              <span className="ml-2 font-medium">
                {FATIGUE_LABELS[data.status_bar.fatigue_risk] || data.status_bar.fatigue_risk}
              </span>
            </div>
            <div>
              <span className="text-[var(--color-text-muted)]">压力</span>
              <span className="ml-2 font-medium">{data.status_bar.pressure_score ?? "—"}</span>
            </div>
            <div>
              <span className="text-[var(--color-text-muted)]">能量</span>
              <span className="ml-2 font-medium">{data.status_bar.energy_score ?? "—"}</span>
            </div>
            <div>
              <span className="text-[var(--color-text-muted)]">习惯</span>
              <span className="ml-2 font-medium">
                {HABIT_LABELS[data.status_bar.habit_level] || data.status_bar.habit_level}
              </span>
            </div>
          </div>
          {data.status_bar.pomodoro_message && (
            <div className="mt-3 text-xs text-[var(--color-text-muted)]">🍅 {data.status_bar.pomodoro_message}</div>
          )}
        </Card>

        {/* 新增待办表单 */}
        {showCreate && (
          <Card title="新增待办" className="mt-4">
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
              <input
                value={manualTitle}
                onChange={(e) => setManualTitle(e.target.value)}
                placeholder="待办标题…"
                className="px-3 py-2 text-sm border border-[var(--color-border)] bg-[var(--color-bg)] sm:col-span-2"
              />
              <select
                value={manualHour}
                onChange={(e) => setManualHour(Number(e.target.value))}
                className="px-3 py-2 text-sm border border-[var(--color-border)] bg-[var(--color-bg)]"
              >
                {HOURS.map((h) => (
                  <option key={h} value={h}>{formatHour(h)}</option>
                ))}
              </select>
              <input
                type="number"
                min={5}
                max={180}
                value={manualMinutes}
                onChange={(e) => setManualMinutes(Number(e.target.value))}
                className="px-3 py-2 text-sm border border-[var(--color-border)] bg-[var(--color-bg)]"
                placeholder="分钟"
              />
            </div>
            <div className="mt-3 flex items-center gap-2">
              <button
                onClick={handleAddManual}
                disabled={!manualTitle.trim()}
                className="px-4 py-2 text-sm bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50"
              >
                添加
              </button>
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 text-sm border border-[var(--color-border)]"
              >
                取消
              </button>
            </div>
          </Card>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
          {/* 时间轴 */}
          <div className="lg:col-span-2 space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-muted)] flex items-center gap-2">
              <Clock size={14} /> 时间轴
            </h2>
            <Card>
              <div className="space-y-1">
                {HOURS.map((h) => {
                  const items = data.timeline_items.filter(
                    (it) => it.scheduled_for && Math.floor(timeOf(it.scheduled_for)) === h,
                  );
                  return (
                    <div
                      key={h}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={() => onTimelineDrop(h)}
                      className="flex items-start gap-3 border-b border-[var(--color-border)] last:border-b-0 py-2 min-h-[60px]"
                    >
                      <div className="text-xs text-[var(--color-text-muted)] pt-1 w-14">
                        {formatHour(h)}
                      </div>
                      <div className="flex-1 space-y-2">
                        {items.map((it) => (
                          <PlanItemCard
                            key={it.id}
                            item={it}
                            busy={busyId === it.id}
                            onStart={() => handleStart(it.id)}
                            onComplete={() => handleComplete(it.id)}
                            onSkip={() => handleSkip(it.id)}
                            onDragStart={() => onDragStart(it.id)}
                            onDragEnd={onDragEnd}
                          />
                        ))}
                        {items.length === 0 && (
                          <div className="text-xs text-[var(--color-text-muted)] opacity-50">
                            拖入项目 →
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          </div>

          {/* 待安排池 + 推荐 */}
          <div className="space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-muted)] flex items-center gap-2">
              <Tag size={14} /> 待安排池
              <span className="text-xs">({data.pending_pool.length})</span>
            </h2>
            <Card>
              {data.pending_pool.length === 0 ? (
                <div className="text-sm text-[var(--color-text-muted)] py-4 text-center">暂无待办</div>
              ) : (
                <div className="space-y-2">
                  {data.pending_pool.map((p) => (
                    <div
                      key={p.id}
                      draggable
                      onDragStart={() => onDragStart(p.id)}
                      onDragEnd={onDragEnd}
                      className="p-3 border border-[var(--color-border)] cursor-move hover:border-[var(--color-accent)]"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs px-1.5 py-0.5 bg-[var(--color-card)] border border-[var(--color-border)]">
                          {SOURCE_LABELS[p.source_module] || p.source_module}
                        </span>
                        <span className="text-xs text-[var(--color-text-muted)]">
                          {p.estimated_minutes} min
                        </span>
                      </div>
                      <div className="text-sm font-medium text-[var(--color-text)]">{p.title}</div>
                      <div className="mt-2 flex items-center gap-1">
                        <button
                          onClick={() => handleComplete(p.id)}
                          disabled={busyId === p.id}
                          className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-[var(--color-accent)] text-white disabled:opacity-50"
                        >
                          <CheckCircle2 size={12} /> 完成
                        </button>
                        <button
                          onClick={() => handleSkip(p.id)}
                          disabled={busyId === p.id}
                          className="inline-flex items-center gap-1 px-2 py-1 text-xs border border-[var(--color-border)] disabled:opacity-50"
                        >
                          <SkipForward size={12} /> 跳过
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-muted)] flex items-center gap-2 mt-6">
              <Lightbulb size={14} /> 自适应推荐
              <span className="text-xs">({data.adaptive_recommendations.length})</span>
            </h2>
            <Card>
              {data.adaptive_recommendations.length === 0 ? (
                <div className="text-sm text-[var(--color-text-muted)] py-4 text-center">
                  暂无推荐 — 点击 <a href="/study" className="text-[var(--color-accent)] hover:underline">学习规划</a> 生成
                </div>
              ) : (
                <div className="space-y-2">
                  {data.adaptive_recommendations.map((rec, i) => (
                    <div
                      key={rec.task_id || rec.skill_id || i}
                      className="p-3 border border-[var(--color-border)]"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-[var(--color-text-muted)]">
                          优先级 {rec.priority ?? "-"} · 难度 {rec.difficulty ?? "-"}
                        </span>
                        <span className="text-xs text-[var(--color-text-muted)]">
                          {rec.estimated_minutes ?? 20} min
                        </span>
                      </div>
                      <div className="text-sm font-medium text-[var(--color-text)]">
                        {rec.title || rec.skill_id}
                      </div>
                      {rec.description && (
                        <div className="text-xs text-[var(--color-text-muted)] mt-1">
                          {rec.description}
                        </div>
                      )}
                      <button
                        onClick={() => adoptRecommendation(rec)}
                        className="mt-2 inline-flex items-center gap-1 px-2 py-1 text-xs border border-[var(--color-accent)] text-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-white"
                      >
                        <Plus size={12} /> 加入今日
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* 日总结 */}
            {data.brief_summary?.summary && (
              <Card title="日总结" className="mt-6">
                <div className="text-sm text-[var(--color-text-muted)] whitespace-pre-wrap">
                  {data.brief_summary.summary}
                </div>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── 计划项卡片 ──

interface PlanItemCardProps {
  item: PlanItem;
  busy: boolean;
  onStart: () => void;
  onComplete: () => void;
  onSkip: () => void;
  onDragStart: () => void;
  onDragEnd: () => void;
}

function PlanItemCard({ item, busy, onStart, onComplete, onSkip, onDragStart, onDragEnd }: PlanItemCardProps) {
  const status = item.status;
  const accent = STATUS_COLORS[status] || "border-l-[var(--color-border)]";
  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      className={`p-3 border border-[var(--color-border)] border-l-4 ${accent} bg-[var(--color-card)] cursor-move ${
        item.is_mood_rule_affected ? "ring-2 ring-amber-300" : ""
      }`}
    >
      <div className="flex items-center justify-between mb-1 gap-2 flex-wrap">
        <div className="flex items-center gap-1.5">
          <span className="text-xs px-1.5 py-0.5 bg-[var(--color-bg)] border border-[var(--color-border)]">
            {SOURCE_LABELS[item.source_module] || item.source_module}
          </span>
          <span className="text-xs text-[var(--color-text-muted)]">
            {STATUS_LABELS[status] || status}
          </span>
          {item.is_mood_rule_affected && (
            <span className="text-xs px-1.5 py-0.5 bg-amber-100 text-amber-700 border border-amber-300">
              心情规则
            </span>
          )}
        </div>
        <span className="text-xs text-[var(--color-text-muted)]">
          {item.estimated_minutes} min
        </span>
      </div>
      <div className="text-sm font-medium text-[var(--color-text)]">{item.title}</div>
      {item.description && (
        <div className="text-xs text-[var(--color-text-muted)] mt-1">{item.description}</div>
      )}
      {item.linked_node_ids && item.linked_node_ids.length > 0 && (
        <div className="text-xs text-[var(--color-text-muted)] mt-1 flex items-center gap-1">
          <Link2 size={11} /> 关联 {item.linked_node_ids.length} 个知识点
        </div>
      )}
      <div className="mt-2 flex items-center gap-1">
        {status !== "in_progress" && status !== "completed" && (
          <button
            onClick={onStart}
            disabled={busy}
            className="inline-flex items-center gap-1 px-2 py-1 text-xs border border-[var(--color-border)] hover:bg-[var(--color-bg)] disabled:opacity-50"
          >
            <Play size={11} /> 开始
          </button>
        )}
        {status !== "completed" && (
          <button
            onClick={onComplete}
            disabled={busy}
            className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-[var(--color-accent)] text-white disabled:opacity-50"
          >
            <CheckCircle2 size={11} /> 完成
          </button>
        )}
        {status !== "skipped" && status !== "completed" && (
          <button
            onClick={onSkip}
            disabled={busy}
            className="inline-flex items-center gap-1 px-2 py-1 text-xs border border-[var(--color-border)] hover:bg-[var(--color-bg)] disabled:opacity-50"
          >
            <SkipForward size={11} /> 跳过
          </button>
        )}
      </div>
    </div>
  );
}
