"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import EmptyState from "@/components/ui/EmptyState";
import PendingItemCard from "./PendingItemCard";
import type { DashboardPendingItem } from "@/lib/api/secretary-dashboard-api";
import { authedFetch } from "@/lib/api/api";

interface PendingPanelProps {
  items: DashboardPendingItem[];
  onChange?: () => void;
}

type TagFilter = "全部" | "建议" | "计划确认" | "通知";

const TAG_FILTERS: TagFilter[] = ["全部", "建议", "计划确认", "通知"];

export default function PendingPanel({ items, onChange }: PendingPanelProps) {
  const [activeTag, setActiveTag] = useState<TagFilter>("全部");
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    return items.filter((item) => {
      const matchesTag =
        activeTag === "全部" ||
        (activeTag === "建议" && item.kind === "proposal") ||
        (activeTag === "计划确认" && item.kind === "confirmation") ||
        (activeTag === "通知" && item.kind === "notification");
      const matchesSearch =
        !search ||
        item.title.toLowerCase().includes(search.toLowerCase()) ||
        item.description.toLowerCase().includes(search.toLowerCase());
      return matchesTag && matchesSearch;
    });
  }, [items, activeTag, search]);

  const handleAccept = async (item: DashboardPendingItem) => {
    try {
      if (item.kind === "confirmation") {
        await authedFetch(`/api/planning/confirmations/${item.id}/accept`, {
          method: "POST",
        });
      } else if (item.kind === "proposal") {
        await authedFetch(`/api/secretary/proposals/${item.id}/accept`, {
          method: "POST",
        });
      }
      onChange?.();
    } catch {
      // 静默失败，后续可加入 Toast
    }
  };

  const handleDismiss = async (item: DashboardPendingItem) => {
    try {
      if (item.kind === "confirmation") {
        await authedFetch(`/api/planning/confirmations/${item.id}/dismiss`, {
          method: "POST",
        });
      } else if (item.kind === "proposal") {
        await authedFetch(`/api/secretary/proposals/${item.id}/dismiss`, {
          method: "POST",
        });
      }
      onChange?.();
    } catch {
      // 静默失败
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-secondary">
          待处理
          <span className="ml-1 text-ink-muted">({items.length})</span>
        </h2>
      </div>

      {/* 标签筛选 */}
      <div className="flex flex-wrap gap-1.5">
        {TAG_FILTERS.map((tag) => (
          <Button
            key={tag}
            variant={activeTag === tag ? "secondary" : "ghost"}
            size="xs"
            onClick={() => setActiveTag(tag)}
          >
            {tag}
          </Button>
        ))}
      </div>

      {/* 搜索 */}
      <Input
        placeholder="搜索待处理事项"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="h-8 text-xs"
        lead={<Search size={14} className="text-ink-muted" />}
      />

      {/* 列表 */}
      {filtered.length === 0 ? (
        <EmptyState
          icon="🎉"
          title="没有待处理的事项"
          description="当前没有建议、计划确认或通知需要处理。"
        />
      ) : (
        <div className="space-y-2">
          {filtered.map((item) => (
            <PendingItemCard
              key={`${item.kind}-${item.id}`}
              item={item}
              onAccept={handleAccept}
              onDismiss={handleDismiss}
            />
          ))}
        </div>
      )}
    </div>
  );
}
