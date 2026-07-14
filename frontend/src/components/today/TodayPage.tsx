"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Clock, Loader2 } from "lucide-react";
import { useSecretaryDashboard } from "@/hooks/useSecretaryDashboard";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import { authedFetch } from "@/lib/api/api";
import type {
  DashboardFocus,
  DashboardRecommendations,
  DashboardActivity,
} from "@/lib/api/secretary-dashboard-api";

// ── 视图模型（叙事驱动） ──────────────────────────────────

interface TodayViewModel {
  greeting: string;
  date: string;
  /** 苹果果的观察：一段完整的第一人称叙事 */
  observation: string;
  /** 聚焦卡片 */
  focusCard: {
    title: string;
    description: string;
    estimatedMinutes: number;
  } | null;
  /** 做完之后的预期 */
  afterPlan: string;
  /** 焦点标题（用于创建 Session） */
  focusTitle: string;
}

function buildViewModel(data: {
  greeting: string;
  date: string;
  focus: DashboardFocus | null;
  recommendations: DashboardRecommendations;
  activities: { items: DashboardActivity[] };
}): TodayViewModel {
  const { greeting, date, focus, recommendations, activities } = data;
  const { suggestion, urgent, building, new_topic } = recommendations;

  // ── Observation：一段叙事 ──
  const observation = buildObservation(activities.items, urgent, building, suggestion);

  // ── Focus Card ──
  const focusCard = buildFocusCard(focus, urgent, building, new_topic);

  // ── After Plan ──
  const topItem = urgent[0] ?? building[0] ?? new_topic[0];
  const afterPlan = buildAfterPlan(topItem);

  return {
    greeting,
    date,
    observation,
    focusCard,
    afterPlan,
    focusTitle: focus?.title || topItem?.label || "",
  };
}

/** 构建「苹果果的观察」叙事文本 */
function buildObservation(
  activities: DashboardActivity[],
  urgent: { label: string }[],
  building: { label: string }[],
  suggestion: string,
): string {
  const parts: string[] = [];

  // 1. 昨天回顾（若能说人话）
  const completed = activities.filter((a) => a.status === "completed").slice(0, 3);
  if (completed.length === 1) {
    parts.push(`昨天我们一起完成了「${completed[0].title}」。`);
  } else if (completed.length === 2) {
    parts.push(`昨天我们一起完成了「${completed[0].title}」和「${completed[1].title}」。`);
  } else if (completed.length >= 3) {
    parts.push(
      `昨天我们一起完成了三件事：「${completed[0].title}」、「${completed[1].title}」和「${completed[2].title}」。`,
    );
  }

  // 2. 苹果果的发现
  if (urgent.length > 0 && building.length > 0) {
    parts.push(`我注意到你在「${building[0].label}」上进步很快，「${urgent[0].label}」还需要再巩固一下。`);
  } else if (urgent.length > 0) {
    parts.push(`我注意到「${urgent[0].label}」是你当前最值得突破的方向。`);
  } else if (building.length > 0) {
    parts.push(`我注意到你在「${building[0].label}」上正在稳步前进。`);
  } else if (suggestion) {
    parts.push(suggestion);
  }

  // 3. 如果什么都没有，给一个温和的开场
  if (parts.length === 0) {
    parts.push("我还在慢慢了解你的学习节奏。完成几次学习后，我会更清楚你适合什么。");
  }

  return parts.join("");
}

/** 构建聚焦卡片 */
function buildFocusCard(
  focus: DashboardFocus | null,
  urgent: { label: string; subject?: string; p_known?: number }[],
  building: { label: string; subject?: string; p_known?: number }[],
  new_topic: { label: string; subject?: string; p_known?: number }[],
): TodayViewModel["focusCard"] {
  if (focus && focus.title) {
    return {
      title: focus.title,
      description: focus.description || "",
      estimatedMinutes: focus.estimated_minutes || 25,
    };
  }

  const item = urgent[0] ?? building[0] ?? new_topic[0];
  if (!item) return null;

  const subjectHint = item.subject ? `（${item.subject}）` : "";
  return {
    title: `${item.label}${subjectHint}`,
    description: "",
    estimatedMinutes: 25,
  };
}

/** 构建「做完以后」叙事 */
function buildAfterPlan(item: { label: string; p_known?: number } | undefined): string {
  if (!item) return "完成今天的练习后，我对你的了解会更准确。";
  const pKnown = item.p_known ?? 0;
  if (pKnown > 0.6) {
    return `做完以后，你对「${item.label}」的理解会更深入，距离熟练掌握就更近一步了。`;
  }
  return `做完以后，你对「${item.label}」的理解会比现在更扎实。`;
}

// ── 加载骨架屏 ────────────────────────────────────────────

function TodaySkeleton() {
  return (
    <div className="max-w-lg mx-auto space-y-5 px-4 py-10">
      <Skeleton variant="title" className="w-40 mb-2" />
      <Skeleton variant="text" className="w-24" />
      <div className="pt-2 space-y-2">
        <Skeleton variant="text" className="w-full" />
        <Skeleton variant="text" className="w-3/4" />
      </div>
      <Skeleton variant="card" className="h-28 mt-4" />
      <Skeleton variant="text" className="w-2/3 mt-2" />
      <div className="flex justify-center pt-4">
        <Skeleton variant="button" className="w-40 h-12" />
      </div>
    </div>
  );
}

// ── 主组件 ────────────────────────────────────────────────

export default function TodayPage() {
  const router = useRouter();
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const { data, loading, error, refetch } = useSecretaryDashboard();

  // ── 创建 Session 的通用 handler ──
  const handleCreateSession = useCallback(
    async (params: { title: string; focus: string; goal: string; estimatedMinutes: number }) => {
      setCreateError(null);
      setCreating(true);
      try {
        const res = await authedFetch("/api/session", {
          method: "POST",
          body: JSON.stringify({
            title: params.title,
            focus: params.focus,
            goal: params.goal,
            estimated_minutes: params.estimatedMinutes,
          }),
        });
        if (!res.ok) {
          const text = await res.text().catch(() => "");
          setCreateError("今天没能顺利开始，我们再试一次。");
          console.error("Create session failed:", res.status, text);
          return;
        }
        const json = await res.json();
        router.push(`/session/${json.session_id}`);
      } catch (e) {
        setCreateError("好像网络不太好，我们再试一次。");
        console.error("Create session error:", e);
      } finally {
        setCreating(false);
      }
    },
    [router],
  );

  // ── Loading ──
  if (loading) return <TodaySkeleton />;

  // ── Error ──
  if (error) {
    return (
      <div className="max-w-lg mx-auto px-4 py-10">
        <ErrorState
          title="加载失败"
          message="无法获取今日学习建议，请稍后重试。"
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  // ── 无数据（新用户） ──
  if (!data) {
    return (
      <div className="max-w-lg mx-auto px-4 py-10">
        <EmptyState
          icon="🍎"
          title="欢迎来到苹果果"
          description="我是你的 AI 学习伙伴。开始第一次学习后，我会在这里为你生成每日学习建议。"
          action={
            <Button
              variant="primary"
              disabled={creating}
              onClick={() =>
                handleCreateSession({
                  title: "",
                  focus: "",
                  goal: "",
                  estimatedMinutes: 25,
                })
              }
            >
              {creating ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  正在准备今天...
                </>
              ) : (
                <>
                  开始第一次学习
                  <ArrowRight size={16} />
                </>
              )}
            </Button>
          }
        />
        {createError && (
          <p className="text-center text-sm text-red-500 mt-4">{createError}</p>
        )}
      </div>
    );
  }

  const vm = buildViewModel(data);
  const hasFocus = vm.focusCard !== null;

  return (
    <div className="max-w-lg mx-auto px-4 py-8 sm:py-10">

      {/* ── 问候 ── */}
      <div className="mb-6">
        <h1 className="text-3xl sm:text-4xl font-bold text-ink-primary mb-1">
          🍎 {vm.greeting}
        </h1>
        <p className="text-sm text-ink-muted">{vm.date}</p>
      </div>

      {/* ── 苹果果的观察（一段叙事） ── */}
      <p className="text-sm leading-relaxed text-ink-secondary mb-6">
        {vm.observation}
      </p>

      {hasFocus ? (
        <>
          {/* ── 今天想带你做的 ── */}
          <p className="text-sm text-ink-secondary mb-3">
            今天我想带你一起：
          </p>

          <div className="mb-6 p-5 rounded-xl bg-surface border border-border/60">
            <h2 className="text-lg font-semibold text-ink-primary mb-1">
              {vm.focusCard!.title}
            </h2>
            {vm.focusCard!.description && (
              <p className="text-sm text-ink-secondary mb-3">
                {vm.focusCard!.description}
              </p>
            )}
            {vm.focusCard!.estimatedMinutes > 0 && (
              <div className="flex items-center gap-1.5 text-xs text-ink-muted">
                <Clock size={13} />
                <span>大概需要 {vm.focusCard!.estimatedMinutes} 分钟</span>
              </div>
            )}
          </div>

          {/* ── 做完以后 ── */}
          {vm.afterPlan && (
            <p className="text-sm text-ink-secondary mb-8">
              {vm.afterPlan}
            </p>
          )}

          {/* ── CTA ── */}
          <div className="flex flex-col items-center gap-2">
            <Button
              variant="primary"
              size="lg"
              disabled={creating}
              onClick={() =>
                handleCreateSession({
                  title: vm.focusTitle || "",
                  focus: vm.focusTitle || "",
                  goal: vm.focusCard?.description || "",
                  estimatedMinutes: vm.focusCard?.estimatedMinutes || 25,
                })
              }
              className="text-base px-10 py-3 rounded-full shadow-md"
            >
              {creating ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  正在准备今天...
                </>
              ) : (
                <>
                  开始今天
                  <ArrowRight size={18} />
                </>
              )}
            </Button>
            {vm.focusCard && vm.focusCard.estimatedMinutes > 0 && (
              <p className="text-xs text-ink-muted">
                不用一次学完
              </p>
            )}
            {createError && (
              <p className="text-xs text-red-500 mt-1">{createError}</p>
            )}
          </div>
        </>
      ) : (
        /* ── 无焦点卡片时：简单提示 ── */
        <div className="text-center pt-8">
          <p className="text-sm text-ink-secondary mb-6">
            我还在准备今天的学习计划。先开始一次自由学习吧。
          </p>
          <Button
            variant="primary"
            size="lg"
            disabled={creating}
            onClick={() =>
              handleCreateSession({
                title: "",
                focus: "",
                goal: "",
                estimatedMinutes: 25,
              })
            }
            className="text-base px-10 py-3 rounded-full shadow-md"
          >
            {creating ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                正在准备今天...
              </>
            ) : (
              <>
                开始学习
                <ArrowRight size={18} />
              </>
            )}
          </Button>
          {createError && (
            <p className="text-xs text-red-500 mt-3">{createError}</p>
          )}
        </div>
      )}
    </div>
  );
}
