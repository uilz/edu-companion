// ═══════════════════════════════════════════════
//  概览卡片组件 — 总题数、正确率、学习天数、学习时长
// ═══════════════════════════════════════════════

import { Target, TrendingUp, CalendarDays, Clock } from "lucide-react";
import Card from "@/components/ui/Card";
import { Overview, deltaStr, deltaColor } from "./utils";

export function OverviewCards({ overview }: { overview: Overview }) {
  const cards = [
    {
      icon: <Target size={16} />,
      label: "总题数",
      val: overview.total_questions,
      prev: overview.prev_week.total_questions,
      fmt: (n: number) => `${n}`,
    },
    {
      icon: <TrendingUp size={16} />,
      label: "正确率",
      val: overview.accuracy,
      prev: overview.prev_week.accuracy,
      fmt: (n: number) => `${(n * 100).toFixed(0)}%`,
    },
    {
      icon: <CalendarDays size={16} />,
      label: "学习天数",
      val: overview.study_days,
      prev: overview.prev_week.study_days,
      fmt: (n: number) => `${n}天`,
    },
    {
      icon: <Clock size={16} />,
      label: "学习时长",
      val: overview.study_minutes,
      prev: overview.prev_week.study_minutes,
      fmt: (n: number) => {
        const hh = Math.floor(n / 60);
        const mm = Math.round(n % 60);
        return hh > 0 ? `${hh}h${mm}m` : `${mm}m`;
      },
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
      {cards.map((c, i) => (
        <Card key={i} className="!p-4">
          <div className="text-accent mb-1.5">{c.icon}</div>
          <div className="text-xl md:text-2xl font-semibold text">
            {c.fmt(c.val)}
          </div>
          <div className="text-[11px] text-muted mt-0.5">
            {c.label}
          </div>
          <div
            className="text-[10px] mt-1"
            style={{ color: deltaColor(c.val, c.prev) }}
          >
            {deltaStr(c.val, c.prev, c.fmt)} vs 上期
          </div>
        </Card>
      ))}
    </div>
  );
}
