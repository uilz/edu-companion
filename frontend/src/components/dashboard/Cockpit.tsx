// ============================================================
// Cockpit — 智能驾驶舱 (任务 #76 / #78 / #79)
//
// 设计目标：
//   当用户进入 / 或 /dashboard 时，主区渲染此组件（所有设备统一）
//   - 1 焦点：今日该做什么（调 /api/planning/daily）
//   - 3 数据卡：调 /api/practice/stats/overview
//   - 连续天数：调 /api/progress/{user_id}/summary
//   - AI 推荐：调 /api/interest/push/today
//   - 时间线：调 /api/planning/daily.timeline_items
//
// 风格遵循 design-language.md professional 风格 (任务 #79 精修)：
//   - 颜色：slate 中性 + 蓝 #2563EB 强调
//   - 字体：Inter 14-16px / 数字 tabular-nums 28px
//   - 圆角：8-12px（卡片 12px）
//   - 阴影：sm 默认 + md hover
//   - 间距：4/8/12/16/24
//   - 动效：transition 150ms ease-out
// ============================================================

"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import {
  Sparkles,
  Calendar,
  Lightbulb,
  Clock,
  CheckCircle2,
  Circle,
  ArrowRight,
  Brain,
  Target,
  Loader2,
  BarChart3,
  Compass,
  Heart,
  MessageSquare,
  RotateCcw,
  Inbox,
  type LucideIcon,
} from "lucide-react";
import { api } from "@/lib/api/api";
import { useAuth } from "@/contexts/AuthContext";

// ── 类型 ──
interface TimelineItem {
  id: string;
  title: string;
  status: string;
  scheduled_for?: string;
  source_module?: string;
}

interface DailyData {
  date?: string;
  timeline_items?: TimelineItem[];
  brief_summary?: string | { summary: string; payload?: Record<string, unknown> };
  status_bar?: any;
  pending_pool?: any[];
  adaptive_recommendations?: any[];
}

interface AnalyticsData {
  // 来自 /api/practice/stats/overview
  total_questions?: number;
  study_minutes?: number;
  mastered_count?: number;
  today_questions?: number;
  accuracy?: number;
  // 来自 /api/progress/{user_id}/summary
  streak_days?: number;
}

interface InterestItem {
  id: string;
  title: string;
  source?: string;
  summary?: string;
  url?: string;
}

export default function Cockpit() {
  const { user } = useAuth();
  const router = useRouter();

  const [daily, setDaily] = useState<DailyData | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [interest, setInterest] = useState<InterestItem[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const [d, a, i, s] = await Promise.allSettled([
        api<DailyData>("/api/planning/daily").catch(() => null),
        api<AnalyticsData>("/api/practice/stats/overview").catch(() => null),
        api<{ items?: InterestItem[] }>("/api/interest/push/today").catch(() => null),
        api<{ streak?: number }>(`/api/progress/${user.id}/summary`).catch(() => null),
      ]);
      if (d.status === "fulfilled" && d.value) setDaily(d.value);
      if (a.status === "fulfilled" && a.value) {
        const overview = a.value;
        const streak = s.status === "fulfilled" ? s.value?.streak : undefined;
        setAnalytics({ ...overview, streak_days: streak });
      }
      if (i.status === "fulfilled" && i.value) {
        const data = i.value as any;
        setInterest(data?.items || data?.pushes || data?.recommendations || []);
      }
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // 今日焦点
  const focus = useMemo(() => {
    if (!daily?.timeline_items) return null;
    const items = daily.timeline_items;
    const pending = items.find(
      (it) => it.status !== "completed" && it.status !== "done",
    );
    return pending || items[0] || null;
  }, [daily]);

  if (loading) {
    return <CockpitSkeleton />;
  }

  return (
    <div className="h-full overflow-y-auto bg-page">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-5 space-y-4">
        {/* 标题区 */}
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-[22px] font-semibold text-ink-primary tracking-tight">
              智能驾驶舱
            </h1>
            <p className="text-[13px] text-ink-secondary mt-1">
              {daily?.date || new Date().toLocaleDateString("zh-CN")} ·{" "}
              {user?.display_name || user?.username || "欢迎"}
            </p>
          </div>
          <button
            onClick={fetchAll}
            className="flex items-center gap-1.5 px-2.5 h-8 text-[13px] text-ink-secondary hover:text-ink-primary hover:bg-surface-hover rounded-md transition-colors"
            title="刷新"
          >
            <RotateCcw size={13} />
            刷新
          </button>
        </div>

        {/* 1 焦点：今日该做什么 */}
        <section
          className="cockpit-card p-5 border-accent/30"
          style={{ borderLeftWidth: "3px", borderLeftColor: "var(--color-accent)" }}
        >
          <div className="flex items-center gap-2 mb-2.5">
            <Target size={14} className="text-accent" />
            <h2 className="text-[12px] font-semibold text-ink-secondary uppercase tracking-wider">
              今日焦点
            </h2>
          </div>
          {focus ? (
            <div className="flex items-center justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="text-[16px] font-semibold text-ink-primary">
                  {focus.title}
                </div>
                {focus.scheduled_for && (
                  <div className="text-[12px] text-ink-secondary mt-1 flex items-center gap-1">
                    <Clock size={11} />
                    {focus.scheduled_for}
                  </div>
                )}
              </div>
              <button
                onClick={() => router.push("/planning")}
                className="flex items-center gap-1.5 px-3.5 h-9 rounded-md bg-accent text-white text-[13px] font-medium hover:bg-accent-hover active:scale-[0.98] transition-all shrink-0 shadow-sm"
              >
                开始
                <ArrowRight size={13} />
              </button>
            </div>
          ) : (
            <EmptyHint
              icon={<Inbox size={20} className="text-ink-muted" />}
              message={
                extractBriefSummary(daily?.brief_summary) ||
                "今日暂未安排任务，可到「规划」页面创建。"
              }
            />
          )}
        </section>

        {/* 3 数据卡 */}
        <section className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <DataCard
            icon={Brain}
            label="累计练习"
            value={analytics?.total_questions ?? 0}
            hint={
              analytics?.today_questions
                ? `今日 ${analytics.today_questions} 题`
                : "今日 0 题"
            }
          />
          <DataCard
            icon={Clock}
            label="学习时长"
            value={`${analytics?.study_minutes ?? 0}m`}
            hint={
              analytics?.accuracy != null
                ? `正确率 ${Math.round(analytics.accuracy)}%`
                : "今日 0m"
            }
          />
          <DataCard
            icon={Target}
            label="已掌握"
            value={analytics?.mastered_count ?? 0}
            hint={
              analytics?.streak_days
                ? `连续 ${analytics.streak_days} 天`
                : "知识原子"
            }
          />
        </section>

        {/* AI 推荐 */}
        <section className="cockpit-card p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Sparkles size={14} className="text-warning" />
              <h2 className="text-[12px] font-semibold text-ink-secondary uppercase tracking-wider">
                AI 推荐
              </h2>
            </div>
            <button
              onClick={() => router.push("/interest")}
              className="text-[12px] text-ink-secondary hover:text-accent flex items-center gap-1 transition-colors"
            >
              更多
              <ArrowRight size={11} />
            </button>
          </div>
          {interest.length === 0 ? (
            <EmptyHint
              icon={<Lightbulb size={20} className="text-ink-muted" />}
              message="今日暂无推荐 — 到「兴趣探索」添加信息源"
            />
          ) : (
            <div className="space-y-1.5">
              {interest.slice(0, 3).map((it) => (
                <button
                  key={it.id}
                  onClick={() => {
                    if (it.url) window.open(it.url, "_blank", "noopener");
                    else router.push("/interest");
                  }}
                  className="w-full text-left flex items-start gap-2.5 p-2.5 rounded-md hover:bg-surface-hover transition-colors"
                >
                  <Lightbulb size={14} className="text-warning mt-0.5 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-[13.5px] text-ink-primary font-medium line-clamp-1">
                      {it.title}
                    </div>
                    {it.summary && (
                      <div className="text-[12px] text-ink-secondary line-clamp-2 mt-0.5">
                        {it.summary}
                      </div>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </section>

        {/* 时间线 */}
        <section className="cockpit-card p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Calendar size={14} className="text-accent" />
              <h2 className="text-[12px] font-semibold text-ink-secondary uppercase tracking-wider">
                今日时间线
              </h2>
            </div>
            <button
              onClick={() => router.push("/planning")}
              className="text-[12px] text-ink-secondary hover:text-accent flex items-center gap-1 transition-colors"
            >
              查看全部
              <ArrowRight size={11} />
            </button>
          </div>
          {!daily?.timeline_items || daily.timeline_items.length === 0 ? (
            <EmptyHint
              icon={<Calendar size={20} className="text-ink-muted" />}
              message="今日无计划"
            />
          ) : (
            <ul className="space-y-1">
              {daily.timeline_items.slice(0, 8).map((it) => {
                const done = it.status === "completed" || it.status === "done";
                return (
                  <li
                    key={it.id}
                    className="flex items-center gap-2.5 px-2.5 py-2 rounded-md hover:bg-surface-hover transition-colors"
                  >
                    {done ? (
                      <CheckCircle2 size={15} className="text-success shrink-0" />
                    ) : (
                      <Circle size={15} className="text-ink-muted shrink-0" />
                    )}
                    <span
                      className={`flex-1 text-[13.5px] truncate ${
                        done ? "text-ink-muted line-through" : "text-ink-primary"
                      }`}
                    >
                      {it.title}
                    </span>
                    {it.scheduled_for && (
                      <span className="text-[11.5px] text-ink-secondary tabular">
                        {it.scheduled_for}
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {/* 快速跳转 */}
        <section className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <QuickLink icon={MessageSquare} label="开始对话" href="/conversation" />
          <QuickLink icon={BarChart3} label="学情分析" href="/analytics" />
          <QuickLink icon={Compass} label="兴趣探索" href="/interest" />
          <QuickLink icon={Heart} label="心情记录" href="/emotion" />
        </section>
      </div>
    </div>
  );
}

// ── 子组件 ──

/** 兼容后端返回的 string 或 { summary, payload } 两种格式 */
function extractBriefSummary(brief: DailyData["brief_summary"]): string {
  if (!brief) return "";
  if (typeof brief === "string") return brief;
  if (typeof brief === "object" && "summary" in brief) {
    return typeof brief.summary === "string" ? brief.summary : "";
  }
  return "";
}

/** Loading skeleton: 4 块 shimmer 占位，避免空白（Task #79） */
function CockpitSkeleton() {
  return (
    <div className="h-full overflow-y-auto bg-page">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-5 space-y-4">
        {/* 标题 skeleton */}
        <div>
          <div className="skeleton-block h-7 w-32" />
          <div className="skeleton-block h-4 w-48 mt-2" />
        </div>
        {/* 焦点 skeleton */}
        <div className="cockpit-card p-5">
          <div className="skeleton-block h-3.5 w-20 mb-3" />
          <div className="skeleton-block h-5 w-64" />
        </div>
        {/* 3 数据卡 skeleton */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="cockpit-data-card">
              <div className="skeleton-block h-3.5 w-16 mb-3" />
              <div className="skeleton-block h-7 w-20 mb-2" />
              <div className="skeleton-block h-3 w-24" />
            </div>
          ))}
        </div>
        {/* AI 推荐 / 时间线 skeleton */}
        {[0, 1].map((i) => (
          <div key={i} className="cockpit-card p-5">
            <div className="skeleton-block h-3.5 w-24 mb-4" />
            <div className="space-y-2.5">
              <div className="skeleton-block h-4 w-full" />
              <div className="skeleton-block h-4 w-3/4" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** 空态：图标 + 引导文字（Task #79） */
function EmptyHint({ icon, message }: { icon: React.ReactNode; message: string }) {
  return (
    <div className="flex items-center gap-3 py-3 px-1">
      <div className="w-9 h-9 rounded-md bg-surface-hover flex items-center justify-center shrink-0">
        {icon}
      </div>
      <div className="text-[13px] text-ink-secondary flex-1">{message}</div>
    </div>
  );
}

function DataCard({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: LucideIcon;
  label: string;
  value: number | string;
  hint?: string;
}) {
  return (
    <div className="cockpit-data-card">
      <div className="flex items-center gap-1.5 text-ink-secondary text-[11.5px] font-medium uppercase tracking-wider">
        <Icon size={12} />
        {label}
      </div>
      <div className="text-[28px] font-semibold text-ink-primary mt-2 leading-none tabular">
        {value}
      </div>
      {hint && (
        <div className="text-[11.5px] text-ink-secondary mt-2 tabular">
          {hint}
        </div>
      )}
    </div>
  );
}

function QuickLink({
  icon: Icon,
  label,
  href,
}: {
  icon: LucideIcon;
  label: string;
  href: string;
}) {
  const router = useRouter();
  return (
    <button
      onClick={() => router.push(href)}
      className="cockpit-card flex items-center gap-2 px-3.5 py-3 text-[13px] text-ink-primary text-left"
    >
      <Icon size={14} className="text-accent shrink-0" />
      <span className="flex-1 font-medium">{label}</span>
      <ArrowRight size={12} className="text-ink-muted shrink-0" />
    </button>
  );
}
