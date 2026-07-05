"use client";

import { useState } from "react";
import { ListChecks, Plus, Loader2, Sparkles } from "lucide-react";
import { useReviews, PeriodicReview } from "@/hooks/planning/usePlanning";
import Card from "@/components/ui/Card";

const SOURCE_LABELS: Record<string, string> = {
  flashcard: "卡片",
  practice: "练习",
  project: "项目",
  reading: "阅读",
  language_room: "语言房",
  manual: "手动",
};

function lastWeek(): { start: string; end: string } {
  const d = new Date();
  const day = d.getDay();
  const diffToMon = d.getDate() - day + (day === 0 ? -6 : 1) - 7;
  const start = new Date(d);
  start.setDate(diffToMon);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  return {
    start: start.toISOString().split("T")[0],
    end: end.toISOString().split("T")[0],
  };
}

function thisMonth(): { start: string; end: string } {
  const d = new Date();
  const start = new Date(d.getFullYear(), d.getMonth(), 1);
  const end = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  return {
    start: start.toISOString().split("T")[0],
    end: end.toISOString().split("T")[0],
  };
}

export default function ReviewsPage() {
  const { reviews, loading, reload, generate } = useReviews();
  const [showCreate, setShowCreate] = useState(false);
  const [periodType, setPeriodType] = useState<"weekly" | "monthly">("weekly");
  const [start, setStart] = useState(lastWeek().start);
  const [end, setEnd] = useState(lastWeek().end);
  const [note, setNote] = useState("");

  const handleGenerate = async () => {
    try {
      await generate({ period_type: periodType, period_start: start, period_end: end, user_note: note });
      setShowCreate(false);
      setNote("");
    } catch (e) {
      console.error(e);
    }
  };

  const preset = (kind: "lastweek" | "thismonth") => {
    if (kind === "lastweek") {
      const r = lastWeek();
      setStart(r.start);
      setEnd(r.end);
      setPeriodType("weekly");
    } else {
      const r = thisMonth();
      setStart(r.start);
      setEnd(r.end);
      setPeriodType("monthly");
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-[var(--color-text-muted)]" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-[var(--color-text)] tracking-tight flex items-center gap-2">
              <ListChecks size={20} /> 周期回顾
            </h1>
            <p className="text-sm text-[var(--color-text-muted)] mt-1">
              周/月汇总：各模块时长、目标完成、偏差
            </p>
          </div>
          <button
            onClick={() => setShowCreate((s) => !s)}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm bg-[var(--color-accent)] text-white hover:opacity-90"
          >
            <Sparkles size={14} /> 生成回顾
          </button>
        </div>

        {showCreate && (
          <Card title="生成周期回顾" className="mb-6">
            <div className="space-y-3">
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  onClick={() => preset("lastweek")}
                  className="px-3 py-1.5 text-xs border border-[var(--color-border)] hover:bg-[var(--color-card)]"
                >
                  上周
                </button>
                <button
                  onClick={() => preset("thismonth")}
                  className="px-3 py-1.5 text-xs border border-[var(--color-border)] hover:bg-[var(--color-card)]"
                >
                  本月
                </button>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <select
                  value={periodType}
                  onChange={(e) => setPeriodType(e.target.value as "weekly" | "monthly")}
                  className="px-3 py-2 text-sm border border-[var(--color-border)] bg-[var(--color-bg)]"
                >
                  <option value="weekly">周报</option>
                  <option value="monthly">月报</option>
                </select>
                <input
                  type="date"
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                  className="px-3 py-2 text-sm border border-[var(--color-border)] bg-[var(--color-bg)]"
                />
                <input
                  type="date"
                  value={end}
                  onChange={(e) => setEnd(e.target.value)}
                  className="px-3 py-2 text-sm border border-[var(--color-border)] bg-[var(--color-bg)]"
                />
              </div>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="用户备注（可选）…"
                rows={2}
                className="w-full px-3 py-2 text-sm border border-[var(--color-border)] bg-[var(--color-bg)]"
              />
              <div className="flex items-center gap-2">
                <button
                  onClick={handleGenerate}
                  className="px-4 py-2 text-sm bg-[var(--color-accent)] text-white hover:opacity-90"
                >
                  生成
                </button>
                <button
                  onClick={() => setShowCreate(false)}
                  className="px-4 py-2 text-sm border border-[var(--color-border)]"
                >
                  取消
                </button>
              </div>
            </div>
          </Card>
        )}

        {reviews.length === 0 ? (
          <Card>
            <div className="text-center py-12">
              <ListChecks size={40} className="mx-auto mb-3 text-[var(--color-text-muted)]" />
              <div className="text-sm text-[var(--color-text-muted)]">还没有周期回顾</div>
              <div className="text-xs text-[var(--color-text-muted)] mt-1">点击右上角"生成回顾"开始</div>
            </div>
          </Card>
        ) : (
          <div className="space-y-3">
            {reviews.map((r) => (
              <ReviewCard key={r.id} review={r} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ReviewCard({ review }: { review: PeriodicReview }) {
  const data = review.summary_data || {};
  const byModule = data.by_module || [];
  const total = data.items_total || 0;
  const completed = data.items_completed || 0;
  const completionRate = total ? Math.round((completed / total) * 100) : 0;
  return (
    <Card>
      <div className="flex items-start justify-between gap-3 mb-3 flex-wrap">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs px-1.5 py-0.5 bg-[var(--color-card)] border border-[var(--color-border)]">
              {review.period_type === "weekly" ? "周报" : "月报"}
            </span>
            <h3 className="text-base font-semibold text-[var(--color-text)]">
              {review.period_start} → {review.period_end}
            </h3>
          </div>
          {review.user_note && (
            <div className="text-sm text-[var(--color-text-muted)] mt-1">{review.user_note}</div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        <div className="p-3 border border-[var(--color-border)]">
          <div className="text-xs text-[var(--color-text-muted)]">总项数</div>
          <div className="text-lg font-semibold">{total}</div>
        </div>
        <div className="p-3 border border-[var(--color-border)]">
          <div className="text-xs text-[var(--color-text-muted)]">已完成</div>
          <div className="text-lg font-semibold text-emerald-600">{completed}</div>
        </div>
        <div className="p-3 border border-[var(--color-border)]">
          <div className="text-xs text-[var(--color-text-muted)]">完成率</div>
          <div className="text-lg font-semibold">{completionRate}%</div>
        </div>
        <div className="p-3 border border-[var(--color-border)]">
          <div className="text-xs text-[var(--color-text-muted)]">实际时长</div>
          <div className="text-lg font-semibold">{data.actual_minutes || 0} min</div>
        </div>
      </div>

      {byModule.length > 0 && (
        <div className="mt-3">
          <div className="text-xs uppercase tracking-wider text-[var(--color-text-muted)] mb-2">模块分布</div>
          <div className="space-y-1">
            {byModule.map((m, i) => (
              <div key={i} className="flex items-center gap-2">
                <span className="text-xs w-20 text-[var(--color-text-muted)]">
                  {SOURCE_LABELS[m.source_module] || m.source_module}
                </span>
                <div className="flex-1 bg-[var(--color-card)] border border-[var(--color-border)] h-2">
                  <div
                    className="h-full bg-[var(--color-accent)]"
                    style={{
                      width: `${(m.minutes / Math.max(...byModule.map((x) => x.minutes || 0), 1)) * 100}%`,
                    }}
                  />
                </div>
                <span className="text-xs text-[var(--color-text-muted)] w-20 text-right">
                  {m.count} 项 · {m.minutes || 0} min
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
