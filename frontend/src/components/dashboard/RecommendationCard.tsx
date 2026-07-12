"use client";

import { Sparkles, Lightbulb, ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";
import Card from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import EmptyState from "@/components/ui/EmptyState";
import type { DashboardRecommendations } from "@/lib/api/secretary-dashboard-api";

interface RecommendationCardProps {
  recommendations: DashboardRecommendations;
}

const GROUP_CONFIG = [
  { key: "urgent" as const, title: "🔥 紧急补强", variant: "danger" as const },
  { key: "building" as const, title: "📈 巩固提升", variant: "success" as const },
  { key: "new_topic" as const, title: "🔭 新知识", variant: "accent" as const },
];

export default function RecommendationCard({ recommendations }: RecommendationCardProps) {
  const router = useRouter();
  const { suggestion, urgent, building, new_topic } = recommendations;
  const hasAny = urgent.length > 0 || building.length > 0 || new_topic.length > 0;

  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Sparkles size={14} className="text-warning" />
          <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-secondary">
            AI 推荐
          </h2>
        </div>
      </div>

      {suggestion && (
        <div className="p-3 rounded-md bg-warning/5 border border-warning/20 mb-3">
          <div className="flex items-start gap-2.5">
            <Lightbulb size={14} className="text-warning mt-0.5 shrink-0" />
            <p className="text-sm text-ink-primary leading-relaxed">{suggestion}</p>
          </div>
        </div>
      )}

      {!hasAny ? (
        <EmptyState
          icon="💡"
          title="暂无推荐"
          description="开始练习后，AI 会基于你的薄弱点生成推荐。"
        />
      ) : (
        <div className="space-y-3">
          {GROUP_CONFIG.map(({ key, title, variant }) => {
            const items = recommendations[key];
            if (items.length === 0) return null;
            return (
              <div key={key}>
                <div className="text-[11px] text-ink-muted mb-1.5 font-medium">{title}</div>
                <div className="space-y-1">
                  {items.map((item) => (
                    <button
                      key={item.skill_id}
                      onClick={() => router.push(`/practice?node=${item.skill_id}`)}
                      className="w-full text-left flex items-center justify-between text-xs px-2.5 py-1.5 rounded hover:bg-surface-hover transition-colors"
                    >
                      <span className="text-ink-primary truncate flex-1">{item.label}</span>
                      {item.p_known != null && (
                        <Badge variant={variant} className="ml-2 shrink-0">
                          {(item.p_known * 100).toFixed(0)}%
                        </Badge>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
