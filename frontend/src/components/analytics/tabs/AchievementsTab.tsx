"use client";

import { useState, useEffect, useCallback } from "react";
import { authedFetch } from "@/lib/api/api";
import {
  Trophy, Loader2, RefreshCw,
} from "lucide-react";
import Card from "@/components/ui/Card";

interface Achievement {
  id: string;
  name: string;
  icon: string;
  tier: string;
  description: string;
  unlocked: boolean;
  level: number;
  max_level: number;
  progress: number;
  progress_label: string;
  unlocked_at: string | null;
}

interface BadgeStats {
  total_unlocked: number;
  total_possible: number;
  bronze: number;
  silver: number;
  gold: number;
}

const TIER_CONFIG: Record<string, { label: string; color: string; bg: string; border: string }> = {
  bronze: { label: "青铜", color: "text-amber-700", bg: "bg-amber-50 dark:bg-amber-950/30", border: "border-amber-400/50" },
  silver: { label: "白银", color: "text-slate-500", bg: "bg-slate-50 dark:bg-slate-900/50", border: "border-slate-300/50" },
  gold: { label: "黄金", color: "text-yellow-600", bg: "bg-yellow-50 dark:bg-yellow-950/30", border: "border-yellow-400/50" },
};

/** 成就墙标签（嵌入 analytics 页面使用，也可独立路由访问） */
export default function AchievementsTab() {
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [stats, setStats] = useState<BadgeStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [ach, st] = await Promise.all([
        authedFetch("/api/practice/achievements").then(r => r.json()),
        authedFetch("/api/practice/achievements/stats").then(r => r.json()),
      ]);
      setAchievements(ach);
      setStats(st);
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const filtered = filter === "all"
    ? achievements
    : achievements.filter((a) => a.tier === filter);

  if (loading && achievements.length === 0) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="animate-spin text-[var(--color-accent)]" size={24} />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-[var(--color-text)] tracking-tight flex items-center gap-2">
          <Trophy size={22} className="text-yellow-500" />
          成就墙
        </h1>
        <button onClick={loadData} className="p-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]/60 text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors">
          <RefreshCw size={14} />
        </button>
      </div>

      {stats && (
        <div className="grid grid-cols-4 gap-3 mb-6">
          {[
            { label: "已解锁", value: `${stats.total_unlocked}/${stats.total_possible}`, icon: <Trophy size={16} className="text-yellow-500" /> },
            { label: "青铜", value: stats.bronze, icon: <span className="text-lg">🥉</span> },
            { label: "白银", value: stats.silver, icon: <span className="text-lg">🥈</span> },
            { label: "黄金", value: stats.gold, icon: <span className="text-lg">🥇</span> },
          ].map((c, i) => (
            <div key={i} className="p-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/60 text-center">
              <div className="mb-1">{c.icon}</div>
              <div className="text-xl font-bold text-[var(--color-text)]">{c.value}</div>
              <div className="text-[10px] text-[var(--color-text-muted)]">{c.label}</div>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2 mb-4">
        {[
          { key: "all", label: `全部 (${achievements.length})` },
          { key: "bronze", label: "青铜" },
          { key: "silver", label: "白银" },
          { key: "gold", label: "黄金" },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setFilter(t.key)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              filter === t.key
                ? "bg-[var(--color-accent)] text-white"
                : "bg-[var(--color-surface)] border border-[var(--color-border)]/60 text-[var(--color-text-muted)] hover:border-[var(--color-accent)]/30"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {filtered.map((ach) => {
          const cfg = TIER_CONFIG[ach.tier] || TIER_CONFIG.bronze;
          const isUnlocked = ach.unlocked;
          return (
            <div
              key={`${ach.id}_${ach.level}`}
              className={`rounded-xl border p-4 transition-all ${
                isUnlocked
                  ? `${cfg.bg} ${cfg.border}`
                  : "bg-[var(--color-surface)] border-[var(--color-border)]/40 opacity-60"
              }`}
            >
              <div className="flex items-start gap-3">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-xl ${
                  isUnlocked ? cfg.bg : "bg-[var(--color-bg)]"
                }`}>
                  {isUnlocked ? ach.icon : "🔒"}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`text-sm font-semibold ${
                      isUnlocked ? "text-[var(--color-text)]" : "text-[var(--color-text-muted)]"
                    }`}>
                      {ach.name}
                    </span>
                    {ach.max_level > 1 && (
                      <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${
                        isUnlocked ? `${cfg.bg} ${cfg.color}` : "bg-[var(--color-bg)] text-[var(--color-text-muted)]"
                      }`}>
                        Lv{ach.level}/{ach.max_level}
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">
                    {ach.description}
                  </p>
                  <div className="mt-2">
                    <div className="w-full h-1.5 bg-[var(--color-border)] rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          isUnlocked ? "bg-[var(--color-accent)]" : "bg-[var(--color-border)]"
                        }`}
                        style={{ width: `${Math.min(ach.progress * 100, 100)}%` }}
                      />
                    </div>
                    <div className="flex items-center justify-between mt-1">
                      <span className="text-[9px] text-[var(--color-text-muted)]">
                        {ach.progress_label}
                      </span>
                      {isUnlocked && ach.unlocked_at && (
                        <span className="text-[9px] text-[var(--color-text-muted)]">
                          {ach.unlocked_at.slice(0, 10)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-12">
          <Trophy size={32} className="text-[var(--color-text-muted)] mx-auto mb-2" />
          <p className="text-sm text-[var(--color-text-muted)]">暂无成就</p>
        </div>
      )}
    </div>
  );
}
