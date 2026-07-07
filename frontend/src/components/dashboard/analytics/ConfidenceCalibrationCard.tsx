"use client";

import { useEffect, useState } from "react";
import { Loader2, Target, TrendingUp } from "lucide-react";
import Card from "@/components/ui/Card";
import { fetchConfidenceReport, type ConfidenceReport } from "@/lib/api/practice-api";

export default function ConfidenceCalibrationCard() {
  const [report, setReport] = useState<ConfidenceReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchConfidenceReport({ days: 30 })
      .then(setReport)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <Card title="🎯 自信度校准">
        <div className="py-4 text-center">
          <Loader2 size={14} className="animate-spin mx-auto" />
        </div>
      </Card>
    );
  }

  if (!report || report.by_subject.length === 0) {
    return null;
  }

  const directionEmoji: Record<string, string> = {
    overconfident: "🔥",
    underconfident: "💧",
    accurate: "✅",
  };

  const directionColor: Record<string, string> = {
    overconfident: "text-danger",
    underconfident: "text-info",
    accurate: "text-success",
  };

  const maxAbsBias = Math.max(
    ...report.by_subject.map((s) => Math.abs(s.mean_bias)),
    4
  );

  return (
    <Card title="🎯 自信度校准">
      <div className="space-y-3">
        {/* 总览 */}
        <div className="flex items-center gap-3 px-3 py-2 bg-surface rounded-xl">
          <Target size={18} className="text-accent flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="text-xs text-muted">总体偏差</div>
            <div className="text-sm font-semibold text">
              {report.overall_bias > 0 ? "+" : ""}{report.overall_bias.toFixed(1)}
              <span className="text-[10px] text-muted ml-1">
                ({report.overall_bias > 1 ? "偏自信" : report.overall_bias < -1 ? "偏保守" : "准确"})
              </span>
            </div>
          </div>
        </div>

        {/* 按学科柱状图 */}
        {report.by_subject.map((s) => {
          const absBias = Math.abs(s.mean_bias);
          const barWidth = Math.max(8, (absBias / maxAbsBias) * 100);
          const isPositive = s.mean_bias > 0;
          return (
            <div key={s.subject} className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-xs text-secondary flex-1 truncate">
                  {s.subject}
                </span>
                <span className={`text-[10px] font-semibold ${directionColor[s.direction] || ""}`}>
                  {directionEmoji[s.direction] || ""} {s.direction === "overconfident" ? "偏自信" : s.direction === "underconfident" ? "偏保守" : "准确"}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-5 bg-surface rounded-lg overflow-hidden flex">
                  {/* 负偏差（低估） */}
                  {s.mean_bias < 0 && (
                    <div
                      className="h-full bg-info/80 dark:bg-info rounded-l-lg"
                      style={{ width: `${barWidth}%`, marginLeft: "auto" }}
                    />
                  )}
                  {/* 正偏差（过度自信） */}
                  {s.mean_bias > 0 && (
                    <div
                      className="h-full bg-danger/80 dark:bg-danger rounded-l-lg"
                      style={{ width: `${barWidth}%` }}
                    />
                  )}
                  {/* 准确 */}
                  {s.mean_bias === 0 && (
                    <div
                      className="h-full bg-success/80 dark:bg-success"
                      style={{ width: "100%" }}
                    />
                  )}
                </div>
                <span className="text-[10px] text-muted w-14 text-right flex-shrink-0">
                  {isPositive ? "+" : ""}{s.mean_bias.toFixed(1)} · {s.sample_count}次
                </span>
              </div>
            </div>
          );
        })}

        {/* 建议 */}
        {report.suggestion && (
          <div className="flex items-start gap-2 px-3 py-2 bg-surface rounded-xl">
            <TrendingUp size={14} className="text-accent flex-shrink-0 mt-0.5" />
            <p className="text-xs text-secondary leading-relaxed">
              {report.suggestion}
            </p>
          </div>
        )}
      </div>
    </Card>
  );
}
