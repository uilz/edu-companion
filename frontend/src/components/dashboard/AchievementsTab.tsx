"use client";

// 导入所需依赖：React 状态与副作用钩子、图标、自定义 Card 组件
import { useState, useEffect } from "react";
import { Award, Loader2, Lock } from "lucide-react";
import Card from "@/components/ui/Card";
import { API_BASE } from "@/lib/api";

// 成就数据结构定义
interface Achievement {
  id: string;
  name: string;
  icon: string;
  tier: "bronze" | "silver" | "gold";         // 成就品质：青铜、白银、黄金
  description: string;
  unlocked: boolean;                            // 是否已解锁
  level: number;                                // 当前等级
  max_level: number;                            // 最大等级
  progress: number;                             // 当前进度（0~1 之间）
  progress_label: string;                       // 进度文本描述
  unlocked_at: string | null;                   // 解锁时间戳
}

// 各品质对应的颜色方案：背景色、边框色、文字色
const TIER_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  bronze: { bg: "#92400e20", border: "#92400e", text: "#d97706" },
  silver: { bg: "#64748b20", border: "#64748b", text: "#94a3b8" },
  gold: { bg: "#b4530920", border: "#b45309", text: "#f59e0b" },
};

// 成就墙 Tab 组件
export function AchievementsTab() {
  // 成就列表状态与加载状态
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [loading, setLoading] = useState(true);

  // 组件挂载时从后端获取用户成就数据
  useEffect(() => {
    fetch(`${API_BASE}/api/achievements/default_user`)
      .then((r) => r.json())
      .then((d) => setAchievements(d.achievements || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // 计算已解锁成就数量
  const unlockedCount = achievements.filter((a) => a.unlocked).length;

  // 加载中状态：显示旋转加载图标
  if (loading) {
    return (
      <div>
        <Loader2 size={24} className="animate-spin text-[var(--color-accent)]" />
      </div>
    );
  }

  return (
    <div>
      <div>
        {/* 页头：标题与解锁统计 */}
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

        {/* 全局进度条：反映总体解锁进度 */}
        <div className="mb-8 w-full h-1.5 bg-[var(--color-surface)]">
          <div
            className="h-full bg-[#f59e0b] transition-all duration-700"
            style={{ width: `${(unlockedCount / Math.max(achievements.length, 1)) * 100}%` }}
          />
        </div>

        {/* 按品质（青铜/白银/黄金）分组展示成就 */}
        {(["bronze", "silver", "gold"] as const).map((tier) => {
          const tierAchievements = achievements.filter((a) => a.tier === tier);
          const tierLabel = { bronze: "🥉 青铜成就", silver: "🥈 白银成就", gold: "🥇 黄金成就" }[tier];
          const colors = TIER_COLORS[tier];

          return (
            <div key={tier} className="mb-8">
              {/* 品质标题 */}
              <h2
                className="text-sm font-bold mb-4 px-1"
                style={{ color: colors.text }}
              >
                {tierLabel}
              </h2>
              {/* 成就卡片网格布局 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {tierAchievements.map((ach) => (
                  /* 单个成就卡片：已解锁显示正常样式，未解锁降低透明度 */
                  <div
                    key={ach.id}
                    className={`border p-4 transition-all ${
                      ach.unlocked
                        ? "bg-[var(--color-card)] border-[var(--color-border)]"
                        : "bg-[var(--color-surface)] border-[var(--color-border)] opacity-60"
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      {/* 成就图标：已解锁显示对应图标，未解锁显示锁图标 */}
                      <div className="text-3xl flex-shrink-0">
                        {ach.unlocked ? ach.icon : <Lock size={20} className="text-[var(--color-text-muted)]" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        {/* 成就名称与等级标签 */}
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
                        {/* 成就描述 */}
                        <p className="text-xs text-[var(--color-text-muted)] mb-2">
                          {ach.description}
                        </p>

                        {/* 单项进度条：已解锁为绿色，未解锁使用对应品质颜色 */}
                        <div className="w-full h-1 bg-[var(--color-surface)] mb-1">
                          <div
                            className="h-full transition-all duration-500"
                            style={{
                              width: `${Math.min(ach.progress * 100, 100)}%`,
                              backgroundColor: ach.unlocked ? "#22c55e" : colors.text,
                            }}
                          />
                        </div>
                        {/* 进度文本与解锁日期 */}
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

        {/* 无成就数据时的空状态提示 */}
        {achievements.length === 0 && (
          <p className="text-center text-sm text-[var(--color-text-muted)] py-16">
            开始练习，解锁第一个成就吧！🎯
          </p>
        )}
      </div>
    </div>
  );
}
