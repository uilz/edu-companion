"use client";

import { Bell, Clock, AlertTriangle, TrendingUp } from "lucide-react";
import type { SnapshotData } from "./shared";

// ══════════════════════════════════════════════════════════════
//  StatsCards
// ══════════════════════════════════════════════════════════════

interface StatsCardsProps {
  snapshot: SnapshotData | null;
}

export default function StatsCards({ snapshot }: StatsCardsProps) {
  return (
    <div className="grid grid-cols-4 gap-3">
      {[
        { label: "薄弱点", value: snapshot?.weak_count ?? 0, icon: AlertTriangle, color: "text-error", bg: "bg-error/5" },
        { label: "停滞项", value: snapshot?.stagnant_count ?? 0, icon: Clock, color: "text-warning", bg: "bg-warning/5" },
        { label: "学习天数", value: snapshot?.streak_days ?? 0, icon: TrendingUp, color: "text-success", bg: "bg-success/5" },
        { label: "认知负荷", value: snapshot?.cognitive_load != null ? `${Math.round(snapshot.cognitive_load * 100)}%` : "—", icon: Bell, color: "text-info", bg: "bg-accent/5" },
      ].map((stat) => {
        const Icon = stat.icon;
        return (
          <div key={stat.label} className={`p-3 rounded-lg ${stat.bg}`}>
            <Icon size={14} className={stat.color} />
            <div className="text-lg font-semibold text mt-1">{stat.value}</div>
            <div className="text-[10px] text-muted">{stat.label}</div>
          </div>
        );
      })}
    </div>
  );
}