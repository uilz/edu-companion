"use client";

import { useState, useEffect, useCallback } from "react";
import { authedFetch } from "@/lib/api/api";
import {
  Heart, TrendingUp, AlertTriangle, Smile, Meh, Frown,
  Brain, Sparkles, Activity, Loader2, Plus, Settings,
  ShieldCheck, Bell, Eye, EyeOff, Trash2, Wand2,
} from "lucide-react";
import { ManualRecordCard } from "@/components/emotion/ManualRecordCard";
import { InterventionPanel } from "@/components/emotion/InterventionPanel";

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

interface MoodStressDashboard {
  days: number;
  prefs: Record<string, unknown>;
  latest_manual: {
    id: string;
    source: string;
    emotion_tags: string[];
    pressure_score: number | null;
    energy_score: number | null;
    text_note: string | null;
    created_at: string;
  } | null;
  stats: {
    days: number;
    total: number;
    manual_total: number;
    auto_total: number;
    avg_pressure: number | null;
    avg_energy: number | null;
    tag_distribution: Record<string, number>;
  };
  recent_records: Array<{
    id: string;
    source: string;
    emotion_tags: string[];
    pressure_score: number | null;
    energy_score: number | null;
    text_note: string | null;
    created_at: string;
  }>;
  recent_interventions: Array<{
    id: string;
    intervention_type: string;
    duration_seconds: number | null;
    created_at: string;
  }>;
  unread_behavior_signals: Array<{
    id: string;
    signal_type: string;
    signal_data: Record<string, unknown>;
    severity: number;
    created_at: string;
  }>;
  rules: Array<Record<string, unknown>>;
  auto_summary: Partial<EmotionTrend>;
  principles: Record<string, boolean>;
}

interface Constants {
  emotion_tags: Array<{ value: string; label: string; emoji: string; severity: string }>;
  intervention_types: Array<{ value: string; label: string; emoji: string; side: string }>;
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

const SIGNAL_LABELS: Record<string, { label: string; emoji: string }> = {
  task_switch: { label: "频繁切换任务", emoji: "🔀" },
  stay_duration: { label: "同一知识点停留异常", emoji: "⏱️" },
  error_rate: { label: "练习错误率突增", emoji: "📈" },
  undo: { label: "连续撤销/修改", emoji: "↩️" },
  session_anomaly: { label: "会话时长异常", emoji: "⏰" },
  flashcard_failure: { label: "卡片困难比例上升", emoji: "🃏" },
  voice_features: { label: "语音特征变化", emoji: "🎙️" },
};

const INTERVENTION_LABELS: Record<string, { label: string; emoji: string }> = {
  breathing: { label: "呼吸引导", emoji: "🫁" },
  knowledge_breathing: { label: "知识呼吸", emoji: "🌬️" },
  cognitive_reappraisal: { label: "认知重评", emoji: "🧭" },
  environment: { label: "环境切换", emoji: "🎨" },
};

export default function EmotionDashboard() {
  const [trend, setTrend] = useState<EmotionTrend | null>(null);
  const [stats, setStats] = useState<EmotionStats | null>(null);
  const [recent, setRecent] = useState<EmotionRecord[]>([]);
  const [dashboard, setDashboard] = useState<MoodStressDashboard | null>(null);
  const [constants, setConstants] = useState<Constants | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"overview" | "history" | "intervention" | "privacy">("overview");
  const [recordOpen, setRecordOpen] = useState(false);

  const reload = useCallback(async () => {
    try {
      const [t, s, r, d, c] = await Promise.all([
        authedFetch("/api/conversations/emotion/trend?window_hours=168").then((r) => r.json()),
        authedFetch("/api/conversations/emotion/stats").then((r) => r.json()),
        authedFetch("/api/conversations/emotion/recent?limit=20").then((r) => r.json()),
        authedFetch("/api/secretary/mood-stress/dashboard?days=7").then((r) => r.json()),
        authedFetch("/api/secretary/mood-stress/constants").then((r) => r.json()),
      ]);
      setTrend(t);
      setStats(s);
      setRecent(r.records || []);
      setDashboard(d);
      setConstants(c);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
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
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <Heart className="w-6 h-6 text-rose-400" />
          <h1 className="text-xl font-semibold">情绪陪伴</h1>
          <span className="text-xs px-2 py-0.5 rounded-full bg-rose-100 dark:bg-rose-900/30 text-rose-600 dark:text-rose-300">
            自动 {stats?.total_records || 0} · 手动 {dashboard?.stats.manual_total || 0}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setRecordOpen(true)}
            className="px-3 py-1.5 rounded-lg bg-indigo-500 hover:bg-indigo-600 text-white text-sm flex items-center gap-1"
          >
            <Plus className="w-4 h-4" />
            现在记录
          </button>
        </div>
      </div>

      {/* ── Tab 切换 ── */}
      <div className="flex items-center gap-2 border-b border-gray-200 dark:border-gray-700">
        {[
          { key: "overview", label: "总览" },
          { key: "history", label: "历史" },
          { key: "intervention", label: "干预工具" },
          { key: "privacy", label: "隐私" },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key as "overview" | "history" | "intervention" | "privacy")}
            className={`px-3 py-2 text-sm border-b-2 transition ${
              tab === t.key
                ? "border-indigo-500 text-indigo-600 dark:text-indigo-300"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <>
          {/* ── 手动记录优先展示 ── */}
          {dashboard?.latest_manual && (
            <div className="rounded-2xl border-2 border-indigo-200 dark:border-indigo-800 bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-indigo-950/40 dark:to-purple-950/30 p-5">
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs text-indigo-600 dark:text-indigo-300 font-medium flex items-center gap-1">
                  <Wand2 className="w-3 h-3" />
                  最新手动记录（手动优先）
                </div>
                <span className="text-xs text-gray-500">
                  {new Date(dashboard.latest_manual.created_at).toLocaleString("zh-CN", { hour12: false })}
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5 mb-3">
                {(dashboard.latest_manual.emotion_tags || []).map((t) => {
                  const cfg = EMOTION_CONFIG[t];
                  return (
                    <span
                      key={t}
                      className="px-2 py-0.5 rounded-full text-xs"
                      style={{ backgroundColor: cfg ? `${cfg.color}20` : "#e5e7eb", color: cfg?.color || "#6b7280" }}
                    >
                      {cfg?.emoji} {cfg?.label || t}
                    </span>
                  );
                })}
              </div>
              <div className="flex items-center gap-4 text-sm">
                {dashboard.latest_manual.pressure_score !== null && (
                  <span>😓 压力 <b className="text-rose-500">{dashboard.latest_manual.pressure_score}</b>/10</span>
                )}
                {dashboard.latest_manual.energy_score !== null && (
                  <span>⚡ 能量 <b className="text-emerald-500">{dashboard.latest_manual.energy_score}</b>/10</span>
                )}
              </div>
              {dashboard.latest_manual.text_note && (
                <p className="mt-2 text-sm text-gray-600 dark:text-gray-300 italic">
                  "{dashboard.latest_manual.text_note}"
                </p>
              )}
            </div>
          )}

          {/* ── 主导情绪卡片 ── */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/60 p-5">
              <div className="text-4xl mb-2">{stats?.dominant_emoji}</div>
              <div className="text-lg font-semibold">主导情绪（自动）</div>
              <div className="text-sm text-gray-500 mt-1">
                {EMOTION_CONFIG[stats?.dominant_emotion || ""]?.label || stats?.dominant_emotion || "—"}
              </div>
            </div>

            <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/60 p-5">
              <div className="text-4xl mb-2">{trendInfo?.icon || "➡️"}</div>
              <div className="text-lg font-semibold">趋势</div>
              <div className={`text-sm mt-1 ${trendInfo?.color || "text-gray-500"}`}>
                {trendInfo?.label || "稳定"}
              </div>
            </div>

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

          {/* ── 周期统计 (MoodStress) ── */}
          {dashboard && (
            <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/60 p-5">
              <h2 className="font-medium mb-4 flex items-center gap-2"><Activity className="w-4 h-4" />近 {dashboard.days} 天周期统计</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="rounded-lg bg-gray-50 dark:bg-gray-900/40 p-3">
                  <div className="text-xs text-gray-500">手动记录</div>
                  <div className="text-xl font-semibold mt-1">{dashboard.stats.manual_total}</div>
                </div>
                <div className="rounded-lg bg-gray-50 dark:bg-gray-900/40 p-3">
                  <div className="text-xs text-gray-500">自动检测</div>
                  <div className="text-xl font-semibold mt-1">{dashboard.stats.auto_total}</div>
                </div>
                <div className="rounded-lg bg-gray-50 dark:bg-gray-900/40 p-3">
                  <div className="text-xs text-gray-500">平均压力</div>
                  <div className="text-xl font-semibold mt-1 text-rose-500">
                    {dashboard.stats.avg_pressure ?? "—"}
                  </div>
                </div>
                <div className="rounded-lg bg-gray-50 dark:bg-gray-900/40 p-3">
                  <div className="text-xs text-gray-500">平均能量</div>
                  <div className="text-xl font-semibold mt-1 text-emerald-500">
                    {dashboard.stats.avg_energy ?? "—"}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── 行为信号摘要 ── */}
          {dashboard && dashboard.unread_behavior_signals.length > 0 && (
            <div className="rounded-2xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 p-5">
              <h2 className="font-medium mb-3 flex items-center gap-2">
                <Eye className="w-4 h-4 text-amber-500" />
                行为信号（仅提示，不自动修改）
              </h2>
              <div className="space-y-2">
                {dashboard.unread_behavior_signals.slice(0, 5).map((s) => {
                  const cfg = SIGNAL_LABELS[s.signal_type] || { label: s.signal_type, emoji: "❓" };
                  return (
                    <div
                      key={s.id}
                      className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-200"
                    >
                      <span className="text-base">{cfg.emoji}</span>
                      <span className="flex-1">{cfg.label}</span>
                      <span className="text-xs text-gray-400">严重度 {s.severity}/3</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

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

          {/* ── 情绪分布（自动检测） ── */}
          {sortedCategories.length > 0 && (
            <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/60 p-5">
              <h2 className="font-medium mb-4 flex items-center gap-2"><Activity className="w-4 h-4" />情绪分布（自动检测）</h2>
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
          )}
        </>
      )}

      {tab === "history" && (
        <>
          {/* ── 手动记录历史 ── */}
          <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/60 p-5">
            <h2 className="font-medium mb-4 flex items-center gap-2"><Heart className="w-4 h-4" />手动记录历史</h2>
            <div className="space-y-2">
              {dashboard?.recent_records.filter((r) => r.source === "manual").map((r) => (
                <div
                  key={r.id}
                  className="rounded-lg border border-gray-100 dark:border-gray-700 p-3"
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex flex-wrap gap-1">
                      {(r.emotion_tags || []).map((t) => {
                        const cfg = EMOTION_CONFIG[t];
                        return (
                          <span
                            key={t}
                            className="text-xs px-1.5 py-0.5 rounded"
                            style={{
                              backgroundColor: cfg ? `${cfg.color}20` : "#e5e7eb",
                              color: cfg?.color || "#6b7280",
                            }}
                          >
                            {cfg?.emoji} {cfg?.label || t}
                          </span>
                        );
                      })}
                    </div>
                    <span className="text-xs text-gray-400">
                      {new Date(r.created_at).toLocaleString("zh-CN", { hour12: false })}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-gray-500">
                    {r.pressure_score !== null && <span>压力 {r.pressure_score}/10</span>}
                    {r.energy_score !== null && <span>能量 {r.energy_score}/10</span>}
                  </div>
                  {r.text_note && (
                    <p className="mt-1 text-xs text-gray-500 italic">"{r.text_note}"</p>
                  )}
                </div>
              ))}
              {(!dashboard || dashboard.recent_records.filter((r) => r.source === "manual").length === 0) && (
                <p className="text-sm text-gray-400 text-center py-4">还没有手动记录，点上方"现在记录"开始 ✏️</p>
              )}
            </div>
          </div>

          {/* ── 自动检测历史（保留原页面） ── */}
          <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/60 p-5">
            <h2 className="font-medium mb-4 flex items-center gap-2"><Sparkles className="w-4 h-4" />最近自动检测记录</h2>
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
        </>
      )}

      {tab === "intervention" && (
        <div className="space-y-4">
          <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/60 p-5">
            <h2 className="font-medium mb-4 flex items-center gap-2">
              <Sparkles className="w-4 h-4" />
              干预工具（4 种）
            </h2>
            {constants && (
              <InterventionPanel
                types={constants.intervention_types}
                onUsed={reload}
              />
            )}
            <p className="text-xs text-gray-500 mt-3">
              🛡️ 干预工具不修改学习数据（Belief/FSRS），仅本地记录 + 事件流。
            </p>
          </div>

          {dashboard && dashboard.recent_interventions.length > 0 && (
            <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/60 p-5">
              <h2 className="font-medium mb-4">最近干预记录</h2>
              <div className="space-y-2">
                {dashboard.recent_interventions.slice(0, 10).map((it) => {
                  const cfg = INTERVENTION_LABELS[it.intervention_type] || { label: it.intervention_type, emoji: "❓" };
                  return (
                    <div key={it.id} className="flex items-center gap-2 text-sm">
                      <span>{cfg.emoji}</span>
                      <span className="flex-1">{cfg.label}</span>
                      {it.duration_seconds !== null && (
                        <span className="text-xs text-gray-500">{it.duration_seconds}s</span>
                      )}
                      <span className="text-xs text-gray-400">
                        {new Date(it.created_at).toLocaleString("zh-CN", { hour12: false })}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "privacy" && dashboard && (
        <PrivacyPanel prefs={dashboard.prefs} onUpdated={reload} />
      )}

      {/* 手动记录弹窗 */}
      <ManualRecordCard
        open={recordOpen}
        onClose={() => setRecordOpen(false)}
        onSaved={reload}
      />
    </div>
  );
}

// ──────────────────────────────────────────────
// 隐私设置面板
// ──────────────────────────────────────────────

function PrivacyPanel({
  prefs,
  onUpdated,
}: {
  prefs: Record<string, unknown>;
  onUpdated: () => void;
}) {
  const [local, setLocal] = useState<Record<string, unknown>>(prefs);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setLocal(prefs);
  }, [prefs]);

  const save = async () => {
    setSaving(true);
    try {
      const res = await authedFetch("/api/secretary/mood-stress/prefs", {
        method: "PUT",
        body: JSON.stringify(local),
      });
      if (res.ok) onUpdated();
    } finally {
      setSaving(false);
    }
  };

  const setFlag = (key: string, value: boolean) => {
    setLocal((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/60 p-5">
        <h2 className="font-medium mb-4 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-500" />
          隐私与控制
        </h2>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium">手动记录提醒</div>
              <div className="text-xs text-gray-500">默认关闭，需用户主动开启</div>
            </div>
            <Switch
              checked={Boolean(local.reminder_enabled)}
              onChange={(v) => setFlag("reminder_enabled", v)}
            />
          </div>

          <div className="border-t border-gray-100 dark:border-gray-700 pt-3">
            <div className="text-xs text-gray-500 mb-2">行为信号采集（可逐项关闭）</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {[
                ["auto_collect_task_switch", "频繁切换任务"],
                ["auto_collect_stay_duration", "同一知识点停留异常"],
                ["auto_collect_error_rate", "练习错误率突增"],
                ["auto_collect_undo", "连续撤销/修改"],
                ["auto_collect_session_anomaly", "会话时长异常"],
                ["auto_collect_flashcard_failure", "卡片困难比例上升"],
                ["auto_collect_voice_features", "语音特征（默认关闭）"],
              ].map(([key, label]) => (
                <div key={key} className="flex items-center justify-between text-sm">
                  <span>{label}</span>
                  <Switch
                    checked={Boolean(local[key])}
                    onChange={(v) => setFlag(key as string, v)}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="border-t border-gray-100 dark:border-gray-700 pt-3">
            <div className="text-xs text-gray-500 mb-2">输出控制</div>
            <div className="space-y-2">
              {[
                ["output_to_planning", "向规划模块输出压力/能量"],
                ["output_to_conversation", "向对话模块输出情绪状态"],
                ["output_to_language_room", "向语言房间输出"],
              ].map(([key, label]) => (
                <div key={key} className="flex items-center justify-between text-sm">
                  <span>{label}</span>
                  <Switch
                    checked={Boolean(local[key])}
                    onChange={(v) => setFlag(key as string, v)}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="border-t border-gray-100 dark:border-gray-700 pt-3 flex items-center justify-between">
            <div>
              <div className="text-sm font-medium">数据保留期</div>
              <div className="text-xs text-gray-500">默认 90 天，到期自动清理</div>
            </div>
            <select
              value={Number(local.data_retention_days) || 90}
              onChange={(e) =>
                setLocal((prev) => ({ ...prev, data_retention_days: Number(e.target.value) }))
              }
              className="px-2 py-1 rounded border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-900 text-sm"
            >
              <option value={30}>30 天</option>
              <option value={90}>90 天</option>
              <option value={180}>180 天</option>
              <option value={365}>1 年</option>
            </select>
          </div>
        </div>

        <div className="mt-4 pt-3 border-t border-gray-100 dark:border-gray-700 flex justify-end">
          <button
            onClick={save}
            disabled={saving}
            className="px-4 py-2 rounded-lg bg-indigo-500 hover:bg-indigo-600 text-white text-sm disabled:opacity-50 flex items-center gap-1"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Settings className="w-4 h-4" />}
            保存设置
          </button>
        </div>
      </div>

      <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/60 p-5 text-sm space-y-2 text-gray-600 dark:text-gray-300">
        <p className="font-medium text-gray-800 dark:text-gray-100">🛡️ 系统边界（不做什么）</p>
        <ul className="list-disc pl-5 space-y-1 text-xs">
          <li>不诊断情绪障碍 / 不替代专业心理咨询</li>
          <li>不自动评判/打分/评价用户状态</li>
          <li>干预工具不修改学习数据（Belief/FSRS/Scheduling）</li>
          <li>行为信号仅提示，不自动触发任何学习数据修改</li>
          <li>语音特征默认关闭，需用户主动开启</li>
          <li>情绪记录不会进入全局事件流污染其他模块</li>
        </ul>
      </div>
    </div>
  );
}

function Switch({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${
        checked ? "bg-indigo-500" : "bg-gray-300 dark:bg-gray-600"
      }`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${
          checked ? "translate-x-6" : "translate-x-1"
        }`}
      />
    </button>
  );
}
