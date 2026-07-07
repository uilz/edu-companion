"use client";

import { useState, useEffect } from "react";
import { BarChart3, ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { useWeeklyView } from "@/hooks/planning/usePlanning";
import Card from "@/components/ui/Card";

function getWeekStart(d: Date): string {
  const dt = new Date(d);
  const day = dt.getDay();
  const diff = dt.getDate() - day + (day === 0 ? -6 : 1);
  dt.setDate(diff);
  return dt.toISOString().split("T")[0];
}

function addDays(iso: string, n: number): string {
  const d = new Date(iso);
  d.setDate(d.getDate() + n);
  return d.toISOString().split("T")[0];
}

const WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

export default function WeeklyPage() {
  const [weekStart, setWeekStart] = useState<string>(() => getWeekStart(new Date()));
  const { data, loading, reload } = useWeeklyView(weekStart);

  useEffect(() => {
    // refresh on weekStart change
    reload(weekStart);
  }, [weekStart, reload]);

  const maxMinutes = data
    ? Math.max(1, ...data.days.map((d) => d.total_minutes || 0))
    : 1;

  return (
    <div className="min-h-screen bg-page">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-semibold text tracking-tight flex items-center gap-2">
              <BarChart3 size={20} /> 周视图
            </h1>
            <p className="text-sm text-muted mt-1">
              {data ? `${data.week_start} 至 ${data.week_end}` : "加载中…"}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setWeekStart((w) => addDays(w, -7))}
              className="inline-flex items-center gap-1 px-3 py-2 text-sm border border hover:bg-surface"
            >
              <ChevronLeft size={14} /> 上一周
            </button>
            <button
              onClick={() => setWeekStart(getWeekStart(new Date()))}
              className="px-3 py-2 text-sm border border hover:bg-surface"
            >
              本周
            </button>
            <button
              onClick={() => setWeekStart((w) => addDays(w, 7))}
              className="inline-flex items-center gap-1 px-3 py-2 text-sm border border hover:bg-surface"
            >
              下一周 <ChevronRight size={14} />
            </button>
          </div>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 size={24} className="animate-spin text-muted" />
          </div>
        )}

        {data && (
          <>
            <Card>
              <div className="grid grid-cols-7 gap-2 items-end h-48">
                {data.days.map((d, i) => {
                  const heightPct = (d.total_minutes / maxMinutes) * 100;
                  const completedPct = d.item_count
                    ? (d.completed_count / d.item_count) * 100
                    : 0;
                  return (
                    <div key={d.date} className="flex flex-col items-center gap-1">
                      <div className="text-xs text-muted h-6">
                        {d.item_count > 0 ? d.item_count : ""}
                      </div>
                      <div className="w-full bg-surface border border flex-1 relative" style={{ minHeight: 80 }}>
                        <div
                          className="absolute bottom-0 left-0 right-0 bg-accent"
                          style={{ height: `${heightPct}%` }}
                        />
                        <div
                          className="absolute bottom-0 left-0 right-0 bg-success/60"
                          style={{ height: `${heightPct * (completedPct / 100)}%` }}
                        />
                      </div>
                      <div className="text-xs font-medium">{WEEKDAY_LABELS[i]}</div>
                      <div className="text-xs text-muted">{d.date.slice(5)}</div>
                    </div>
                  );
                })}
              </div>
            </Card>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
              <Card title="本周总数">
                <div className="text-2xl font-semibold">{data.totals.total_items || 0}</div>
                <div className="text-sm text-muted mt-1">项计划</div>
              </Card>
              <Card title="已完成">
                <div className="text-2xl font-semibold text-success">
                  {data.totals.total_completed || 0}
                </div>
                <div className="text-sm text-muted mt-1">
                  完成率{" "}
                  {data.totals.total_items
                    ? Math.round((data.totals.total_completed / data.totals.total_items) * 100)
                    : 0}
                  %
                </div>
              </Card>
              <Card title="总时长">
                <div className="text-2xl font-semibold">{data.totals.total_minutes || 0}</div>
                <div className="text-sm text-muted mt-1">分钟</div>
              </Card>
            </div>

            <Card title="每日详情" className="mt-6">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border">
                      <th className="text-left py-2 px-2">日期</th>
                      <th className="text-left py-2 px-2">星期</th>
                      <th className="text-right py-2 px-2">项数</th>
                      <th className="text-right py-2 px-2">总时长</th>
                      <th className="text-right py-2 px-2">已完成</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.days.map((d, i) => (
                      <tr key={d.date} className="border-b border last:border-b-0">
                        <td className="py-2 px-2">{d.date}</td>
                        <td className="py-2 px-2">{WEEKDAY_LABELS[i]}</td>
                        <td className="text-right py-2 px-2">{d.item_count}</td>
                        <td className="text-right py-2 px-2">{d.total_minutes} min</td>
                        <td className="text-right py-2 px-2 text-success">{d.completed_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
