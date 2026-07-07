// ═══════════════════════════════════════════════
//  习惯养成 Tab — 展示每日目标、番茄钟、微习惯等
// ═══════════════════════════════════════════════

import {
  Timer, Flame, Zap, TrendingUp, Loader2,
} from "lucide-react";
import Link from "next/link";
import Card from "@/components/ui/Card";
import { BehaviorData, hourLabel } from "@/components/dashboard/analytics/utils";

// ── 习惯 Tab 主组件 ──
export function HabitTab({ data }: { data: BehaviorData | null }) {
  if (!data) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="animate-spin text-accent" size={24} />
      </div>
    );
  }

  const { behavior, daily_goal, tiny_habits, pomodoro } = data;
  const levelLabels: Record<string, string> = { beginner: "入门", regular: "日常", intensive: "强化" };

  return (
    <div className="space-y-6">
      {/* ── 每日目标卡片 ── */}
      <Card className="!p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text">
            🎯 今日目标 · {levelLabels[daily_goal.level] || daily_goal.level}模式
          </h3>
          <span className="text-[10px] text-muted">
            目标：{daily_goal.target_questions}题/天
          </span>
        </div>

        {/* 进度环 */}
        <div className="flex items-center gap-6 mb-4">
          <div className="relative w-20 h-20 flex-shrink-0">
            <svg viewBox="0 0 80 80" className="w-full h-full -rotate-90">
              <circle cx="40" cy="40" r="34" fill="none" stroke="var(--color-surface)" strokeWidth="6" />
              <circle
                cx="40" cy="40" r="34" fill="none"
                stroke={daily_goal.is_completed ? "var(--color-success)" : "var(--color-accent)"}
                strokeWidth="6" strokeLinecap="round"
                strokeDasharray={`${2 * Math.PI * 34}`}
                strokeDashoffset={`${2 * Math.PI * 34 * (1 - Math.min(daily_goal.today_done / daily_goal.target_questions, 1))}`}
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-lg font-semibold text">{daily_goal.today_done}</span>
              <span className="text-[9px] text-muted">/{daily_goal.target_questions}</span>
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-secondary leading-relaxed">
              {daily_goal.message}
            </p>
            {daily_goal.today_accuracy > 0 && (
              <p className="text-[11px] text-muted mt-1">
                今日正确率 {(daily_goal.today_accuracy * 100).toFixed(0)}%
              </p>
            )}
          </div>
        </div>

        {/* 未完成时显示「去练习」按钮 */}
        {!daily_goal.is_completed && daily_goal.today_remaining > 0 && (
          <Link
            href="/practice"
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-accent text-white text-xs hover:bg-accent-hover active:scale-[0.97] transition-colors"
            style={{ borderRadius: "2px" }}
          >
            <Timer size={13} /> 去完成今日目标
          </Link>
        )}
      </Card>

      {/* ── Streak + 最佳时段 + 规律性（三栏） ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 连续学习 */}
        <Card className="!p-4">
          <div className="flex items-center gap-2 mb-2">
            <Flame size={16} className="text-warning" />
            <span className="text-xs font-semibold text">连续学习</span>
          </div>
          <div className="text-2xl font-semibold text">
            {behavior.current_streak}<span className="text-sm text-muted">天</span>
          </div>
          <div className="text-[10px] text-muted mt-1">
            最长连续 {behavior.longest_streak} 天
          </div>
          {behavior.current_streak >= 7 && (
            <div className="mt-2 text-[10px] text-success font-medium">🔥 习惯已形成</div>
          )}
        </Card>

        {/* 最佳时段 */}
        <Card className="!p-4">
          <div className="flex items-center gap-2 mb-2">
            <Zap size={16} className="text-accent" />
            <span className="text-xs font-semibold text">最佳时段</span>
          </div>
          {behavior.best_study_hours.length > 0 ? (
            <div className="text-sm text-secondary">
              {behavior.best_study_hours.map((h) => hourLabel(h)).join(" · ")}
            </div>
          ) : (
            <div className="text-sm text-muted">数据收集中</div>
          )}
          <div className="text-[10px] text-muted mt-1">
            效率最高的学习时段
          </div>
        </Card>

        {/* 规律性评分 */}
        <Card className="!p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp size={16} className="text-success" />
            <span className="text-xs font-semibold text">规律性</span>
          </div>
          <div className="text-2xl font-semibold text">
            {(behavior.regularity_score * 100).toFixed(0)}<span className="text-sm text-muted">分</span>
          </div>
          <div className="text-[10px] text-muted mt-1">
            {behavior.regularity_score > 0.7 ? "学习节奏很稳定 ✨" :
             behavior.regularity_score > 0.4 ? "正在形成规律 💪" : "时间不太固定"}
          </div>
        </Card>
      </div>

      {/* ── 番茄钟建议 ── */}
      <Card title="🍅 番茄钟建议" className="!p-5">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-4 py-2 bg-surface" style={{ borderRadius: "2px" }}>
            <span className="text-lg font-semibold text-accent">{pomodoro.work_minutes}</span>
            <span className="text-xs text-muted">分钟学习</span>
          </div>
          <span className="text-muted text-xs">+</span>
          <div className="flex items-center gap-2 px-4 py-2 bg-surface" style={{ borderRadius: "2px" }}>
            <span className="text-lg font-semibold text-success">{pomodoro.break_minutes}</span>
            <span className="text-xs text-muted">分钟休息</span>
          </div>
        </div>
        <p className="text-xs text-secondary mt-3">{pomodoro.message}</p>
      </Card>

      {/* ── 微习惯推荐 ── */}
      <Card title="🌱 微习惯推荐 (TinyHabits)" className="!p-5">
        <div className="space-y-4">
          {tiny_habits.map((h, i) => (
            <div key={i} className="flex items-start gap-3 p-3 bg-surface" style={{ borderRadius: "2px" }}>
              <div className="w-8 h-8 bg-accent flex items-center justify-center flex-shrink-0 active:scale-[0.97] transition-transform" style={{ borderRadius: "2px" }}>
                <span className="text-white text-xs font-semibold">{i + 1}</span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text">{h.name}</p>
                <p className="text-[11px] text-secondary mt-0.5">
                  <span className="text-muted">{h.anchor}</span> → {h.behavior}
                </p>
                <p className="text-[10px] text-muted mt-1">
                  坚持率 {(h.consistency * 100).toFixed(0)}% · {h.celebration}
                </p>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* ── 行为分析建议 ── */}
      {behavior.recommendations.length > 0 && (
        <Card title="💡 个性化建议" className="!p-5">
          <div className="space-y-2">
            {behavior.recommendations.map((r, i) => (
              <div key={i} className="flex items-start gap-2 text-sm text-secondary leading-relaxed">
                <span className="text-accent mt-0.5">•</span>
                <span>{r}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ── 汇总统计 ── */}
      <Card className="!p-5">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-lg font-semibold text">{behavior.total_sessions}</div>
            <div className="text-[10px] text-muted">总练习次数</div>
          </div>
          <div>
            <div className="text-lg font-semibold text">{behavior.avg_session_minutes.toFixed(0)}min</div>
            <div className="text-[10px] text-muted">平均每次</div>
          </div>
          <div>
            <div className="text-lg font-semibold text">
              {behavior.fatigue_drop_minute ? `${behavior.fatigue_drop_minute}min` : "—"}
            </div>
            <div className="text-[10px] text-muted">专注力峰值</div>
          </div>
        </div>
      </Card>
    </div>
  );
}
