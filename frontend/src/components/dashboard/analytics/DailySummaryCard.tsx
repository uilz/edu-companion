// ═══════════════════════════════════════════════
//  每日摘要组件 — 昨日回顾 + 今日推荐
// ═══════════════════════════════════════════════

import { useState, useEffect } from "react";
import { DailySummary } from "@/components/dashboard/analytics/utils";

// ── API 地址：优先使用环境变量，否则回退到本地 8000 ──
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function DailySummaryCard() {
  const [summary, setSummary] = useState<DailySummary | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/progress/default_user/summary`)
      .then((r) => r.json())
      .then((d) => {
        if (d.yesterday) setSummary(d);
      })
      .catch(() => {});
  }, []);

  if (!summary) return null;

  // 环比变化文本
  const deltaStr = summary.vs_previous.delta > 0
    ? `↑${summary.vs_previous.delta}`
    : summary.vs_previous.delta < 0
    ? `↓${Math.abs(summary.vs_previous.delta)}`
    : "→";

  return (
    <div className="mb-8 p-5 border border-[var(--color-accent)]/30 bg-[var(--color-accent)]/5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-[var(--color-text)]">
          📊 昨日回顾 · {summary.yesterday.date}
        </h3>
        {/* 连续学习天数 */}
        {summary.streak > 0 && (
          <span className="text-xs text-[var(--color-warning)] flex items-center gap-1">
            🔥 连续 {summary.streak} 天
          </span>
        )}
      </div>
      {/* 三列摘要统计 */}
      <div className="grid grid-cols-3 gap-3 mb-3">
        <div>
          <div className="text-lg font-bold text-[var(--color-text)]">
            {summary.yesterday.total}<span className="text-xs text-[var(--color-text-muted)]">题</span>
          </div>
          <div className="text-[10px] text-[var(--color-text-muted)]">
            较前日 {deltaStr}
          </div>
        </div>
        <div>
          <div className="text-lg font-bold text-[var(--color-text)]">
            {(summary.yesterday.accuracy * 100).toFixed(0)}<span className="text-xs text-[var(--color-text-muted)]">%</span>
          </div>
          <div className="text-[10px] text-[var(--color-text-muted)]">正确率</div>
        </div>
        <div>
          <div className="text-lg font-bold text-[var(--color-text)]">
            {summary.yesterday.correct}/{summary.yesterday.total}
          </div>
          <div className="text-[10px] text-[var(--color-text-muted)]">正确/总题</div>
        </div>
      </div>
      {/* 今日推荐知识点 */}
      {summary.recommendations.length > 0 && (
        <div className="flex items-center gap-2 text-[10px] text-[var(--color-text-muted)]">
          <span>🎯 今日推荐：</span>
          {summary.recommendations.map((r) => (
            <span key={r.skill_id} className="px-1.5 py-0.5 bg-[var(--color-surface)] text-[var(--color-text-secondary)]">
              {r.skill_id} ({r.mastery}%)
            </span>
          ))}
        </div>
      )}
      <p className="text-[10px] text-[var(--color-text-muted)] mt-2">{summary.encourage}</p>
    </div>
  );
}
