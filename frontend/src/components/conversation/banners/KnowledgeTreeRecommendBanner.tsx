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
export default function KnowledgeTreeRecommendBanner() {
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
    const fetchRecs = async () => {
      try {
        const res = await authedFetch("/api/knowledge-graph/ai/recommendation?source=conversation");
        if (!res.ok) return;
        const d = await res.json();
        const recs: Recommendation[] = d.recommendations || [];

        const store = useNotificationStore.getState();
        const existingIds = new Set(store.notifications.map((n) => n.id));
        const dismissedSet = loadDismissedSet();

        for (const rec of recs) {
          const notifId = `tree_rec_${rec.type}`;
          if (existingIds.has(notifId)) continue;
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
  }, []);

  if (pendingRecs.length === 0) return null;

  return (
    <div className="space-y-1.5 px-4 pt-2">
      {pendingRecs.map((n) => (
        <div
          key={n.id}
          className="flex items-center gap-2 px-3 py-2 rounded-md text-xs"
          style={{
            backgroundColor: "var(--banner-recommend-bg)",
            border: "1px solid var(--banner-recommend-border)",
            color: "var(--color-green)",
          }}
        >
          <GitGraph size={14} className="flex-shrink-0" />
          <span className="flex-1" style={{ color: "var(--color-ink-primary)" }}>{n.description}</span>
          <Link
            href="/knowledge-tree"
            className="px-2 py-0.5 rounded font-medium flex-shrink-0 transition-colors"
            style={{
              backgroundColor: "var(--banner-recommend-border)",
              color: "var(--color-green)",
            }}
          >
            去知识树
          </Link>
          <button
            type="button"
            onClick={() => handleDismiss(n.id)}
            className="p-0.5 rounded transition-colors flex-shrink-0"
            style={{ color: "var(--color-green)" }}
            aria-label="关闭提醒"
          >
            <X size={12} />
          </button>
        </div>
      ))}
    </div>
  );
}