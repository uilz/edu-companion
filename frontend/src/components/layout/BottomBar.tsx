// ============================================================
// BottomBar — 底栏 (任务 #76)
//
// 设计目标：
//   - 高度 40px (默认)，可被 Workbench 拖动调整
//   - 4 个区域：心情压力 mini 卡片 / 通知 / 快速记录 / 今日进度
//   - 信息密度高，单行展示
//
// 数据源：
//   - 心情压力：/api/secretary/mood_stress/dashboard
//   - 通知：/api/secretary/proposals/pending
//   - 今日进度：/api/planning/daily
//
// SSR 安全：所有 API 失败回退到占位
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Heart,
  Bell,
  Plus,
  TrendingUp,
  Smile,
  Activity,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api/api";

// ── 类型 ──
interface MoodSnapshot {
  emotion_label?: string;
  pressure_score?: number;
  energy_score?: number;
  taken_at?: string;
}

interface DailySummary {
  total: number;
  done: number;
  date: string;
}

export default function BottomBar() {
  const { user } = useAuth();
  const router = useRouter();

  // ── 心情压力 ──
  const [mood, setMood] = useState<MoodSnapshot | null>(null);
  const [moodLoading, setMoodLoading] = useState(true);

  // ── 通知数 ──
  const [notifCount, setNotifCount] = useState(0);

  // ── 今日进度 ──
  const [daily, setDaily] = useState<DailySummary | null>(null);

  useEffect(() => {
    if (!user) return;
    let active = true;

    // 心情压力
    api<any>("/api/secretary/mood_stress/dashboard?days=1")
      .then((data) => {
        if (!active) return;
        // 最新一条手动记录
        const manual = data?.manual_records?.[0] || data?.records?.[0];
        if (manual) {
          setMood({
            emotion_label: manual.emotion_label || manual.emotion_tags?.[0] || "未记录",
            pressure_score: manual.pressure_score,
            energy_score: manual.energy_score,
            taken_at: manual.taken_at || manual.recorded_at,
          });
        }
      })
      .catch(() => {})
      .finally(() => active && setMoodLoading(false));

    // 通知
    api<any[]>(`/api/secretary/proposals/pending?user_id=${user.id}`)
      .then((arr) => {
        if (Array.isArray(arr)) setNotifCount(arr.length);
      })
      .catch(() => {});

    // 今日规划
    api<any>("/api/planning/daily")
      .then((d) => {
        if (!active) return;
        const items = d?.timeline_items || d?.items || [];
        const total = Array.isArray(items) ? items.length : 0;
        const done = Array.isArray(items)
          ? items.filter((it: any) => it.status === "completed" || it.status === "done").length
          : 0;
        setDaily({ total, done, date: d?.date || "" });
      })
      .catch(() => {});

    return () => {
      active = false;
    };
  }, [user]);

  // 快速记录：跳到秘书页
  const onQuickRecord = () => router.push("/secretary");

  // 心情图标选择
  const moodIcon = (() => {
    if (moodLoading) return <Activity size={14} className="animate-pulse text-ink-muted" />;
    if (!mood) return <Smile size={14} className="text-ink-muted" />;
    const p = mood.pressure_score ?? 0;
    if (p >= 7) return <Activity size={14} className="text-red-500" />;
    if (p >= 4) return <Heart size={14} className="text-amber-500" />;
    return <Smile size={14} className="text-green-500" />;
  })();

  // 进度条
  const progress = daily && daily.total > 0 ? Math.round((daily.done / daily.total) * 100) : 0;

  return (
    <div
      className="h-full w-full flex items-center gap-3 px-3 bg-page border-t border-divider text-[12px] text-ink-secondary"
      style={{ minHeight: 32 }}
    >
      {/* 心情压力 mini 卡片 */}
      <button
        onClick={() => router.push("/emotion")}
        className="flex items-center gap-1.5 px-2 h-7 rounded hover:bg-surface-hover transition-colors"
        title="心情压力"
      >
        {moodIcon}
        <span className="text-ink-primary">
          {mood?.emotion_label || "未记录"}
        </span>
        {mood?.pressure_score != null && (
          <span className="text-ink-muted">·压 {mood.pressure_score}</span>
        )}
      </button>

      <div className="w-px h-4 bg-divider" />

      {/* 通知 */}
      <button
        onClick={() => router.push("/secretary")}
        className="relative flex items-center gap-1.5 px-2 h-7 rounded hover:bg-surface-hover transition-colors"
        title="通知"
      >
        <Bell size={14} />
        <span>通知</span>
        {notifCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 flex items-center justify-center rounded-full bg-red-500 text-white text-[9px] font-semibold leading-none">
            {notifCount > 99 ? "99+" : notifCount}
          </span>
        )}
      </button>

      <div className="w-px h-4 bg-divider" />

      {/* 快速记录 */}
      <button
        onClick={onQuickRecord}
        className="flex items-center gap-1.5 px-2 h-7 rounded bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
        title="快速记录 (跳到秘书页)"
      >
        <Plus size={12} />
        <span>快速记录</span>
      </button>

      {/* 中部 / 右侧：进度条 */}
      <div className="flex-1" />
      {daily ? (
        <div className="flex items-center gap-2 text-ink-muted">
          <TrendingUp size={12} />
          <span className="text-ink-primary">
            今日 <span className="font-semibold text-accent">{daily.done}</span>/{daily.total}
          </span>
          <div className="w-24 h-1.5 rounded-full bg-surface overflow-hidden">
            <div
              className="h-full bg-accent transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="text-[10px] tabular-nums">{progress}%</span>
        </div>
      ) : (
        <span className="text-ink-muted text-[11px]">—</span>
      )}
    </div>
  );
}
