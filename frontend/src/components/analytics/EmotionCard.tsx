// 情感陪伴卡片 — 嵌入分析页面
//
// 显示:
// - 当前情绪标签（emoji + 文字）
// - 负面情绪比例（进度条）
// - 情绪趋势（improving/declining/stable）
// - 一句话温暖洞察

"use client";

import { useState, useEffect } from "react";
import { Heart, TrendingUp, TrendingDown, Minus, Loader2 } from "lucide-react";
import Card from "@/components/ui/Card";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// 情绪分类展示
const EMOTION_DISPLAY: Record<string, { emoji: string; label: string; color: string }> = {
  frustration: { emoji: "😤", label: "挫败", color: "#ef4444" },
  anxiety: { emoji: "😰", label: "焦虑", color: "#f97316" },
  confusion: { emoji: "🤔", label: "困惑", color: "#eab308" },
  boredom: { emoji: "😴", label: "无聊", color: "#64748b" },
  overwhelm: { emoji: "😵", label: "压力大", color: "#dc2626" },
  procrastination: { emoji: "🥱", label: "拖延", color: "#a855f7" },
  motivated: { emoji: "💪", label: "有动力", color: "#22c55e" },
  achievement: { emoji: "🎉", label: "成就感", color: "#f59e0b" },
  curious: { emoji: "🔍", label: "好奇", color: "#3b82f6" },
  calm: { emoji: "😌", label: "平静", color: "#06b6d4" },
  neutral: { emoji: "📝", label: "中性", color: "#94a3b8" },
};

const TREND_CONFIG: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
  improving: { icon: <TrendingUp size={14} />, label: "在变好", color: "#22c55e" },
  declining: { icon: <TrendingDown size={14} />, label: "需要关心", color: "#ef4444" },
  stable: { icon: <Minus size={14} />, label: "平稳", color: "#3b82f6" },
  volatile: { icon: <Minus size={14} />, label: "波动", color: "#a855f7" },
};

interface EmotionTrend {
  dominant_emotion: string;
  dominant_count: number;
  negative_ratio: number;
  positive_ratio: number;
  trend_direction: string;
  insight: string;
  recent_records: Array<{
    category: string;
    intensity: number;
    summary: string;
    timestamp: string;
  }>;
}

export default function EmotionCard({ className = "" }: { className?: string }) {
  const [trend, setTrend] = useState<EmotionTrend | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/api/v2/emotion/trend/default_user?window_hours=72`)
      .then((r) => {
        if (!r.ok) throw new Error("Failed");
        return r.json();
      })
      .then((data) => {
        if (!cancelled) {
          setTrend(data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError(true);
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <Card title="❤️ 心理陪伴" className={className}>
        <div className="flex items-center justify-center py-6">
          <Loader2 className="animate-spin text-[var(--color-text-tertiary)]" size={20} />
        </div>
      </Card>
    );
  }

  if (error || !trend) {
    return (
      <Card title="❤️ 心理陪伴" className={className}>
        <div className="text-xs text-[var(--color-text-tertiary)] py-4 text-center">
          稍后再来看看你的情绪状态吧 🌱
        </div>
      </Card>
    );
  }

  const dominant = EMOTION_DISPLAY[trend.dominant_emotion] || EMOTION_DISPLAY.neutral;
  const trendCfg = TREND_CONFIG[trend.trend_direction] || TREND_CONFIG.stable;

  return (
    <Card title="❤️ 心理陪伴" className={className}>
      <div className="space-y-3">
        {/* 当前主导情绪 */}
        <div className="flex items-center gap-3">
          <span className="text-3xl">{dominant.emoji}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-[var(--color-text)]">
                {dominant.label}
              </span>
              <span
                className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded"
                style={{ backgroundColor: trendCfg.color + "20", color: trendCfg.color }}
              >
                {trendCfg.icon}
                {trendCfg.label}
              </span>
            </div>
            <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">
              {trend.insight}
            </p>
          </div>
        </div>

        {/* 情绪平衡条 */}
        <div className="space-y-1">
          <div className="flex justify-between text-[10px] text-[var(--color-text-tertiary)]">
            <span>负面 {Math.round(trend.negative_ratio * 100)}%</span>
            <span>正面 {Math.round(trend.positive_ratio * 100)}%</span>
          </div>
          <div className="h-1.5 bg-[var(--color-border-subtle)] rounded-full overflow-hidden flex">
            <div
              className="h-full rounded-l-full transition-all"
              style={{
                width: `${Math.round(trend.negative_ratio * 100)}%`,
                backgroundColor: "#ef4444",
              }}
            />
            <div
              className="h-full transition-all"
              style={{
                width: `${Math.max(1, Math.round((1 - trend.negative_ratio - trend.positive_ratio) * 100))}%`,
                backgroundColor: "#94a3b8",
              }}
            />
            <div
              className="h-full rounded-r-full transition-all"
              style={{
                width: `${Math.round(trend.positive_ratio * 100)}%`,
                backgroundColor: "#22c55e",
              }}
            />
          </div>
        </div>

        {/* 最近记录 */}
        {trend.recent_records.length > 0 && (
          <div className="space-y-1.5">
            <div className="text-[10px] font-medium text-[var(--color-text-tertiary)] uppercase tracking-wide">
              最近状态
            </div>
            {trend.recent_records.slice(-3).reverse().map((r, i) => {
              const display = EMOTION_DISPLAY[r.category] || EMOTION_DISPLAY.neutral;
              const ts = new Date(r.timestamp);
              const timeStr = `${ts.getHours().toString().padStart(2, "0")}:${ts.getMinutes().toString().padStart(2, "0")}`;
              return (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span>{display.emoji}</span>
                  <span className="text-[var(--color-text-secondary)] flex-1 truncate">
                    {r.summary}
                  </span>
                  <span className="text-[10px] text-[var(--color-text-tertiary)] shrink-0">
                    {timeStr}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Card>
  );
}
