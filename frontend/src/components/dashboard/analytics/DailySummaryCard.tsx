// ═══════════════════════════════════════════════
//  每日摘要组件 — 昨日回顾 + 今日推荐
// ═══════════════════════════════════════════════

import { useState, useEffect } from "react";
import { authedFetch, API_BASE } from "@/lib/api/api";

interface DailyTrendPoint {
  date: string;
  count: number;
  correct: number;
  wrong: number;
  minutes: number;
}

interface WeakSkill {
  skill_id: string;
  label: string;
  mastery: number;
}

export function DailySummaryCard() {
  const [yesterday, setYesterday] = useState<DailyTrendPoint | null>(null);
  const [dayBefore, setDayBefore] = useState<DailyTrendPoint | null>(null);
  const [recommendations, setRecommendations] = useState<WeakSkill[]>([]);

  useEffect(() => {
    async function load() {
      try {
        const [dailyRes, weakRes] = await Promise.all([
          authedFetch(`/api/practice/stats/daily?days=3`),
          authedFetch(`/api/practice/stats/weak-skills`),
        ]);
        if (dailyRes.ok) {
          const trend: DailyTrendPoint[] = await dailyRes.json();
          // trend 是按时间升序排列，取最后两天
          if (trend.length >= 2) {
            setDayBefore(trend[trend.length - 2]);
            setYesterday(trend[trend.length - 1]);
          } else if (trend.length === 1) {
            setYesterday(trend[0]);
          }
        }
        if (weakRes.ok) {
          const wData = await weakRes.json();
          setRecommendations((wData.weak_skills || wData || []).slice(0, 3));
        }
      } catch {}
    }
    load();
  }, []);

  if (!yesterday || yesterday.count === 0) return null;

  const delta = dayBefore ? yesterday.count - dayBefore.count : 0;
  const deltaStr = delta > 0 ? `↑${delta}` : delta < 0 ? `↓${Math.abs(delta)}` : "→0";
  const accuracy = yesterday.count > 0 ? yesterday.correct / yesterday.count : 0;

  const encourages = [
    "坚持下去，复利效应正在发生 📈",
    "每一个知识点都是未来的砖瓦 🧱",
    "今天比昨天多会一点，就是胜利 ✨",
    "学习是一场马拉松，不是冲刺 🏃",
  ];

  return (
    <div className="mb-8 p-5 border border-accent/30 bg-accent/5 active:scale-[0.97] transition-transform">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text">
          📊 昨日回顾 · {yesterday.date}
        </h3>
      </div>
      <div className="grid grid-cols-3 gap-3 mb-3">
        <div>
          <div className="text-lg font-semibold text">
            {yesterday.count}<span className="text-xs text-muted">题</span>
          </div>
          <div className="text-[10px] text-muted">
            较前日 {deltaStr}
          </div>
        </div>
        <div>
          <div className="text-lg font-semibold text">
            {(accuracy * 100).toFixed(0)}<span className="text-xs text-muted">%</span>
          </div>
          <div className="text-[10px] text-muted">正确率</div>
        </div>
        <div>
          <div className="text-lg font-semibold text">
            {yesterday.correct}/{yesterday.count}
          </div>
          <div className="text-[10px] text-muted">正确/总题</div>
        </div>
      </div>
      {recommendations.length > 0 && (
        <div className="flex items-center gap-2 text-[10px] text-muted">
          <span>🎯 今日推荐：</span>
          {recommendations.map((r) => (
            <span key={r.skill_id} className="px-1.5 py-0.5 bg-surface text-secondary">
              {r.label} ({Math.round(r.mastery * 100)}%)
            </span>
          ))}
        </div>
      )}
      <p className="text-[10px] text-muted mt-2">
        {encourages[Math.floor(Math.random() * encourages.length)]}
      </p>
    </div>
  );
}
