"use client";

import { useState, useEffect, useCallback } from"react";
import { authedFetch } from"@/lib/api/api";
import {
  Heart, TrendingUp, AlertTriangle, Smile, Meh, Frown,
  Brain, Sparkles, Activity, Loader2, Plus,
  Bell, Eye, EyeOff, Trash2, Wand2,
} from"lucide-react";
import { ManualRecordCard } from"@/components/emotion/ManualRecordCard";
import { InterventionPanel } from"@/components/emotion/InterventionPanel";
import PrivacyPanel from"@/components/emotion/PrivacyPanel";
import {
  EMOTION_CONFIG, DIRECTION_LABELS, SIGNAL_LABELS, INTERVENTION_LABELS,
} from"@/components/emotion/constants";

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

export default function EmotionDashboard() {
  const [trend, setTrend] = useState<EmotionTrend | null>(null);
  const [stats, setStats] = useState<EmotionStats | null>(null);
  const [recent, setRecent] = useState<EmotionRecord[]>([]);
  const [dashboard, setDashboard] = useState<MoodStressDashboard | null>(null);
  const [constants, setConstants] = useState<Constants | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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
      setError(e instanceof Error ? e.message : "加载情绪数据失败");
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
        <Loader2 className="w-8 h-8 animate-spin text-accent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-6 text-center">
        <div className="p-4 border border-danger/20 bg-danger/10 rounded-lg text-danger mb-4">
          {error}
        </div>
        <button
          onClick={() => { setError(null); reload(); }}
          className="px-4 py-2 rounded-lg bg-accent text-white hover:bg-accent-hover text-sm"
        >
          重试
        </button>
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
          <Heart className="w-6 h-6 text-danger" />
          <h1 className="text-xl font-semibold">情绪陪伴</h1>
          <span className="text-xs px-2 py-0.5 rounded-full bg-danger/20 dark:bg-danger/10 text-danger dark:text-danger">
            自动 {stats?.total_records || 0} · 手动 {dashboard?.stats.manual_total || 0}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setRecordOpen(true)}
            className="px-3 py-1.5 rounded-lg bg-accent hover:bg-accent-hover text-white text-sm flex items-center gap-1"
          >
            <Plus className="w-4 h-4" />
            现在记录
          </button>
        </div>
      </div>

      {/* ── Tab 切换 ── */}
      <div className="flex items-center gap-2 border-b border dark:border">
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
                ? "border-accent text-accent dark:text-accent"
                : "border-transparent text-muted hover:text"
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
            <div className="rounded-2xl border-2 border-accent/20 dark:border-accent/80 bg-gradient-to-br from-accent/5 to-accent/5 dark:from-accent/10 dark:to-accent/10 p-5">
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs text-accent dark:text-accent font-medium flex items-center gap-1">
                  <Wand2 className="w-3 h-3" />
                  最新手动记录（手动优先）
                </div>
                <span className="text-xs text-muted">
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
                  <span>😓 压力 <b className="text-danger">{dashboard.latest_manual.pressure_score}</b>/10</span>
                )}
                {dashboard.latest_manual.energy_score !== null && (
                  <span>⚡ 能量 <b className="text-success">{dashboard.latest_manual.energy_score}</b>/10</span>
                )}
              </div>
              {dashboard.latest_manual.text_note && (
                <p className="mt-2 text-sm text-muted dark:text-muted italic">
                  "{dashboard.latest_manual.text_note}"
                </p>
              )}
            </div>
          )}

          {/* ── 主导情绪卡片 ── */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-2xl border border dark:border bg-white dark:bg-surface/60 p-5">
              <div className="text-4xl mb-2">{stats?.dominant_emoji}</div>
              <div className="text-lg font-semibold">主导情绪（自动）</div>
              <div className="text-sm text-muted mt-1">
                {EMOTION_CONFIG[stats?.dominant_emotion || ""]?.label || stats?.dominant_emotion || "—"}
              </div>
            </div>

            <div className="rounded-2xl border border dark:border bg-white dark:bg-surface/60 p-5">
              <div className="text-4xl mb-2">{trendInfo?.icon || "➡️"}</div>
              <div className="text-lg font-semibold">趋势</div>
              <div className={`text-sm mt-1 ${trendInfo?.color || "text-muted"}`}>
                {trendInfo?.label || "稳定"}
              </div>
            </div>

            <div className="rounded-2xl border border dark:border bg-white dark:bg-surface/60 p-5">
              <div className="text-4xl mb-2">
                {(stats?.negative_ratio || 0) > 0.5 ? "😰" : (stats?.negative_ratio || 0) > 0.3 ? "😐" : "😊"}
              </div>
              <div className="text-lg font-semibold">负面情绪占比</div>
              <div className="text-sm mt-1">
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-2 rounded-full bg-surface-hover dark:bg-surface-hover overflow-hidden">
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
            <div className="rounded-2xl border border dark:border bg-white dark:bg-surface/60 p-5">
              <h2 className="font-medium mb-4 flex items-center gap-2"><Activity className="w-4 h-4" />近 {dashboard.days} 天周期统计</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="rounded-lg bg-surface dark:bg-surface/40 p-3">
                  <div className="text-xs text-muted">手动记录</div>
                  <div className="text-xl font-semibold mt-1">{dashboard.stats.manual_total}</div>
                </div>
                <div className="rounded-lg bg-surface dark:bg-surface/40 p-3">
                  <div className="text-xs text-muted">自动检测</div>
                  <div className="text-xl font-semibold mt-1">{dashboard.stats.auto_total}</div>
                </div>
                <div className="rounded-lg bg-surface dark:bg-surface/40 p-3">
                  <div className="text-xs text-muted">平均压力</div>
                  <div className="text-xl font-semibold mt-1 text-danger">
                    {dashboard.stats.avg_pressure ?? "—"}
                  </div>
                </div>
                <div className="rounded-lg bg-surface dark:bg-surface/40 p-3">
                  <div className="text-xs text-muted">平均能量</div>
                  <div className="text-xl font-semibold mt-1 text-success">
                    {dashboard.stats.avg_energy ?? "—"}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── 行为信号摘要 ── */}
          {dashboard && dashboard.unread_behavior_signals.length > 0 && (
            <div className="rounded-2xl border border-warning/20 dark:border-warning/20 bg-warning/10 dark:bg-warning/10 p-5">
              <h2 className="font-medium mb-3 flex items-center gap-2">
                <Eye className="w-4 h-4 text-warning" />
                行为信号（仅提示，不自动修改）
              </h2>
              <div className="space-y-2">
                {dashboard.unread_behavior_signals.slice(0, 5).map((s) => {
                  const cfg = SIGNAL_LABELS[s.signal_type] || { label: s.signal_type, emoji: "❓" };
                  return (
                    <div
                      key={s.id}
                      className="flex items-center gap-2 text-sm text dark:text"
                    >
                      <span className="text-base">{cfg.emoji}</span>
                      <span className="flex-1">{cfg.label}</span>
                      <span className="text-xs text-muted">严重度 {s.severity}/3</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── AI 洞察 ── */}
          {trend?.insight && (
            <div className="rounded-2xl border border-accent/20 dark:border-accent/20 bg-accent/10 dark:bg-accent/10 p-4 flex items-start gap-3">
              <Brain className="w-5 h-5 text-accent shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-accent dark:text-accent">苹小果的陪伴洞察</p>
                <p className="text-sm text-accent dark:text-accent mt-1">{trend.insight}</p>
              </div>
            </div>
          )}

          {/* ── 情绪分布（自动检测） ── */}
          {sortedCategories.length > 0 && (
            <div className="rounded-2xl border border dark:border bg-white dark:bg-surface/60 p-5">
              <h2 className="font-medium mb-4 flex items-center gap-2"><Activity className="w-4 h-4" />情绪分布（自动检测）</h2>
              <div className="space-y-2.5">
                {sortedCategories.map(([cat, count]) => {
                  const cfg = EMOTION_CONFIG[cat] || { label: cat, emoji: "❓", color: "#6b7280", severity: "neutral" };
                  return (
                    <div key={cat} className="flex items-center gap-3">
                      <span className="text-lg w-8 text-center">{cfg.emoji}</span>
                      <span className="text-sm w-16">{cfg.label}</span>
                      <div className="flex-1 h-4 rounded-full bg-surface dark:bg-surface-hover overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{ width: `${(count / maxCatCount) * 100}%`, backgroundColor: cfg.color }}
                        />
                      </div>
                      <span className="text-xs text-muted w-6 text-right">{count}</span>
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
          <div className="rounded-2xl border border dark:border bg-white dark:bg-surface/60 p-5">
            <h2 className="font-medium mb-4 flex items-center gap-2"><Heart className="w-4 h-4" />手动记录历史</h2>
            <div className="space-y-2">
              {dashboard?.recent_records.filter((r) => r.source === "manual").map((r) => (
                <div
                  key={r.id}
                  className="rounded-lg border border  dark:border p-3"
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
                    <span className="text-xs text-muted">
                      {new Date(r.created_at).toLocaleString("zh-CN", { hour12: false })}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted">
                    {r.pressure_score !== null && <span>压力 {r.pressure_score}/10</span>}
                    {r.energy_score !== null && <span>能量 {r.energy_score}/10</span>}
                  </div>
                  {r.text_note && (
                    <p className="mt-1 text-xs text-muted italic">"{r.text_note}"</p>
                  )}
                </div>
              ))}
              {(!dashboard || dashboard.recent_records.filter((r) => r.source === "manual").length === 0) && (
                <p className="text-sm text-muted text-center py-4">还没有手动记录，点上方"现在记录"开始 ✏️</p>
              )}
            </div>
          </div>

          {/* ── 自动检测历史（保留原页面） ── */}
          <div className="rounded-2xl border border dark:border bg-white dark:bg-surface/60 p-5">
            <h2 className="font-medium mb-4 flex items-center gap-2"><Sparkles className="w-4 h-4" />最近自动检测记录</h2>
            <div className="space-y-2">
              {recent.slice().reverse().map((r, i) => {
                const cfg = EMOTION_CONFIG[r.category] || { label: r.category, emoji: "❓", color: "#6b7280", severity: "neutral" };
                const time = new Date(r.timestamp);
                const timeStr = `${time.getMonth() + 1}/${time.getDate()} ${String(time.getHours()).padStart(2, "0")}:${String(time.getMinutes()).padStart(2, "0")}`;
                return (
                  <div key={i} className="flex items-start gap-3 py-2 border-b border  dark:border /50 last:border-0">
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
                      <p className="text-xs text-muted truncate mt-0.5">"{r.source_text}"</p>
                    </div>
                    <span className="text-xs text-muted shrink-0">{timeStr}</span>
                  </div>
                );
              })}
              {recent.length === 0 && (
                <p className="text-sm text-muted text-center py-4">还没有情绪记录，开始对话吧 💬</p>
              )}
            </div>
          </div>
        </>
      )}

      {tab === "intervention" && (
        <div className="space-y-4">
          <div className="rounded-2xl border border dark:border bg-white dark:bg-surface/60 p-5">
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
            <p className="text-xs text-muted mt-3">
              🛡️ 干预工具不修改学习数据（Belief/FSRS），仅本地记录 + 事件流。
            </p>
          </div>

          {dashboard && dashboard.recent_interventions.length > 0 && (
            <div className="rounded-2xl border border dark:border bg-white dark:bg-surface/60 p-5">
              <h2 className="font-medium mb-4">最近干预记录</h2>
              <div className="space-y-2">
                {dashboard.recent_interventions.slice(0, 10).map((it) => {
                  const cfg = INTERVENTION_LABELS[it.intervention_type] || { label: it.intervention_type, emoji: "❓" };
                  return (
                    <div key={it.id} className="flex items-center gap-2 text-sm">
                      <span>{cfg.emoji}</span>
                      <span className="flex-1">{cfg.label}</span>
                      {it.duration_seconds !== null && (
                        <span className="text-xs text-muted">{it.duration_seconds}s</span>
                      )}
                      <span className="text-xs text-muted">
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
