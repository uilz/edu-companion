"use client";

import { ChevronRight } from "lucide-react";
import { useConversationStore } from "@/store/conversation/conversation-store";
import { useTreeStore } from "@/store/conversation/tree-store";
import type { GraphNode } from "@/components/conversation/tree/SidebarTreeNode";
import { useMemo } from "react";

/**
 * NodePathBreadcrumb — 只读路径面包屑
 *
 * 利用 selectedNode.path 显示完整祖先链 + 当前节点名。
 * 新架构：所有 node 统一从 childMap 中查找标签。
 */
export default function NodePathBreadcrumb() {
  const selectedNodeId = useConversationStore((s) => s.selectedNodeId);
  const selectedNodeType = useConversationStore((s) => s.selectedNodeType);
  const selectedNode = useConversationStore((s) => s.selectedNode);
  const childMap = useTreeStore((s) => s.childMap);

  // ── 从 childMap 中按 ID 找标签 ──
  function findLabel(id: string): string | null {
    let label: string | null = null;
    childMap.forEach((nodes: GraphNode[]) => {
      const found = nodes.find((n) => n.id === id);
      if (found) label = found.label;
    });
    return label;
  }

  // ── 构建面包屑段 ──
  const segments = useMemo(() => {
    const result: string[] = [];

    // 沿 path 显示所有祖先目录
    if (selectedNode?.path) {
      for (const aid of selectedNode.path) {
        const label = findLabel(aid);
        if (label) result.push(label);
      }
    }

    // conv 节点末尾加上会话名（从 childMap 查找）
    const convId = selectedNodeType === "conv" ? selectedNodeId : null;
    if (convId) {
      const convLabel = findLabel(convId);
      if (convLabel) result.push(convLabel);
    }

    return result;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNode?.path, selectedNodeType, selectedNodeId, childMap]);

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
