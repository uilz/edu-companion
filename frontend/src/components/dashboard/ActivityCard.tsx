"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Calendar, Radio, WifiOff, RefreshCw, AlertCircle } from "lucide-react";
import Card from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { ActivityItem, ActivityItemData } from "@/components/ui/ActivityItem";
import EmptyState from "@/components/ui/EmptyState";
import {
  useLearningActivityStream,
  type ActivityStreamEvent,
} from "@/hooks/useLearningActivityStream";
import type { DashboardActivity } from "@/lib/api/secretary-dashboard-api";
import type { LearningActivity } from "@/lib/api/learning-activity-api";

interface ActivityCardProps {
  activities: DashboardActivity[];
  onRefetch?: () => void;
}

const MODULE_CONFIG: Record<string, { label: string; icon: string; color: string }> = {
  practice: { label: "练习", icon: "Target", color: "text-success" },
  flashcard: { label: "闪卡", icon: "Brain", color: "text-accent" },
  reading: { label: "阅读", icon: "BookOpen", color: "text-info" },
  knowledge_tree: { label: "知识树", icon: "Layers", color: "text-warning" },
  planning: { label: "计划", icon: "Calendar", color: "text-lime-500" },
  secretary: { label: "秘书", icon: "Bot", color: "text-muted" },
  error_book: { label: "错题", icon: "AlertCircle", color: "text-danger" },
};

function formatTime(ts: string | undefined): string {
  if (!ts) return "";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return "";
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffH = Math.floor(diffMs / 3600000);
  const diffD = Math.floor(diffMs / 86400000);

  if (diffMin < 1) return "刚刚";
  if (diffMin < 60) return `${diffMin} 分钟前`;
  if (diffH < 24) return `${diffH} 小时前`;
  if (diffD < 7) return `${diffD} 天前`;

  const pad = (n: number) => String(n).padStart(2, "0");
  const mm = pad(d.getMonth() + 1);
  const dd = pad(d.getDate());
  const hh = pad(d.getHours());
  const mi = pad(d.getMinutes());
  if (d.getFullYear() === now.getFullYear()) {
    return `${mm}-${dd} ${hh}:${mi}`;
  }
  return `${d.getFullYear()}-${mm}-${dd} ${hh}:${mi}`;
}

export default function ActivityCard({ activities, onRefetch }: ActivityCardProps) {
  const [liveItems, setLiveItems] = useState<DashboardActivity[]>([]);

  useEffect(() => {
    setLiveItems((prev) => {
      const merged = [...activities, ...prev];
      const seen = new Set<string>();
      return merged.filter((item) => {
        if (seen.has(item.id)) return false;
        seen.add(item.id);
        return true;
      });
    });
  }, [activities]);

  const handleActivity = useCallback((evt: ActivityStreamEvent) => {
    const payload = evt.data as LearningActivity | undefined;
    if (!payload || !payload.id) return;
    const converted: DashboardActivity = {
      id: payload.id,
      activity_type: payload.activity_type,
      module: payload.module,
      title: payload.title || payload.activity_type,
      description: payload.description || "",
      timestamp: payload.timestamp || new Date().toISOString(),
      status: payload.status || "completed",
      deep_link: payload.deep_link || "",
      meta: payload.meta,
    };
    setLiveItems((prev) => {
      const filtered = prev.filter((i) => i.id !== converted.id);
      return [converted, ...filtered].slice(0, 20);
    });
  }, []);

  const { connected, error: streamError, reconnect } = useLearningActivityStream({
    onActivity: handleActivity,
    refetchOnConnect: onRefetch,
  });

  const items = useMemo(() => {
    const sorted = [...liveItems].sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
    );
    const seen = new Set<string>();
    return sorted.filter((item) => {
      if (seen.has(item.id)) return false;
      seen.add(item.id);
      return true;
    });
  }, [liveItems]);

  const activityItems: ActivityItemData[] = useMemo(
    () =>
      items.map((item) => {
        const cfg = MODULE_CONFIG[item.module] || MODULE_CONFIG.secretary;
        return {
          id: item.id,
          title: item.title || item.activity_type,
          description: item.description,
          timestamp: formatTime(item.timestamp),
          status: item.status as "completed" | "pending" | "failed",
          module: cfg.label,
          deepLink: item.deep_link || undefined,
        };
      }),
    [items],
  );

  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Calendar size={14} className="text-accent" />
          <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-secondary">
            学习活动
          </h2>
          <span
            className={`inline-flex items-center gap-1 text-[10px] ${
              connected ? "text-success" : "text-ink-muted"
            }`}
          >
            {connected ? <Radio size={10} /> : <WifiOff size={10} />}
            {connected ? "实时" : "离线"}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {!connected && (
            <Button variant="ghost" size="icon" onClick={reconnect}>
              <Radio size={12} />
            </Button>
          )}
          <Button variant="ghost" size="icon" onClick={onRefetch}>
            <RefreshCw size={12} />
          </Button>
        </div>
      </div>

      {streamError && (
        <div className="flex items-center gap-2 p-2 rounded-md bg-danger/5 text-xs text-danger mb-3">
          <AlertCircle size={12} />
          <span>{streamError}</span>
        </div>
      )}

      {activityItems.length === 0 ? (
        <EmptyState
          icon="📭"
          title="暂无学习活动"
          description="完成练习、阅读或闪卡复习后，这里会实时展示你的学习记录。"
        />
      ) : (
        <div className="space-y-1">
          {activityItems.map((item) => (
            <ActivityItem key={item.id} item={item} />
          ))}
        </div>
      )}
    </Card>
  );
}
