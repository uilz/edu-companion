"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { BarChart3 } from "lucide-react";
import { authedFetch } from "@/lib/api/api";
import { Skeleton } from "@/components/ui/Skeleton";

// ── 类型 ──

interface TimelineItem {
  id: string;
  date: number;
  title: string;
  summary: string;
  is_latest: boolean;
}

interface GrowthSummary {
  total_sessions: number;
  total_duration_minutes: number;
  total_skill_gains: number;
  total_gain_score: number;
  streak_days: number;
  recent_records: unknown[];
  growth_narrative: string;
  timeline: TimelineItem[];
}

// ── 页面组件 ──

export default function GrowthPage() {
  const [summary, setSummary] = useState<GrowthSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await authedFetch("/api/growth/summary");
        if (res.ok) setSummary(await res.json());
      } catch (e) {
        console.error("Growth load failed:", e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  // ── Loading ──
  if (loading) return <GrowthSkeleton />;

  const timeline = summary?.timeline ?? [];

  // ── Empty ──
  if (timeline.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 px-6">
        <div className="w-16 h-16 rounded-2xl bg-accent/10 flex items-center justify-center">
          <BarChart3 size={32} className="text-accent" />
        </div>
        <h2 className="text-xl font-bold text-ink-primary">还没有成长记录</h2>
        <p className="text-ink-muted text-sm text-center max-w-xs">
          完成一次学习 Session 后，这里会展示你的成长轨迹
        </p>
        <Link
          href="/"
          className="text-ink-link text-sm font-medium hover:underline"
        >
          返回首页开始学习 →
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen bg-page px-4 py-4">
      <h1 className="text-title font-bold text-ink-primary mb-space-5">
        你的成长
      </h1>

      {/* ── 成长叙事 ── */}
      {summary?.growth_narrative && (
        <div
          className="bg-surface rounded-lg p-space-5 mb-space-6 text-[17px] leading-[1.7] text-ink-primary shadow-[0_0_0_1px_var(--color-divider-soft)]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          {summary.growth_narrative}
        </div>
      )}

      {/* ── 时间线 ── */}
      <div className="flex flex-col gap-space-3">
        {timeline.map((item) => (
          <TimelineItem key={item.id} item={item} />
        ))}
      </div>
    </div>
  );
}

// ── 时间线项 ──

function TimelineItem({ item }: { item: TimelineItem }) {
  return (
    <div
      className={`bg-surface rounded-md p-4 transition-shadow ${
        item.is_latest
          ? "ring-2 ring-accent shadow-glow"
          : "shadow-[0_0_0_1px_var(--color-divider-soft)]"
      }`}
    >
      <div className="text-xs text-ink-muted mb-1.5">
        {formatRelativeTime(item.date)}
      </div>
      <h3 className="text-base font-semibold text-ink-primary mb-1">
        {item.title || "学习 Session"}
      </h3>
      <p className="text-sm text-ink-secondary leading-relaxed">
        {item.summary}
      </p>
    </div>
  );
}

function formatRelativeTime(startedAtSeconds: number): string {
  const now = new Date();
  const date = new Date(startedAtSeconds * 1000);
  const diffSec = Math.floor(
    (now.getTime() - date.getTime()) / 1000,
  );

  if (diffSec < 3600) {
    return "刚才";
  }

  const nowDay = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
  );
  const dateDay = new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
  );
  const dayDiff = Math.floor(
    (nowDay.getTime() - dateDay.getTime()) / (1000 * 86400),
  );

  if (dayDiff === 0) return "今天";
  if (dayDiff === 1) return "昨天";
  if (dayDiff < 7) return `${dayDiff} 天前`;
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}

// ── 骨架屏 ──

function GrowthSkeleton() {
  return (
    <div className="flex flex-col min-h-screen bg-page px-4 py-4">
      <Skeleton className="h-8 w-32 mb-space-5" />
      <Skeleton className="h-28 rounded-lg mb-space-6" />
      <div className="flex flex-col gap-space-3">
        <Skeleton className="h-20 rounded-md" />
        <Skeleton className="h-20 rounded-md" />
        <Skeleton className="h-20 rounded-md" />
      </div>
    </div>
  );
}
