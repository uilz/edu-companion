"use client";

import { Target, Clock, ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";
import Card from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import type { DashboardFocus } from "@/lib/api/secretary-dashboard-api";

interface FocusCardProps {
  focus: DashboardFocus | null;
}

export default function FocusCard({ focus }: FocusCardProps) {
  const router = useRouter();

  return (
    <Card className="border-l-4 border-l-accent">
      <div className="flex items-center gap-2 mb-3">
        <Target size={14} className="text-accent" />
        <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-secondary">
          今日焦点
        </h2>
      </div>

      {focus ? (
        <div className="flex items-center justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="text-base font-semibold text-ink-primary truncate">
              {focus.title}
            </div>
            {focus.description && (
              <p className="text-sm text-ink-secondary mt-1 line-clamp-2">
                {focus.description}
              </p>
            )}
            {focus.estimated_minutes > 0 && (
              <div className="flex items-center gap-1 text-xs text-ink-muted mt-2">
                <Clock size={11} />
                <span>约 {focus.estimated_minutes} 分钟</span>
              </div>
            )}
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={() => {
              if (focus.action?.target) {
                router.push(focus.action.target);
              } else {
                router.push("/study");
              }
            }}
            className="shrink-0"
          >
            开始
            <ArrowRight size={13} />
          </Button>
        </div>
      ) : (
        <div className="text-sm text-ink-secondary">
          还没有学习计划，到「学习规划」生成个性化计划。
        </div>
      )}
    </Card>
  );
}
