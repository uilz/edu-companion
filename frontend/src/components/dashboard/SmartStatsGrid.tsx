"use client";

import type { ComponentType } from "react";
import {
  AlertTriangle,
  Clock,
  Target,
  Brain,
  BarChart3,
  CheckCircle,
  Flame,
} from "lucide-react";
import { StatCard } from "@/components/ui/StatCard";
import type { DashboardStat } from "@/lib/api/secretary-dashboard-api";

interface SmartStatsGridProps {
  stats: DashboardStat[];
}

const ICON_MAP: Record<string, ComponentType<{ size?: number; className?: string }>> = {
  alert: AlertTriangle,
  clock: Clock,
  target: Target,
  brain: Brain,
  "bar-chart": BarChart3,
  "check-circle": CheckCircle,
  flame: Flame,
};

const COLOR_MAP: Record<string, string> = {
  high: "text-danger",
  medium: "text-warning",
  low: "text-ink-muted",
};

const SCHEME_MAP: Record<string, "rose" | "amber" | "indigo"> = {
  high: "rose",
  medium: "amber",
  low: "indigo",
};

export default function SmartStatsGrid({ stats }: SmartStatsGridProps) {
  if (stats.length === 0) return null;

  return (
    <div
      className="grid grid-cols-2 sm:grid-cols-4 gap-3 auto-rows-[minmax(80px,auto)]"
      style={{ gridAutoFlow: "dense" }}
    >
      {stats.map((stat) => {
        const Icon = ICON_MAP[stat.icon] || Target;
        const isLarge = stat.priority === "high";
        const isMedium = stat.priority === "medium";

        return (
          <StatCard
            key={stat.key}
            label={stat.label}
            value={stat.value}
            icon={<Icon size={isLarge ? 20 : 14} className={COLOR_MAP[stat.priority]} />}
            color={COLOR_MAP[stat.priority]}
            colorScheme={SCHEME_MAP[stat.priority]}
            className={`
              ${isLarge ? "col-span-2 row-span-2" : ""}
              ${isMedium ? "row-span-2" : ""}
              ${!isLarge && !isMedium ? "row-span-1" : ""}
            `}
          />
        );
      })}
    </div>
  );
}
