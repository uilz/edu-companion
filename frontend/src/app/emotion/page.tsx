"use client";

import { useState, useEffect } from "react";
import {
  Heart, TrendingUp, AlertTriangle, Smile, Meh, Frown,
  Brain, Sparkles, Thermometer, Activity,
  ChevronRight, Loader2,
} from "lucide-react";

interface EmotionRecord {
  timestamp: string;
  category: string;
  intensity: number;
  source_text: string;
  summary: string;
}

interface EmotionTrend {
  dominant_emotion: string;
  dominant_count: number;
  negative_ratio: number;
  positive_ratio: number;
  trend_direction: string;
  insight: string;
  recent_records: EmotionRecord[];
}

interface EmotionStats {
  status: string;
  total_records: number;
  dominant_emotion: string;
  dominant_emoji: string;
  negative_ratio: number;
  categories: Record<string, number>;
}

// ── 情绪配置 ──
const EMOTION_CONFIG: Record<string, { label: string; emoji: string; color: string; severity: string }> = {
  frustration: { label: "挫败", emoji: "😤", color: "#ef4444", severity: "negative" },
  anxiety: { label: "焦虑", emoji: "😰", color: "#f97316", severity: "negative" },
  confusion: { label: "困惑", emoji: "🤔", color: "#eab308", severity: "neutral" },
  boredom: { label: "无聊", emoji: "😴", color: "#a1a1aa", severity: "negative" },
  overwhelm: { label: "压力大", emoji: "😵", color: "#dc2626", severity: "negative" },
  procrastination: { label: "拖延", emoji: "🥱", color: "#d946ef", severity: "negative" },
  motivated: { label: "有动力", emoji: "💪", color: "#22c55e", severity: "positive" },
  achievement: { label: "成就感", emoji: "🎉", color: "#06b6d4", severity: "positive" },
  curious: { label: "好奇", emoji: "🔍", color: "#6366f1", severity: "positive" },
  calm: { label: "平静", emoji: "😌", color: "#8b5cf6", severity: "positive" },
  neutral: { label: "中性", emoji: "📝", color: "#6b7280", severity: "neutral" },
};

const DIRECTION_LABELS: Record<string, { label: string; icon: string; color: string }> = {
  improving: { label: "变好", icon: "📈", color: "text-green-500" },
  declining: { label: "变差", icon: "📉", color: "text-red-500" },
  stable: { label: "稳定", icon: "➡️", color: "text-gray-500" },
  volatile: { label: "波动", icon: "〰️", color: "text-amber-500" },
};

export default function EmotionDashboard() {
  const [trend, setTrend] = useState<EmotionTrend | null>(null);
  const [stats, setStats] = useState<EmotionStats | null>(null);
  const [recent, setRecent] = useState<EmotionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"overview" | "history">("overview");

  useEffect(() => {
    Promise.all([
      fetch("/api/conversations/emotion/trend?window_hours=168").then(r => r.json()),
      fetch("/api/conversations/emotion/stats").then(r => r.json()),
      fetch("/api/conversations/emotion/recent?limit=20").then(r => r.json()),
    ]).then(([t, s, r]) => {
      setTrend(t);
      setStats(s);
      setRecent(r.records || []);
    }).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  if (stats?.status === "insufficient_data") {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16 text-center space-y-4">
        <Heart className="w-16 h-16 mx-auto text-rose-300" />
        <h1 className="text-xl font-semibold">情绪陪伴</h1>
        <p className="text-gray-500">和 AI 多聊聊，我会感知你的学习情绪，\n在你挫败时鼓励、焦虑时安慰、进步时庆祝 🫂</p>
        <p className="text-xs text-gray-400">开始对话后，情绪数据会自动收集</p>
      </div>
    );
  }

  const trendInfo = trend ? DIRECTION_LABELS[trend.trend_direction] : null;
  const sortedCategories = stats?.categories
    ? Object.entries(stats.categories).sort(([, a], [, b]) => b - a)
    : [];
  const maxCatCount = sortedCategories[0]?.[1] || 1;

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
      {/* ── 页面标题 ── */}
      <div className="flex items-center gap-3">
        <Heart className="w-6 h-6 text-rose-400" />
        <h1 className="text-xl font-semibold">情绪陪伴</h1>
        <span className="text-xs px-2 py-0.5 rounded-full bg-rose-100 dark:bg-rose-900/30 text-rose-600 dark:text-rose-300">
          共 {stats?.total_records || 0} 条记录
        </span>
      </div>

      {/* ── 主导情绪卡片 ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 当前情绪 */}
        <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/60 p-5">
          <div className="text-4xl mb-2">{stats?.dominant_emoji}</div>
          <div className="text-lg font-semibold">主导情绪</div>
          <div className="text-sm text-gray-500 mt-1">
            {EMOTION_CONFIG[stats?.dominant_emotion || ""]?.label || stats?.dominant_emotion}
          </div>
        </div>

        {/* 情绪方向 */}
        <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/60 p-5">
          <div className="text-4xl mb-2">{trendInfo?.icon || "➡️"}</div>
          <div className="text-lg font-semibold">趋势</div>
          <div className={`text-sm mt-1 ${trendInfo?.color || "text-gray-500"}`}>
            {trendInfo?.label || "稳定"}
          </div>
        </div>

        {/* 负面占比 */}
        <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/60 p-5">
          <div className="text-4xl mb-2">
            {(stats?.negative_ratio || 0) > 0.5 ? "😰" : (stats?.negative_ratio || 0) > 0.3 ? "😐" : "😊"}
          </div>
          <div className="text-lg font-semibold">负面情绪占比</div>
          <div className="text-sm mt-1">
            <div className="flex items-center gap-2">
              <div className="flex-1 h-2 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${((stats?.negative_ratio || 0) * 100)}%`,
                    backgroundColor: (stats?.negative_ratio || 0) > 0.5 ? "#ef4444" : (stats?.negative_ratio || 0) > 0.3 ? "#f97316" : "#22c55e",
                  }}
                />
              </div>
              <span className="text-xs font-medium">{Math.round((stats?.negative_ratio || 0) * 100)}%</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── AI 洞察 ── */}
      {trend?.insight && (
        <div className="rounded-2xl border border-indigo-100 dark:border-indigo-900/40 bg-indigo-50 dark:bg-indigo-950/30 p-4 flex items-start gap-3">
          <Brain className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-indigo-700 dark:text-indigo-300">苹小果的陪伴洞察</p>
            <p className="text-sm text-indigo-600 dark:text-indigo-400 mt-1">{trend.insight}</p>
          </div>
        </div>
      )}

      {/* ── 情绪分布 ── */}
      <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/60 p-5">
        <h2 className="font-medium mb-4 flex items-center gap-2"><Activity className="w-4 h-4" />情绪分布</h2>
        <div className="space-y-2.5">
          {sortedCategories.map(([cat, count]) => {
            const cfg = EMOTION_CONFIG[cat] || { label: cat, emoji: "❓", color: "#6b7280", severity: "neutral" };
            return (
              <div key={cat} className="flex items-center gap-3">
                <span className="text-lg w-8 text-center">{cfg.emoji}</span>
                <span className="text-sm w-16">{cfg.label}</span>
                <div className="flex-1 h-4 rounded-full bg-gray-100 dark:bg-gray-700 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${(count / maxCatCount) * 100}%`, backgroundColor: cfg.color }}
                  />
                </div>
                <span className="text-xs text-gray-400 w-6 text-right">{count}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── 最近情绪记录 ── */}
      <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/60 p-5">
        <h2 className="font-medium mb-4 flex items-center gap-2"><Sparkles className="w-4 h-4" />最近情绪记录</h2>
        <div className="space-y-2">
          {recent.slice().reverse().map((r, i) => {
            const cfg = EMOTION_CONFIG[r.category] || { label: r.category, emoji: "❓", color: "#6b7280", severity: "neutral" };
            const time = new Date(r.timestamp);
            const timeStr = `${time.getMonth() + 1}/${time.getDate()} ${String(time.getHours()).padStart(2, "0")}:${String(time.getMinutes()).padStart(2, "0")}`;
            return (
              <div key={i} className="flex items-start gap-3 py-2 border-b border-gray-100 dark:border-gray-700/50 last:border-0">
                <span className="text-lg">{cfg.emoji}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{cfg.label}</span>
                    <span className="text-xs px-1.5 py-0.5 rounded"
                      style={{
                        backgroundColor: r.intensity > 0.6 ? `${cfg.color}20` : `${cfg.color}10`,
                        color: cfg.color,
                      }}
                    >
                      强度 {r.intensity.toFixed(1)}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 truncate mt-0.5">"{r.source_text}"</p>
                </div>
                <span className="text-xs text-gray-400 shrink-0">{timeStr}</span>
              </div>
            );
          })}
          {recent.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-4">还没有情绪记录，开始对话吧 💬</p>
          )}
        </div>
      </div>
    </div>
  );
}
