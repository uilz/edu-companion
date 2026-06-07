"use client";

import { ChevronRight } from "lucide-react";
import { useConversationStore } from "@/store/conversation/conversation-store";
import type { GraphNode } from "@/components/conversation/tree/SidebarTreeNode";

/**
 * NodePathBreadcrumb — 只读路径面包屑
 *
 * 显示 分区 > 领域 > 专题 > 会话 的完整路径。
 * 数据来源于 conversation-store 的 childMap / convCache。
 */
export default function NodePathBreadcrumb() {
  const partitionId = useConversationStore((s) => s.selectedPartitionId);
  const domainId = useConversationStore((s) => s.activeDomainId);
  const topicId = useConversationStore((s) => s.activeTopicId);
  const convId = useConversationStore((s) => s.activeConversationId);

  const partitions = useConversationStore((s) => s.partitions);
  const childMap = useConversationStore((s) => s.childMap);
  const convCache = useConversationStore((s) => s.convCache);

  // ── 从 childMap 中按 ID 找标签 ──
  function findLabel(id: string | null): string | null {
    if (!id) return null;
    let label: string | null = null;
    childMap.forEach((nodes: GraphNode[]) => {
      const found = nodes.find((n) => n.id === id);
      if (found) label = found.label;
    });
    return label;
  }

  const activePartition = partitions.find((p) => p.id === partitionId);
  const partitionLabel = activePartition
    ? `${activePartition.emoji || ""} ${activePartition.name}`
    : null;
  const domainLabel = domainId ? findLabel(domainId) : null;
  const topicLabel = topicId ? findLabel(topicId) : null;

  // 从 convCache 找会话名
  let convLabel: string | null = null;
  if (convId && topicId) {
    const convs = convCache.get(topicId);
    if (convs) {
      const found = convs.find((c) => c.id === convId);
      convLabel = found?.name || null;
    }
  }

  const segments = [partitionLabel, domainLabel, topicLabel, convLabel].filter(
    Boolean,
  ) as string[];

  if (segments.length === 0) return null;

  return (
    <div className="flex items-center gap-1.5 text-xs text-[var(--color-text-muted)] max-w-full overflow-hidden flex-shrink-0">
      {segments.map((seg, i) => (
        <span key={seg + i} className="flex items-center gap-1.5 min-w-0">
          {i > 0 && (
            <ChevronRight size={10} className="flex-shrink-0 opacity-50" />
          )}
          <span className="truncate max-w-[120px]">{seg}</span>
        </span>
      ))}
    </div>
  );
}