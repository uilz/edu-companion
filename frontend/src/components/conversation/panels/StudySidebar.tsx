"use client";

import { useEffect, useMemo } from "react";
import { Plus, Hash, FolderOpen } from "lucide-react";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { NewNodeDialog } from "@/components/ui/NewNodeDialog";
import { SidebarTreeNode } from "@/components/conversation/tree/SidebarTreeNode";
import { useTreeNavigation } from "@/hooks/graph/useTreeNavigation";
import { useConversationStore } from "@/store/conversation/conversation-store";
import type { GraphNode } from "@/components/conversation/tree/SidebarTreeNode";
import { ROOT_KEY } from "@/components/conversation/tree/SidebarTreeNode";

interface Props {
  partitions?: unknown[];
  selectedPartitionId: string | null;
  activeConversationId: string | null;
  activeDomainId?: string | null;
  activeTopicId?: string | null;
  initialConversationId?: string;
  onSelectConversation: (pid: string, cid: string) => void;
  onCreatePartition: () => void;
  onRenamePartition?: (id: string, name: string) => void;
  loading?: boolean;
  compact?: boolean;
  onNewConversation?: (level: string, parentId: string, partitionId?: string) => void;
  onConversationReady?: (partitionId: string, conversationId: string) => void;
  onTreeChanged?: () => void;
  onSelectConv?: (partitionId: string, conversationId: string) => void;
}

export default function StudySidebar({
  selectedPartitionId: _selectedNodeId,
  activeConversationId,
  activeDomainId,
  activeTopicId,
  initialConversationId,
  onCreatePartition,
  loading = false, compact = false,
  onConversationReady,
  onTreeChanged,
  onSelectConv,
}: Props) {
  // 挂载时加载根节点
  useEffect(() => {
    const store = useConversationStore.getState();
    if (!store.rootLoaded) store.loadRootNodes();
  }, []);

  const nav = useTreeNavigation(onConversationReady, onTreeChanged);
  const selectGraphNode = useConversationStore(s => s.selectGraphNode);
  const selectedNode = useConversationStore(s => s.selectedNode);
  const childMap = useConversationStore(s => s.childMap);
  const convCache = useConversationStore(s => s.convCache);
  const convActiveConvId = useConversationStore(s => s.activeConversationId);
  const effectiveConvId = activeConversationId ?? convActiveConvId;

  // ── 构建 parentMap（子→父映射），用于计算祖先链 ──
  const parentMap = useMemo(() => {
    const map = new Map<string, string>();
    childMap.forEach((children, parentId) => {
      for (const child of children) {
        map.set(child.id, parentId);
      }
    });
    return map;
  }, [childMap]);

  // ── 计算祖先链 ──
  const ancestorIds = useMemo(() => {
    const ids = new Set<string>();

    // 先确定起始节点 ID：如果有活跃会话，从其 parent_id 开始
    let startId: string | null = null;
    if (effectiveConvId) {
      convCache.forEach((convs) => {
        if (startId) return;
        const c = convs.find((cv) => cv.id === effectiveConvId);
        if (c?.parent_id) startId = c.parent_id;
      });
    }
    // 如果没有活跃会话或没找到 parent_id，回退到 selectedNode.parent
    if (!startId) {
      startId = selectedNode?.parent ?? null;
    }

    if (!startId) return ids;

    let cur: string | null = startId;
    while (cur) {
      if (cur === ROOT_KEY) break;
      ids.add(cur);
      cur = parentMap.get(cur) || null;
    }
    return ids;
  }, [selectedNode, parentMap, effectiveConvId, convCache]);

  // ── 选中+展开（交由 store 自包含处理）──
  const handleSelectGraphNode = async (node: GraphNode, partitionId: string) => {
    await selectGraphNode(node, partitionId);
  };

  // 有活跃会话时，树节点不显示选中态（会话自身的强高亮由 activeConversationId 控制）
  const treeSelectedNode = effectiveConvId ? null : selectedNode;

  return (
    <div className="flex flex-col h-full bg-[var(--color-page-secondary)] border-r border-[var(--color-border)] select-none">
      {!compact && (
        <div className="flex items-center justify-between px-3 py-2.5 border-b border-[var(--color-border)]">
          <div className="flex items-center gap-1.5">
            <FolderOpen size={15} className="text-[var(--color-accent)]" />
            <span className="text-xs font-semibold text-[var(--color-text)]">学习空间</span>
          </div>
          <button onClick={onCreatePartition}
            className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] active:scale-[0.97] transition-all rounded" title="新建分区">
            <Plus size={15} />
          </button>
        </div>
      )}
      <div className="flex-1 overflow-y-auto py-1">
        {loading ? (
          <div className="px-4 py-8 text-center text-xs text-[var(--color-text-muted)]">加载中...</div>
        ) : nav.rootNodes.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <Hash size={18} className="text-[var(--color-text-muted)] mx-auto mb-2" />
            <div className="text-xs text-[var(--color-text-muted)]">暂无分区</div>
            <div className="text-[10px] text-[var(--color-text-muted)] mt-1 opacity-60">发送消息将自动创建</div>
          </div>
        ) : (
          nav.rootNodes.map(node => (
            <SidebarTreeNode
              key={node.id} node={node} depth={0}
              partitionId={node.level === "partition" ? node.id : undefined}
              expandedSet={nav.expandedSet} loadingSet={nav.loadingSet}
              childMap={nav.childMap}
              selectedNode={treeSelectedNode}
              ancestorIds={ancestorIds}
              convCache={nav.convCache} activeConversationId={activeConversationId}
              editingId={nav.editingId} editValue={nav.editValue}
              toggleExpand={nav.toggleExpand} handleCreateChild={nav.handleCreateChild}
              handleNewConvClick={nav.handleNewConvClick}
              setEditingId={nav.setEditingId} setEditValue={nav.setEditValue}
              setDeleteTarget={nav.setDeleteTarget}
              handleRename={nav.handleRename} handleRenameConv={nav.handleRenameConv}
              onSelectConv={onSelectConv}
              onSelectGraphNode={handleSelectGraphNode}
            />
          ))
        )}
      </div>
      {nav.deleteTarget && (
        <ConfirmDialog onConfirm={nav.confirmDelete} onCancel={() => nav.setDeleteTarget(null)}>
          确认删除「{nav.deleteTarget.label}」及其所有子节点？此项操作不可恢复。
        </ConfirmDialog>
      )}
      <NewNodeDialog
        open={!!nav.newChildTarget}
        onClose={() => nav.setNewChildTarget(null)}
        onCreate={nav.confirmCreateChild}
        title={nav.newChildTarget?.level === "domain" ? "新建领域" : nav.newChildTarget?.level === "topic" ? "新建专题" : "新建"}
        namePlaceholder={nav.newChildTarget?.level === "domain" ? "例如: 分析" : nav.newChildTarget?.level === "topic" ? "例如: 微积分" : "输入名称"}
        defaultEmoji={nav.newChildTarget?.defaultEmoji || "📚"}
        nameLabel={nav.newChildTarget?.level === "domain" ? "领域名称" : nav.newChildTarget?.level === "topic" ? "专题名称" : "名称"}
      />
    </div>
  );
}
