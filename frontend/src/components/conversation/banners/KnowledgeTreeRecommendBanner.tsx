"use client";

import { useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import { GitGraph, X } from "lucide-react";
import { useNotificationStore } from "@/store/notification/notification-store";
import { dismissNotification } from "@/store/notification/notification-service";
import type { SecretaryNotification, PageType } from "@/store/notification/types";
import { authedFetch } from "@/lib/api/api";

const DISMISSED_STORAGE_KEY = "tree_rec_dismissed_v1";

interface Recommendation {
  type: string;
  message: string;
  action: string;
  partition_id: string;
  nodes?: { id: string; label: string }[];
}

/** 从 localStorage 读取已关闭的 ID 集合 */
function loadDismissedSet(): Set<string> {
  try {
    const raw = localStorage.getItem(DISMISSED_STORAGE_KEY);
    if (raw) return new Set(JSON.parse(raw));
  } catch { /* ignore */ }
  return new Set();
}

/** 将 ID 永久写入 localStorage */
function persistDismissedId(dismissedId: string) {
  try {
    const set = loadDismissedSet();
    set.add(dismissedId);
    localStorage.setItem(DISMISSED_STORAGE_KEY, JSON.stringify(Array.from(set)));
  } catch { /* ignore */ }
}

/**
 * KnowledgeTreeRecommendBanner
 * 轮询知识树推荐信息，通过 NotificationStore 管理通知状态，
 * 关闭后持久化（不随页面刷新丢失），并接入秘书系统管理。
 */
export default function KnowledgeTreeRecommendBanner({
  partitionId,
}: {
  partitionId: string | null;
}) {
  // 从 NotificationStore 中读取活跃（pending）的树推荐通知
  const allNotifications = useNotificationStore((s) => s.notifications);
  const pendingRecs = useMemo(
    () =>
      allNotifications.filter(
        (n) =>
          n.source === "tree_recommendation" &&
          n.status === "pending" &&
          !n.hidden &&
          n.target.pages.includes("learn" as PageType),
      ),
    [allNotifications],
  );

  const handleDismiss = useCallback((id: string) => {
    dismissNotification(id);
    persistDismissedId(id);
  }, []);

  // 轮询推荐 → 写入 NotificationStore
  useEffect(() => {
    if (!partitionId) return;

    const fetchRecs = async () => {
      try {
        const res = await authedFetch("/api/knowledge/graph/recommendation?source=conversation",
        );
        if (!res.ok) return;
        const d = await res.json();
        const recs: Recommendation[] = d.recommendations || [];

        const store = useNotificationStore.getState();
        const existingIds = new Set(store.notifications.map((n) => n.id));
        const dismissedSet = loadDismissedSet();

        for (const rec of recs) {
          // 使用 partition_id + type 作为唯一 ID 避免重复添加
          const notifId = `tree_rec_${rec.partition_id}_${rec.type}`;
          if (existingIds.has(notifId)) continue;
          // 已经关闭过的（localStorage 持久化）不再添加
          if (dismissedSet.has(notifId)) continue;

          const notif: SecretaryNotification = {
            id: notifId,
            emoji: "🌳",
            title: "知识树整理提醒",
            description: rec.message,
            priority: 3,
            target: { pages: ["learn" as PageType] },
            source: "tree_recommendation",
            sourceModule: "knowledge_tree",
            read: false,
            status: "pending",
            created_at: Date.now(),
          };
          store.addNotification(notif);
          existingIds.add(notifId);
        }
      } catch {
        // 静默失败
      }
    };

    // 初始加载
    fetchRecs();

    // 每 30 秒轮询
    const interval = setInterval(fetchRecs, 30000);
    return () => clearInterval(interval);
  }, [partitionId]);

  if (pendingRecs.length === 0) return null;

  return (
    <div className="space-y-1.5 px-4 pt-2">
      {pendingRecs.map((n) => (
        <div
          key={n.id}
          className="flex items-center gap-2 px-3 py-2 rounded-md bg-violet-50 dark:bg-violet-950/20 border border-violet-200 dark:border-violet-800/30 text-xs text-violet-700 dark:text-violet-400"
        >
          <GitGraph size={14} className="flex-shrink-0" />
          <span className="flex-1">{n.description}</span>
          <Link
            href="/knowledge-tree"
            className="px-2 py-0.5 rounded bg-violet-200 dark:bg-violet-800/40 hover:bg-violet-300 dark:hover:bg-violet-700/40 transition-colors font-medium flex-shrink-0"
          >
            去知识树
          </Link>
          <button
            type="button"
            onClick={() => handleDismiss(n.id)}
            className="p-0.5 rounded hover:bg-violet-200/50 dark:hover:bg-violet-800/20 transition-colors flex-shrink-0"
            aria-label="关闭提醒"
          >
            <X size={12} />
          </button>
        </div>
      ))}
    </div>
  );
}