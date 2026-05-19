"use client";

import { useState, useEffect } from "react";
import { Award, Loader2, Lock } from "lucide-react";
import Card from "@/components/ui/Card";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Achievement {
  id: string;
  name: string;
  icon: string;
  tier: "bronze" | "silver" | "gold";
  description: string;
  unlocked: boolean;
  level: number;
  max_level: number;
  progress: number;
  progress_label: string;
  unlocked_at: string | null;
}

const TIER_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  bronze: { bg: "#92400e20", border: "#92400e", text: "#d97706" },
  silver: { bg: "#64748b20", border: "#64748b", text: "#94a3b8" },
  gold: { bg: "#b4530920", border: "#b45309", text: "#f59e0b" },
};

export default function AchievementsPage() {
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/achievements/default_user`)
      .then((r) => r.json())
      .then((d) => setAchievements(d.achievements || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const unlockedCount = achievements.filter((a) => a.unlocked).length;

  if (loading) {
    return (
      <main className="min-h-screen bg-[var(--color-bg)] flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-[var(--color-accent)]" />
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-4xl mx-auto px-4 md:px-6 py-8 md:py-12">
        <div className="flex items-center gap-3 mb-8">
          <Award size={28} className="text-[#f59e0b]" />
          <div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-[var(--color-text)]">
              成就墙
            </h1>
            <p className="text-xs text-[var(--color-text-muted)] mt-1">
              {unlockedCount}/{achievements.length} 已解锁
            </p>
          </div>
        </div>

        {/* Progress bar */}
        <div className="mb-8 w-full h-1.5 bg-[var(--color-surface)]">
          <div
            className="h-full bg-[#f59e0b] transition-all duration-700"
            style={{ width: `${(unlockedCount / Math.max(achievements.length, 1)) * 100}%` }}
          />
        </div>

        {/* Tiers */}
        {(["bronze", "silver", "gold"] as const).map((tier) => {
          const tierAchievements = achievements.filter((a) => a.tier === tier);
          const tierLabel = { bronze: "🥉 青铜成就", silver: "🥈 白银成就", gold: "🥇 黄金成就" }[tier];
          const colors = TIER_COLORS[tier];

          return (
            <div key={tier} className="mb-8">
              <h2
                className="text-sm font-bold mb-4 px-1"
                style={{ color: colors.text }}
              >
                {tierLabel}
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {tierAchievements.map((ach) => (
                  <div
                    key={ach.id}
                    className={`border p-4 transition-all ${
                      ach.unlocked
                        ? "bg-[var(--color-card)] border-[var(--color-border)]"
                        : "bg-[var(--color-surface)] border-[var(--color-border)] opacity-60"
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className="text-3xl flex-shrink-0">
                        {ach.unlocked ? ach.icon : <Lock size={20} className="text-[var(--color-text-muted)]" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-bold text-[var(--color-text)]">
                            {ach.name}
                          </span>
                          {ach.max_level > 1 && ach.unlocked && (
                            <span className="text-[10px] px-1.5 py-0.5 bg-[var(--color-accent)]/10 text-[var(--color-accent)]">
                              Lv{ach.level}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-[var(--color-text-muted)] mb-2">
                          {ach.description}
                        </p>

                        {/* Progress bar */}
                        <div className="w-full h-1 bg-[var(--color-surface)] mb-1">
                          <div
                            className="h-full transition-all duration-500"
                            style={{
                              width: `${Math.min(ach.progress * 100, 100)}%`,
                              backgroundColor: ach.unlocked ? "#22c55e" : colors.text,
                            }}
                          />
                        </div>
                        <div className="flex justify-between text-[9px] text-[var(--color-text-muted)]">
                          <span>{ach.unlocked ? "✅ 已解锁" : ach.progress_label}</span>
                          {ach.unlocked_at && (
                            <span>{new Date(ach.unlocked_at).toLocaleDateString()}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}

        {achievements.length === 0 && (
          <p className="text-center text-sm text-[var(--color-text-muted)] py-16">
            开始练习，解锁第一个成就吧！🎯
          </p>
        )}
      </div>
    </main>
  );
}
