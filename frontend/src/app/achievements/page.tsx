"use client";

// ===== 导入依赖 =====
import { useState, useEffect } from "react";
import { Award, Loader2, Lock } from "lucide-react";
import Card from "@/components/ui/Card";

// ===== API 基础地址 =====
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ===== 成就数据类型定义 =====
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

// ===== 各阶成就的主题色 =====
const TIER_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  bronze: { bg: "#92400e20", border: "#92400e", text: "#d97706" },
  silver: { bg: "#64748b20", border: "#64748b", text: "#94a3b8" },
  gold: { bg: "#b4530920", border: "#b45309", text: "#f59e0b" },
};

// ===== 成就页面组件 =====
export default function AchievementsPage() {
  // ===== 状态管理：成就列表 & 加载状态 =====
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [loading, setLoading] = useState(true);

  // ===== 组件挂载时从后端获取成就数据 =====
  useEffect(() => {
    fetch(`${API_BASE}/api/achievements/default_user`)
      .then((r) => r.json())
      .then((d) => setAchievements(d.achievements || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // ===== 计算已解锁成就数量 =====
  const unlockedCount = achievements.filter((a) => a.unlocked).length;

  // ===== 加载中：显示旋转加载图标 =====
  if (loading) {
    return (
      <main className="min-h-screen bg-[var(--color-bg)] flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-[var(--color-accent)]" />
      </main>
    );
  }

  // ===== 主内容渲染 =====
  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-4xl mx-auto px-4 md:px-6 py-8 md:py-12">
        {/* ===== 页面标题与统计 ===== */}
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

        {/* ===== 总体进度条 ===== */}
        <div className="mb-8 w-full h-1.5 bg-[var(--color-surface)]">
          <div
            className="h-full bg-[#f59e0b] transition-all duration-700"
            style={{ width: `${(unlockedCount / Math.max(achievements.length, 1)) * 100}%` }}
          />
        </div>

        {/* ===== 按阶分组展示成就：青铜、白银、黄金 ===== */}
        {(["bronze", "silver", "gold"] as const).map((tier) => {
          const tierAchievements = achievements.filter((a) => a.tier === tier);
          const tierLabel = { bronze: "🥉 青铜成就", silver: "🥈 白银成就", gold: "🥇 黄金成就" }[tier];
          const colors = TIER_COLORS[tier];

          return (
            <div key={tier} className="mb-8">
              {/* ===== 阶标题 ===== */}
              <h2
                className="text-sm font-bold mb-4 px-1"
                style={{ color: colors.text }}
              >
                {tierLabel}
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {/* ===== 单个成就卡片 ===== */}
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
                      {/* ===== 成就图标（未解锁则显示锁图标） ===== */}
                      <div className="text-3xl flex-shrink-0">
                        {ach.unlocked ? ach.icon : <Lock size={20} className="text-[var(--color-text-muted)]" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        {/* ===== 成就名称与等级 ===== */}
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
                        {/* ===== 成就描述 ===== */}
                        <p className="text-xs text-[var(--color-text-muted)] mb-2">
                          {ach.description}
                        </p>

                        {/* ===== 单条成就进度条 ===== */}
                        <div className="w-full h-1 bg-[var(--color-surface)] mb-1">
                          <div
                            className="h-full transition-all duration-500"
                            style={{
                              width: `${Math.min(ach.progress * 100, 100)}%`,
                              backgroundColor: ach.unlocked ? "#22c55e" : colors.text,
                            }}
                          />
                        </div>
                        {/* ===== 进度文字 & 解锁时间 ===== */}
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

        {/* ===== 无成就时的空状态提示 ===== */}
        {achievements.length === 0 && (
          <p className="text-center text-sm text-[var(--color-text-muted)] py-16">
            开始练习，解锁第一个成就吧！🎯
          </p>
        )}
      </div>
    </main>
  );
}
