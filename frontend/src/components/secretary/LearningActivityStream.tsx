"use client";

import {
  Target, Brain, BookOpen, Calendar, Bot, Layers,
  AlertCircle, RefreshCw, Radio, WifiOff, Loader2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityItem, ActivityItemData } from "@/components/ui/ActivityItem";
import EmptyState from "@/components/ui/EmptyState";
import { useLearningActivities } from "@/hooks/useLearningActivities";
import { useLearningActivityStream, type ActivityStreamEvent } from "@/hooks/useLearningActivityStream";
import type { LearningActivity } from "@/lib/api/learning-activity-api";

// ══════════════════════════════════════════════════════════════
//  Types
// ══════════════════════════════════════════════════════════════

interface LearningActivityStreamProps {
  module?: string;
  limit?: number;
}

// ══════════════════════════════════════════════════════════════
//  Helpers
// ══════════════════════════════════════════════════════════════

const MODULE_CONFIG: Record<string, { label: string; icon: typeof Target; color: string }> = {
  practice: { label: "练习", icon: Target, color: "text-success" },
  flashcard: { label: "闪卡", icon: Brain, color: "text-accent" },
  reading: { label: "阅读", icon: BookOpen, color: "text-info" },
  knowledge_tree: { label: "知识树", icon: Layers, color: "text-warning" },
  planning: { label: "计划", icon: Calendar, color: "text-lime-500" },
  secretary: { label: "秘书", icon: Bot, color: "text-muted" },
  error_book: { label: "错题", icon: AlertCircle, color: "text-danger" },
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

function toActivityItemData(activity: LearningActivity): ActivityItemData {
  const cfg = MODULE_CONFIG[activity.module] || MODULE_CONFIG.secretary;
  const Icon = cfg.icon;
  return {
    id: activity.id,
    icon: <Icon size={16} className={cfg.color} />,
    title: activity.title || activity.activity_type,
    description: activity.description,
    timestamp: formatTime(activity.timestamp),
    status: activity.status as "completed" | "pending" | "failed",
    module: cfg.label,
    deepLink: activity.deep_link || undefined,
  };
}

function dedupeById(items: LearningActivity[]): LearningActivity[] {
  const seen = new Set<string>();
  const result: LearningActivity[] = [];
  for (const item of items) {
    if (seen.has(item.id)) continue;
    seen.add(item.id);
    result.push(item);
  }
  return result;
}

// ══════════════════════════════════════════════════════════════
//  Component
// ══════════════════════════════════════════════════════════════

export default function LearningActivityStream({ module, limit = 50 }: LearningActivityStreamProps) {
  const { data, loading, error, refetch } = useLearningActivities({ module, limit });
  const [liveItems, setLiveItems] = useState<LearningActivity[]>([]);

  const handleActivity = useCallback((evt: ActivityStreamEvent) => {
    const payload = evt.data as LearningActivity | undefined;
    if (!payload || !payload.id) return;
    setLiveItems((prev) => {
      // 如果已经在列表中，替换；否则 prepend
      const filtered = prev.filter((i) => i.id !== payload.id);
      const next = [payload, ...filtered];
      return next.slice(0, 200);
    });
  }, []);

  const handleRefetchOnConnect = useCallback(() => {
    refetch();
  }, [refetch]);

  const { connected, lastEvent, error: streamError, reconnect } = useLearningActivityStream({
    onActivity: handleActivity,
    refetchOnConnect: handleRefetchOnConnect,
  });

  // 初始数据变更时合并到 liveItems
  useEffect(() => {
    if (!data?.items) return;
    setLiveItems((prev) => {
      const merged = [...prev, ...data.items];
      return dedupeById(merged);
    });
  }, [data]);

  const items = useMemo(() => {
    const sorted = [...liveItems].sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
    );
    return dedupeById(sorted).slice(0, limit);
  }, [liveItems, limit]);

  const activityItems = useMemo(() => items.map(toActivityItemData), [items]);

  const isLoading = loading && items.length === 0;
  const hasError = error || streamError;

  return (
    <div className="space-y-4">
      {/* ── 工具栏 ── */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1 text-xs ${
              connected ? "text-success" : "text-muted"
            }`}
            title={connected ? "实时连接中" : "实时连接已断开"}
          >
            {connected ? <Radio size={12} /> : <WifiOff size={12} />}
            {connected ? "实时连接中" : "已断开"}
          </span>
          {lastEvent?.event === "heartbeat" && (
            <span className="text-[10px] text-muted">· 心跳正常</span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {!connected && (
            <button
              onClick={reconnect}
              className="inline-flex items-center gap-1 px-2 py-1 text-xs text-accent bg-accent/5 rounded border border-accent/20 hover:bg-accent/10 transition-colors"
            >
              <Radio size={12} />
              重连
            </button>
          )}
          <button
            onClick={() => refetch()}
            disabled={loading}
            className="inline-flex items-center gap-1 px-2 py-1 text-xs text-muted bg-surface rounded border border hover:text transition-colors disabled:opacity-50"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
            刷新
          </button>
        </div>
      </div>

      {/* ── 错误提示 ── */}
      {hasError && (
        <div className="flex items-center gap-2 p-3 rounded-lg border border-danger/20 bg-danger/5 text-xs text-danger">
          <AlertCircle size={14} />
          <span className="flex-1">
            {error?.message || streamError}
          </span>
        </div>
      )}

      {/* ── 加载中 ── */}
      {isLoading && (
        <div className="flex items-center justify-center py-8 text-xs text-muted">
          <Loader2 size={14} className="animate-spin mr-2" />
          加载学习活动…
        </div>
      )}

      {/* ── 空状态 ── */}
      {!isLoading && activityItems.length === 0 && (
        <div className="py-8">
          <EmptyState
            title="暂无学习活动"
            description="完成练习、阅读或闪卡复习后，这里会实时展示你的学习记录。"
          />
        </div>
      )}

      {/* ── 活动列表 ── */}
      {activityItems.length > 0 && (
        <div className="space-y-1">
          {activityItems.map((item) => (
            <ActivityItem key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}
