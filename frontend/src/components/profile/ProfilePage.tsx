"use client";

import { useState, useEffect } from "react";
import {
  Target, BookOpen, Sparkles, TrendingUp, Loader2, Clock,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { authedFetch } from "@/lib/api/api";

// ── 类型 ──────────────────────────────────────────────────

interface TimelineEntry {
  date: string;
  title: string;
  summary: string;
  key_takeaways: string[];
}

interface ProfileData {
  narrative: string;
  profile: {
    user_id: string;
    nickname: string;
    subjects: string[];
    learning_style: string;
    persona: { type: string; confidence: number };
    updated_at: string | null;
  };
  goals: {
    id: string;
    title: string;
    status: string;
    progress_pct: number;
  }[];
  growth_summary: {
    total_sessions: number;
    total_duration_minutes: number;
    total_gain_score: number;
    streak_days: number;
  };
  growth_narrative: string;
  timeline: TimelineEntry[];
}

// ── 组件 ──────────────────────────────────────────────────

export default function ProfilePage() {
  const [data, setData] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadProfile();
  }, []);

  async function loadProfile() {
    setLoading(true);
    setError(null);
    try {
      const res = await authedFetch("/api/profile");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json as ProfileData);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  // ── Loading ──
  if (loading) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  // ── Error ──
  if (error) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-12 text-center">
        <p className="text-red-500 mb-4">加载失败：{error}</p>
        <Button variant="outline" onClick={loadProfile}>重试</Button>
      </div>
    );
  }

  if (!data) return null;

  const { narrative, growth_narrative, goals, timeline } = data;
  const activeGoals = goals.filter((g) => g.status === "active");
  const hasTimeline = timeline.length > 0;

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-8">

      {/* ── 🍎 苹果果眼中的你 ── */}
      <section className="bg-card border rounded-xl p-6 space-y-3">
        <div className="flex items-center gap-2 text-primary">
          <Sparkles className="w-5 h-5" />
          <h2 className="text-lg font-semibold">苹果果眼中的你</h2>
        </div>
        <p className="text-sm leading-relaxed text-card-foreground/85">
          {narrative || "苹果果还在慢慢了解你。完成第一次学习后，这里会出现苹果果对你的认识。"}
        </p>
        <p className="text-xs text-muted-foreground">
          苹果果根据你的学习行为生成。完成的学习越多，认识越准确。
        </p>
      </section>

      {/* ── 你的成长 ── */}
      <section className="bg-card border rounded-xl p-6 space-y-3">
        <div className="flex items-center gap-2 text-green-600">
          <TrendingUp className="w-5 h-5" />
          <h2 className="text-lg font-semibold">你的成长</h2>
        </div>
        <p className="text-sm leading-relaxed text-card-foreground/85">
          {growth_narrative || "完成第一次学习后，这里会开始记录你的成长轨迹。"}
        </p>
      </section>

      {/* ── 正在努力 ── */}
      <section className="bg-card border rounded-xl p-6 space-y-4">
        <div className="flex items-center gap-2 text-amber-600">
          <Target className="w-5 h-5" />
          <h2 className="text-lg font-semibold">正在努力</h2>
        </div>

        {activeGoals.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-4">
            完成一次学习后，苹果果会帮你建立第一个目标。
          </p>
        ) : (
          <div className="space-y-3">
            {activeGoals.map((goal) => (
              <div
                key={goal.id}
                className="flex items-start gap-3 p-3 rounded-lg bg-secondary/30"
              >
                <BookOpen className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{goal.title}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── 最近学会了什么 ── */}
      <section className="bg-card border rounded-xl p-6 space-y-4">
        <div className="flex items-center gap-2 text-blue-600">
          <Clock className="w-5 h-5" />
          <h2 className="text-lg font-semibold">最近学会了什么</h2>
        </div>

        {!hasTimeline ? (
          <p className="text-sm text-muted-foreground text-center py-4">
            完成学习后，这里会记录你每一次的收获。
          </p>
        ) : (
          <div className="space-y-4">
            {timeline.map((entry, i) => (
              <div key={i} className="flex gap-3">
                {/* 时间线竖线 */}
                <div className="flex flex-col items-center shrink-0">
                  <div className="w-2 h-2 rounded-full bg-blue-400 mt-1.5" />
                  {i < timeline.length - 1 && (
                    <div className="w-px flex-1 bg-border mt-1" />
                  )}
                </div>
                <div className="min-w-0 pb-2">
                  <p className="text-sm font-medium">{entry.title || "一次学习"}</p>
                  {entry.summary && (
                    <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                      {entry.summary}
                    </p>
                  )}
                  {entry.key_takeaways.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {entry.key_takeaways.map((t, j) => (
                        <span
                          key={j}
                          className="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-100"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

    </div>
  );
}
